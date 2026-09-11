# extractor.py
import re
from io import BytesIO
from itertools import zip_longest
import pdfplumber
import pandas as pd

# ── IGNORE PATTERNS (headers / footers) ──────────────────────────────────────
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
    r"account no",
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
    r"transaction summary",
    r"opening balance",
    r"^\s*s\.?no\.?\s*$",
    r"^\s*sr\.?\s*no\.?\s*$",
]

HEADER_ALIASES = {
    "date":        ["date", "txn date", "transaction date", "post date", "tran date", "trans date"],
    "particulars": ["particulars", "description", "narration", "transaction particulars",
                    "details", "remarks", "remark", "transaction details", "narr"],
    "debit":       ["debit", "withdrawal", "dr", "withdrawal amt", "withdrawal amount",
                    "debit amount", "debits", "debit(dr)"],
    "credit":      ["credit", "deposit", "cr", "deposit amt", "deposit amount",
                    "credit amount", "credits", "credit(cr)"],
    "balance":     ["balance", "running balance", "closing balance", "bal", "avl bal",
                    "available bal", "net balance"],
    "amount":      ["amount", "amt"],
    "type":        ["type", "dr/cr", "cr/dr"],
}

DATE_RE   = re.compile(r'\b\d{1,2}[-/]\d{1,2}[-/]\d{2,4}\b')
AMOUNT_RE = re.compile(r'[-+]?\d{1,3}(?:[,\s]\d{3})*(?:\.\d+)?|\d+(?:\.\d+)?')


# ── HELPERS ───────────────────────────────────────────────────────────────────
def normalize(cell):
    return str(cell).strip().lower() if cell else ""


def map_header(h):
    h = normalize(h)
    # Value Date is a secondary date column — never let it win over
    # Transaction Date / Post Date / Date for the "date" field.
    if "value date" in h or "value dt" in h:
        return None
    # Cheque/instrument reference columns (e.g. "Cheque Details", "Chq./Ref.No.")
    # must never be mistaken for the narration column via the "details" alias.
    if "cheque" in h or "chq" in h or "instrument" in h:
        return None
    # Combo headers like "Amount(DR/CR)", "Balance(DR/CR)", "Type(DR/CR)"
    # contain both dr+cr tokens — they are amount/balance/type fields, not
    # a plain debit/credit column, so don't let the loose "dr"/"cr" aliases
    # grab them.
    has_combo = ("dr" in h) and ("cr" in h)
    for std, aliases in HEADER_ALIASES.items():
        if has_combo and std in ("debit", "credit"):
            continue
        for a in aliases:
            if a == h or h.startswith(a) or a in h:
                return std
    return None


def parse_amount(s):
    if s is None:
        return None
    s = str(s).strip().replace('\xa0', ' ').replace('INR', '').replace('Rs.', '').replace('Rs', '')
    s = re.sub(r'[^\d\-,.\s]', '', s).replace('', '').replace(',', '')
    if s in ('', '-'):
        return None
    try:
        return float(s)
    except ValueError:
        m = AMOUNT_RE.search(str(s))
        if m:
            try:
                return float(m.group(0).replace(',', '').replace(' ', ''))
            except ValueError:
                return None
        return None


def is_ignore_line(text):
    t = str(text or "")
    return any(re.search(p, t, re.IGNORECASE) for p in IGNORE_PATTERNS)


# ── HEAD CLASSIFICATION ───────────────────────────────────────────────────────
# No predefined rules. Heads come entirely from user-defined rules, each of
# form {"head": "SALARY", "keywords": ["SALARY", "PAYROLL"]}. First matching
# rule (in list order) wins. Unmatched particulars fall back to "OTHER".
def classify_head(particulars, rules=None):
    # Normalise (upper + strip spaces) on both sides — particulars coming
    # from table rows already have spaces stripped, but the text-fallback
    # path doesn't, so match space-insensitively either way.
    p = re.sub(r'\s+', '', str(particulars or "").upper())
    if rules:
        for rule in rules:
            head     = rule.get("head")
            keywords = rule.get("keywords") or []
            if not head:
                continue
            for kw in keywords:
                kw_norm = re.sub(r'\s+', '', str(kw or "").upper())
                if kw_norm and kw_norm in p:
                    return head
    return "OTHER"


