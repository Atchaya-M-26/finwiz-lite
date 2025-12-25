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
)
from datetime import datetime, timezone, timedelta
from bson.objectid import ObjectId
from models import users_collection, files_collection
from werkzeug.utils import secure_filename
from flask_bcrypt import Bcrypt
import os

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

os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)

bcrypt = Bcrypt(app)

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

# PREMIUM ROUTES

@app.route("/upgrade")
@login_required
def upgrade():
    return render_template("upgrade.html")

@app.route("/upgrade/confirm", methods=["POST"])
@login_required
def upgrade_confirm():
    payment_method = request.form.get("payment_method")
    user_id = session.get("user_id")
    flash(
        f"✅ Payment successful via {payment_method}! Premium activated for 12 months."
    )
    PREMIUM_USERS.add(user_id)
    return redirect(url_for("dashboard"))

@app.route("/cancel-premium", methods=["POST"])
@login_required
def cancel_premium():
    user_id = session.get("user_id")
    if user_id in PREMIUM_USERS:
        PREMIUM_USERS.remove(user_id)
        flash(
            "😢 Premium cancelled. You'll keep premium features until end of billing period."
        )
    return redirect(url_for("dashboard"))

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
        save_file_record(user_id, filename, file.filename)
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

if __name__ == "__main__":
    app.run(debug=True)
