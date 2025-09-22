# extractor.py
import re
from io import BytesIO
from itertools import zip_longest
import pdfplumber

# ✅ DO NOT import app.py or extractor again here

# ----------------- CONFIG -----------------
HEAD_RULES = {
    "CASH": ["ATM", "CASH", "CSH", "CASA"],
    "Withdrawal": ["UPI", "IMPS", "NEFT", "RTGS", "WITHDRAWAL", "DEBIT", "PAYMENT"],
    "Interest": ["INT", "INTEREST", "CR INT"],
    "Charge": ["CHRG", "CHARGE", "FEE", "GST", "PENALTY"],
    "Salary": ["SALARY", "PAYROLL"],
    "Refund": ["REFUND", "REVERSAL"],
    "LIC": ["LIC"],
    "ICICI SECURITIES": ["ICICISEC", "ICICI SECURITIES"],
}
# ... (rest of extractor.py same as I gave you earlier, unchanged)
