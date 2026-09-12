import re
import pandas as pd
from .layout_detector import detect_layout

DATE_RE = re.compile(r"\b(?:\d{1,2}[-/.]\d{1,2}[-/.]\d{2,4}|\d{1,2}\s+[A-Za-z]{3,9}\s+\d{2,4})\b")

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
