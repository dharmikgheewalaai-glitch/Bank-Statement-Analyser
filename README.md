# Bank Statement Extractor

A Streamlit application that extracts structured transactions from bank statement PDFs.

## Features
- Accurate table extraction using pdfplumber  
- Intelligent fallback text extraction  
- Classification of transaction heads  
- Cleans dates, amounts, and balances  
- Exports results as:
  - CSV
  - Excel (XLSX)
  - PDF
- Skips header/footer lines like:
  - “STATEMENT OF ACCOUNT…”
  - “Page X of Y”
  - “Printed On…”

## Run Locally

```bash
pip install -r requirements.txt
streamlit run app.py