# ── TABLE HEADER DETECTION ────────────────────────────────────────────────────
def find_header_row(table):
    """Return index of the row most likely to be the column header row."""
    best_idx, best_score = 0, -1
    for i, row in enumerate(table[:5]):
        score = 0
        for cell in row:
            if not cell:
                continue
            c = normalize(cell)
            for aliases in HEADER_ALIASES.values():
                for a in aliases:
                    if a in c:
                        score += 3
            if re.search(r'[a-zA-Z]', c):
                score += 1
        if score > best_score:
            best_idx, best_score = i, score
    return best_idx


# ── TABLE → TRANSACTIONS ──────────────────────────────────────────────────────
def table_to_transactions(table, meta, page_no=None, rules=None):
    txns = []
    if not table or len(table) < 2:
        return txns

    header_idx  = find_header_row(table)
    raw_headers = table[header_idx]

    std_headers = [
        map_header(normalize(h)) or normalize(h) or f"col{i}"
        for i, h in enumerate(raw_headers)
    ]

    for row in table[header_idx + 1:]:
        # Normalise row length
        row = list(row or [])
        row = (row + [""] * len(raw_headers))[:len(raw_headers)]
        row_cells = [str(c or "").strip() for c in row]

        if not any(row_cells):
            continue

        joined = " ".join(row_cells)
        if is_ignore_line(joined):
            continue

        row_dict = {k: v for k, v in zip_longest(std_headers, row_cells, fillvalue="")}

        date        = row_dict.get("date", "").strip() or None
        particulars = re.sub(r'\s+', '', row_dict.get("particulars", "")).strip()
        debit_raw   = row_dict.get("debit", "")
        credit_raw  = row_dict.get("credit", "")
        balance_raw = row_dict.get("balance", "")

        debit_amt   = parse_amount(debit_raw)
        credit_amt  = parse_amount(credit_raw)
        balance_val = parse_amount(balance_raw)

        # Single "Amount(DR/CR)" column banks (flag lives in a separate
        # "Type" column, or suffixed on the amount cell itself, e.g. "500 DR")
        if debit_amt is None and credit_amt is None:
            amount_raw = row_dict.get("amount", "")
            amount_val = parse_amount(amount_raw)
            if amount_val is not None:
                flag_source = row_dict.get("type", "") or amount_raw or joined
                flag = str(flag_source).upper()
                if "DR" in flag and "CR" not in flag:
                    debit_amt = amount_val
                elif "CR" in flag:
                    credit_amt = amount_val
                else:
                    flag2 = joined.upper()
                    if "CR" in flag2 or "CREDIT" in flag2:
                        credit_amt = amount_val
                    else:
                        debit_amt = amount_val

        # Skip rows missing date/particulars or both amounts
        if not date or not particulars:
            continue
        if debit_amt is None and credit_amt is None:
            continue
        if is_ignore_line(particulars):
            continue

        txns.append({
            "Date":        date,
            "Particulars": particulars,
            "Debit":       debit_amt,
            "Credit":      credit_amt,
            "Head":        classify_head(particulars, rules),
            "Balance":     balance_val,
            "Page":        page_no,
        })

    return txns


