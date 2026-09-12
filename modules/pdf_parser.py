import pandas as pd
from .text_extractor import extract_pages
from .table_detector import detect_text_table
from .table_validator import validate_table
from .camelot_parser import extract_with_camelot
from .normalizer import normalize

def parse_pdf(path):
    frames, detections = [], []
    for page in extract_pages(path):
        df, meta = detect_text_table(page["text"])
        if not df.empty:
            frames.append(df)
            detections.append(meta)

    if frames:
        raw = pd.concat(frames, ignore_index=True)
        validation = validate_table(raw)
        layout = detections[0].get("layout", {}) if detections else {}
        if validation["ok"] and layout.get("confidence", 0) >= 60:
            return normalize(raw), {
                "method":"Text-first",
                "fallback":False,
                "layout":layout,
                "validation":validation
            }

    raw, errors = extract_with_camelot(path)
    validation = validate_table(raw)
    return normalize(raw), {
        "method":"Camelot fallback",
        "fallback":True,
        "layout":{},
        "validation":validation,
        "camelot_errors":errors
    }
