import streamlit as st
import pandas as pd
from extractor import process_file

st.title("📑 Bank Statement Extractor")

uploaded_file = st.file_uploader("Upload your Bank Statement (PDF)", type=["pdf"])

if uploaded_file:
    file_bytes = uploaded_file.read()
    filename = uploaded_file.name

    with st.spinner("Processing file..."):
        meta, transactions = process_file(file_bytes, filename)

    if not transactions:
        st.error("No transactions found in this PDF.")
    else:
        df = pd.DataFrame(transactions)

        st.success(f"✅ Extracted {len(df)} transactions from {filename}")
        st.dataframe(df)

        # Save to Excel with same file name
        excel_name = filename.replace(".pdf", ".xlsx")
        df.to_excel(excel_name, index=False)

        st.download_button(
            label="📥 Download Excel",
            data=open(excel_name, "rb").read(),
            file_name=excel_name,
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
