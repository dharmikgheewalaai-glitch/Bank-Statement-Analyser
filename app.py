import streamlit as st
import pandas as pd
from extractor import process_file   # extractor.py must be in the same folder

st.set_page_config(page_title="Bank Statement Analyzer", layout="wide")

st.title("🏦 Bank Statement Analyzer")

uploaded_file = st.file_uploader("Upload Bank Statement PDF", type=["pdf"])

if uploaded_file is not None:
    filename = uploaded_file.name
    file_bytes = uploaded_file.read()

    with st.spinner("Extracting transactions..."):
        meta, transactions = process_file(file_bytes, filename)

    if not transactions:
        st.error("❌ No transactions found in this file.")
    else:
        df = pd.DataFrame(transactions)

        # Format Date column → DD/MM/YYYY
        if "Date" in df.columns:
            df["Date"] = pd.to_datetime(df["Date"], errors="coerce").dt.strftime("%d/%m/%Y")

        st.success(f"✅ Extracted {len(df)} transactions")

        # Show DataFrame in Streamlit
        st.dataframe(df, use_container_width=True)

        # Allow Excel download
        output_filename = filename.replace(".pdf", ".xlsx")
        st.download_button(
            label="📥 Download as Excel",
            data=df.to_excel(index=False, engine="openpyxl"),
            file_name=output_filename,
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )

    # Debug logs
    if "_logs" in meta:
        with st.expander("🔍 Debug Logs"):
            for log in meta["_logs"]:
                st.text(log)
