from flask import (
    Flask,
    render_template,
    request,
    redirect,
    url_for,
    flash,
    session,
    send_file,
    send_from_directory,
    jsonify,
)
from datetime import datetime, timezone, timedelta
from bson.objectid import ObjectId
from models import users_collection, files_collection
from werkzeug.utils import secure_filename
from flask_bcrypt import Bcrypt
from flask_mail import Mail, Message
import os
import json
import csv
import io
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

from ai_service import process_pdf_summary, generate_pdf_summary
from models import (
    find_user_by_email,
    create_user,
    get_user_by_id,
    save_file_record,
    get_files_for_user,
)

app = Flask(__name__)
app.config["SECRET_KEY"] = "change-this-secret-key"
app.config["UPLOAD_FOLDER"] = "uploads"
app.config["MAX_CONTENT_LENGTH"] = 16 * 1024 * 1024  # 16 MB per request

# Flask-Mail Configuration
app.config["MAIL_SERVER"] = os.getenv("MAIL_SERVER", "smtp.gmail.com")
app.config["MAIL_PORT"] = int(os.getenv("MAIL_PORT", 587))
app.config["MAIL_USE_TLS"] = os.getenv("MAIL_USE_TLS", True)
app.config["MAIL_USERNAME"] = os.getenv("MAIL_USERNAME", "")
app.config["MAIL_PASSWORD"] = os.getenv("MAIL_PASSWORD", "")
app.config["MAIL_DEFAULT_SENDER"] = os.getenv("MAIL_DEFAULT_SENDER", "no-reply@finwiz.com")

os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)

bcrypt = Bcrypt(app)
mail = Mail(app)

# Premium users set (in-memory demo)
PREMIUM_USERS = set()

# -------------- Helpers --------------

def current_user():
    user_id = session.get("user_id")
    if not user_id:
        return None
    return get_user_by_id(user_id)

def is_premium(user_id):
    return str(user_id) in PREMIUM_USERS

def get_today_analyses_count(user_id):
    """Count PDF analyses done TODAY by user."""
    today_start = datetime.now(timezone.utc).replace(
        hour=0, minute=0, second=0, microsecond=0
    )
    today_files = list(
        files_collection.find(
            {"user_id": user_id, "upload_date": {"$gte": today_start}}
        )
    )
    return len(today_files)

def login_required(func):
    from functools import wraps

    @wraps(func)
    def wrapper(*args, **kwargs):
        if not session.get("user_id"):
            flash("Please log in to access that page.")
            return redirect(url_for("login"))
        return func(*args, **kwargs)

    return wrapper

# -------------- Routes --------------

@app.route("/")
def landing():
    if session.get("user_id"):
        return redirect(url_for("dashboard"))
    return render_template("landing.html")

@app.route("/signup", methods=["GET", "POST"])
def signup():
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password")
        confirm = request.form.get("confirm")

        if not name or not email or not password:
            flash("All fields are required.")
            return redirect(url_for("signup"))

        if password != confirm:
            flash("Passwords do not match.")
            return redirect(url_for("signup"))

        existing = find_user_by_email(email)
        if existing:
            flash("Account already exists for this email. Please log in.")
            return redirect(url_for("login"))

        pw_hash = bcrypt.generate_password_hash(password).decode("utf-8")
        result = create_user(name, email, pw_hash)
        session["user_id"] = str(result.inserted_id)
        session["user_name"] = name
        flash("Signup successful. Welcome to FinWiz Lite!")
        return redirect(url_for("dashboard"))

    return render_template("signup.html")

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password")

        user = find_user_by_email(email)
        if not user or not bcrypt.check_password_hash(
            user["password_hash"], password
        ):
            flash("Incorrect email or password.")
            return redirect(url_for("login"))

        session["user_id"] = str(user["_id"])
        session["user_name"] = user.get("name", "User")
        flash("Logged in successfully.")
        return redirect(url_for("dashboard"))

    return render_template("login.html")

@app.route("/logout")
def logout():
    session.clear()
    flash("You have been logged out.")
    return redirect(url_for("landing"))

# Dashboard is the main page

# DASHBOARD

