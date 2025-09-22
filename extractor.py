import pdfplumber
import pandas as pd
import re

# --- Clean Date ---
def clean_date(text: str) -> str:
    match = re.search(r"(\d{1,2})[/-](\d{1,2})[/-](\d{2,4})", str(text))
    if match:
        day, month, year = match.groups()
        if len(year) == 2:
            year = "20" + year  # Fix YY → YYYY
        return f"{int(day):02d}/{int(month):02d}/{year}"
    return str(text)

# --- Detect Head (Transaction Type) ---
def detect_head(particulars: str) -> str:
    particulars = particulars.upper()

    if any(word in particulars for word in ["ATM", "CASH", "CASA"]):
        return "CASH"
    elif any(word in particulars for word in ["UPI", "IMPS"]):
        return "WITHDRAWAL"
    elif any(word in particulars for word in ["INT", "INTEREST"]):
        return "INTEREST"
    elif any(word in particulars for word in ["CHRG", "CHARGE", "GST"]):
        return "CHARGE"
    elif any(word in particulars for word in ["TRANSFER", "TRF", "INTRA"]):
        return "TRANSFER"
    else:
        return "WITHDRAWAL"  # Default bucket

# --- Detect Sub Head (Names & Account Numbers) ---
def detect_sub_head(particulars: str) -> str:
    # Check for masked account numbers like Acc:xxxx0301 or XXXXXXXX9012
    acc_match = re.search(r"(Acc:\s*X{2,}\d{3,4}|X{6,}\d{2,4})", particulars, re.IGNORECASE)
    if acc_match:
        return acc_match.group(0).strip()

    # Check for proper names (2–4 capitalized words, like "Chetan C Gheewala")
    name_match = re.search(r"\b([A-Z][a-zA-Z]+(?:\s+[A-Z][a-zA-Z]+){1,3})\b", particulars)
    if name_match:
        return name_match.group(0).strip()

    return ""

# --- Extract from PDF ---
def process_file(file_path):
    rows = []

    with pdfplumber.open(file_path) as pdf:
        for page in pdf.pages:  # ✅ Process all pages
            table = page.extract_table()
            if not table:
                continue

            headers = [h.strip().upper() for h in table[0]]
            for row in table[1:]:
                row_dict = dict(zip(headers, row))

                date = clean_date(row_dict.get("DATE", ""))
                particulars = str(row_dict.get("PARTICULARS", "")).strip()
                debit = row_dict.get("DEBIT", "")
                credit = row_dict.get("CREDIT", "")
                balance = row_dict.get("BALANCE", "")

                head = detect_head(particulars)
                sub_head = detect_sub_head(particulars)

                rows.append({
                    "Date": date,
                    "Particulars": particulars,
                    "Debit": debit,
                    "Credit": credit,
                    "Balance": balance,
                    "Head": head,
                    "Sub Head": sub_head
                })

    df = pd.DataFrame(rows)
    return df
