import pandas as pd
from .text_extractor import extract_pages
from .table_detector import build_grid_from_words, detect_text_table
from .camelot_parser import extract_with_camelot
from .transaction_extractor import table_to_transactions

def _txns_to_df(txns):
    cols = ["Date","Particulars","Debit","Credit","Head","Balance","Page"]
    if not txns:
        return pd.DataFrame(columns=cols)
    df = pd.DataFrame(txns)
    df["Date"] = pd.to_datetime(df["Date"], errors="coerce", dayfirst=True)
    parse_fail = int(df["Date"].isna().sum())
    df = df.dropna(subset=["Date"]).reset_index(drop=True)
    return df, parse_fail

def _grid_for_page(page):
    grid = build_grid_from_words(page.get("words", []))
    if grid:
        return grid, "word-position"
    df_legacy, meta_legacy = detect_text_table(page["text"])
    if not df_legacy.empty:
        grid = [list(df_legacy.columns)] + df_legacy.astype(str).values.tolist()
        return grid, "line-regex"
    return [], None

def _smart_text(path, rules=None):
    all_txns, pages_used, methods, raw_grids = [], [], set(), []
    for pno, page in enumerate(extract_pages(path), 1):
        grid, method = _grid_for_page(page)
        if grid:
            raw_grids.append((pno, grid))
        if grid:
            txns = table_to_transactions(grid, page_no=pno, rules=rules)
            if txns:
                all_txns.extend(txns)
                pages_used.append(pno)
                if method:
                    methods.add(method)
    out, parse_fail = _txns_to_df(all_txns)
    debug = {
        "raw_columns": raw_grids[0][1][0] if raw_grids else None,
        "pages_with_table": [p for p, _ in raw_grids],
        "pages_with_transactions": pages_used,
        "raw_rows": len(all_txns),
        "date_parse_fail": parse_fail,
    }
    label = "Smart text (" + "+".join(sorted(methods)) + ")" if methods else "Smart text"
    return out, {"method": label, "fallback": False, "debug": debug,
                 "page": pages_used[0] if pages_used else None}

def _camelot(path, flavors, label, rules=None):
    raw, errors = extract_with_camelot(path, flavors=flavors)
    if raw.empty:
        return pd.DataFrame(columns=["Date","Particulars","Debit","Credit","Head","Balance","Page"]), {
            "method": label, "fallback": True, "camelot_errors": errors,
            "debug": {"raw_columns": None, "raw_rows": 0, "date_parse_fail": 0}
        }
    grid = [list(raw.columns)] + raw.astype(str).values.tolist()
    txns = table_to_transactions(grid, rules=rules)
    out, parse_fail = _txns_to_df(txns)
    debug = {"raw_columns": grid[0], "raw_rows": len(txns), "date_parse_fail": parse_fail}
    return out, {"method": label, "fallback": True, "camelot_errors": errors, "debug": debug}

def parse_pdf(path, mode="auto", rules=None):
    """
    mode: "auto" (smart text, fallback to camelot both flavors)
          "smart_text" (word-position/text-line grid only, no camelot)
          "lattice" (camelot lattice only)
          "stream" (camelot stream only)
    """
    if mode == "lattice":
        return _camelot(path, ("lattice",), "Camelot (lattice)", rules)
    if mode == "stream":
        return _camelot(path, ("stream",), "Camelot (stream)", rules)
    if mode == "smart_text":
        return _smart_text(path, rules)

    out, meta = _smart_text(path, rules)
    if not out.empty:
        return out, meta
    return _camelot(path, ("lattice", "stream"), "Camelot fallback", rules)
