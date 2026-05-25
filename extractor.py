# extractor.py
import re
from io import BytesIO
from itertools import zip_longest
import pdfplumber

# ------------- IGNORE PATTERNS -------------
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
    r"closing balance",
    r"transaction summary",
    r"^\s*date\s+particulars",
    r"^\s*sr\.?\s*no",
]

HEAD_RULES = {
    "CASH":       ["ATM WDL", "CASH WDL", "CASH", "CSH", "SELF"],
    "SALARY":     ["SALARY", "PAYROLL"],
    "WITHDRAWAL": ["ATM ISSUER REV", "UPI", "UPI REV", "POS"],
}

HEADER_ALIASES = {
    "date":        ["date", "txn date", "transaction date", "value date", "tran date"],
    "particulars": ["particulars", "description", "narration", "transaction particulars", "details", "remarks"],
    "debit":       ["debit", "withdrawal", "dr", "withdrawal amt", "withdrawal amount", "debit amount"],
    "credit":      ["credit", "deposit", "cr", "deposit amt", "deposit amount", "credit amount"],
    "balance":     ["balance", "running balance", "bal"],
}

DATE_RE   = re.compile(r'\b\d{1,2}[-/]\d{1,2}[-/]\d{2,4}\b')
AMOUNT_RE = re.compile(r'[-+]?\d{1,3}(?:[,\s]\d{3})*(?:\.\d+)?|\d+(?:\.\d+)?')


# ------------- HELPERS -------------
def normalize(cell):
    return str(cell).strip().lower() if cell else ""


def map_header(h):
    h = (h or "").strip().lower()
    for std, aliases in HEADER_ALIASES.items():
        for a in aliases:
            if h == a or h.startswith(a) or a in h:
                return std
    return None


def parse_amount(s):
    if s is None:
        return None
    s = str(s).strip().replace('\xa0', ' ')
    s = re.sub(r'[^\d\-,.\s]', '', s).replace(' ', '').replace(',', '')
    if not s:
        return None
    try:
        return float(s)
    except ValueError:
        m = AMOUNT_RE.search(str(s))
        if m:
            try:
                return float(m.group(0).replace(',', '').replace(' ', ''))
            except ValueError:
                pass
    return None


def is_ignore_row(row):
    text = " ".join(str(x) for x in row if x)
    return any(re.search(p, text, re.IGNORECASE) for p in IGNORE_PATTERNS)


# ------------- HEAD CLASSIFICATION -------------
def classify_head(particulars):
    p = str(particulars or "").upper()
    checks = [
        (["BAJAJ FINANCE LIMITE", "BAJAJ FINANCE LTD", "BAJAJFIN"],    "BAJAJ FINANCE LTD"),
        (["CGST", "CHARGES", "CHGS", "CHRG", "SGST", "GST"],           "CHARGES"),
        (["PETROL", "PETROLEUM"],                                        "CONVEYANCE"),
        (["DIVIDEND"],                                                   "DIVIDEND"),
        (["ICICI SECURITIES LTD", "ICICISEC.UPI", "ICICISECURITIES"],   "ICICI DIRECT"),
        (["IDFC FIRST BANK", "IDFCFBLIMITED"],                          "IDFC FIRST BANK LTD"),
        (["BAJAJ ALLIANZ GEN INS"],                                      "INSURANCE"),
        (["INT PD", "INT CR", "INTEREST"],                               "INTEREST"),
        (["LIC OF INDIA", "LIFE INSURANCE CORPORATIO"],                  "LIC"),
        (["TAX REFUND"],                                                  "TAX REFUND"),
        (["EMI", "LOAN"],                                                 "LOAN EMI"),
        (["RENT"],                                                        "RENT"),
        (["SCHOOL", "COLLEGE", "TUITION", "FEES"],                       "EDUCATION"),
        (["HOSPITAL", "MEDICAL", "PHARMA", "CLINIC"],                    "MEDICAL"),
        (["AMAZON", "FLIPKART", "MYNTRA", "MEESHO", "SWIGGY", "ZOMATO",
          "BLINKIT", "BIGBASKET"],                                        "ONLINE SHOPPING"),
        (["NEFT", "RTGS", "IMPS"],                                       "TRANSFER"),
    ]
    for kws, head in checks:
        if any(kw in p for kw in kws):
            return head
    for head, kws in HEAD_RULES.items():
        for kw in kws:
            if kw in p:
                return head
    return "OTHER"


