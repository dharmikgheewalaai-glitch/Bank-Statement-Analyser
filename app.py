import streamlit as st
import pandas as pd
import re
import io
import os
import json
import uuid
from datetime import datetime
import importlib.util

_p = next((f for f in ["extractor.py", "extractor-v1.py"] if os.path.exists(f)), None)
if _p:
    _s = importlib.util.spec_from_file_location("extractor", _p)
    _m = importlib.util.module_from_spec(_s); _s.loader.exec_module(_m)
    process_file = _m.process_file
else:
    raise ImportError("extractor not found")

from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import getSampleStyleSheet
from openpyxl import Workbook
from openpyxl.utils.dataframe import dataframe_to_rows
from openpyxl.styles import Alignment, Font, PatternFill, numbers as xl_numbers

st.set_page_config(page_title="Bank Statement Analyser", layout="wide")

# ── STORAGE PATHS ─────────────────────────────────────────────────────────────
RULES_FILE   = "rules.json"
HISTORY_FILE = "history.json"
HISTORY_DIR  = "history_store"
os.makedirs(HISTORY_DIR, exist_ok=True)


# ── PERSISTENCE HELPERS ───────────────────────────────────────────────────────
def load_json(path, default):
    if os.path.exists(path):
        try:
            with open(path, "r") as f:
                return json.load(f)
        except Exception:
            return default
    return default


def save_json(path, data):
    with open(path, "w") as f:
        json.dump(data, f, indent=2)


if "rules" not in st.session_state:
    st.session_state.rules = load_json(RULES_FILE, [])       # [{"head":..., "keywords":[...]}]
if "history" not in st.session_state:
    st.session_state.history = load_json(HISTORY_FILE, [])   # [{"id","filename","timestamp",...}]


# ── DATE CLEANING ─────────────────────────────────────────────────────────────
def clean_date(value):
    if not value:
        return None
    text = str(value).strip()
    match = re.search(r"(\d{1,2})[\/\-.](\d{1,2})[\/\-.](\d{2,4})", text)
    if match:
        d, m, y = match.groups()
        if len(y) == 2:
            y = "20" + y
        return f"{int(d):02d}/{int(m):02d}/{y}"
    return text


# ── AMOUNT CLEANING ────────────────────────────────────────────────────────────
def clean_amount(value):
    if value is None or str(value).strip() in ("", "None", "nan"):
        return 0.00
    try:
        return round(float(str(value).replace(",", "").strip()), 2)
    except Exception:
        return 0.00


# ── EXCEL BUILDER ──────────────────────────────────────────────────────────────
def build_excel(df_final):
    excel_buffer = io.BytesIO()
    wb = Workbook()
    ws = wb.active
    ws.title = "Transactions"

    HEADER_FILL = PatternFill("solid", fgColor="2F5496")
    HEADER_FONT = Font(bold=True, color="FFFFFF")
    NUM_COLS    = {"Debit", "Credit", "Balance"}

    for r_idx, row_data in enumerate(dataframe_to_rows(df_final, index=False, header=True), start=1):
        ws.append(row_data)
        for c_idx, cell in enumerate(ws[r_idx], start=1):
            header_val = ws.cell(1, c_idx).value or ""
            if r_idx == 1:
                cell.fill = HEADER_FILL
                cell.font = HEADER_FONT
                cell.alignment = Alignment(horizontal="center", vertical="center")
            else:
                if header_val in NUM_COLS:
                    cell.number_format = xl_numbers.FORMAT_NUMBER_00
                    cell.alignment = Alignment(horizontal="left")
                else:
                    cell.alignment = Alignment(horizontal="left", wrap_text=True)

    for col_cells in ws.columns:
        max_len = max((len(str(c.value or "")) for c in col_cells), default=10)
        ws.column_dimensions[col_cells[0].column_letter].width = min(max_len + 4, 50)

    ws.freeze_panes = "A2"
    wb.save(excel_buffer)
    excel_buffer.seek(0)
    return excel_buffer


