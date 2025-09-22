# app.py
import streamlit as st
import pandas as pd
from extractor import process_file   # ✅ Only app.py imports extractor.py

st.set_page_config(page_title="Bank Statement Analyser", layout="wide")
st.title("📑 Bank Statement Analyser")

uploaded_file = st.file_uploader("Upload your Bank Statement (PDF)", type=["pdf"])

if uploaded_file:
    file_bytes = uploaded_file.read()
    filename = uploaded_file.name

    with st.spinner("⏳ Processing file..."):
        meta, transactions = process_file(file_bytes, filename)

    if not transactions:
        st.error("⚠️ No transactions found in this PDF.")
    else:
        df = pd.DataFrame(transactions)

        if "Date" in df.columns:
            df["Date"] = df["Date"].astype(str).str.replace("'", "").str.strip()

        st.success(f"✅ Extracted {len(df)} transactions from {filename}")
        st.dataframe(df, use_container_width=True)

        excel_name = filename.replace(".pdf", ".xlsx")
        df.to_excel(excel_name, index=False)

        with open(excel_name, "rb") as f:
            st.download_button(
                label="📥 Download Excel",
                data=f,
                file_name=excel_name,
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )

    with st.expander("🔍 Processing Logs"):
        for log in meta.get("_logs", []):
            st.text(log)
