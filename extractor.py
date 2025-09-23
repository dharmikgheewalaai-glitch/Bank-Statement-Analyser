# extractor.py
import re
from io import BytesIO
from itertools import zip_longest
import pdfplumber

# ----------------- CONFIG -----------------
HEAD_RULES = {
    "CASH": ["ATM WDL", "CASH", "CASH WDL", "CSH", "SELF"],
    "SALARY": ["SALARY", "PAYROLL"],
    "WITHDRAWAL": ["ATM ISSUER REV", "UPI", "UPI REV"],
}

HEADER_ALIASES = {
    "date": ["date", "txn date", "transaction date", "value date", "tran date"],
    "particulars": ["particulars", "description", "narration", "transaction particulars", "details", "remarks"],
    "debit": ["debit", "withdrawal", "dr", "withdrawal amt", "withdrawal amount", "debit amount"],
    "credit": ["credit", "deposit", "cr", "deposit amt", "deposit amount", "credit amount"],
    "balance": ["balance", "running balance", "closing balance", "bal"]
}

DATE_RE = re.compile(r'\b\d{1,2}[-/]\d{1,2}[-/]\d{2,4}\b')
AMOUNT_RE = re.compile(r'[-+]?\d{1,3}(?:[, ]\d{3})*(?:\.\d+)?|\d+(?:\.\d+)?')

# ----------------- HELPERS -----------------
def log(msg, meta):
    meta.setdefault("_logs", []).append(str(msg))

def normalize_header_cell(cell):
    return str(cell).strip().lower() if cell else ""

def map_header_to_std(h):
    h = (h or "").strip().lower()
    for std, aliases in HEADER_ALIASES.items():
        for a in aliases:
            if h.startswith(a) or a in h:
                return std
    return None

def parse_amount(s):
    if s is None:
        return None
    s = str(s).strip().replace('\xa0', ' ')
    s = re.sub(r'[^\d\-,.\s]', '', s)
    s = s.replace(' ', '').replace(',', '')
    if s == '':
        return None
    try:
        return float(s)
    except:
        m = AMOUNT_RE.search(str(s))
        if m:
            try:
                return float(m.group(0).replace(',', '').replace(' ', ''))
            except:
                return None
        return None

# ----------------- HEAD CLASSIFICATION -----------------
def classify_head(particulars):
    p = (particulars or "").upper()

    # Transfers
    if any(kw in p for kw in ["TRANSFER", "TRF", "INTRA", "TO", "FROM"]):
        return "Transfer"

    if any(kw in p for kw in ["BAJAJ FINANCE LIMITE", "BAJAJ FINANCE LTD", "BAJAJFIN"]):
        return "BAJAJ FINANCE LTD"

    if any(kw in p for kw in ["CGST", "CHARGES", "CHGS", "CHRG", "SGST", "GST"]):
        return "CHARGES"

    if any(kw in p for kw in ["PETROL", "PETROLEUM"]):
        return "CONVEYANCE"

    if "DIVIDEND" in p:
        return "DIVIDEND"

    if any(kw in p for kw in ["ICICI SECURITIES LTD", "ICICISEC.UPI", "ICICISECURITIES"]):
        return "ICICI DIRECT"

    if any(kw in p for kw in ["IDFC FIRST BANK", "IDFCFBLIMITED"]):
        return "IDFC FIRST BANK LTD"

    if "BAJAJ ALLIANZ GEN INS COM" in p:
        return "INSURANCE"

    if any(kw in p for kw in ["INT", "INTEREST"]):
        return "INTEREST"

    if any(kw in p for kw in ["LIC OF INDIA", "LIFE INSURANCE CORPORATIO", "LIFE INSURANCE CORPORATION OF INDIA"]):
        return "LIC"

    if "TAX REFUND" in p:
        return "TAX REFUND"

    # Fallback to predefined simple rules
    for head, kws in HEAD_RULES.items():
        for kw in kws:
            if kw in p:
                return head

    return "Other"
