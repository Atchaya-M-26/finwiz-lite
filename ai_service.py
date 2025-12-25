import os
import tempfile
import re
import pdfplumber
import pandas as pd
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet

# ---------- PDF TEXT EXTRACTION ----------

def extract_text_from_pdf(pdf_path):
    text = ""
    page_count = 0

    with pdfplumber.open(pdf_path) as pdf:
        page_count = len(pdf.pages)
        for i, page in enumerate(pdf.pages):
            page_text = page.extract_text()
            if page_text:
                text += page_text + f"\n--- Page {i+1} ---\n"

    return text, page_count

# ---------- SIMPLE TRANSACTION PARSER ----------

def parse_transactions(text):
    """
    Very simple heuristic parser:
    looks for lines with a date and an amount.
    You can tweak this later for your bank format.
    """
    lines = [l.strip() for l in text.split("\n") if l.strip()]
    rows = []

    date_pattern = r"\b(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})\b"
    amount_pattern = r"([₹$]?\s*[0-9,]+\.\d{2})"

    for line in lines:
        date_match = re.search(date_pattern, line)
        amount_match = re.search(amount_pattern, line)
        if amount_match:
            amount_str = amount_match.group(1)
            clean_amount = float(
                amount_str.replace("₹", "").replace("$", "").replace(",", "").strip()
            )
            # crude credit/debit guess
            txn_type = "credit" if "cr" in line.lower() or "credit" in line.lower() else "debit"
            rows.append(
                {
                    "raw_line": line,
                    "date": date_match.group(1) if date_match else "",
                    "amount": clean_amount,
                    "type": txn_type,
                }
            )

    if not rows:
        return pd.DataFrame(columns=["raw_line", "date", "amount", "type"])

    df = pd.DataFrame(rows)

    # simple keyword-based category
    def categorize(row):
        text = row["raw_line"].lower()
        if any(k in text for k in ["salary", "credit salary", "payroll"]):
            return "salary"
        if any(k in text for k in ["rent", "lease"]):
            return "rent"
        if any(k in text for k in ["emi", "loan", "instalment"]):
            return "emi"
        if any(k in text for k in ["food", "swiggy", "zomato", "restaurant", "hotel"]):
            return "food"
        if any(k in text for k in ["shopping", "amazon", "flipkart", "myntra"]):
            return "shopping"
        if any(k in text for k in ["insurance", "premium", "policy"]):
            return "insurance"
        return "other"

    df["category"] = df.apply(categorize, axis=1)
    return df

def compute_analytics(df: pd.DataFrame):
    if df.empty:
        return {
            "total_income": 0.0,
            "total_expense": 0.0,
            "net_savings": 0.0,
            "by_category": {},
        }

    income = df[df["type"] == "credit"]["amount"].sum()
    expense = df[df["type"] == "debit"]["amount"].sum()
    net = income - expense
    by_cat = (
        df[df["type"] == "debit"]
        .groupby("category")["amount"]
        .sum()
        .sort_values(ascending=False)
        .to_dict()
    )

    return {
        "total_income": round(income, 2),
        "total_expense": round(expense, 2),
        "net_savings": round(net, 2),
        "by_category": {k: round(v, 2) for k, v in by_cat.items()},
    }

# ---------- OFFLINE SUMMARY (NO EXTERNAL API) ----------

def call_model_summary(text, analytics, style="simple", mode="quick"):
    """
    Offline fallback summary that does NOT call any external API.
    It just uses the extracted analytics + a few sample lines.
    """

    lines = [l.strip() for l in text.split("\n") if l.strip()]
    sample_lines = lines[:5]

    style_label = "Simple explanation" if style == "simple" else "Analyst-style explanation"
    mode_label = {
        "quick": "Quick 5–6 bullet overview.",
        "detailed": "Detailed sections: Overview, Income, Expenses, Risk, Suggestions.",
        "loan": "Focus on EMIs, interest/charges and credit risk.",
    }.get(mode, "Quick overview.")

    summary_parts = [
        "⚠️ AI cloud summary is disabled (no external credits).",
        "",
        f"Style: {style_label}",
        f"Mode: {mode_label}",
        "",
        "📊 Basic analytics from your statement:",
        f"- Total income (credits): ₹{analytics['total_income']}",
        f"- Total expenses (debits): ₹{analytics['total_expense']}",
        f"- Net savings: ₹{analytics['net_savings']}",
    ]

    if analytics["by_category"]:
        summary_parts.append("- Expenses by category:")
        for cat, amt in analytics["by_category"].items():
            summary_parts.append(f"  • {cat}: ₹{amt}")

    if sample_lines:
        summary_parts.append("")
        summary_parts.append("📝 Sample lines from your statement:")
        for ln in sample_lines:
            summary_parts.append(f"- {ln[:120]}")

    summary_parts.append("")
    summary_parts.append("Later you can plug in a real AI API here to generate a smarter narrative summary.")
    return "\n".join(summary_parts)

# ---------- MAIN ENTRY POINTS ----------

def process_pdf_summary(pdf_path, style="simple", mode="quick", lang="en"):
    text, page_count = extract_text_from_pdf(pdf_path)
    if len(text.strip()) < 50:
        # no text -> probably scanned
        base_msg = (
            "This looks like a scanned or image-only PDF. "
            "OCR support is not enabled yet. Try uploading an e-statement downloaded from your bank website."
        )
        # English-only for now
        return base_msg, None, None, None, None

    df = parse_transactions(text)
    analytics = compute_analytics(df)
    summary_en = call_model_summary(text, analytics, style=style, mode=mode)

    # Tamil/Hindi disabled for now -> None
    return summary_en, None, None, df, analytics

def generate_pdf_summary(summary_text):
    temp_pdf = tempfile.NamedTemporaryFile(delete=False, suffix=".pdf")
    doc = SimpleDocTemplate(temp_pdf.name, pagesize=letter)
    styles = getSampleStyleSheet()
    story = [
        Paragraph("FinWiz Lite – Financial Summary", styles["Title"]),
        Spacer(1, 12),
        Paragraph(summary_text.replace("\n", "<br/>"), styles["Normal"]),
    ]
    doc.build(story)
    return temp_pdf.name
