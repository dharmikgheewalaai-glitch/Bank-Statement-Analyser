import streamlit as st
import pandas as pd
import re
import io
from extractor import process_file
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from openpyxl import Workbook
from openpyxl.utils.dataframe import dataframe_to_rows
from openpyxl.styles import Alignment, numbers

st.set_page_config(page_title="Bank Statement Analyser", layout="wide")
st.title("Bank Statement Analyser")

uploaded_file = st.file_uploader("Upload Bank Statement (PDF)", type=["pdf"])


def clean_date(value):
    """Convert any detected date into DD/MM/YYYY"""
    if not value:
        return None
    text = str(value).strip()

    match = re.search(r"(\d{1,2})[\/\-.](\d{1,2})[\/\-.](\d{2,4})", text)
    if match:
        d, m, y = match.groups()
        if len(y) == 2:
            y = "20" + y
        return f"{int(d):02d}/{int(m):02d}/{y}"
    return None


def clean_amount(value):
    """Make the amount a float with 2 decimals"""
    try:
        return round(float(str(value).replace(",", "").strip()), 2)
    except:
        return 0.00


if uploaded_file is not None:
    st.info(f"Processing: {uploaded_file.name} ...")

    file_bytes = uploaded_file.read()
    meta, transactions = process_file(file_bytes, uploaded_file.name)

    if not transactions:
        st.error("⚠️ No transactions found.")
    else:
        df = pd.DataFrame(transactions)

        # Clean Date → DD/MM/YYYY
        if "Date" in df.columns:
            df["Date"] = df["Date"].apply(clean_date)

        # Clean amount columns → numeric floats with 2 decimals
        for col in ["Debit", "Credit", "Balance"]:
            if col in df.columns:
                df[col] = df[col].apply(clean_amount)

        # Swap Head and Balance if required
        cols = list(df.columns)
        if "Head" in cols and "Balance" in cols:
            h = cols.index("Head")
            b = cols.index("Balance")
            cols[h], cols[b] = cols[b], cols[h]
            df = df[cols]

        # Display copy (Streamlit) → numbers remain floats but formatted
        df_display = df.copy()
        for col in ["Debit", "Credit", "Balance"]:
            if col in df_display.columns:
                df_display[col] = df_display[col].map(lambda x: f"{x:.2f}")

        st.success("Transactions Extracted Successfully!")
        st.dataframe(df_display, use_container_width=True)

        # Base filename
        base = uploaded_file.name.rsplit(".", 1)[0]
        csv_name = f"{base}.csv"
        xlsx_name = f"{base}.xlsx"
        pdf_name = f"{base}.pdf"

        # CSV Export → floats with 2 decimals
        csv_bytes = df.to_csv(index=False, float_format="%.2f").encode("utf-8")

        # Excel Export
        excel_buffer = io.BytesIO()
        wb = Workbook()
        ws = wb.active
        ws.title = "Transactions"

        for row in dataframe_to_rows(df, index=False, header=True):
            ws.append(row)

        # Excel formatting
        for col in ws.iter_cols(min_col=1, max_col=ws.max_column, min_row=1):
            header = col[0].value
            for cell in col:
                if header in ["Debit", "Credit", "Balance"] and cell.row > 1:
                    cell.alignment = Alignment(horizontal="right")
                    cell.number_format = numbers.FORMAT_NUMBER_00  # 2 decimals
                elif header in ["Particular", "Particulars"]:
                    cell.alignment = Alignment(horizontal="left")
                elif header == "Date":
                    cell.alignment = Alignment(horizontal="center")
                else:
                    cell.alignment = Alignment(horizontal="center")

        wb.save(excel_buffer)
        excel_buffer.seek(0)

        # PDF Export → force 2 decimal formatting
        df_pdf = df.copy()
        for col in ["Debit", "Credit", "Balance"]:
            if col in df_pdf.columns:
                df_pdf[col] = df_pdf[col].map(lambda x: f"{x:.2f}")

        pdf_buffer = io.BytesIO()
        doc = SimpleDocTemplate(pdf_buffer, pagesize=A4)
        elements = []

        data = [list(df_pdf.columns)] + df_pdf.values.tolist()

        table = Table(data, repeatRows=1)
        table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey),
            ("GRID", (0, 0), (-1, -1), 0.25, colors.black),
            ("FONTNAME", (0, 0), (-1, -1), "Helvetica"),
            ("FONTSIZE", (0, 0), (-1, -1), 7),
            ("WORDWRAP", (0, 0), (-1, -1), True),
            ("ALIGN", (0, 0), (-1, 0), "CENTER"),
            ("ALIGN", (0, 0), (0, -1), "CENTER"),
            ("ALIGN", (1, 0), (1, -1), "LEFT"),
            ("ALIGN", (2, 0), (-1, -1), "RIGHT"),
        ]))

        elements.append(table)
        doc.build(elements)
        pdf_buffer.seek(0)

        col1, col2, col3 = st.columns(3)

        with col1:
            st.download_button("Download CSV", data=csv_bytes, file_name=csv_name)

        with col2:
            st.download_button("Download Excel", data=excel_buffer,
                               file_name=xlsx_name,
                               mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

        with col3:
            st.download_button("Download PDF", data=pdf_buffer,
                               file_name=pdf_name,
                               mime="application/pdf")
