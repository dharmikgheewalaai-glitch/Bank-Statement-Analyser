import re
from itertools import zip_longest
from config.layouts import FIELD_PRIORITY
from .head_rules import DEFAULT_RULES, classify

# ── IGNORE PATTERNS (headers / footers / non-transaction junk lines) ────────
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
_IGNORE_RE = [re.compile(p, re.I) for p in IGNORE_PATTERNS]

HEADER_KEYWORDS = [
    "date","description","details","narration","particulars","debit","credit",
    "withdrawal","deposit","balance","remarks","remark"
]


def is_ignore_line(text):
    t = (text or "").strip()
    if not t:
        return False
    return any(p.search(t) for p in _IGNORE_RE)


def normalize(h):
    return re.sub(r"\s+", " ", str(h or "").lower().strip())


def map_header(h):
    """h must already be normalize()d (lowercase). Priority order = which
    alias list wins when several columns could match the same field."""
    for field, aliases in FIELD_PRIORITY.items():
        if any(a in h for a in aliases):
            return field
    return None


def find_header_row(table):
    for i, row in enumerate(table):
        joined = " ".join(str(c or "") for c in row).lower()
        hits = sum(k in joined for k in HEADER_KEYWORDS)
        if hits >= 3:
            return i
    return 0


def parse_amount(raw):
    if raw is None:
        return None
    s = str(raw).strip()
    if not s:
        return None
    s = s.upper().replace("₹", "").replace("RS.", "").replace("INR", "")
    s = s.replace(",", "").replace(" ", "")
    s = re.sub(r"[^0-9.\-]", "", s)
    if not s or s in ("-", "."):
        return None
    try:
        return float(s)
    except ValueError:
        return None


def classify_head(particulars, rules=None):
    return classify(particulars, rules or DEFAULT_RULES)


def table_to_transactions(table, meta=None, page_no=None, rules=None):
    txns = []
    if not table or len(table) < 2:
        return txns

    header_idx = find_header_row(table)
    raw_headers = table[header_idx]

    std_headers = [
        map_header(normalize(h)) or normalize(h) or f"col{i}"
        for i, h in enumerate(raw_headers)
    ]

    for row in table[header_idx + 1:]:
        row = list(row or [])
        row = (row + [""] * len(raw_headers))[:len(raw_headers)]
        row_cells = [str(c or "").strip() for c in row]

        if not any(row_cells):
            continue

        joined = " ".join(row_cells)
        if is_ignore_line(joined):
            continue

        row_dict = {k: v for k, v in zip_longest(std_headers, row_cells, fillvalue="")}

        date = row_dict.get("date", "").strip() or None
        # Normalize internal whitespace to single spaces (not strip entirely —
        # collapsing all whitespace would jam narration words together)
        particulars = re.sub(r"\s+", " ", row_dict.get("particulars", "")).strip()
        debit_raw = row_dict.get("debit", "")
        credit_raw = row_dict.get("credit", "")
        balance_raw = row_dict.get("balance", "")

        debit_amt = parse_amount(debit_raw)
        credit_amt = parse_amount(credit_raw)
        balance_val = parse_amount(balance_raw)

        if not date or not particulars:
            continue
        if debit_amt is None and credit_amt is None:
            # Some banks use single "Amount" column + Dr/Cr flag
            amount_raw = row_dict.get("amount", "") or row_dict.get("amt", "")
            flag = joined.upper()
            amount_val = parse_amount(amount_raw)
            if amount_val is not None:
                if "CR" in flag or "CREDIT" in flag:
                    credit_amt = amount_val
                else:
                    debit_amt = amount_val
        if debit_amt is None and credit_amt is None:
            continue
        if is_ignore_line(particulars):
            continue

        txns.append({
            "Date": date,
            "Particulars": particulars,
            "Debit": debit_amt or 0.0,
            "Credit": credit_amt or 0.0,
            "Head": classify_head(particulars, rules),
            "Balance": balance_val or 0.0,
            "Page": page_no,
        })

    return txns
