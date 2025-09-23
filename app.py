# app.py
import streamlit as st
import pandas as pd
import re
import io
from extractor import process_file
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_RIGHT

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


def clean_amount(value):
    """Convert amounts like ₹1,234.50 or 1,234.50Dr to float"""
    if pd.isna(value):
        return None
    text = str(value).replace(",", "").replace("₹", "").strip()
    # Remove any trailing non-numeric characters (e.g., "Dr", "Cr")
    text = re.sub(r"[^\d.\-]", "", text)
    try:
        return float(text)
    except ValueError:
        return None


if uploaded_file is not None:
    st.info(f"Processing: {uploaded_file.name} ...")

    file_bytes = uploaded_file.read()

    # Call extractor
    meta, transactions = process_file(file_bytes, uploaded_file.name)

    if not transactions:
        st.error("⚠️ No transactions found. Try with another PDF or check if it's a scanned copy.")
    else:
        # ✅ Handle both dicts and lists
        if isinstance(transactions[0], dict):
            df = pd.DataFrame(transactions)
        else:
            df = pd.DataFrame(
                transactions,
                columns=["Date", "Particulars", "Debit", "Credit", "Balance", "Head", "Page"],
            )

        # Clean Date
        if "Date" in df.columns:
            df["Date"] = df["Date"].apply(clean_date)

        # Clean amounts
        for col in ["Debit", "Credit", "Balance"]:
            if col in df.columns:
                df[col] = df[col].apply(clean_amount).round(2)

        st.success("✅ Transactions Extracted Successfully!")

        # Show full metadata again
        with st.expander("📌 Account Details"):
            st.json(meta)

        # Show DataFrame
        st.dataframe(df, use_container_width=True)

        # =============================
        # 📥 Download Options
        # =============================

        col1, col2, col3 = st.columns(3)

        # CSV
        csv_filename = uploaded_file.name.replace(".pdf", ".csv").replace(".PDF", ".csv")
        csv_data = df.to_csv(index=False).encode("utf-8")
        with col1:
            st.download_button(
                label="⬇️ Download CSV File",
                data=csv_data,
                file_name=csv_filename,
                mime="text/csv",
            )

        # Excel
        excel_filename = uploaded_file.name.replace(".pdf", ".xlsx").replace(".PDF", ".xlsx")
        excel_buffer = io.BytesIO()
        with pd.ExcelWriter(excel_buffer, engine="openpyxl") as writer:
            df.to_excel(writer, index=False, sheet_name="Transactions")
        excel_buffer.seek(0)
        with col2:
            st.download_button(
                label="⬇️ Download Excel File",
                data=excel_buffer,
                file_name=excel_filename,
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )

        # PDF
        pdf_filename = uploaded_file.name.replace(".pdf", ".pdf").replace(".PDF", ".pdf")
        pdf_buffer = io.BytesIO()
        doc = SimpleDocTemplate(pdf_buffer, pagesize=A4)
        elements = []

        styles = getSampleStyleSheet()
        header_style = styles["Heading4"]
        header_style.alignment = TA_CENTER

        # Add Title
        elements.append(Paragraph("Transaction Statement", header_style))

        # Prepare table data
        table_data = [list(df.columns)] + df.values.tolist()

        # Convert all cells to string
        table_data = [[str(cell) if cell is not None else "" for cell in row] for row in table_data]

        # Build Table
        table = Table(table_data, repeatRows=1)

        # Table Style
        style = TableStyle(
            [
                ("FONTNAME", (0, 0), (-1, -1), "Helvetica"),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.black),
                ("ALIGN", (0, 0), (-1, 0), "CENTER"),  # Header center
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ]
        )

        # Column alignments
        col_map = {
            "Date": "CENTER",
            "Particulars": "LEFT",
            "Debit": "RIGHT",
            "Credit": "RIGHT",
            "Balance": "RIGHT",
            "Head": "CENTER",
            "Page": "CENTER",
        }

        for idx, col in enumerate(df.columns):
            align = col_map.get(col, "LEFT")
            style.add("ALIGN", (idx, 1), (idx, -1), align)

        table.setStyle(style)
        elements.append(table)

        doc.build(elements)
        pdf_buffer.seek(0)

        with col3:
            st.download_button(
                label="⬇️ Download PDF File",
                data=pdf_buffer,
                file_name=pdf_filename,
                mime="application/pdf",
            )
