# app.py
import streamlit as st
import pandas as pd
import re
from extractor import process_file
from io import BytesIO
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle

st.title("📄 Bank Statement Extractor")

uploaded_file = st.file_uploader("Upload Bank Statement (PDF)", type=["pdf"])

def clean_date(value):
    """Extract date, remove prefix/suffix, normalize to DD/MM/YYYY"""
    if not value:
        return None
    text = str(value).strip().replace("'", "").replace('"', "")
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
        
        # Show DataFrame
        st.dataframe(df, use_container_width=True)

        # --- CSV Export ---
        csv_filename = uploaded_file.name.replace(".pdf", ".csv").replace(".PDF", ".csv")
        csv_data = df.to_csv(index=False).encode("utf-8")
        st.download_button(
            label="⬇️ Download CSV File",
            data=csv_data,
            file_name=csv_filename,
            mime="text/csv"
        )

        # --- Excel Export ---
        excel_filename = uploaded_file.name.replace(".pdf", ".xlsx").replace(".PDF", ".xlsx")
        excel_buffer = BytesIO()
        with pd.ExcelWriter(excel_buffer, engine="openpyxl") as writer:
            df.to_excel(writer, index=False, sheet_name="Transactions")
        st.download_button(
            label="⬇️ Download Excel File",
            data=excel_buffer.getvalue(),
            file_name=excel_filename,
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )

        # --- PDF Export ---
        pdf_filename = uploaded_file.name.replace(".pdf", "_transactions.pdf").replace(".PDF", "_transactions.pdf")
        pdf_buffer = BytesIO()
        doc = SimpleDocTemplate(pdf_buffer, pagesize=A4)
        data = [df.columns.tolist()] + df.values.tolist()
        table = Table(data)
        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.lightblue),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.black),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 10),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 6),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
        ]))
        doc.build([table])
        st.download_button(
            label="⬇️ Download PDF File",
            data=pdf_buffer.getvalue(),
            file_name=pdf_filename,
            mime="application/pdf"
        )

