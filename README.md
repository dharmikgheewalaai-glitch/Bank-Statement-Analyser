# Bank Statement Analyzer

Streamlit application for converting bank statements into a normalized transaction table and optional Tally-ready output.

## Features
- PDF, CSV and Excel upload
- Text-first PDF extraction
- Automatic detection of 7 statement layouts
- Table validation
- Camelot fallback only when the text-first result looks unreliable
- Normal output: Date, Particulars, Debit, Credit, Balance, Head
- Tally output: + v-Type, Accounts, Bank Name
- Custom Head rules
- Account and Journal mappings
- Dashboard, History and Rules tabs
- Excel export

## Run
```bash
pip install -r requirements.txt
streamlit run app.py
```

## GitHub
```bash
git init
git add .
git commit -m "Initial Bank Statement Analyzer"
git branch -M main
git remote add origin YOUR_REPOSITORY_URL
git push -u origin main
```

For Streamlit Community Cloud, select `app.py` as the entry point.
