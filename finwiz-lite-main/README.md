FinWiz Lite - Professional PDF Finance Analyzer
🚀 AI-powered bank statement analyzer with daily limits & premium features

[![GitHub Repo](https://img.shields.io/badge/GitHub-Repo-bluehttps://github.com/Atchaya-M-26/finwiz-lite

📊 PDF Bank Statement Analysis - Extracts transactions, balances, EMIs

⚡ Daily Limits - 10 free PDFs/day | Unlimited premium

💰 EMI Calculator - Auto-calculates loan installments

📁 Archive & Delete - Manage analysis history

🔒 Secure - No data stored beyond session (except archive)

🎯 Demo
text
Upload PDF → AI extracts: Income, Expenses, Savings Rate, EMIs
Daily Limit: 10 Free | Unlimited Premium
🚀 Quick Start (1 minute)
bash
# 1. Clone
git clone https://github.com/Atchaya-M-26/finwiz-lite.git
cd finwiz-lite

# 2. Install
pip install -r requirements.txt

# 3. Run
python app.py

# 4. Open browser
http://127.0.0.1:5000
📋 Tech Stack
text
Backend: Flask + MongoDB
AI: pdfplumber, pandas, numpy
Frontend: HTML/CSS/JS (Bootstrap)
Deployment: Ready for Render/Heroku/Vercel
🛠️ File Structure
text
finwiz-lite/
├── app.py              # Main Flask app + routes
├── ai_service.py       # PDF extraction + EMI calculator
├── models.py           # MongoDB user/analysis models
├── requirements.txt    # 15+ packages
├── templates/          # Dashboard, landing pages
├── static/             # CSS/JS
├── .gitignore          # Excludes venv/uploads
└── README.md           # This file!
🔑 Environment Variables
bash
# .env file (create locally, don't commit)
MONGODB_URI=mongodb://localhost:27017/finwiz
SECRET_KEY=your-secret-key-here
🌐 Deploy to Production
Render.com (Free)
Push to GitHub ✅ (Done!)

render.com → New Web Service → Connect GitHub repo

Build: pip install -r requirements.txt

Start: python app.py

Heroku
bash
heroku create finwiz-lite
git push heroku main
📈 Premium Features
Free	Premium
10 PDFs/day	Unlimited
Basic analysis	EMI calculator
No archive	Full archive/delete
🤝 Contributing
Fork repo

git checkout -b feature-branch

git add . && git commit -m "Add feature"

git push origin feature-branch

Open PR!

📄 License
MIT - Free for commercial use

👩‍💻 Author
Atchaya M - Full Stack Developer
GitHub | Portfolio

⭐ Star this repo if it helps!
Deploy live in 2 minutes → http://your-app.render.com