@app.route("/dashboard", methods=["GET", "POST"])
@login_required
def dashboard():
    user_id = session.get("user_id")
    user = current_user()

    # premium status
    user["is_premium"] = str(user_id) in PREMIUM_USERS

    # files (non-archived)
    all_files = list(get_files_for_user(user_id))
    display_files = all_files[-5:]
    total_files = len([f for f in all_files if not f.get("archived", False)])

    # daily limits: 10 for free, unlimited for premium
    today_analyses = get_today_analyses_count(user_id)
    daily_limit = "Unlimited" if user["is_premium"] else 10
    analyze_disabled = (not user["is_premium"]) and today_analyses >= 10

    storage_full = False  # no storage limit

    summary_en = summary_ta = summary_hi = None
    analytics = None
    transactions = None
    selected_file = None
    file_id = None

    if request.method == "POST":
        # enforce daily limit for non-premium users
        if (not user["is_premium"]) and today_analyses >= 10:
            flash(
                f"📊 Daily limit reached! {today_analyses}/10 analyses today. Premium = Unlimited!"
            )
            return redirect(url_for("dashboard"))

        style = request.form.get("style", "simple")
        mode = request.form.get("mode", "quick")
        file = request.files.get("file")

        if not file or file.filename == "":
            flash("Please choose a PDF file.")
            return redirect(url_for("dashboard"))

        if not file.filename.lower().endswith(".pdf"):
            flash("Only PDF files are supported.")
            return redirect(url_for("dashboard"))

        filename = secure_filename(file.filename)
        filepath = os.path.join(app.config["UPLOAD_FOLDER"], filename)
        file.save(filepath)

        # make sure save_file_record sets archived=False and upload_date=now
        result = save_file_record(user_id, filename, file.filename)
        file_id = str(result.inserted_id)
        selected_file = filename

        summary_en, summary_ta, summary_hi, df, analytics = process_pdf_summary(
            filepath, style=style, mode=mode, lang="en"
        )
        transactions = df.to_dict(orient="records") if df is not None else None

        # refresh stats after upload
        all_files = list(get_files_for_user(user_id))
        display_files = all_files[-5:]
        total_files = len([f for f in all_files if not f.get("archived", False)])
        today_analyses = get_today_analyses_count(user_id)

    # update last_login
    users_collection.update_one(
        {"_id": ObjectId(user_id)},
        {"$set": {"last_login": datetime.now(timezone.utc)}},
    )

    user["last_login_str"] = user.get(
        "last_login", datetime.now(timezone.utc)
    ).strftime("%Y-%m-%d %H:%M")

    return render_template(
        "dashboard.html",
        user=user,
        files=display_files,
        all_files_count=total_files,
        storage_full=storage_full,
        today_analyses=today_analyses,
        daily_limit=daily_limit,
        analyze_disabled=analyze_disabled,
        summary_en=summary_en,
        summary_ta=summary_ta,
        summary_hi=summary_hi,
        filename=selected_file,
        file_id=file_id,
        style="simple",
        mode="quick",
        analytics=analytics,
        transactions=transactions,
    )

# DELETE (hard delete)

@app.route("/delete/<file_id>", methods=["POST"])
@login_required
def delete_file(file_id):
    """Delete physical file + DB record."""
    user = current_user()
    doc = files_collection.find_one(
        {"_id": ObjectId(file_id), "user_id": user["_id"]}
    )
    if not doc:
        flash("File not found.")
        return redirect(url_for("dashboard"))

    filepath = os.path.join(app.config["UPLOAD_FOLDER"], doc["filename"])
    try:
        if os.path.exists(filepath):
            os.remove(filepath)
    except Exception as e:
        print(f"Error deleting {filepath}: {e}")

    files_collection.delete_one({"_id": doc["_id"]})
    flash("✅ File deleted successfully!")
    return redirect(url_for("dashboard"))

# ARCHIVE (soft delete)

@app.route("/archive/<file_id>", methods=["POST"])
@login_required
def archive_file(file_id):
    user = current_user()
    doc = files_collection.find_one(
        {"_id": ObjectId(file_id), "user_id": user["_id"]}
    )
    if not doc:
        flash("File not found.")
        return redirect(url_for("dashboard"))

    files_collection.update_one(
        {"_id": doc["_id"]},
        {"$set": {"archived": True}},
    )
    flash("📁 File moved to archive.")
    return redirect(url_for("dashboard"))

@app.route("/archive")
@login_required
def archive():
    user = current_user()
    archived_files = list(
        files_collection.find(
            {"user_id": user["_id"], "archived": True}
        ).sort("upload_date", -1)
    )
    return render_template("archive.html", user=user, files=archived_files)

@app.route("/update_profile", methods=["POST"])
@login_required
def update_profile():
    user = current_user()
    name = request.form.get("name", user["name"]).strip()
    preferred_lang = request.form.get("preferred_lang", user.get("preferred_lang", "en"))
    preferred_currency = request.form.get("preferred_currency", user.get("preferred_currency", "INR"))
    
    users_collection.update_one(
        {"_id": user["_id"]},
        {"$set": {
            "name": name,
            "preferred_lang": preferred_lang,
            "preferred_currency": preferred_currency
        }}
    )
    flash("Profile updated successfully!")
    return redirect(url_for("dashboard"))

# VIEW FILE

