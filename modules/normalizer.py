import re
import pandas as pd
from config.layouts import ALIASES, FIELD_PRIORITY

def money(value):
    if pd.isna(value): return 0.0
    s = str(value).upper().replace("₹","").replace("RS.","").replace("INR","")
    s = s.replace(",","").replace(" ","")
    s = re.sub(r"[^0-9.\-]", "", s)
    try: return float(s) if s else 0.0
    except ValueError: return 0.0

def find_col(columns, aliases, priority=None):
    """Alias order (priority list, if given) decides the winner when several
    columns could match the same field — not table column order. e.g. when
    both 'Transaction Date' and 'Value Date' exist, 'transaction date' being
    earlier in the priority list wins, regardless of which column comes first
    in the table."""
    order = priority if priority else aliases
    norm_cols = [(col, re.sub(r"\s+"," ",str(col).lower().strip())) for col in columns]
    for a in order:
        for col, c in norm_cols:
            if a in c:
                return col
    return None

def normalize_debug(df):
    cols = list(df.columns)
    date_col = find_col(cols, ALIASES["date"], FIELD_PRIORITY["date"])
    part_col = find_col(cols, ALIASES["particulars"], FIELD_PRIORITY["particulars"])
    debit_col = find_col(cols, ALIASES["debit"], FIELD_PRIORITY["debit"])
    credit_col = find_col(cols, ALIASES["credit"], FIELD_PRIORITY["credit"])
    balance_col = find_col(cols, ALIASES["balance"], FIELD_PRIORITY["balance"])

    out = pd.DataFrame()
    out["Date"] = df[date_col] if date_col else ""
    out["Particulars"] = df[part_col] if part_col else ""
    out["Debit"] = df[debit_col].map(money) if debit_col else 0.0
    out["Credit"] = df[credit_col].map(money) if credit_col else 0.0
    out["Balance"] = df[balance_col].map(money) if balance_col else 0.0

    if debit_col is None and credit_col is None:
        amount_col = find_col(cols, ALIASES["amount_drcr"])
        if amount_col:
            raw = df[amount_col].astype(str)
            out["Debit"] = raw.map(lambda x: money(x) if "DR" in x.upper() else 0.0)
            out["Credit"] = raw.map(lambda x: money(x) if "CR" in x.upper() else 0.0)

    raw_dates = out["Date"].head(5).tolist()
    parsed = pd.to_datetime(out["Date"], errors="coerce", dayfirst=True)
    debug = {
        "raw_columns": cols,
        "matched": {"date":date_col,"particulars":part_col,"debit":debit_col,
                    "credit":credit_col,"balance":balance_col},
        "raw_rows": len(out),
        "date_parse_fail": int(parsed.isna().sum()),
        "sample_raw_dates": raw_dates,
    }
    out["Date"] = parsed
    out = out.dropna(subset=["Date"]).reset_index(drop=True)
    return out, debug

def normalize(df):
    out, _ = normalize_debug(df)
    return out
