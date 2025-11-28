# ================= app.py =================

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
    if not value:
        return None
    text = str(value).strip().replace("'", "").replace('"', "")
    m = re.search(r"(\d{1,2})[\/\-.](\d{1,2})[\/\-.](\d{2,4})", text)
    if m:
        d, mth, y = m.group(1), m.group(2), m.group(3)
        if len(y) == 2:
            y = "20" + y
        return f"{int(d):02d}/{int(mth):02d}/{y}"
    return text


def clean_amount(v):
    try:
        return float(str(v).replace(",", "").strip())
    except:
        return 0.0


if uploaded_file is not None:
    st.info(f"Processing: {uploaded_file.name} ...")

    file_bytes = uploaded_file.read()
    meta, transactions = process_file(file_bytes, uploaded_file.name)

    if not transactions:
        st.error("⚠️ No transactions found. Try with another PDF or check if it's a scanned copy.")
    else:
        df = pd.DataFrame(transactions)

        if "Date" in df.columns:
            df["Date"] = df["Date"].apply(clean_date)

        for col in ["Debit", "Credit", "Balance"]:
            if col in df.columns:
                df[col] = df[col].apply(clean_amount)
                df[col] = df[col].map(lambda x: f"{x:.2f}")

        cols = list(df.columns)
        if "Head" in cols and "Balance" in cols:
            head_idx = cols.index("Head")
            balance_idx = cols.index("Balance")
            cols[head_idx], cols[balance_idx] = cols[balance_idx], cols[head_idx]
            df = df[cols]

        st.success("✅ Transactions Extracted Successfully!")
        st.dataframe(df, use_container_width=True)

        csv_filename = uploaded_file.name.replace(".pdf", ".csv").replace(".PDF", ".csv")
        csv = df.to_csv(index=False).encode("utf-8")

        excel_buffer = io.BytesIO()
        wb = Workbook()
        ws = wb.active
        ws.title = "Transactions"

        for r in dataframe_to_rows(df, index=False, header=True):
            ws.append(r)

        for col in ws.iter_cols(min_col=1, max_col=ws.max_column, min_row=1):
            header = col[0].value
            for cell in col:
                if header in ["Debit", "Credit", "Balance"] and cell.row > 1:
                    cell.alignment = Alignment(horizontal="right")
                    cell.number_format = numbers.FORMAT_NUMBER_00
                elif header == "Particulars":
                    cell.alignment = Alignment(horizontal="left", vertical="top")
                elif header == "Date":
                    cell.alignment = Alignment(horizontal="center", vertical="top")
                else:
                    cell.alignment = Alignment(horizontal="center", vertical="top")

        wb.save(excel_buffer)
        excel_buffer.seek(0)

        pdf_buffer = io.BytesIO()
        doc = SimpleDocTemplate(pdf_buffer, pagesize=A4)
        elements = []

        data = [list(df.columns)] + df.values.tolist()
        table = Table(data, repeatRows=1)
        table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey),
            ("GRID", (0, 0), (-1, -1), 0.25, colors.black),
            ("FONTNAME", (0, 0), (-1, -1), "Helvetica"),
            ("ALIGN", (0, 0), (-1, 0), "CENTER"),
            ("ALIGN", (0, 0), (0, -1), "CENTER"),
            ("VALIGN", (0, 0), (0, -1), "TOP"),
            ("ALIGN", (1, 0), (1, -1), "LEFT"),
            ("VALIGN", (1, 0), (1, -1), "TOP"),
            ("ALIGN", (2, 0), (-1, -1), "RIGHT"),
            ("VALIGN", (2, 0), (-1, -1), "TOP"),
        ]))
        elements.append(table)
        doc.build(elements)
        pdf_buffer.seek(0)

        col1, col2, col3 = st.columns(3)

        with col1:
            st.download_button(
                label="Download CSV File",
                data=csv,
                file_name=csv_filename,
                mime="text/csv"
            )

        with col2:
            st.download_button(
                label="Download Excel File",
                data=excel_buffer,
                file_name=uploaded_file.name.replace(".pdf", ".xlsx"),
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )

        with col3:
            st.download_button(
                label="Download PDF File",
                data=pdf_buffer,
                file_name=uploaded_file.name.replace(".pdf", ".pdf"),
                mime="application/pdf"
            )
