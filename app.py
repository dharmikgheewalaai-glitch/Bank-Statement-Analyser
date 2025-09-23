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

        # ✅ Format Debit, Credit, Balance → 2 decimal places
        for col in ["Debit", "Credit", "Balance"]:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors="coerce").round(2)

        st.success("✅ Transactions Extracted Successfully!")

        # Show DataFrame with alignment
        st.dataframe(
            df.style.format({
                "Debit": "{:,.2f}",
                "Credit": "{:,.2f}",
                "Balance": "{:,.2f}"
            }).set_properties(
                subset=["Debit", "Credit", "Balance"], **{"text-align": "right"}
            ).set_properties(
                subset=["Particulars"], **{"text-align": "left"}
            ),
            use_container_width=True
        )

        # --- Filenames ---
        base_name = uploaded_file.name.rsplit(".", 1)[0]  # remove extension
        csv_filename = f"{base_name}.csv"
        excel_filename = f"{base_name}.xlsx"
        pdf_filename = f"{base_name}.pdf"

        # --- Prepare CSV ---
        csv_data = df.to_csv(index=False).encode("utf-8")

        # --- Prepare Excel ---
        excel_buffer = BytesIO()
        with pd.ExcelWriter(excel_buffer, engine="openpyxl") as writer:
            df.to_excel(writer, index=False, sheet_name="Transactions")
            # Apply alignment and format in Excel
            from openpyxl import load_workbook
            from openpyxl.styles import Alignment, numbers
            excel_buffer.seek(0)
            wb = load_workbook(excel_buffer)
            ws = wb.active
            for col in ["Debit", "Credit", "Balance"]:
                if col in df.columns:
                    col_idx = df.columns.get_loc(col) + 1
                    for row in ws.iter_rows(min_col=col_idx, max_col=col_idx, min_row=2):
                        for cell in row:
                            cell.alignment = Alignment(horizontal="right")
                            cell.number_format = numbers.FORMAT_NUMBER_00
            if "Particulars" in df.columns:
                col_idx = df.columns.get_loc("Particulars") + 1
                for row in ws.iter_rows(min_col=col_idx, max_col=col_idx, min_row=2):
                    for cell in row:
                        cell.alignment = Alignment(horizontal="left")
            excel_buffer = BytesIO()
            wb.save(excel_buffer)

        # --- Prepare PDF ---
        pdf_buffer = BytesIO()
        doc = SimpleDocTemplate(pdf_buffer, pagesize=A4)
        data = [df.columns.tolist()] + df.values.tolist()
        table = Table(data)
        style = TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.lightblue),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.black),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 10),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 6),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
        ])

        # Align columns
        if "Particulars" in df.columns:
            idx = df.columns.get_loc("Particulars")
            style.add('ALIGN', (idx, 1), (idx, -1), 'LEFT')
        for col in ["Debit", "Credit", "Balance"]:
            if col in df.columns:
                idx = df.columns.get_loc(col)
                style.add('ALIGN', (idx, 1), (idx, -1), 'RIGHT')

        table.setStyle(style)
        doc.build([table])

        # --- Show all three download buttons in one row ---
        col1, col2, col3 = st.columns(3)

        with col1:
            st.download_button(
                label="Download CSV File",
                data=csv_data,
                file_name=csv_filename,
                mime="text/csv"
            )

        with col2:
            st.download_button(
                label="Download Excel File",
                data=excel_buffer.getvalue(),
                file_name=excel_filename,
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )

        with col3:
            st.download_button(
                label="Download PDF File",
                data=pdf_buffer.getvalue(),
                file_name=pdf_filename,
                mime="application/pdf"
            )
