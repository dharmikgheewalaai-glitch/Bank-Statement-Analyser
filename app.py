# app.py
import streamlit as st
import pandas as pd
import re
from io import BytesIO
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from extractor import process_file

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
        if len(year) == 2:  # handle yy format
            year = "20" + year
        return f"{int(day):02d}/{int(month):02d}/{year}"
    return None

if uploaded_file is not None:
    st.info(f"Processing: {uploaded_file.name} ...")

    # Read file
    file_bytes = uploaded_file.read()

    # Extract
    meta, transactions = process_file(file_bytes, uploaded_file.name)

    if not transactions:
        st.error("⚠️ No transactions found. Try another PDF or check if it's scanned.")
    else:
        df = pd.DataFrame(transactions)

        # ✅ Clean Date
        if "Date" in df.columns:
            df["Date"] = df["Date"].apply(clean_date)

        st.success("✅ Transactions Extracted Successfully!")

        # Show metadata
        with st.expander("📌 Account Details"):
            st.json(meta)

        # Show DataFrame
        st.dataframe(df, use_container_width=True)

        # File names
        csv_filename = uploaded_file.name.replace(".pdf", ".csv").replace(".PDF", ".csv")
        excel_filename = uploaded_file.name.replace(".pdf", ".xlsx").replace(".PDF", ".xlsx")
        pdf_filename = uploaded_file.name.replace(".pdf", "_transactions.pdf").replace(".PDF", "_transactions.pdf")

        # CSV download
        csv_data = df.to_csv(index=False).encode("utf-8")
        st.download_button(
            label="Download CSV File",
            data=csv_data,
            file_name=csv_filename,
            mime="text/csv"
        )

        # Excel download
        excel_buffer = BytesIO()
        with pd.ExcelWriter(excel_buffer, engine="openpyxl") as writer:
            df.to_excel(writer, index=False, sheet_name="Transactions")
        st.download_button(
            label="Download Excel File",
            data=excel_buffer.getvalue(),
            file_name=excel_filename,
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )

        # PDF download
        pdf_buffer = BytesIO()
        doc = SimpleDocTemplate(pdf_buffer, pagesize=A4)
        elements = []
        style = getSampleStyleSheet()["Normal"]

        # Add metadata
        if meta:
            elements.append(Paragraph("Account Details", style))
            for k, v in meta.items():
                elements.append(Paragraph(f"<b>{k}:</b> {v}", style))

        # Add transactions table
        table_data = [df.columns.tolist()] + df.values.tolist()
        table = Table(table_data)
        table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey),
            ("GRID", (0, 0), (-1, -1), 0.25, colors.black),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("ALIGN", (0, 0), (-1, -1), "LEFT"),
        ]))
        elements.append(table)

        doc.build(elements)

        st.download_button(
            label="Download PDF File",
            data=pdf_buffer.getvalue(),
            file_name=pdf_filename,
            mime="application/pdf"
        )
