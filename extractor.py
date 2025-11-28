# extractor.py
import re
from io import BytesIO
from itertools import zip_longest
import pdfplumber

# ----------------- GLOBAL IGNORE LIST (BLOCK ALL HEADERS/FOOTERS) -----------------
IGNORE_PATTERNS = [
    r"statement of account",
    r"account statement",
    r"for the period",
    r"period from",
    r"statement period",
    r"page\s+\d+\s+of\s+\d+",
    r"printed on",
    r"print date",
    r"account number",
    r"customer id",
    r"ifsc",
    r"micr",
    r"branch",
    r"available balance",
    r"ledger balance",
    r"dear customer",
    r"computer generated",
    r"thank you",
    r"end of statement",
    r"opening balance",
    r"closing balance",
    r"transaction summary",
]

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
    p = str(particulars or "").upper()

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
    if any(kw in p for kw in ["INT PD", "INT CR", "INTEREST"]):
        return "INTEREST"
    if any(kw in p for kw in ["LIC OF INDIA", "LIFE INSURANCE CORPORATIO", "LIFE INSURANCE CORPORATION OF INDIA"]):
        return "LIC"
    if "TAX REFUND" in p:
        return "TAX REFUND"

    for head, kws in HEAD_RULES.items():
        for kw in kws:
            if kw in p:
                return head

    return "OTHER"


# ----------------- TABLE PROCESSING -----------------
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
            best_idx = i
            best_score = score
    return best_idx


def table_to_transactions(table, meta, page_no=None):
    txns = []
    if not table or len(table) < 2:
        return txns

    header_idx = find_header_row(table)
    headers = table[header_idx]

    std_headers = []
    for h in headers:
        mapped = map_header_to_std(normalize_header_cell(h)) or normalize_header_cell(h)
        std_headers.append(mapped)

    for row in table[header_idx + 1:]:
        # Skip header/footer text inside tables
        if any(re.search(p, " ".join(str(x) for x in row), re.IGNORECASE) for p in IGNORE_PATTERNS):
            continue

        # Normalize row length
        if len(row) < len(headers):
            row = row + [""] * (len(headers) - len(row))
        if len(row) > len(headers):
            row = row[:len(headers)]

        row_cells = [c or "" for c in row]
        if all((not str(x).strip()) for x in row_cells):
            continue

        row_dict = {}
        for k, v in zip_longest(std_headers, row_cells, fillvalue=""):
            row_dict[k or "col"] = (v or "").strip()

        date = row_dict.get("date") or None
        particulars = row_dict.get("particulars") or ""
        debit_amt = parse_amount(row_dict.get("debit") or "")
        credit_amt = parse_amount(row_dict.get("credit") or "")
        balance_val = parse_amount(row_dict.get("balance") or "")

        # Skip invalid rows & table headers disguised as rows
        if any(re.search(p, str(particulars), re.IGNORECASE) for p in IGNORE_PATTERNS):
            continue

        if not (date and particulars):
            continue

        if debit_amt is None and credit_amt is None:
            continue

        head = classify_head(particulars)

        txns.append({
            "Date": str(date).strip(),
            "Particulars": str(particulars).strip(),
            "Debit": debit_amt,
            "Credit": credit_amt,
            "Head": head,
            "Balance": balance_val,
            "Page": page_no
        })

    return txns


# ----------------- TEXT FALLBACK -----------------
def text_fallback_extract(page_text, meta, page_no=None):
    txns = []
    lines = [ln.strip() for ln in page_text.splitlines() if ln.strip()]

    for ln in lines:
        if any(re.search(p, ln, re.IGNORECASE) for p in IGNORE_PATTERNS):
            continue

        if not DATE_RE.search(ln):
            continue

        amounts = AMOUNT_RE.findall(ln)
        if not amounts:
            continue

        nums = [parse_amount(x) for x in amounts if parse_amount(x) is not None]
        if not nums:
            continue

        date = DATE_RE.search(ln).group(0)
        debit_amt = credit_amt = balance_val = None

        if len(nums) == 1:
            debit_amt = nums[0]
        elif len(nums) == 2:
            debit_amt, balance_val = nums
        elif len(nums) >= 3:
            debit_amt, credit_amt, balance_val = nums[:3]

        head = classify_head(ln)

        txns.append({
            "Date": date,
            "Particulars": ln,
            "Debit": debit_amt,
            "Credit": credit_amt,
            "Head": head,
            "Balance": balance_val,
            "Page": page_no
        })

    return txns


# ----------------- MAIN API -----------------
def process_file(file_bytes, filename):
    meta = {"_logs": []}
    transactions = []

    try:
        pdf = pdfplumber.open(BytesIO(file_bytes))
    except:
        return meta, transactions

    with pdf:
        for idx, page in enumerate(pdf.pages, start=1):
            try:
                tables = page.extract_tables()
                page_txns = []
                for table in tables:
                    page_txns.extend(table_to_transactions(table, meta, page_no=idx))

                if not page_txns:
                    text = page.extract_text() or ""
                    page_txns.extend(text_fallback_extract(text, meta, page_no=idx))

                transactions.extend(page_txns)
            except:
                continue

    # Deduplicate
    seen, result = set(), []
    for r in transactions:
        key = (r["Date"], r["Particulars"], r["Debit"], r["Credit"], r["Page"])
        if key not in seen:
            seen.add(key)
            result.append(r)

    return meta, result
