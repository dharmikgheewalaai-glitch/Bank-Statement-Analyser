import pandas as pd

def validate_table(df):
    if df is None or df.empty:
        return {"ok":False,"score":0,"reasons":["empty table"]}
    score, reasons = 0, []
    text = " ".join(map(str, df.columns)).lower()
    if any(k in text for k in ["date","value"]): score += 20
    else: reasons.append("date column missing")
    if any(k in text for k in ["description","details","narration","particular","remark"]): score += 20
    else: reasons.append("particulars column missing")
    amount = [c for c in df.columns if any(k in str(c).lower()
             for k in ["debit","credit","withdraw","deposit","amount","balance"])]
    if len(amount) >= 2: score += 25
    else: reasons.append("amount columns missing")
    if len(df) >= 2: score += 15
    else: reasons.append("too few rows")
    if df.notna().mean().mean() >= .55: score += 10
    else: reasons.append("too many empty cells")
    if len(df.columns) <= 12: score += 10
    return {"ok":score >= 65,"score":score,"reasons":reasons}
