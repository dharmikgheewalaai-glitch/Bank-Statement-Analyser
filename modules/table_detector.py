import re
import pandas as pd
from .layout_detector import detect_layout

DATE_RE = re.compile(r"\b(?:\d{1,2}[-/.]\d{1,2}[-/.]\d{2,4}|\d{1,2}\s+[A-Za-z]{3,9}\s+\d{2,4})\b")

HEADER_KEYWORDS = [
    "date","description","details","narration","particulars","debit","credit",
    "withdrawal","deposit","balance","remarks","remark","serial","sr","cheque","chq"
]

def split_line(line):
    return [x.strip() for x in re.split(r"\s{2,}|\t+|\|", line.strip()) if x.strip()]

def detect_text_table(text):
    lines = [x for x in text.splitlines() if x.strip()]
    header_idx, header = None, None
    for i, line in enumerate(lines):
        parts = split_line(line)
        low = line.lower()
        hits = sum(k in low for k in [
            "date","description","details","narration","particulars","debit","credit",
            "withdrawal","deposit","balance","remarks","remark"
        ])
        if hits >= 3:
            header_idx, header = i, parts
            break
    if header is None:
        return pd.DataFrame(), {"reason":"table header not found"}

    detection = detect_layout(header)
    rows, current = [], []
    for line in lines[header_idx+1:]:
        parts = split_line(line)
        if DATE_RE.search(line):
            if current: rows.append(current)
            current = parts
        elif current:
            current.extend(parts)
    if current: rows.append(current)

    width = len(header)
    clean = []
    for row in rows:
        if len(row) >= width:
            clean.append(row[:width])
        elif len(row) >= 2:
            clean.append(row + [""]*(width-len(row)))
    df = pd.DataFrame(clean, columns=header[:width]) if clean else pd.DataFrame()
    return df, {"header":header, "layout":detection, "header_index":header_idx}


def _group_rows(words, y_eps=3):
    """Cluster words into physical lines by y0 proximity (real glyph coords,
    not reading-order text) then sort each line left-to-right by x0."""
    ws = sorted(words, key=lambda w: w[1])
    rows, cur, cur_y = [], [], None
    for w in ws:
        y = w[1]
        if cur and abs(y - cur_y) > y_eps:
            rows.append(cur)
            cur = []
        cur.append(w)
        cur_y = y
    if cur: rows.append(cur)
    for r in rows:
        r.sort(key=lambda w: w[0])
    rows.sort(key=lambda r: r[0][1])
    return rows


def _cluster_header_columns(header_row, col_gap=10):
    cols = []
    cur = {"label": header_row[0][4], "x0": header_row[0][0], "x1": header_row[0][2]}
    for w in header_row[1:]:
        gap = w[0] - cur["x1"]
        if gap > col_gap:
            cols.append(cur)
            cur = {"label": w[4], "x0": w[0], "x1": w[2]}
        else:
            cur["label"] += " " + w[4]
            cur["x1"] = max(cur["x1"], w[2])
    cols.append(cur)
    return cols


def build_grid_from_words(words):
    """Rebuild the page as a raw grid (list of row cell-lists), using the
    same word-position column clustering as detect_word_table, but WITHOUT
    doing header detection, row merging, or junk filtering ourselves —
    table_to_transactions() owns that (find_header_row + IGNORE_PATTERNS)."""
    if not words:
        return []
    rows = _group_rows(words)
    header_row = None
    for row in rows:
        low = " ".join(w[4] for w in row).lower()
        hits = sum(k in low for k in HEADER_KEYWORDS)
        if hits >= 3:
            header_row = row
            break
    if header_row is None:
        return []

    cols = _cluster_header_columns(header_row)
    if len(cols) < 3:
        return []

    boundaries = [float("-inf")]
    for a, b in zip(cols, cols[1:]):
        boundaries.append((a["x1"] + b["x0"]) / 2)
    boundaries.append(float("inf"))

    def col_index(cx):
        for i in range(len(boundaries) - 1):
            if boundaries[i] <= cx < boundaries[i + 1]:
                return i
        return len(cols) - 1

    grid = []
    for row in rows:
        cells = [""] * len(cols)
        for w in row:
            cx = (w[0] + w[2]) / 2
            idx = col_index(cx)
            cells[idx] = (cells[idx] + " " + w[4]).strip()
        grid.append(cells)
    return grid


def detect_word_table(words):
    """Primary extractor: reconstruct columns from PyMuPDF word bounding boxes
    instead of trusting whitespace-gap heuristics or Camelot's grid guess.
    Works when the PDF has real glyph positions but no double-space gaps or
    ruling lines (defeats both detect_text_table and Camelot lattice/stream)."""
    if not words:
        return pd.DataFrame(), {"reason": "no words on page"}

    rows = _group_rows(words)
    header_idx, header_row = None, None
    for i, row in enumerate(rows):
        low = " ".join(w[4] for w in row).lower()
        hits = sum(k in low for k in HEADER_KEYWORDS)
        if hits >= 3:
            header_idx, header_row = i, row
            break
    if header_row is None:
        return pd.DataFrame(), {"reason": "table header not found"}

    cols = _cluster_header_columns(header_row)
    if len(cols) < 3:
        return pd.DataFrame(), {"reason": "column clustering failed"}

    boundaries = [float("-inf")]
    for a, b in zip(cols, cols[1:]):
        boundaries.append((a["x1"] + b["x0"]) / 2)
    boundaries.append(float("inf"))

    def col_index(cx):
        for i in range(len(boundaries) - 1):
            if boundaries[i] <= cx < boundaries[i + 1]:
                return i
        return len(cols) - 1

    labels = [c["label"] for c in cols]
    detection = detect_layout(labels)

    records, current = [], None
    for row in rows[header_idx + 1:]:
        row_text = " ".join(w[4] for w in row)
        if DATE_RE.search(row_text):
            if current: records.append(current)
            current = [""] * len(cols)
        if current is None:
            continue
        for w in row:
            cx = (w[0] + w[2]) / 2
            idx = col_index(cx)
            current[idx] = (current[idx] + " " + w[4]).strip()
    if current: records.append(current)

    df = pd.DataFrame(records, columns=labels) if records else pd.DataFrame()
    return df, {"header": labels, "layout": detection, "header_index": header_idx, "method": "word-position"}