# ------------- TABLE EXTRACTION -------------
def find_header_row(table):
    best_idx, best_score = 0, -1
    for i, row in enumerate(table[:5]):
        score = sum(
            3 for cell in row
            if cell and any(
                a in str(cell).strip().lower()
                for aliases in HEADER_ALIASES.values()
                for a in aliases
            )
        )
        if score > best_score:
            best_idx, best_score = i, score
    return best_idx


def table_to_transactions(table, page_no=None):
    txns = []
    if not table or len(table) < 2:
        return txns

    header_idx = find_header_row(table)
    raw_headers = table[header_idx]
    std_headers = [map_header(normalize(h)) or normalize(h) for h in raw_headers]

    for row in table[header_idx + 1:]:
        if is_ignore_row(row):
            continue

        # Pad / trim row to header length
        row = list(row) + [""] * max(0, len(std_headers) - len(row))
        row = row[:len(std_headers)]
        row = [str(c).strip() if c else "" for c in row]

        if not any(row):
            continue

        rd = {}
        for k, v in zip_longest(std_headers, row, fillvalue=""):
            rd[k or "col"] = v

        date        = rd.get("date", "").strip() or None
        particulars = rd.get("particulars", "").strip()
        debit       = parse_amount(rd.get("debit", ""))
        credit      = parse_amount(rd.get("credit", ""))
        balance     = parse_amount(rd.get("balance", ""))

        if not date or not particulars:
            continue
        if not DATE_RE.search(date):
            continue
        if debit is None and credit is None:
            continue
        if is_ignore_row([particulars]):
            continue

        txns.append({
            "Date":        date,
            "Particulars": particulars,
            "Debit":       debit,
            "Credit":      credit,
            "Head":        classify_head(particulars),
            "Balance":     balance,
            "Page":        page_no,
        })

    return txns


# ------------- TEXT FALLBACK -------------
def text_fallback_extract(page_text, page_no=None):
    txns = []
    for ln in (l.strip() for l in page_text.splitlines() if l.strip()):
        if is_ignore_row([ln]):
            continue
        m = DATE_RE.search(ln)
        if not m:
            continue
        nums = [parse_amount(x) for x in AMOUNT_RE.findall(ln)]
        nums = [n for n in nums if n is not None]
        if not nums:
            continue

        date = m.group(0)
        debit = credit = balance = None
        if len(nums) == 1:
            debit = nums[0]
        elif len(nums) == 2:
            debit, balance = nums
        else:
            debit, credit, balance = nums[0], nums[1], nums[-1]

        txns.append({
            "Date":        date,
            "Particulars": ln,
            "Debit":       debit,
            "Credit":      credit,
            "Head":        classify_head(ln),
            "Balance":     balance,
            "Page":        page_no,
        })
    return txns


# ------------- MAIN API -------------
def process_file(file_bytes, filename):
    meta, transactions = {"_logs": []}, []

    try:
        pdf = pdfplumber.open(BytesIO(file_bytes))
    except Exception as e:
        meta["_logs"].append(f"PDF open error: {e}")
        return meta, transactions

    with pdf:
        for idx, page in enumerate(pdf.pages, start=1):
            try:
                page_txns = []
                for table in (page.extract_tables() or []):
                    page_txns.extend(table_to_transactions(table, page_no=idx))

                if not page_txns:
                    text = page.extract_text() or ""
                    page_txns.extend(text_fallback_extract(text, page_no=idx))

                transactions.extend(page_txns)
            except Exception as e:
                meta["_logs"].append(f"Page {idx} error: {e}")

    # Deduplicate
    seen, result = set(), []
    for r in transactions:
        key = (r["Date"], r["Particulars"], r["Debit"], r["Credit"], r["Page"])
        if key not in seen:
            seen.add(key)
            result.append(r)

    return meta, result
