🧾 FinWiz Lite – AI Financial Document Summarizer

FinWiz Lite is a **web application** that helps users upload complex financial PDFs (bank statements, loan forms, insurance documents) and get **clear, simplified summaries** in **English, Tamil, and Hindi**.

> 🚧 **Status: Work in Progress**  
> This project is actively being built. Features, UI, and AI capabilities will keep improving over time.

 ✨ Current Features

- 📄 Upload financial PDFs (statements, policy docs, etc.)
- 🔍 Extracts text from PDF using Python
- 🧠 Generates a rule-based financial summary
- 🌐 Multi-language support:
  - English
  - Tamil
  - Hindi
- 🎨 Modern dashboard UI with card layout
- 📥 Download generated summary as PDF

 🏗️ Tech Stack

- **Frontend**: HTML, Tailwind CSS, Jinja2 templates  
- **Backend**: Python, Flask  
- **PDF Processing**: `pdfplumber`, `reportlab`  
- **Translation**: `googletrans` (experimental)  

 🚀 How to Run Locally

1. **Clone the repository**
git clone https://github.com/Atchaya-M-26/finwiz-lite.git
cd finwiz-lite

2. **Create virtual environment (optional but recommended)**
python -m venv venv

Windows:
venv\Scripts\activate

3. **Install dependencies**
pip install -r requirements.txt

4. **Run the app**
python app.py

5. Open browser and go to:
http://127.0.0.1:5000

 📌 Roadmap / To‑Do

- [ ] Integrate real AI summarization (LLM-based) for smarter insights  
- [ ] Improve financial pattern detection (accounts, balances, transactions)  
- [ ] Add OCR support for scanned PDFs  
- [ ] Add proper error handling and user messages  
- [ ] Write tests and documentation  
- [ ] Deploy to a cloud platform for live demo  

🤝 Contributions & Feedback

This is a learning/project-in-progress repo. Suggestions, issues, and ideas are welcome.  
You can open an **Issue** or a **Pull Request** if you have improvements.

 📩 Contact
If you want to discuss this project, share feedback, or suggest features, feel free to reach out via GitHub.
Thanks for checking out **FinWiz Lite** – more improvements are coming soon!
