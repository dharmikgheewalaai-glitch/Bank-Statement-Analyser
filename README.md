# ================= README.md =================

# Bank Statement Extractor

A simple Streamlit app to extract transactions from bank statements.

## Features
- Extracts clean transactions from bank statement PDFs
- Merges multi-line transactions
- Ignores headers/footers like "STATEMENT OF ACCOUNT" and "Page X of Y Printed"
- Exports CSV, Excel and PDF

## Run locally

1. Create a virtualenv (optional)

```bash
python -m venv venv
source venv/bin/activate  # mac/linux
venv\Scripts\activate     # windows
```

2. Install requirements

```bash
pip install -r requirements.txt
```

3. Run app

```bash
streamlit run app.py
```
