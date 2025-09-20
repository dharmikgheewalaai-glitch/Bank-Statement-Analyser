import re
from io import BytesIO
from itertools import zip_longest
import pdfplumber

# ----------------- CONFIG -----------------
HEAD_RULES = {
    "CASH": ["ATM", "CASH", "CSH", "CASA"],
    "Withdrawal": ["UPI", "IMPS", "NEFT", "RTGS", "PAYMENT", "ECOM", "DEBIT"],
    "Interest": ["INT", "INTEREST", "CR INT"],
    "Charge": ["CHRG", "CHARGE", "FEE", "GST", "PENALTY"],
    "Salary": ["SALARY", "PAYROLL"],
    "Refund": ["REFUND", "REVERSAL"],
    "LIC": ["LIC", "LIFE"],
    # ❌ Removed "SUTEX": ["SUTEX", "CO-OP", "COOPERATIVE"]
}

HEADER_ALIASES = {
    "date": ["date", "txn date", "transaction date", "value date", "tran date"],
    "particulars": ["particulars", "description", "narration", "transaction particulars", "details", "remarks"],
    "debit": ["debit", "withdrawal", "dr", "withdrawal amt", "withdrawal amount", "debit amount"],
    "credit": ["credit", "deposit", "cr", "deposit amt", "deposit amount", "credit amount"],
    "balance": ["balance", "running balance", "closing balance", "bal"]
}

# Regex patterns
DATE_RE = re.compile(r'\b\d{1,2}[./-]\d{1,2}[./-]\d{2,4}\b')
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
    """Parse debit/credit/balance values into absolute floats"""
    if s is None:
        return None
    s = str(s).strip().replace('\xa0', ' ')
    s = re.sub(r'[^\d\-,.\s]', '', s)
    s = s.replace(' ', '').replace(',', '')
    if s == '':
        return None
    try:
        return abs(float(s))
    except:
        m = AMOUNT_RE.search(str(s))
        if m:
            try:
                return abs(float(m.group(0).replace(',', '').replace(' ', '')))
            except:
                return None
        return None

def classify_head(particulars):
    """Classify transactions based on narration (Particulars)"""
    p = (particulars or "").upper()

    # ✅ Step 1: Special handling for Transfers
    if any(kw in p for kw in ["TRANSFER", "TRF", "INTRA", "TO ", "FROM "]):
        acc_match = re.search(r"\b\d{6,16}\b", p)  # 6–16 digit account numbers
        if acc_match:
            return f"Account {acc_match.group(0)}"
        
        name_match = re.search(r"(?:TO|FROM|TRF|TRANSFER)\s+([A-Z ]+)", p)
        if name_match:
            name = name_match.group(1).strip()
            return name.title()

        return "Transfer"

    # ✅ Step 2: Generic head rules
    for head, kws in HEAD_RULES.items():
        for kw in kws:
            if kw in p:
                return head

    return "Other"

def find_header_row(table):
    """Find the most likely header row"""
    best_idx, best_score = 0, -1
    for i, row in enumerate(table[:4]):  # first 4 rows
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
        particulars = row_dict.get("particulars") or None

        if not date:
            for cell in row_cells:
                if DATE_RE.search(str(cell)):
                    date = DATE_RE.search(str(cell)).group(0)
                    break

        if not particulars:
            text_cells = [str(c).strip() for c in row_cells if re.search(r'[A-Za-z]', str(c) or '')]
            particulars = max(text_cells, key=len) if text_cells else ""

        debit_raw = row_dict.get("debit") or ""
        credit_raw = row_dict.get("credit") or ""
        balance_raw = row_dict.get("balance") or ""

        debit_amt = parse_amount(debit_raw)
        credit_amt = parse_amount(credit_raw)
        balance_val = parse_amount(balance_raw)

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

        debit_amt = credit_amt = None
        balance_val = None

        if len(nums) == 1:
            if re.search(r'\b(debit|withdrawal|dr|withd)\b', ln, re.I):
                debit_amt = nums[0]
            elif re.search(r'\b(credit|deposit|cr)\b', ln, re.I):
                credit_amt = nums[0]
            else:
                debit_amt = nums[0]
        elif len(nums) == 2:
            debit_amt = nums[0] if re.search(r'\b(debit|withdrawal|dr)\b', ln, re.I) else None
            credit_amt = nums[0] if re.search(r'\b(credit|deposit|cr)\b', ln, re.I) else None
            if debit_amt is None and credit_amt is None:
                debit_amt = nums[0]
            balance_val = nums[1]
        else:
            balance_val = nums[-1]
            amt_candidate = nums[-2]
            if re.search(r'\b(debit|withdrawal|dr)\b', ln, re.I):
                debit_amt = amt_candidate
            elif re.search(r'\b(credit|deposit|cr)\b', ln, re.I):
                credit_amt = amt_candidate
            else:
                debit_amt = amt_candidate

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
            log(f"--- Page {p_idx} ---", meta)
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
