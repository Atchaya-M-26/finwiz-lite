import pdfplumber
import os
import tempfile
import re
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet
from googletrans import Translator

translator = Translator()

def extract_text_from_pdf(pdf_path):
    text = ""
    page_count = 0
    
    try:
        with pdfplumber.open(pdf_path) as pdf:
            page_count = len(pdf.pages)
            print(f"📄 Found {page_count} pages")
            
            for i, page in enumerate(pdf.pages):
                page_text = page.extract_text(use_text_flow=True)
                if not page_text:
                    page_text = page.extract_text_simple()
                if not page_text:
                    page_text = page.extract_words()
                    page_text = ' '.join([word.get('text', '') for word in page_text]) if page_text else ""
                
                if page_text:
                    text += page_text + "\n--- Page " + str(i+1) + " ---\n"
                else:
                    text += f"[Page {i+1}: No text extracted]\n"
                    
    except Exception as e:
        text = f"❌ Error: {str(e)}"
    
    print(f"📝 Extracted {len(text)} characters")
    return text, page_count

def generate_financial_summary(text, page_count):
    if len(text.strip()) < 50:
        return f"""
❌ NO TEXT FOUND ({page_count} pages)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━
• PDF is scanned image (needs OCR)
• Use text-based bank statement PDF
"""
    
    lines = [line.strip() for line in text.split('\n') if line.strip()]
    
    # REAL financial data extraction
    patterns = {
        'account': r'(account|acc|no|a/c|acct)[:\s]*([A-Z0-9]{8,20})',
        'balance': r'(balance|bal|closing|total)[:\s]*[₹$]?([0-9,]+\.?[0-9]{0,2})',
        'credit': r'(credit|cr|credited|deposit|income)[:\s]*[₹$]?([0-9,]+\.?[0-9]{0,2})',
        'debit': r'(debit|dr|debited|withdrawal|payment)[:\s]*[₹$]?([0-9,]+\.?[0-9]{0,2})',
        'name': r'(name|holder|customer|account\s+name)[:\s]*([A-Z][a-z]+\s+[A-Z][a-z]+)',
    }
    
    extracted = {}
    for key, pattern in patterns.items():
        matches = re.findall(pattern, text, re.IGNORECASE | re.MULTILINE)
        if matches:
            extracted[key] = matches[0][1] if isinstance(matches[0], tuple) else matches[0]
    
    # Build actual summary
    summary = [f"📊 BANK STATEMENT ANALYSIS"]
    summary.append("=" * 35)
    summary.append(f"📄 Pages: {page_count} | Lines: {len(lines)}")
    
    if extracted.get('name'):
        summary.append(f"👤 Name: {extracted['name']}")
    if extracted.get('account'):
        summary.append(f"🆔 Account: {extracted['account']}")
    if extracted.get('balance'):
        summary.append(f"💰 Balance: ₹{extracted['balance']}")
    if extracted.get('credit'):
        summary.append(f"➕ Credits: ₹{extracted['credit']}")
    if extracted.get('debit'):
        summary.append(f"➖ Debits: ₹{extracted['debit']}")
    
    # Show actual transactions
    summary.append("\n📋 RECENT TRANSACTIONS:")
    transaction_lines = []
    for line in lines:
        if re.search(r'[₹$]\s*\d+[,\d]*\.?\d{0,2}', line):
            transaction_lines.append(line[:60])
    
    for i, txn in enumerate(transaction_lines[:5]):
        summary.append(f"• {txn}")
    
    return '\n'.join(summary)

def translate_summary(summary, target_lang):
    if target_lang == 'en':
        return summary
    try:
        translations = {'ta': 'ta', 'hi': 'hi'}
        result = translator.translate(summary, dest=translations.get(target_lang, 'en'))
        return result.text if result else summary
    except:
        return summary

def process_pdf_summary(pdf_path, preferred_lang):
    text, page_count = extract_text_from_pdf(pdf_path)
    english_summary = generate_financial_summary(text, page_count)
    tamil_summary = translate_summary(english_summary, 'ta')
    hindi_summary = translate_summary(english_summary, 'hi')
    return english_summary, tamil_summary, hindi_summary

def generate_pdf_summary(pdf_path, lang):
    summary_en, summary_ta, summary_hi = process_pdf_summary(pdf_path, lang)
    summaries = {'en': summary_en, 'ta': summary_ta, 'hi': summary_hi}
    selected_summary = summaries[lang]
    
    temp_pdf = tempfile.NamedTemporaryFile(delete=False, suffix='.pdf')
    doc = SimpleDocTemplate(temp_pdf.name, pagesize=letter)
    styles = getSampleStyleSheet()
