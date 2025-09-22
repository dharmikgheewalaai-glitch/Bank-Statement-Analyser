import re
from io import BytesIO
from itertools import zip_longest
import pdfplumber

# ----------------- CONFIG -----------------
HEAD_RULES = {
    "CASH": ["ATM", "CASH", "CSH", "CASA"],
    "Withdrawal": ["UPI", "IMPS", "NEFT", "RTGS", "WITHDRAWAL", "DEBIT", "PAYMENT"],
    "Interest": ["INT", "INTEREST", "CR INT"],
    "Charge": ["CHRG", "CHARGE", "FEE", "GST", "PENALTY"],
    "Salary": ["SALARY", "PAYROLL"],
    "Refund": ["REFUND", "REVERSAL"],
    "LIC": ["LIC"],
    "ICICI SECURITIES": ["ICICISEC", "ICICI SECURITIES"],
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

# 🔹 New regex for account numbers (plain + masked)
ACCOUNT_RE = re.compile(r"\b(?:X{2,}\d{3,6}|\d{6,16})\b")

# names & institutions (will refine via regex)
NAME_RE = re.compile(r"(?:TO|FROM|BY|FAVOUR|IN FAVOUR OF|BENEFICIARY)\s+([A-Z ]{3,})")

# ----------------- HELPERS -----------------
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

def classify_head(particulars):
    p = (particulars or "").upper()
    for head, kws in HEAD_RULES.items():
        for kw in kws:
            if kw in p:
                return head
    return "Other"

def extract_subhead(particulars):
    """
    Extract specific entity: account number, name, institution, or bank
    """
    p = (particulars or "").upper()

    # 1. Account number (masked or plain)
    acc_match = ACCOUNT_RE.search(p)
    if acc_match:
        return f"Account {acc_match.group(0)}"

    # 2. Common banks/institutions keywords
    banks = ["SBI", "STATE BANK", "HDFC", "ICICI", "AXIS", "KOTAK", "PNB",
             "BANK OF BARODA", "BOB", "LIC", "AMAZON", "FLIPKART", "PAYTM",
             "PHONEPE", "GOOGLE", "BHARTI", "AIRTEL"]
    for b in banks:
        if b in p:
            return b.title()

    # 3. Name after keywords like TO/FROM/BY
    name_match = NAME_RE.search(p)
    if name_match:
        return name_match.group(1).title().strip()

    # 4. Fallback → longest word that looks like a name
    tokens = [t for t in p.split() if len(t) > 3 and t.isalpha()]
    if tokens:
        return tokens[0].title()

    return ""
