import streamlit as st
import pandas as pd
import os
from extractor import process_file

st.set_page_config(page_title="Bank Statement Analyser", layout="wide")

st.title("🏦 Bank Statement Analyser")

uploaded_file = st.file_uploader("Upload your bank statement (PDF)", type=["pdf"])

if uploaded_file:
    file_bytes = uploaded_file.read()
    filename = uploaded_file.name

    with st.spinner("Processing your bank statement..."):
        meta, transactions = process_file(file_bytes, filename)

    if not transactions:
        st.error("No transactions found. Please check if the PDF is a valid bank statement.")
    else:
        df = pd.DataFrame(transactions)

        # Clean date column (remove quotes, format DD/MM/YYYY)
        if "Date" in df.columns:
            df["Date"] = df["Date"].astype(str).str.strip("'").str.strip()

        # Save with same name as uploaded file
        out_name = os.path.splitext(filename)[0] + ".csv"
        df.to_csv(out_name, index=False)

        st.success(f"✅ Processed {len(df)} transactions")
        st.download_button("📥 Download Extracted CSV", data=df.to_csv(index=False).encode("utf-8"),
                           file_name=out_name, mime="text/csv")

        st.dataframe(df, use_container_width=True)

        with st.expander("🔍 Debug Info"):
            st.write(meta["_logs"])
