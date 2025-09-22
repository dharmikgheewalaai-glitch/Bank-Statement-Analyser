import re
from io import BytesIO
from itertools import zip_longest
import pdfplumber
from collections import Counter

# ----------------- CONFIG -----------------
HEAD_RULES = {
    "CASH": ["ATM", "CASH", "CSH", "CASA"],
    "Withdrawal": ["UPI", "IMPS", "NEFT", "RTGS", "WITHDRAWAL", "DEBIT", "PAYMENT"],
    "Interest": ["INT", "INTEREST", "CR INT"],
    "Charge": ["CHRG", "CHARGE", "FEE", "GST", "PENALTY"],
    "Salary": ["SALARY", "PAYROLL"],
    "Refund": ["REFUND", "REVERSAL"],
    
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
ACCOUNT_RE = re.compile(r"\b\d{6,16}\b")  # account numbers (6–16 digits)
NAME_RE = re.compile(r"(?:TO|FROM|BY|IN FAVOUR OF|FAVOUR)\s+([A-Z ]{3,})")

# ----------------- HELPERS -----------------
def parse_amount(s):
    if s is None:
        return None
    s = str(s).strip().replace('\xa0', ' ')
    s = re.sub(r'[^\d\-,.\s]', '', s)  # remove currency symbols
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
def table_to_transactions(table, page_no=None):
    txns = []
    if not table or len(table) < 2:
        return txns

    header_idx = find_header_row(table)
    headers = table[header_idx]

    std_headers = []
    for h in headers:
        h = (h or "").strip().lower()
        mapped = None
        for std, aliases in HEADER_ALIASES.items():
            for a in aliases:
                if h.startswith(a) or a in h:
                    mapped = std
                    break
            if mapped:
                break
        std_headers.append(mapped or h)

    for row in table[header_idx + 1:]:
        row_cells = [c or "" for c in row]
        if all((not str(x).strip()) for x in row_cells):
            continue

        row_dict = {}
        for k, v in zip_longest(std_headers, row_cells, fillvalue=""):
            row_dict[k or "col"] = (v or "").strip()

        date = row_dict.get("date")
        particulars = row_dict.get("particulars")

        if not particulars:
            text_cells = [str(c).strip() for c in row_cells if re.search(r'[A-Za-z]', str(c) or '')]
            particulars = max(text_cells, key=len) if text_cells else ""

        debit_amt = parse_amount(row_dict.get("debit"))
        credit_amt = parse_amount(row_dict.get("credit"))
        balance_val = row_dict.get("balance") or None

        if not (date and particulars and (debit_amt is not None or credit_amt is not None)):
            continue

        head = classify_head(particulars)

        txns.append({
            "Date": str(date).strip(),
            "Particulars": particulars.strip(),  # ✅ Keep exactly as uploaded
            "Debit": debit_amt,
            "Credit": credit_amt,
            "Head": head,
            "SubHead": "",  # will fill later
            "Balance": balance_val,
            "Page": page_no
        })
    return txns

# ----------------- MAIN API -----------------
def process_file(file_bytes, filename):
    transactions = []
    try:
        pdf = pdfplumber.open(BytesIO(file_bytes))
    except Exception as e:
        return {"error": f"ERROR opening PDF: {e}"}, []

    with pdf:
        for p_idx, page in enumerate(pdf.pages, start=1):
            tables = page.extract_tables()
            page_txns = []
            for t_idx, table in enumerate(tables, start=1):
                if not table or len(table) < 2:
                    continue
                tt = table_to_transactions(table, page_no=p_idx)
                page_txns.extend(tt)

            if not page_txns:
                text = page.extract_text() or ""
                # (text fallback can be added if needed)
            transactions.extend(page_txns)

    # ✅ Find repeating account numbers / names for SubHead
    subhead_candidates = []
    for t in transactions:
        p = t["Particulars"].upper()
        acc_match = ACCOUNT_RE.search(p)
        if acc_match:
            subhead_candidates.append(acc_match.group(0))
        else:
            name_match = NAME_RE.search(p)
            if name_match:
                subhead_candidates.append(name_match.group(1).strip())

    counts = Counter(subhead_candidates)
    common_subheads = {x for x, c in counts.items() if c > 1}  # repeated ones only

    for t in transactions:
        p = t["Particulars"].upper()
        sub = ""
        acc_match = ACCOUNT_RE.search(p)
        if acc_match and acc_match.group(0) in common_subheads:
            sub = acc_match.group(0)
        else:
            name_match = NAME_RE.search(p)
            if name_match and name_match.group(1).strip() in common_subheads:
                sub = name_match.group(1).title()
        t["SubHead"] = sub

    # ✅ Deduplicate
    seen = set()
    deduped = []
    for r in transactions:
        key = (r.get("Date"), r.get("Particulars"), r.get("Debit"), r.get("Credit"))
        if key in seen:
            continue
        seen.add(key)
        deduped.append(r)

    return {"count": len(deduped)}, deduped