# ── PDF BUILDER ────────────────────────────────────────────────────────────────
def build_pdf(df_final, base):
    df_pdf = df_final.copy()
    for col in ["Debit", "Credit", "Balance"]:
        if col in df_pdf.columns:
            df_pdf[col] = df_pdf[col].map(lambda x: f"{x:,.2f}")

    pdf_buffer = io.BytesIO()
    styles = getSampleStyleSheet()
    doc = SimpleDocTemplate(
        pdf_buffer, pagesize=landscape(A4),
        leftMargin=20, rightMargin=20, topMargin=20, bottomMargin=20
    )
    elements = []
    elements.append(Paragraph(f"Bank Statement — {base}", styles["Title"]))
    elements.append(Spacer(1, 10))

    data = [list(df_pdf.columns)] + [
        [str(v) for v in row] for row in df_pdf.values.tolist()
    ]

    col_widths = []
    for c in df_pdf.columns:
        if c == "Particulars":
            col_widths.append(220)
        elif c == "Date":
            col_widths.append(65)
        else:
            col_widths.append(70)

    table = Table(data, repeatRows=1, colWidths=col_widths)
    table.setStyle(TableStyle([
        ("BACKGROUND",   (0, 0), (-1, 0),  colors.HexColor("#2F5496")),
        ("TEXTCOLOR",    (0, 0), (-1, 0),  colors.white),
        ("FONTNAME",     (0, 0), (-1, 0),  "Helvetica-Bold"),
        ("FONTSIZE",     (0, 0), (-1, 0),  8),
        ("ALIGN",        (0, 0), (-1, 0),  "CENTER"),
        ("VALIGN",       (0, 0), (-1, 0),  "MIDDLE"),
        ("FONTNAME",     (0, 1), (-1, -1), "Helvetica"),
        ("FONTSIZE",     (0, 1), (-1, -1), 7),
        ("ALIGN",        (0, 1), (-1, -1), "LEFT"),
        ("VALIGN",       (0, 1), (-1, -1), "MIDDLE"),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#EEF2F8")]),
        ("GRID",         (0, 0), (-1, -1), 0.25, colors.grey),
        ("TOPPADDING",   (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING",(0, 0), (-1, -1), 3),
        ("LEFTPADDING",  (0, 0), (-1, -1), 4),
        ("RIGHTPADDING", (0, 0), (-1, -1), 4),
    ]))

    elements.append(table)
    doc.build(elements)
    pdf_buffer.seek(0)
    return pdf_buffer


# ── CLEAN + FINALIZE A RAW TRANSACTIONS LIST ───────────────────────────────────
def finalize_df(transactions):
    df = pd.DataFrame(transactions)
    df_final = df.copy()

    if "Date" in df_final.columns:
        df_final["Date"] = df_final["Date"].apply(clean_date)
    for col in ["Debit", "Credit", "Balance"]:
        if col in df_final.columns:
            df_final[col] = df_final[col].apply(clean_amount)
    if "Page" in df_final.columns:
        df_final.drop(columns=["Page"], inplace=True)

    preferred_order = ["Date", "Particulars", "Debit", "Credit", "Balance", "Head"]
    existing_cols = [c for c in preferred_order if c in df_final.columns]
    extra_cols = [c for c in df_final.columns if c not in existing_cols]
    df_final = df_final[existing_cols + extra_cols]
    return df_final


st.title("🏦 Bank Statement Analyser")

tab_dash, tab_hist, tab_rules = st.tabs(["📊 Dashboard", "🕑 History", "🏷️ Rules"])

# ═══════════════════════════════════════════════════════════════════════════
#                                RULES TAB
# ═══════════════════════════════════════════════════════════════════════════
with tab_rules:
    st.subheader("Head Classification Rules")
    st.caption(
        "No predefined rules — every transaction is tagged **OTHER** until you "
        "add keyword → Head mappings below. First matching rule (top to bottom) wins."
    )

    with st.form("add_rule_form", clear_on_submit=True):
        c1, c2 = st.columns([1, 2])
        head_in = c1.text_input("Head name", placeholder="e.g. SALARY")
        kw_in   = c2.text_input("Keywords (comma separated)", placeholder="e.g. SALARY, PAYROLL")
        add_clicked = st.form_submit_button("➕ Add Rule")
        if add_clicked:
            if not head_in.strip() or not kw_in.strip():
                st.warning("Head name and at least one keyword are required.")
            else:
                keywords = [k.strip().upper() for k in kw_in.split(",") if k.strip()]
                st.session_state.rules.append({"head": head_in.strip().upper(), "keywords": keywords})
                save_json(RULES_FILE, st.session_state.rules)
                st.success(f"Rule added for **{head_in.strip().upper()}**.")
                st.rerun()

    st.markdown("---")

    if not st.session_state.rules:
        st.info("No rules defined yet.")
    else:
        for i, rule in enumerate(st.session_state.rules):
            rc1, rc2, rc3 = st.columns([1.2, 3, 0.6])
            rc1.markdown(f"**{rule.get('head','')}**")
            rc2.write(", ".join(rule.get("keywords", [])))
            if rc3.button("🗑️ Delete", key=f"del_rule_{i}"):
                st.session_state.rules.pop(i)
                save_json(RULES_FILE, st.session_state.rules)
                st.rerun()


# ═══════════════════════════════════════════════════════════════════════════
#                               DASHBOARD TAB
# ═══════════════════════════════════════════════════════════════════════════
with tab_dash:
    uploaded_file = st.file_uploader(
        "Upload Bank Statement (PDF, Excel, or CSV)",
        type=["pdf", "xlsx", "xls", "csv"],
    )

    if uploaded_file is not None:
        st.info(f"⏳ Processing: **{uploaded_file.name}** ...")
        file_bytes = uploaded_file.read()

        try:
            meta, transactions = process_file(file_bytes, uploaded_file.name, rules=st.session_state.rules)
        except Exception as e:
            st.error(f"Extraction failed: {e}")
            st.stop()

        if not transactions:
            st.error("⚠️ No transactions found. Check PDF format.")
            st.stop()

        df_final = finalize_df(transactions)

        total_debit  = df_final["Debit"].sum()  if "Debit"  in df_final.columns else 0
        total_credit = df_final["Credit"].sum() if "Credit" in df_final.columns else 0
        row_count    = len(df_final)

        c1, c2, c3 = st.columns(3)
        c1.metric("Total Transactions", row_count)
        c2.metric("Total Debit",  f"₹ {total_debit:,.2f}")
        c3.metric("Total Credit", f"₹ {total_credit:,.2f}")

        df_display = df_final.copy()
        for col in ["Debit", "Credit", "Balance"]:
            if col in df_display.columns:
                df_display[col] = df_display[col].map(lambda x: f"{x:,.2f}")

        st.success(f"✅ {row_count} transactions extracted!")
        st.dataframe(df_display, use_container_width=True)

        base      = uploaded_file.name.rsplit(".", 1)[0]
        csv_name  = f"{base}.csv"
        xlsx_name = f"{base}.xlsx"
        pdf_name  = f"{base}_report.pdf"

        csv_bytes     = df_final.to_csv(index=False, float_format="%.2f").encode("utf-8")
        excel_buffer  = build_excel(df_final)
        pdf_buffer    = build_pdf(df_final, base)

        st.markdown("---")
        dl1, dl2, dl3 = st.columns(3)
        with dl1:
            st.download_button("⬇️ Download CSV", data=csv_bytes,
                                file_name=csv_name, mime="text/csv")
        with dl2:
            st.download_button("⬇️ Download Excel", data=excel_buffer,
                                file_name=xlsx_name,
                                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
        with dl3:
            st.download_button("⬇️ Download PDF", data=pdf_buffer,
                                file_name=pdf_name, mime="application/pdf")

        # Save one history record per uploaded file (avoid duplicate on rerun)
        file_signature = f"{uploaded_file.name}_{uploaded_file.size}"
        if st.session_state.get("_last_saved_signature") != file_signature:
            entry_id = uuid.uuid4().hex[:12]
            csv_path = os.path.join(HISTORY_DIR, f"{entry_id}.csv")
            df_final.to_csv(csv_path, index=False)
            st.session_state.history.insert(0, {
                "id": entry_id,
                "filename": uploaded_file.name,
                "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "row_count": row_count,
                "total_debit": float(total_debit),
                "total_credit": float(total_credit),
                "csv_path": csv_path,
            })
            save_json(HISTORY_FILE, st.session_state.history)
            st.session_state["_last_saved_signature"] = file_signature


# ═══════════════════════════════════════════════════════════════════════════
#                                HISTORY TAB
# ═══════════════════════════════════════════════════════════════════════════
with tab_hist:
    st.subheader("Processed Statements")

    if not st.session_state.history:
        st.info("No statements processed yet.")
    else:
        hist_table = pd.DataFrame(st.session_state.history)[
            ["timestamp", "filename", "row_count", "total_debit", "total_credit"]
        ].rename(columns={
            "timestamp": "Processed On", "filename": "File", "row_count": "Rows",
            "total_debit": "Total Debit", "total_credit": "Total Credit",
        })
        st.dataframe(hist_table, use_container_width=True)

        options = [f"{h['timestamp']} — {h['filename']}" for h in st.session_state.history]
        sel_label = st.selectbox("View a past statement", options)
        sel_idx = options.index(sel_label)
        rec = st.session_state.history[sel_idx]

        if os.path.exists(rec["csv_path"]):
            hist_df = pd.read_csv(rec["csv_path"])
            st.dataframe(hist_df, use_container_width=True)

            dl_col, del_col = st.columns([1, 1])
            with dl_col:
                st.download_button(
                    "⬇️ Download CSV",
                    data=open(rec["csv_path"], "rb").read(),
                    file_name=f"{rec['filename'].rsplit('.', 1)[0]}_history.csv",
                    mime="text/csv",
                    key=f"hist_dl_{rec['id']}",
                )
            with del_col:
                if st.button("🗑️ Delete this record", key=f"hist_del_{rec['id']}"):
                    if os.path.exists(rec["csv_path"]):
                        os.remove(rec["csv_path"])
                    st.session_state.history.pop(sel_idx)
                    save_json(HISTORY_FILE, st.session_state.history)
                    st.rerun()
        else:
            st.warning("Stored data for this record is missing.")
