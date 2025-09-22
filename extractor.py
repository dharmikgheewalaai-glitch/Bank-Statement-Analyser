import pdfplumber
import re
from io import BytesIO

# ----------------- HELPERS -----------------
def clean_date(text: str) -> str:
    match = re.search(r"(\d{1,2})[/-](\d{1,2})[/-](\d{2,4})", str(text))
    if match:
        day, month, year = match.groups()
        if len(year) == 2:
            year = "20" + year
        return f"{int(day):02d}/{int(month):02d}/{year}"
    return str(text)

def detect_head(particulars: str) -> str:
    particulars = particulars.upper()
    if any(word in particulars for word in ["ATM", "CASH", "CASA"]):
        return "CASH"
    elif any(word in particulars for word in ["UPI", "IMPS", "NEFT", "RTGS", "TRANSFER", "TRF", "INTRA"]):
        return "TRANSFER"
    elif any(word in particulars for word in ["INT", "INTEREST"]):
        return "INTEREST"
    elif any(word in particulars for word in ["CHRG", "CHARGE", "FEE", "GST", "PENALTY"]):
        return "CHARGE"
    elif any(word in particulars for word in ["SALARY", "PAYROLL"]):
        return "SALARY"
    elif any(word in particulars for word in ["REFUND", "REVERSAL"]):
        return "REFUND"
    elif any(word in particulars for word in ["LIC"]):
        return "LIC"
    elif any(word in particulars for word in ["ICICI SECURITIES", "ICICISEC"]):
        return "ICICI SECURITIES"
    else:
        return "OTHER"

def detect_sub_head(particulars: str) -> str:
    # Account numbers like XXXXXXX
