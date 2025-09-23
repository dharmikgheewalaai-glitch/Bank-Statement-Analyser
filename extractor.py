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

    # ✅ Step 4: Generic head rules
    for head, kws in HEAD_RULES.items():
        for kw in kws:
            if kw in p:
                return head

    # ✅ Default
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
            best_score = score
            best_idx = i
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

        if not (date and particulars and (debit_amt is not None or credit_amt is not None)):
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
        if not DATE_RE.search(ln):
            continue
        amounts = AMOUNT_RE.findall(ln)
        if not amounts:
            continue
        date = DATE_RE.search(ln).group(0)
        nums = [parse_amount(x) for x in amounts if parse_amount(x) is not None]
        if not nums:
            continue

        debit_amt, credit_amt, balance_val = None, None, None
        if len(nums) == 1:
            debit_amt = nums[0]
        elif len(nums) >= 2:
            debit_amt, balance_val = nums[-2], nums[-1]

        desc = ln
        head = classify_head(desc)

        txns.append({
            "Date": date,
            "Particulars": desc,
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
    except Exception as e:
        return meta, transactions

    with pdf:
        for p_idx, page in enumerate(pdf.pages, start=1):
            try:
                tables = page.extract_tables()
                page_txns = []
                for table in tables:
                    tt = table_to_transactions(table, meta, page_no=p_idx)
                    page_txns.extend(tt)

                if not page_txns:
                    text = page.extract_text() or ""
                    txt_tx = text_fallback_extract(text, meta, page_no=p_idx)
                    page_txns.extend(txt_tx)

                transactions.extend(page_txns)
            except:
                continue

    # Deduplicate
    seen, deduped = set(), []
    for r in transactions:
        key = (r.get("Date"), r.get("Particulars"), r.get("Debit"), r.get("Credit"), r.get("Page"))
        if key not in seen:
            seen.add(key)
            deduped.append(r)

    return meta, deduped
