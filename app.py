# app.py
import streamlit as st
import pandas as pd
from extractor import process_file   # import from extractor.py

st.title("📑 Bank Statement Extractor")

uploaded_file = st.file_uploader("Upload your Bank Statement (PDF)", type=["pdf"])

if uploaded_file is not None:
    # read file bytes
    file_bytes = uploaded_file.read()

    # process the PDF -> returns list of transactions
    transactions = process_file(file_bytes, uploaded_file.name)

    if transactions:
        df = pd.DataFrame(transactions)

        # Clean Date format (DD/MM/YYYY without quotes)
        def clean_date(text):
            if not text:
                return ""
            text = str(text).strip().replace("'", "")
            return text

        if "Date" in df.columns:
            df["Date"] = df["Date"].apply(clean_date)

        # Save CSV with same name as PDF
        csv_filename = uploaded_file.name.replace(".pdf", ".csv")
        st.download_button(
            label="⬇️ Download CSV",
            data=df.to_csv(index=False),
            file_name=csv_filename,
            mime="text/csv"
        )

        st.success(f"Extracted {len(df)} transactions ✅")
        st.dataframe(df)
    else:
        st.warning("⚠️ No transactions found in this file.")
