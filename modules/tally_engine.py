def apply_tally(df, accounts, journal_heads, bank_account_name):
    out = df.copy()
    out["v-Type"] = ""
    out["Accounts"] = ""
    out["Bank Name"] = ""

    journal = {str(x).strip().lower() for x in journal_heads}

    for i, row in out.iterrows():
        head = str(row["Head"]).strip()
        debit, credit = float(row["Debit"] or 0), float(row["Credit"] or 0)
        low = head.lower()

        if low in journal:
            vtype = "Journal"
        elif "cash" in low:
            vtype = "Contra"
        elif debit > 0:
            vtype = "Payment"
        elif credit > 0:
            vtype = "Receipt"
        else:
            vtype = ""

        if "cash" in low:
            if debit > 0:
                account, bank = bank_account_name, "CASH"
            elif credit > 0:
                account, bank = "CASH", bank_account_name
            else:
                account, bank = accounts.get(head, head), bank_account_name
        else:
            account, bank = accounts.get(head, head), bank_account_name

        out.at[i,"v-Type"] = vtype
        out.at[i,"Accounts"] = account
        out.at[i,"Bank Name"] = bank
    return out
