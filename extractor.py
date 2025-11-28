import re
from io import BytesIO
from itertools import zip_longest
import pdfplumber

# Keywords for grouping
HEAD_RULES = {
    "CASH": ["ATM WDL", "CASH", "CASH WDL", "CSH", "SELF"],
    "SALARY": ["SALARY", "PAYROLL"],
    "WITHDRAWAL": ["ATM ISSUER REV", "UPI", "UPI REV"],
}

# Header name aliases
HEADER_ALIASES = {
    "date": ["date", "txn date", "transaction date", "value date", "tran date"],
    "particulars": ["particulars", "description", "narration", "transaction particulars", "details", "remarks"],
    "debit": ["debit", "withdrawal", "dr", "withdrawal amt", "withdrawal amount", "debit amount"],
    "credit": ["credit", "deposit", "cr", "deposit amt", "deposit amount", "credit amount"],
    "balance": ["balance", "running balance", "closing balance", "bal"],
}

# Lines to skip
IGNORE_LINES = ["PRINTED ON", "PAGE"]

DATE_RE = re.compile(r"\b\d{1,2}[-/]\d{1,2}[-/]\d{2,4}\b")
AMOUNT_RE = re.compile(r"[-+]?\d{1,3}(?:[, ]\d{3})*(?:\.\d+)?|\d+(?:\.\d+)?")

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
    s = str(s).strip().replace("\xa0", " ")
    s = re.sub(r"[^\d\-,.\s]", "", s)
    s = s.replace(" ", "").replace(",", "")
    if s == "":
        return None
    try:
        return float(s)
    except:
        m = AMOUNT_RE.search(str(s))
        return float(m.group(0)) if m else None

def classify_head(particulars):
    p = (particulars or "").upper()

    if any(kw in p for kw in ["BAJAJ FINANCE", "BAJAJFIN"]): return "BAJAJ FINANCE LTD"
    if any(kw in p for kw in ["CGST", "CHARGES", "GST"]): return "CHARGES"
    if "PETROL" in p: return "CONVEYANCE"
    if "DIVIDEND" in p: return "DIVIDEND"
    if "ICICI" in p: return "ICICI DIRECT"
    if "IDFC" in p: return "IDFC FIRST BANK LTD"
    if "INSURANCE" in p: return "INSURANCE"
    if "INTEREST" in p: return "INTEREST"
    if "LIC" in p: return "LIC"
    if "TAX REFUND" in p: return "TAX REFUND"

    for head, kws in HEAD_RULES.items():
        if any(kw in p for kw in kws):
            return head

    return "OTHER"

def merge_multiline_rows(table, header_idx):
    merged, buffer = [], None

    for row in table[header_idx + 1:]:
        first_cell = (row[0] or "").strip()

        # New row detected
        if first_cell and DATE_RE.search(first_cell):
            if buffer:
                merged.append(buffer)
            buffer = row
        else:
            # Merge into previous row EXACTLY without altering text
            if buffer:
                buffer = [
                    (buffer[i] + " " + row[i]).strip()
                    if row[i] else buffer[i]
                    for i in range(len(row))
                ]

    if buffer:
        merged.append(buffer)

    return merged

def find_header_row(table):
    best_idx, best_score = 0, -1
    for i, row in enumerate(table[:4]):
        score = 0
        for cell in row:
            if not cell: continue
            c = str(cell).strip().lower()
            if any(a in c for aliases in HEADER_ALIASES.values() for a in aliases):
                score += 3
        if score > best_score:
            best_idx, best_score = i, score
    return best_idx

def table_to_transactions(table, meta, page_no=None):
    if not table or len(table) < 2:
        return []

    header_idx = find_header_row(table)
    headers = table[header_idx]

    std_headers = [
        map_header_to_std(normalize_header_cell(h)) or normalize_header_cell(h)
        for h in headers
    ]

    merged_rows = merge_multiline_rows(table, header_idx)

    txns = []
    for row in merged_rows:
        row_cells = [c or "" for c in row]

        # Keep original text EXACTLY
        full_text_raw = " ".join(row_cells).strip()

        if any(skip in full_text_raw.upper() for skip in IGNORE_LINES):
            continue

        row_dict = {
            k or "col": (v or "").strip()
            for k, v in zip_longest(std_headers, row_cells, fillvalue="")
        }

        date = row_dict.get("date")
        particulars_raw = row_dict.get("particulars")

        particulars = particulars_raw if particulars_raw else full_text_raw  # EXACT

        debit = parse_amount(row_dict.get("debit"))
        credit = parse_amount(row_dict.get("credit"))
        balance = parse_amount(row_dict.get("balance"))

        if not (date and particulars and (debit is not None or credit is not None)):
            continue

        txns.append({
            "Date": date,
            "Particulars": particulars,  # EXACT FROM PDF
            "Debit": debit,
            "Credit": credit,
            "Head": classify_head(particulars),
            "Balance": balance,
            "Page": page_no,
        })

    return txns

def text_fallback_extract(text, meta, page_no=None):
    txns = []
    for line in text.splitlines():
        line = line.strip()
        if not line or any(skip in line.upper() for skip in IGNORE_LINES):
            continue
        if not DATE_RE.search(line):
            continue

        amounts = [
            parse_amount(a)
            for a in AMOUNT_RE.findall(line)
            if parse_amount(a) is not None
        ]
        if not amounts:
            continue

        date = DATE_RE.search(line).group(0)
        debit = amounts[-2] if len(amounts) >= 2 else amounts[0]
        balance = amounts[-1] if len(amounts) >= 2 else None

        txns.append({
            "Date": date,
            "Particulars": line,  # EXACT PDF TEXT
            "Debit": debit,
            "Credit": None,
            "Head": classify_head(line),
            "Balance": balance,
            "Page": page_no,
        })
    return txns

def process_file(file_bytes, filename):
    meta = {"_logs": []}
    txns = []

    try:
        pdf = pdfplumber.open(BytesIO(file_bytes))
    except:
        return meta, txns

    with pdf:
        for i, page in enumerate(pdf.pages, start=1):
            try:
                tables = page.extract_tables() or []
                page_txns = []

                for table in tables:
                    page_txns.extend(table_to_transactions(table, meta, i))

                if not page_txns:
                    page_txns = text_fallback_extract(
                        page.extract_text() or "",
                        meta,
                        i,
                    )

                txns.extend(page_txns)

            except Exception as e:
                meta["_logs"].append(str(e))

    return meta, txns
