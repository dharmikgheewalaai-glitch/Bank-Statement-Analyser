# app.py
import streamlit as st
import pandas as pd
import re
from io import BytesIO
from extractor import process_file

# Excel/PDF libs
from openpyxl import Workbook
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph
from reportlab.lib.styles import getSampleStyleSheet

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
        if len(year) == 2:
            year = "20" + year
        return f"{int(day):02d}/{int(month):02d}/{year}"
    return None


if uploaded_file is not None:
    st.info(f"Processing: {uploaded_file.name} ...")

    file_bytes = uploaded_file.read()
    transactions = process_file(file_bytes, uploaded_file.name)

    if not transactions:
        st.error("⚠️ No transactions found. Try with another PDF or check if it's a scanned copy.")
    else:
        df = pd.DataFrame(transactions)

        # ✅ Clean Date
        if "Date" in df.columns:
            df["Date"] = df["Date"].apply(clean_date)

        st.success("✅ Transactions Extracted Successfully!")
        st.dataframe(df, use_container_width=True)

        # --- CSV Export ---
        csv_filename = uploaded_file.name.replace(".pdf", ".csv").replace(".PDF", ".csv")
        csv_data = df.to_csv(index=False).encode("utf-8")

        # --- Excel Export ---
        excel_filename = uploaded_file.name.replace(".pdf", ".xlsx").replace(".PDF", ".xlsx")
        excel_buffer = BytesIO()
        wb = Workbook()
        ws = wb.active
        ws.append(list(df.columns))
        for row in df.itertuples(index=False, name=None):
            ws.append(row)
        wb.save(excel_buffer)
        excel_buffer.seek(0)
        excel_data = excel_buffer.getvalue()

        # --- PDF Export ---
        pdf_filename = uploaded_file.name.replace(".pdf", ".pdf").replace(".PDF", ".pdf")
        pdf_buffer = BytesIO()
        doc = SimpleDocTemplate(pdf_buffer, pagesize=letter)
        styles = getSampleStyleSheet()
        elements = []

        elements.append(Paragraph("Transactions", styles['Heading2']))

        data = [list(df.columns)] + df.values.tolist()
        formatted_data = []
        for i, row in enumerate(data):
            new_row = []
            for j, val in enumerate(row):
                if j in [2, 3, 4]:  # Debit, Credit, Balance
                    try:
                        if i == 0:
                            new_row.append(str(val))
                        else:
                            new_row.append(f"{float(val):,.2f}" if val not in [None, ""] else "")
                    except:
                        new_row.append(str(val))
                else:
                    new_row.append(str(val))
            formatted_data.append(new_row)

        table = Table(formatted_data)

        # ✅ Column alignment rules
        align_map = {
            "Date": "CENTER",
            "Particulars": "LEFT",
            "Debit": "RIGHT",
            "Credit": "RIGHT",
            "Balance": "RIGHT",
            "Head": "CENTER",
            "Page": "CENTER",
        }

        style_commands = [
            ('BACKGROUND', (0, 0), (-1, 0), colors.lightblue),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 0), (-1, -1), 12),
            ('GRID', (0, 0), (-1, -1), 0.25, colors.grey),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ]

        for col_name, align in align_map.items():
            if col_name in df.columns:
                col_idx = df.columns.get_loc(col_name)
                style_commands.append(('ALIGN', (col_idx, 0), (col_idx, -1), align))

        table.setStyle(TableStyle(style_commands))
        elements.append(table)
        doc.build(elements)
        pdf_buffer.seek(0)
        pdf_data = pdf_buffer.getvalue()

        # --- Buttons in one row ---
        col1, col2, col3 = st.columns(3)

        with col1:
            st.download_button(
                label="📥 Download CSV File",
                data=csv_data,
                file_name=csv_filename,
                mime="text/csv"
            )
        with col2:
            st.download_button(
                label="📊 Download Excel File",
                data=excel_data,
                file_name=excel_filename,
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
        with col3:
            st.download_button(
                label="📄 Download PDF File",
                data=pdf_data,
                file_name=pdf_filename,
                mime="application/pdf"
            )
