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


## Streamlit Community Cloud deployment fix

The previous build used `camelot-py[cv]`, which can pull GUI/OpenCV dependencies that are
unnecessary for this server-side application. This version uses `camelot-py==2.0.0` without
the optional CV extra and imports Camelot lazily only when the text-first extractor needs a
fallback.

Files added/changed:
- `requirements.txt` — Cloud-safe dependency set
- `runtime.txt` — Python 3.12 consistency hint
- `modules/camelot_parser.py` — lazy Camelot import + Camelot 2.x-compatible fallback

Streamlit Community Cloud reads Python dependencies from `requirements.txt` and can use
`packages.txt` for Linux/apt dependencies when needed.
