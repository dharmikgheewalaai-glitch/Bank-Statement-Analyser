import re
from io import BytesIO
from itertools import zip_longest
import pdfplumber

# ----------------- CONFIG -----------------
HEAD_RULES = {
    "CASH": ["ATM", "CASH", "CSH", "CASA"],
    "Withdrawal": ["UPI", "IMPS", "NEFT", "RTGS", "WITHDRAWAL", "DEBIT", "PAYMENT", "TRANSFER", "TRF", "INTRA"],
    "Interest": ["INT", "INTEREST", "CR INT"],
    "Charge": ["CHRG", "CHARGE", "FEE", "GST", "PENALTY"],
    "Salary": ["SALARY", "PAYROLL"],
    "Refund": ["REFUND", "REVERSAL"],
    "LIC": ["LIC"],
    "ICICI SECURITIES": ["icicisec", "ICICI SECURITIES"],
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

# Detect account numbers (Acc:xxxx0301, XXXXX9012, etc.)
ACCOUNT_RE = re.compile(r'\b(?:Acc(?:ount)?[:\s]*X{2,}\d+|\d{6,})\b', re.I)

# Detect individual / institution names (basic heuristic: 2+ capitalized words)
NAME_RE = re.compile(r'\b([A-Z][a-z]+\s+[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)\b')

# ----------------- HELPERS -----------------
def log(msg, meta):
    meta.setdefault("_logs", []).append(str(msg))

def normalize_header_cell(cell):
    if cell is None:
        return ""
    return str(cell).strip().lower()

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

def classify_head(particulars):
    p = (particulars or "").upper()
    for head, kws in HEAD_RULES.items():
        for kw in kws:
            if kw in p:
                return head
    return "Other"

def extract_subhead(particulars):
    """Extract name or account number from particulars"""
    if not particulars:
        return ""
    # Check account number
    acc = ACCOUNT_RE.search(particulars)
    if acc:
        return acc.group(0)
    # Check for person/institution name
    name = NAME_RE.search(particulars)
    if name:
        return name.group(0)
    return ""

def find_header_row(table):
    best_idx, best_score = 0, -1
    for i, row in enumerate(table[:4]):
        score = 0
        for cell in row:
            if not cell:
                continue
            c = str(cell).strip().lower()
            for aliases in HEADER_ALIASES.values():
                for a in aliases:
                    if a in c:
                        score += 3
            if re.search(r'[a-zA-Z]', c):
                score += 1
        if score > best_score:
            best_score = score
            best_idx = i
    return best_idx

# ----------------- TABLE PROCESSING -----------------
def table_to_transactions(table, meta, page_no=None):
    txns = []
    if not table or len(table) < 2:
        return txns

    header_idx = find_header_row(table)
    headers = table[header_idx]
    std_headers = [map_header_to_std(normalize_header_cell(h)) or normalize_header_cell(h) for h in headers]

    for row in table[header_idx + 1:]:
        row_cells = [c or "" for c in row]
        if all((not str(x).strip()) for x in row_cells):
            continue
        row_dict = {k or "col": (v or "").strip() for k, v in zip_longest(std_headers, row_cells, fillvalue="")}

        date = row_dict.get("date") or None
        particulars = row_dict.get("particulars") or None

        if not date:
            for cell in row_cells:
                if DATE_RE.search(str(cell)):
                    date = DATE_RE.search(str(cell)).group(0)
                    break

        if not particulars:
            text_cells = [str(c).strip() for c in row_cells if re.search(r'[A-Za-z]', str(c) or '')]
            particulars = max(text_cells, key=len) if text_cells else ""

        debit_amt = parse_amount(row_dict.get("debit"))
        credit_amt = parse_amount(row_dict.get("credit"))
        balance_val = row_dict.get("balance") or None

        if not (date and particulars and (debit_amt is not None or credit_amt is not None)):
            continue

        head = classify_head(particulars)
        sub_head = extract_subhead(particulars)

        txns.append({
            "Date": str(date).strip(),
            "Particulars": str(particulars).strip(),
            "Debit": debit_amt,
            "Credit": credit_amt,
            "Head": head,
            "Sub Head": sub_head,
            "Balance": balance_val,
            "Page": page_no
        })
    return txns

# ----------------- MAIN API -----------------
def process_file(file_bytes, filename):
    meta = {"account_number": None, "name": None, "bank": None, "_logs": []}
    transactions = []
    try:
        pdf = pdfplumber.open(BytesIO(file_bytes))
    except Exception as e:
        log(f"ERROR opening PDF: {e}", meta)
        return meta, transactions

    with pdf:
        log(f"PDF opened: {len(pdf.pages)} pages", meta)
        for p_idx, page in enumerate(pdf.pages, start=1):
            try:
                tables = page.extract_tables()
                page_txns = []
                for t_idx, table in enumerate(tables, start=1):
                    tt = table_to_transactions(table, meta, page_no=p_idx)
                    page_txns.extend(tt)

                if not page_txns:
                    text = page.extract_text() or ""
                    # (text fallback can be added if needed)

                transactions.extend(page_txns)
            except Exception as e:
                log(f"Error processing page {p_idx}: {e}", meta)
                continue

    # Deduplicate
    seen, deduped = set(), []
    for r in transactions:
        key = (r.get("Date"), r.get("Particulars"), r.get("Debit"), r.get("Credit"), r.get("Page"))
        if key in seen:
            continue
        seen.add(key)
        deduped.append(r)

    meta["count"] = len(deduped)
    log(f"Total transactions (deduped): {len(deduped)}", meta)
    return meta, deduped
