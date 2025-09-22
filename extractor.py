# extractor.py
import re
from io import BytesIO
from itertools import zip_longest

import pdfplumber

# ----------------- CONFIG -----------------
HEAD_RULES = {
    "CASH": ["ATM", "CASH", "CSH", "CASA"],
    "Withdrawal": ["UPI", "IMPS", "NEFT", "RTGS", "TRANSFER", "WITHDRAWAL", "DEBIT", "PAYMENT"],
    "Interest": ["INT", "INTEREST", "CR INT", "INTEREST"],
    "Charge": ["CHRG", "CHARGE", "FEE", "GST", "PENALTY"],
    "Salary": ["SALARY", "PAYROLL"],
}

HEADER_ALIASES = {
    "date": ["date", "txn date", "transaction date", "value date", "tran date"],
    "particulars": ["particulars", "description", "narration", "transaction particulars", "details", "remarks"],
    "debit": ["debit", "withdrawal", "dr", "withdrawal amt", "withdrawal amount", "debit amount"],
    "credit": ["credit", "deposit", "cr", "deposit amt", "deposit amount", "credit amount"],
    "balance": ["balance", "running balance", "closing balance", "bal"]
}

DATE_RE = re.compile(r'\b\d{1,2}[-/]\d{1,2}[-/]\d{2,4}\b')  # simple date detection
AMOUNT_RE = re.compile(r'[-+]?\d{1,3}(?:[, ]\d{3})*(?:\.\d+)?|\d+(?:\.\d+)?')

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
    # remove currency symbols and stray characters
    s = re.sub(r'[^\d\-,.\s]', '', s)
    s = s.replace(' ', '').replace(',', '')
    if s == '':
        return None
    try:
        return float(s)
    except:
        # try to find a numeric token
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

def find_header_row(table):
    """
    table: list of rows (each row is list of cells)
    returns index of header row (int) or 0 if not sure
    Heuristic: choose row with most alphabetic tokens and matches to aliases
    """
    best_idx, best_score = 0, -1
    for i, row in enumerate(table[:4]):  # check first 4 rows for header
        score = 0
        for cell in row:
            if not cell:
                continue
            c = str(cell).strip().lower()
            # words matching alias keywords add score
            for aliases in HEADER_ALIASES.values():
                for a in aliases:
                    if a in c:
                        score += 3
            # alphabetic content increases score
            if re.search(r'[a-zA-Z]', c):
                score += 1
        if score > best_score:
            best_score = score
            best_idx = i
    return best_idx

