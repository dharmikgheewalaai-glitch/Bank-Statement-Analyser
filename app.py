# app.py
import streamlit as st
import pandas as pd
import re
from extractor import process_file

st.title("📄 Bank Statement Extractor")

uploaded_file = st.file_uploader("Upload Bank Statement (PDF)", type=["pdf"])

def clean_date(value):
    """Extract date, remove prefix/suffix, normalize to DD/MM/YYYY"""
    if not value:
        return None
    text = str(value).strip().replace("'", "").replace('"', "")

    # ✅ Fix: regex supports /, -, or . as separators
    match = re.search(r"(\d{1,2})[\/\-.](\d{1,2})[\/\-.](\d{2,4})", text)
    if match:
        day, month, year = match.groups()
        if len(year) == 2:  # handle yy format like 24 → 2024
            year = "20" + year
        return f"{int(day):02d}/{int(month):02d}/{year}"
    return None

if uploaded_file is not None:
    st.info(f"Processing: {uploaded_file.name} ...")

    # Read file
    file_bytes = uploaded_file.read()

    # Call extractor
    meta, transactions = process_file(file_bytes, uploaded_file.name)

    if not transactions:
        st.error("⚠️ No transactions found. Try with another PDF or check if it's a scanned copy.")
    else:
        # Convert to DataFrame
        df = pd.DataFrame(transactions)

        # ✅ Clean Date column
        if "Date" in df.columns:
            df["Date"] = df["Date"].apply(clean_date)

        st.success("✅ Transactions Extracted Successfully!")
        
        # Show metadata
        with st.expander("📌 Account Details"):
            st.json(meta)

        # Show DataFrame
        st.dataframe(df, use_container_width=True)

        # ✅ Save with same filename (but .csv)
        csv_filename = uploaded_file.name.replace(".pdf", ".csv").replace(".PDF", ".csv")

        # Allow CSV download
        csv = df.to_csv(index=False).encode("utf-8")
        st.download_button(
            label=f"⬇️ Download Extracted Transactions ({csv_filename})",
            data=csv,
            file_name=csv_filename,
            mime="text/csv"
        )