@app.route("/view/<file_id>")
@login_required
def view_file(file_id):
    user = current_user()
    doc = files_collection.find_one(
        {"_id": ObjectId(file_id), "user_id": user["_id"]}
    )
    if not doc:
        flash("File not found.")
        return redirect(url_for("dashboard"))

    filepath = os.path.join(app.config["UPLOAD_FOLDER"], doc["filename"])
    summary_en, summary_ta, summary_hi, df, analytics = process_pdf_summary(
        filepath, style="simple", mode="quick", lang="en"
    )
    transactions = df.to_dict(orient="records") if df is not None else None

    all_files = list(get_files_for_user(user["_id"]))
    display_files = all_files[-5:]
    total_files = len([f for f in all_files if not f.get("archived", False)])
    today_analyses = get_today_analyses_count(user["_id"])
    daily_limit = "Unlimited" if is_premium(user["_id"]) else 10
    analyze_disabled = (not is_premium(user["_id"])) and today_analyses >= 10
    storage_full = False

    user["is_premium"] = is_premium(user["_id"])

    return render_template(
        "dashboard.html",
        user=user,
        files=display_files,
        all_files_count=total_files,
        storage_full=storage_full,
        today_analyses=today_analyses,
        daily_limit=daily_limit,
        analyze_disabled=analyze_disabled,
        summary_en=summary_en,
        filename=doc["filename"],
        analytics=analytics,
        transactions=transactions,
    )

# DOWNLOAD SUMMARY

@app.route("/download/<filename>")
@login_required
def download_summary(filename):
    filepath = os.path.join(app.config["UPLOAD_FOLDER"], filename)
    summary_en, _, _, _, _ = process_pdf_summary(
        filepath, style="simple", mode="quick", lang="en"
    )
    pdf_path = generate_pdf_summary(summary_en)
    return send_file(pdf_path, as_attachment=True, download_name="summary.pdf")

@app.route("/doc-summarizer")
def doc_summarizer():
    return render_template("doc-summarizer.html")

@app.route("/file/<path:filename>")
@login_required
def serve_file(filename):
    return send_from_directory(app.config["UPLOAD_FOLDER"], filename)

# ============== NEW FEATURES ==============

# FEATURE 1: Analytics API for Charts
@app.route("/api/analytics/<file_id>")
@login_required
def get_analytics(file_id):
    """API endpoint for fetching analytics data for charts"""
    user = current_user()
    doc = files_collection.find_one(
        {"_id": ObjectId(file_id), "user_id": user["_id"]}
    )
    if not doc:
        return jsonify({"error": "File not found"}), 404
    
    filepath = os.path.join(app.config["UPLOAD_FOLDER"], doc["filename"])
    _, _, _, df, analytics = process_pdf_summary(
        filepath, style="simple", mode="quick", lang="en"
    )
    
    if not analytics:
        return jsonify({"error": "No analytics data"}), 400
    
    return jsonify({
        "total_income": analytics.get("total_income", 0),
        "total_expense": analytics.get("total_expense", 0),
        "net_savings": analytics.get("net_savings", 0),
        "by_category": analytics.get("by_category", {}),
        "transactions_count": len(df) if df is not None else 0
    })

# FEATURE 3: CSV Export
@app.route("/export/csv/<file_id>")
@login_required
def export_csv(file_id):
    """Export transactions to CSV"""
    user = current_user()
    try:
        file_obj_id = ObjectId(file_id)
    except:
        flash("Invalid file ID.")
        return redirect(url_for("dashboard"))
    
    doc = files_collection.find_one(
        {"_id": file_obj_id, "user_id": user["_id"]}
    )
    if not doc:
        flash("File not found.")
        return redirect(url_for("dashboard"))
    
    filepath = os.path.join(app.config["UPLOAD_FOLDER"], doc["filename"])
    if not os.path.exists(filepath):
        flash("File not found on disk.")
        return redirect(url_for("dashboard"))
    
    _, _, _, df, analytics = process_pdf_summary(
        filepath, style="simple", mode="quick", lang="en"
    )
    
    if df is None or df.empty:
        flash("No transactions to export.")
        return redirect(url_for("dashboard"))
    
    # Create CSV in memory
    output = io.StringIO()
    df.to_csv(output, index=False)
    output.seek(0)
    
    return send_file(
        io.BytesIO(output.getvalue().encode('utf-8')),
        mimetype='text/csv',
        as_attachment=True,
        download_name=f'transactions_{file_id}.csv'
    )

# Chatbot integrated in dashboard (see API below)

