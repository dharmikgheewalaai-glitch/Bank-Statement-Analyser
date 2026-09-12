def summary(df):
    income = float(df["Credit"].sum())
    expenses = float(df["Debit"].sum())
    return {
        "transactions": len(df),
        "income": income,
        "expenses": expenses,
        "net": income-expenses,
        "savings_rate": ((income-expenses)/income*100) if income else 0
    }

def monthly(df):
    x = df.copy()
    x["Month"] = x["Date"].dt.to_period("M").astype(str)
    return x.groupby("Month", as_index=False).agg(Income=("Credit","sum"), Expenses=("Debit","sum"))
