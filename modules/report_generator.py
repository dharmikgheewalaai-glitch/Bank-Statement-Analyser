from io import BytesIO
import pandas as pd

def excel_bytes(df):
    output = BytesIO()
    with pd.ExcelWriter(output, engine="xlsxwriter") as writer:
        df.to_excel(writer, index=False, sheet_name="Transactions")
    return output.getvalue()
