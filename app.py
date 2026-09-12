import streamlit as st
import pandas as pd
from pathlib import Path

from database.database import init, add, all_history
from modules.pdf_parser import parse_pdf
from modules.normalizer import normalize
from modules.head_rules import DEFAULT_RULES, classify
from modules.tally_engine import apply_tally
from modules.analyzer import summary, monthly
from modules.report_generator import excel_bytes

st.set_page_config(page_title="Bank Statement Analyzer", page_icon="🏦", layout="wide")
init()

for key, default in {
    "df": pd.DataFrame(),
    "rules": {k:list(v) for k,v in DEFAULT_RULES.items()},
    "accounts": {},
    "journal_heads": ["Depreciation","Outstanding Expense","GST Adjustment"],
    "bank_account": ""
}.items():
    if key not in st.session_state: st.session_state[key] = default

st.title("🏦 Bank Statement Analyzer")

with st.sidebar:
    st.header("Statement")
    upload = st.file_uploader("Upload PDF / CSV / Excel", type=["pdf","csv","xlsx","xls"])
    mode_label = st.selectbox(
        "Table detection mode",
        ["Auto (recommended)", "Smart text (auto-detect layout)",
         "Lattice (camelot — grid lines)", "Stream (camelot — whitespace)"],
    )
    mode_map = {
        "Auto (recommended)": "auto",
        "Smart text (auto-detect layout)": "smart_text",
        "Lattice (camelot — grid lines)": "lattice",
        "Stream (camelot — whitespace)": "stream",
    }
    detect_mode = mode_map[mode_label]
    tally = st.checkbox("Tally Output Mode")
    bank_account = st.text_input("Bank Account Name as per Tally",
                                  value=st.session_state.bank_account,
                                  disabled=not tally)
    if tally: st.session_state.bank_account = bank_account

    if upload and st.button("Process Statement", type="primary"):
        suffix = Path(upload.name).suffix.lower()
        temp = Path("temp_statement" + suffix)
        temp.write_bytes(upload.getbuffer())
        try:
            if suffix == ".pdf":
                df, meta = parse_pdf(str(temp), mode=detect_mode)
            elif suffix == ".csv":
                df, meta = normalize(pd.read_csv(temp)), {"method":"CSV","validation":{"score":100}}
            else:
                df, meta = normalize(pd.read_excel(temp)), {"method":"Excel","validation":{"score":100}}

            df["Head"] = df["Particulars"].map(lambda x: classify(x, st.session_state.rules))
            if tally:
                df = apply_tally(df, st.session_state.accounts,
                                 st.session_state.journal_heads,
                                 st.session_state.bank_account)
            st.session_state.df = df
            score = meta.get("validation",{}).get("score",100)
            add(upload.name, len(df), meta.get("method","Unknown"), score)
            st.success(f"{len(df)} transactions processed")
            st.caption(f"Method: {meta.get('method')} | Validation: {score}%")
            if meta.get("layout"):
                st.caption(f"Detected: {meta['layout'].get('name')} ({meta['layout'].get('confidence')}%)")
            if meta.get("page"):
                st.caption(f"Header matched on page {meta['page']}")
            dbg = meta.get("debug")
            if dbg and len(df) == 0:
                st.warning(
                    f"Raw columns detected: {dbg.get('raw_columns')}\n\n"
                    f"Matched columns → Date: `{dbg['matched']['date']}` | "
                    f"Particulars: `{dbg['matched']['particulars']}` | "
                    f"Debit: `{dbg['matched']['debit']}` | Credit: `{dbg['matched']['credit']}`\n\n"
                    f"Raw rows before date filter: {dbg['raw_rows']} | "
                    f"Rows that failed date parse: {dbg['date_parse_fail']}\n\n"
                    f"Sample raw date values: {dbg['sample_raw_dates']}"
                )
        except Exception as e:
            st.error(f"Processing failed: {e}")

dashboard, history, rules_tab = st.tabs(["📊 Dashboard","📜 History","⚙️ Rules"])

with dashboard:
    df = st.session_state.df
    if df.empty:
        st.info("Upload and process a statement from the sidebar.")
    else:
        s = summary(df)
        cols = st.columns(5)
        cols[0].metric("Transactions", s["transactions"])
        cols[1].metric("Income", f"₹{s['income']:,.2f}")
        cols[2].metric("Expenses", f"₹{s['expenses']:,.2f}")
        cols[3].metric("Net Cash Flow", f"₹{s['net']:,.2f}")
        cols[4].metric("Savings Rate", f"{s['savings_rate']:.1f}%")

        m = monthly(df)
        if not m.empty:
            st.subheader("Monthly Cash Flow")
            st.line_chart(m.set_index("Month")[["Income","Expenses"]])

        st.subheader("Transactions")
        edited = st.data_editor(df, use_container_width=True, num_rows="dynamic")
        st.session_state.df = edited

        st.download_button("⬇️ Download Excel",
                           excel_bytes(edited),
                           "bank_statement_analysis.xlsx",
                           "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

with history:
    st.subheader("Processing History")
    rows = all_history()
    hist = pd.DataFrame(rows, columns=["File","Processed At","Transactions","Method","Confidence"])
    if not hist.empty:
        st.dataframe(hist, use_container_width=True, hide_index=True)
    else:
        st.info("No history yet.")

with rules_tab:
    st.subheader("Heads")
    st.caption("Keywords determine the Head. Changes apply to the next processing run.")
    for head in list(st.session_state.rules):
        text = st.text_input(head, ", ".join(st.session_state.rules[head]), key=f"head_{head}")
        st.session_state.rules[head] = [x.strip() for x in text.split(",") if x.strip()]

    st.divider()
    st.subheader("Add Head")
    c1,c2,c3 = st.columns([1,2,1])
    with c1: new_head = st.text_input("Head", key="new_head")
    with c2: new_kw = st.text_input("Keywords (comma separated)", key="new_kw")
    with c3:
        if st.button("Add Head"):
            if new_head:
                st.session_state.rules[new_head] = [x.strip() for x in new_kw.split(",") if x.strip()]
                st.rerun()

    st.divider()
    st.subheader("Accounts")
    for head in st.session_state.rules:
        st.session_state.accounts[head] = st.text_input(
            f"Tally Account for {head}",
            st.session_state.accounts.get(head, head),
            key=f"account_{head}"
        )

    st.divider()
    st.subheader("Journal")
    journal_text = st.text_area("Journal Heads (comma separated)",
                                ", ".join(st.session_state.journal_heads))
    st.session_state.journal_heads = [x.strip() for x in journal_text.split(",") if x.strip()]

    st.divider()
    st.subheader("Bank Account")
    st.write("Tally bank account name:", st.session_state.bank_account or "Not set")