# ----------------- TABLE PROCESSING -----------------
def table_to_transactions(table, meta, page_no=None):
    """
    table: list of rows (list of lists)
    returns list of transaction dicts
    """
    txns = []
    if not table or len(table) < 2:
        return txns

    header_idx = find_header_row(table)
    headers = table[header_idx]
    # normalize header names
    std_headers = []
    for h in headers:
        mapped = map_header_to_std(normalize_header_cell(h)) or normalize_header_cell(h)
        std_headers.append(mapped)

    # iterate data rows after header_idx
    for row in table[header_idx + 1:]:
        # zip with headers even if row shorter or longer
        row_cells = [c or "" for c in row]
        # protect against rows that are entirely empty
        if all((not str(x).strip()) for x in row_cells):
            continue
        row_dict = {}
        for k, v in zip_longest(std_headers, row_cells, fillvalue=""):
            row_dict[k or "col"] = (v or "").strip()

        # attempt to find date & particulars
        date = row_dict.get("date") or row_dict.get("txn date") or row_dict.get("value date") or None
        particulars = row_dict.get("particulars") or row_dict.get("description") or row_dict.get("narration") or row_dict.get("details") or None

        # if date missing, try find any cell matching date pattern
        if not date:
            for cell in row_cells:
                if DATE_RE.search(str(cell)):
                    date = DATE_RE.search(str(cell)).group(0)
                    break

        if not particulars:
            # try to heuristically pick the longest text cell (likely particulars)
            text_cells = [str(c).strip() for c in row_cells if re.search(r'[A-Za-z]', str(c) or '')]
            particulars = max(text_cells, key=len) if text_cells else ""

        # read debit/credit/balance
        debit_raw = row_dict.get("debit") or row_dict.get("dr") or row_dict.get("withdrawal") or ""
        credit_raw = row_dict.get("credit") or row_dict.get("cr") or row_dict.get("deposit") or ""
        balance_raw = row_dict.get("balance") or row_dict.get("bal") or ""

        debit_amt = parse_amount(debit_raw)
        credit_amt = parse_amount(credit_raw)
        balance_val = balance_raw.strip() or None

        # only accept row as transaction if date & particulars & (debit or credit present)
        if not (date and particulars and (debit_amt is not None or credit_amt is not None)):
            # skip non-transaction rows
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
    """
    Fallback parser: tries to find transaction-like lines in free text when tables fail
    """
    txns = []
    lines = [ln.strip() for ln in page_text.splitlines() if ln.strip()]
    for ln in lines:
        # require a date token and at least one amount token
        if not DATE_RE.search(ln):
            continue
        amounts = AMOUNT_RE.findall(ln)
        if not amounts:
            continue
        # pick first date occurence
        date = DATE_RE.search(ln).group(0)
        # pick last two numeric tokens as debit/credit or amount+balance heuristics
        nums = [parse_amount(x) for x in amounts if parse_amount(x) is not None]
        if not nums:
            continue
        # heuristics:
        debit_amt = None
        credit_amt = None
        balance_val = None
        if len(nums) == 1:
            # ambiguous: treat as debit if line contains debit keywords else credit if credit-like words
            if re.search(r'\b(debit|withdrawal|dr|withd)\b', ln, re.I):
                debit_amt = nums[0]
            elif re.search(r'\b(credit|deposit|cr)\b', ln, re.I):
                credit_amt = nums[0]
            else:
                # fallback put into Debit by your default rule
                debit_amt = nums[0]
        elif len(nums) == 2:
            # usually amount & balance OR debit & credit — assume (amount, balance)
            debit_amt = nums[0] if re.search(r'\b(debit|withdrawal|dr)\b', ln, re.I) else None
            credit_amt = nums[0] if re.search(r'\b(credit|deposit|cr)\b', ln, re.I) else None
            # if neither keyword present, treat first as debit (fallback)
            if debit_amt is None and credit_amt is None:
                debit_amt = nums[0]
            balance_val = str(nums[1])
        else:
            # >=3 numbers; often last is balance
            balance_val = str(nums[-1])
            # amount is second last or first depending on format
            amt_candidate = nums[-2]
            # guess debit/credit via keywords
            if re.search(r'\b(debit|withdrawal|dr)\b', ln, re.I):
                debit_amt = amt_candidate
            elif re.search(r'\b(credit|deposit|cr)\b', ln, re.I):
                credit_amt = amt_candidate
            else:
                debit_amt = amt_candidate

        # description/particulars: remove date & numeric tokens
        desc = re.sub(DATE_RE, '', ln)
        desc = re.sub(AMOUNT_RE, '', desc)
        desc = re.sub(r'\s{2,}', ' ', desc).strip()

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
    """
    Public API: returns (meta, transactions)
    meta['_logs'] will contain diagnostic messages (helpful for debugging in Streamlit)
    """
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
            page_logs_start = f"--- Page {p_idx} ---"
            log(page_logs_start, meta)
            try:
                tables = page.extract_tables()
                log(f"Found {len(tables)} tables on page {p_idx}", meta)
                page_txns = []
                for t_idx, table in enumerate(tables, start=1):
                    log(f" Processing table {t_idx} (rows={len(table) if table else 0})", meta)
                    if not table or len(table) < 2:
                        log("  skipping empty/short table", meta)
                        continue
                    tt = table_to_transactions(table, meta, page_no=p_idx)
                    log(f"  table {t_idx} -> {len(tt)} txns", meta)
                    page_txns.extend(tt)

                # if no txns from tables, fallback to text parsing on page
                if not page_txns:
                    text = page.extract_text() or ""
                    log(" No table transactions found; running text fallback", meta)
                    txt_tx = text_fallback_extract(text, meta, page_no=p_idx)
                    log(f"  text fallback -> {len(txt_tx)} txns", meta)
                    page_txns.extend(txt_tx)

                transactions.extend(page_txns)

            except Exception as e:
                log(f"Error processing page {p_idx}: {e}", meta)
                continue

    # final dedupe by (Date, Particulars, Debit, Credit, Page)
    seen = set()
    deduped = []
    for r in transactions:
        key = (r.get("Date"), r.get("Particulars"), r.get("Debit"), r.get("Credit"), r.get("Page"))
        if key in seen:
            continue
        seen.add(key)
        deduped.append(r)

    log(f"Total transactions (deduped): {len(deduped)}", meta)
    meta["count"] = len(deduped)
    return meta, deduped
