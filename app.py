# app.py
import streamlit as st
import pandas as pd
import re
from io import BytesIO
from extractor import process_file
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet
from openpyxl import load_workbook
from openpyxl.styles import Alignment, numbers

st.title("📄 Bank Statement Extractor")

uploaded_file = st.file_uploader("Upload Bank Statement (PDF)", type=["pdf"])


def clean_date(value):
    """Extract date, remove prefix/suffix, normalize to DD/MM/YYYY"""
    if not value:
        return None
    text = str(value).strip().replace("'", "").replace('"', "")

    # ✅ regex supports /, -, or .
    match = re.search(r"(\d{1,2})[\/\-.](\d{1,2})[\/\-.](\d{2,4})", text)
    if match:
        day, month, year = match.groups()
        if len(year) == 2:  # handle yy → 20yy
            year = "20" + year
        return f"{int(day):02d}/{int(month):02d}/{year}"
    return None


if uploaded_file is not None:
    st.info(f"Processing: {uploaded_file.name} ...")

    # Read file
    file_bytes = uploaded_file.read()

    # Call extractor
    _, transactions = process_file(file_bytes, uploaded_file.name)

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

        # ✅ Filenames
        base_filename = uploaded_file.name.rsplit(".", 1)[0]
        csv_filename = base_filename + ".csv"
        excel_filename = base_filename + ".xlsx"
        pdf_filename = base_filename + ".pdf"

        # --- CSV ---
        csv = df.to_csv(index=False).encode("utf-8")

        # --- Excel ---
        excel_buffer = BytesIO()
        with pd.ExcelWriter(excel_buffer, engine="openpyxl") as writer:
            df.to_excel(writer, index=False, sheet_name="Transactions")
        excel_buffer.seek(0)

        wb = load_workbook(excel_buffer)
        ws = wb.active

        # Apply alignments and number formatting
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

        # Auto adjust column widths
        for col in ws.columns:
            max_length = 0
            col_letter = col[0].column_letter
            for cell in col:
                try:
                    if cell.value:
                        max_length = max(max_length, len(str(cell.value)))
                except:
                    pass
            ws.column_dimensions[col_letter].width = min(max_length + 2, 50)

        excel_buffer = BytesIO()
        wb.save(excel_buffer)

        # --- PDF ---
        pdf_buffer = BytesIO()
        doc = SimpleDocTemplate(pdf_buffer, pagesize=letter)
        styles = getSampleStyleSheet()

        data = [list(df.columns)] + df.values.tolist()
        formatted_data = []
        for i, row in enumerate(data):
            new_row = []
            for j, val in enumerate(row):
                if j in [2, 3, 4]:  # Debit, Credit, Balance
                    try:
                        if i == 0:  # header
                            new_row.append(str(val))
                        else:
                            new_row.append(f"{float(val):,.2f}" if val not in [None, ""] else "")
                    except:
                        new_row.append(str(val))
                else:  # Date & Particulars
                    new_row.append(str(val))
            formatted_data.append(new_row)

        table = Table(formatted_data)
        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.lightblue),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('ALIGN', (2, 1), (4, -1), 'RIGHT'),  # Debit, Credit, Balance
            ('ALIGN', (1, 1), (1, -1), 'LEFT'),   # Particulars
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('GRID', (0, 0), (-1, -1), 0.25, colors.grey),
            ('FONTSIZE', (0, 0), (-1, -1), 8),
        ]))

        elements = [Paragraph("Transactions", styles['Heading2']), table]
        doc.build(elements)

        pdf_buffer.seek(0)

        # --- Download buttons in one row ---
        col1, col2, col3 = st.columns(3)

        with col1:
            st.download_button(
                label="⬇️ Download CSV File",
                data=csv,
                file_name=csv_filename,
                mime="text/csv"
            )

        with col2:
            st.download_button(
                label="⬇️ Download Excel File",
                data=excel_buffer.getvalue(),
                file_name=excel_filename,
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )

        with col3:
            st.download_button(
                label="⬇️ Download PDF File",
                data=pdf_buffer,
                file_name=pdf_filename,
                mime="application/pdf"
            )