@app.route("/api/chat", methods=["POST"])
@login_required
def chat_api():
    """Chat API - answers questions about user's documents"""
    data = request.get_json()
    user_question = data.get("question", "").strip()
    file_id = data.get("file_id", "").strip()
    
    if not user_question or not file_id:
        return jsonify({"error": "Missing question or file_id"}), 400
    
    user = current_user()
    doc = files_collection.find_one(
        {"_id": ObjectId(file_id), "user_id": user["_id"]}
    )
    if not doc:
        return jsonify({"error": "File not found"}), 404
    
    filepath = os.path.join(app.config["UPLOAD_FOLDER"], doc["filename"])
    summary_en, _, _, df, analytics = process_pdf_summary(
        filepath, style="detailed", mode="quick", lang="en"
    )
    
    # Simple question-answer logic
    question_lower = user_question.lower()
    
    responses = {
        "income": f"Your total income is ₹{analytics.get('total_income', 0):.2f}",
        "expense": f"Your total expenses are ₹{analytics.get('total_expense', 0):.2f}",
        "savings": f"Your net savings are ₹{analytics.get('net_savings', 0):.2f}",
        "category": f"Your expenses by category: {json.dumps(analytics.get('by_category', {}), indent=2)}",
        "emi": str([t for t in df.to_dict(orient='records') if 'emi' in t.get('category', '').lower()]),
    }
    
    answer = "I'm not sure how to answer that. Try asking about income, expenses, savings, or categories."
    for key, response in responses.items():
        if key in question_lower:
            answer = response
            break
    
    return jsonify({"answer": answer})

# FEATURE 4: Email Alerts (improved with local notifications)
@app.route("/set-email-alerts", methods=["GET", "POST"])
@login_required
def email_alerts():
    """Set email alert preferences"""
    user = current_user()
    user["is_premium"] = is_premium(user["_id"])
    
    if request.method == "POST":
        large_transaction = float(request.form.get("large_transaction", 10000))
        monthly_budget = float(request.form.get("monthly_budget", 50000))
        
        users_collection.update_one(
            {"_id": user["_id"]},
            {
                "$set": {
                    "alert_large_transaction": large_transaction,
                    "alert_monthly_budget": monthly_budget,
                    "alerts_enabled": True
                }
            }
        )
        
        # Send confirmation email
        try:
            msg = Message(
                subject="🔔 Email Alerts Configured - FinWiz Lite",
                recipients=[user["email"]],
                html=f"""
                <html>
                <body style="font-family: Arial, sans-serif; background-color: #f3f4f6; padding: 20px;">
                    <div style="max-width: 500px; background-color: white; border-radius: 10px; padding: 30px; margin: 0 auto; box-shadow: 0 4px 6px rgba(0,0,0,0.1);">
                        <h2 style="color: #16a34a; margin-top: 0;">✅ Email Alerts Activated!</h2>
                        <p style="color: #4b5563; line-height: 1.6;">
                            Hi <strong>{user.get('name', 'User')}</strong>,
                        </p>
                        <p style="color: #4b5563; line-height: 1.6;">
                            Your email alerts have been successfully configured for FinWiz Lite.
                        </p>
                        
                        <div style="background-color: #dcfce7; border-left: 4px solid #16a34a; padding: 15px; margin: 20px 0; border-radius: 5px;">
                            <p style="margin: 5px 0; color: #166534; font-weight: bold;">Your Alert Settings:</p>
                            <p style="margin: 5px 0; color: #166534;">💸 Large Transaction Alert: <strong>₹{large_transaction:,.2f}</strong></p>
                            <p style="margin: 5px 0; color: #166534;">📊 Monthly Budget Limit: <strong>₹{monthly_budget:,.2f}</strong></p>
                        </div>
                        
                        <p style="color: #4b5563; line-height: 1.6;">
                            You'll receive email notifications when:
                        </p>
                        <ul style="color: #4b5563; line-height: 1.8;">
                            <li>A single transaction exceeds ₹{large_transaction:,.2f}</li>
                            <li>Monthly spending exceeds ₹{monthly_budget:,.2f}</li>
                            <li>Unusual spending patterns are detected</li>
                        </ul>
                        
                        <p style="color: #4b5563; line-height: 1.6; margin-top: 25px; padding-top: 15px; border-top: 1px solid #e5e7eb;">
                            <strong>FinWiz Lite Team</strong>
                        </p>
                    </div>
                </body>
                </html>
                """
            )
            mail.send(msg)
            flash("✅ Email alerts configured! Check your email for confirmation.", "success")
        except Exception as e:
            print(f"Email error: {e}")
            flash(f"⚠️ Alerts saved but email not sent. Check SMTP settings. Error: {str(e)}", "warning")
        
        return redirect(url_for("dashboard"))
    
    user_alerts = users_collection.find_one({"_id": user["_id"]})
    return render_template(
        "email_alerts.html",
        user=user,
        alert_large_transaction=user_alerts.get("alert_large_transaction", 10000),
        alert_monthly_budget=user_alerts.get("alert_monthly_budget", 50000)
    )

if __name__ == "__main__":
    app.run(debug=True)
