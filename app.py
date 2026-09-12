import streamlit as st
import pandas as pd
from pathlib import Path

from database.database import init, add, all_history, get_history_data, delete_history
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
    "bank_account": "",
    "source_filename": ""
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
                df, meta = parse_pdf(str(temp), mode=detect_mode, rules=st.session_state.rules)
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
            st.session_state.source_filename = upload.name
            score = meta.get("validation",{}).get("score", 100 if len(df) else 0)
            add(upload.name, len(df), meta.get("method","Unknown"), score,
                df.to_json(orient="records", date_format="iso"))
            st.success(f"{len(df)} transactions processed")
            st.caption(f"Method: {meta.get('method')}")
            if meta.get("page"):
                st.caption(f"Header matched on page {meta['page']}")
            dbg = meta.get("debug")
            if dbg and len(df) == 0:
                st.warning(
                    f"Raw columns detected: {dbg.get('raw_columns')}\n\n"
                    f"Pages with a table found: {dbg.get('pages_with_table')} | "
                    f"Pages that yielded transactions: {dbg.get('pages_with_transactions')}\n\n"
                    f"Rows extracted before date filter: {dbg.get('raw_rows')} | "
                    f"Rows that failed date parse: {dbg.get('date_parse_fail')}"
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
        edited = st.data_editor(df, width="stretch", num_rows="dynamic")
        st.session_state.df = edited

        out_name = Path(st.session_state.source_filename or "bank_statement_analysis").stem + ".xlsx"
        st.download_button("⬇️ Download Excel",
                           excel_bytes(edited),
                           out_name,
                           "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

with history:
    st.subheader("Processing History")
    rows = all_history()
    if not rows:
        st.info("No history yet.")
    else:
        hist = pd.DataFrame(rows, columns=["id","File","Processed At","Transactions","Method","Confidence"])
        header = st.columns([2.5,2,1,1.5,1,1,1])
        for col, label in zip(header, ["File","Processed At","Txns","Method","Conf.","",""]):
            col.markdown(f"**{label}**")
        for _, r in hist.iterrows():
            c = st.columns([2.5,2,1,1.5,1,1,1])
            c[0].write(r["File"])
            c[1].write(r["Processed At"])
            c[2].write(int(r["Transactions"]))
            c[3].write(r["Method"])
            c[4].write(f"{r['Confidence']}%")
            if c[5].button("Open", key=f"open_{r['id']}"):
                data = get_history_data(int(r["id"]))
                if data:
                    st.session_state.df = pd.read_json(data, orient="records")
                    st.session_state.source_filename = r["File"]
                    st.success(f"Loaded '{r['File']}' into Dashboard tab.")
                else:
                    st.warning("No saved data for this row (processed before this feature was added).")
            if c[6].button("🗑️ Delete", key=f"del_{r['id']}"):
                delete_history(int(r["id"]))
                st.rerun()

with rules_tab:
    st.subheader("Heads")
    st.caption("Keywords determine the Head. Edit keywords inline; rename or delete a Head with the buttons.")
    head_to_delete, head_to_rename = None, None
    for head in list(st.session_state.rules):
        c1, c2, c3, c4 = st.columns([2, 3, 1, 1])
        with c1:
            new_name = st.text_input("Head name", head, key=f"headname_{head}", label_visibility="collapsed")
        with c2:
            kw_text = st.text_input("Keywords", ", ".join(st.session_state.rules[head]),
                                     key=f"headkw_{head}", label_visibility="collapsed")
            st.session_state.rules[head] = [x.strip() for x in kw_text.split(",") if x.strip()]
        with c3:
            if st.button("Rename", key=f"headrename_{head}") and new_name and new_name != head:
                head_to_rename = (head, new_name)
        with c4:
            if st.button("🗑️ Delete", key=f"headdel_{head}"):
                head_to_delete = head

    if head_to_delete:
        st.session_state.rules.pop(head_to_delete, None)
        st.session_state.accounts.pop(head_to_delete, None)
        st.session_state.journal_heads = [h for h in st.session_state.journal_heads if h != head_to_delete]
        st.rerun()

    if head_to_rename:
        old, new = head_to_rename
        st.session_state.rules[new] = st.session_state.rules.pop(old)
        if old in st.session_state.accounts:
            st.session_state.accounts[new] = st.session_state.accounts.pop(old)
        st.session_state.journal_heads = [new if h == old else h for h in st.session_state.journal_heads]
        st.rerun()

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
    st.caption("Tally ledger name mapped from each key. Edit the value to rename; add extra keys as needed.")
    for head in st.session_state.rules:
        if head not in st.session_state.accounts:
            st.session_state.accounts[head] = head

    acc_to_delete = None
    for acc_key in list(st.session_state.accounts):
        c1, c2 = st.columns([4, 1])
        with c1:
            val = st.text_input(f"Account for '{acc_key}'", st.session_state.accounts[acc_key], key=f"acc_{acc_key}")
            st.session_state.accounts[acc_key] = val
        with c2:
            if acc_key not in st.session_state.rules and st.button("🗑️ Delete", key=f"accdel_{acc_key}"):
                acc_to_delete = acc_key
    if acc_to_delete:
        st.session_state.accounts.pop(acc_to_delete, None)
        st.rerun()

    st.markdown("**Add Account**")
    c1, c2 = st.columns([4, 1])
    with c1: new_acc_key = st.text_input("Key (Head name or custom ledger key)", key="new_acc_key")
    with c2:
        if st.button("Add Account"):
            if new_acc_key:
                st.session_state.accounts[new_acc_key] = new_acc_key
                st.rerun()

    st.divider()
    st.subheader("Journal")
    st.caption("Heads listed here get v-Type = Journal in Tally mode.")
    jh_to_delete = None
    if st.session_state.journal_heads:
        hc = st.columns([4,1])
        hc[0].markdown("**Head**")
        for jh in list(st.session_state.journal_heads):
            c1, c2 = st.columns([4,1])
            c1.write(jh)
            with c2:
                if st.button("🗑️ Delete", key=f"jhdel_{jh}"):
                    jh_to_delete = jh
    else:
        st.info("No journal heads yet.")
    if jh_to_delete:
        st.session_state.journal_heads.remove(jh_to_delete)
        st.rerun()

    st.markdown("**Add Journal Head**")
    options = [h for h in st.session_state.rules if h not in st.session_state.journal_heads]
    c1, c2 = st.columns([4,1])
    with c1:
        pick = st.selectbox("Head", options, key="journal_pick") if options else None
    with c2:
        if st.button("Add", key="add_journal"):
            if pick:
                st.session_state.journal_heads.append(pick)
                st.rerun()

    st.divider()
    st.subheader("Bank Account")
    st.write("Tally bank account name:", st.session_state.bank_account or "Not set")