# ── TEXT FALLBACK ─────────────────────────────────────────────────────────────
def text_fallback_extract(page_text, meta, page_no=None, rules=None):
    txns = []
    lines = [ln.strip() for ln in page_text.splitlines() if ln.strip()]

    for ln in lines:
        if is_ignore_line(ln):
            continue
        dm = DATE_RE.search(ln)
        if not dm:
            continue

        nums = [parse_amount(x) for x in AMOUNT_RE.findall(ln)]
        nums = [n for n in nums if n is not None]
        if not nums:
            continue

        date        = dm.group(0)
        debit_amt   = None
        credit_amt  = None
        balance_val = None

        # Heuristic: last number is usually balance
        if len(nums) == 1:
            debit_amt   = nums[0]
        elif len(nums) == 2:
            debit_amt   = nums[0]
            balance_val = nums[1]
        elif len(nums) >= 3:
            # Could be debit + credit + balance; one of debit/credit usually 0 or absent
            debit_amt   = nums[0] if nums[0] else None
            credit_amt  = nums[1] if nums[1] else None
            balance_val = nums[-1]

        txns.append({
            "Date":        date,
            "Particulars": ln,
            "Debit":       debit_amt,
            "Credit":      credit_amt,
            "Head":        classify_head(ln, rules),
            "Balance":     balance_val,
            "Page":        page_no,
        })

    return txns


# ── TABULAR (EXCEL / CSV) → TRANSACTIONS ──────────────────────────────────────
def _rows_from_dataframe(df):
    """Turn a raw (header-less) DataFrame into list-of-lists, like a pdfplumber table."""
    rows = df.fillna("").astype(str).values.tolist()
    return rows


def tabular_to_transactions(file_bytes, filename, meta, rules=None):
    """Handle .xlsx / .xls / .csv uploads by re-using the same header-mapping and
    row-parsing logic as the PDF table pipeline."""
    txns = []
    ext = filename.rsplit(".", 1)[-1].lower()

    try:
        if ext == "csv":
            raw = pd.read_csv(BytesIO(file_bytes), header=None, dtype=str, keep_default_na=False)
            sheets = {"Sheet1": raw}
        else:
            xls = pd.ExcelFile(BytesIO(file_bytes))
            sheets = {
                name: pd.read_excel(xls, sheet_name=name, header=None, dtype=str)
                for name in xls.sheet_names
            }
    except Exception as e:
        meta["_logs"].append(f"Tabular read error: {e}")
        return txns

    for sheet_name, raw_df in sheets.items():
        raw_df = raw_df.where(raw_df.notna(), "")
        table = _rows_from_dataframe(raw_df)
        if not table or len(table) < 2:
            continue
        try:
            txns.extend(table_to_transactions(table, meta, page_no=sheet_name, rules=rules))
        except Exception as e:
            meta["_logs"].append(f"Sheet '{sheet_name}' error: {e}")
            continue

    return txns


# ── MAIN API ──────────────────────────────────────────────────────────────────
def process_file(file_bytes, filename, rules=None):
    meta         = {"filename": filename, "_logs": []}
    transactions = []

    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""

    if ext in ("xlsx", "xls", "csv"):
        transactions = tabular_to_transactions(file_bytes, filename, meta, rules=rules)

    elif ext == "pdf" or ext == "":
        try:
            pdf = pdfplumber.open(BytesIO(file_bytes))
        except Exception as e:
            meta["_logs"].append(f"PDF open error: {e}")
            return meta, transactions

        with pdf:
            for idx, page in enumerate(pdf.pages, start=1):
                try:
                    tables    = page.extract_tables() or []
                    page_txns = []

                    for table in tables:
                        page_txns.extend(table_to_transactions(table, meta, page_no=idx, rules=rules))

                    # Fallback to raw text if table extraction gave nothing
                    if not page_txns:
                        text = page.extract_text() or ""
                        if text.strip():
                            page_txns.extend(text_fallback_extract(text, meta, page_no=idx, rules=rules))

                    transactions.extend(page_txns)

                except Exception as e:
                    meta["_logs"].append(f"Page {idx} error: {e}")
                    continue
    else:
        meta["_logs"].append(f"Unsupported file type: .{ext}")
        return meta, transactions

    # Deduplicate
    seen, result = set(), []
    for r in transactions:
        key = (r["Date"], r["Particulars"], r["Debit"], r["Credit"], r["Page"])
        if key not in seen:
            seen.add(key)
            result.append(r)

    return meta, result
