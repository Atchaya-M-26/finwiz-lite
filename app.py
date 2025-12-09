from flask import Flask, render_template, request, jsonify, send_file, flash, session
from werkzeug.utils import secure_filename
import os
from ai_service import process_pdf_summary, generate_pdf_summary
import os

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your-secret-key-change-this'
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max

os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

# Simplified language handling (no Flask-Babel needed)
LANGUAGES = {'en': 'English 🇺🇸', 'ta': 'தமிழ் 🇮🇳', 'hi': 'हिंदी 🇮🇳'}

@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        lang = request.form.get('language', 'en')
        session['lang'] = lang
        
        if 'file' not in request.files:
            flash('No file selected')
            return render_template('index.html')
        
        file = request.files['file']
        if file.filename == '':
            flash('No file selected')
            return render_template('index.html')
        
        if file and file.filename.endswith('.pdf'):
            filename = secure_filename(file.filename)
            filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            file.save(filepath)
            
            summary_en, summary_ta, summary_hi = process_pdf_summary(filepath, lang)
            
            return render_template('index.html', 
                                 summary_en=summary_en,
                                 summary_ta=summary_ta, 
                                 summary_hi=summary_hi,
                                 filename=filename,
                                 languages=LANGUAGES)
    
    return render_template('index.html', languages=LANGUAGES)

@app.route('/download/<filename>/<lang>')
def download_summary(filename, lang):
    filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    pdf_path = generate_pdf_summary(filepath, lang)
    return send_file(pdf_path, as_attachment=True, download_name=f"summary_{lang}.pdf")

if __name__ == '__main__':
    app.run(debug=True)
