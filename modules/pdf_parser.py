import pandas as pd
from .text_extractor import extract_pages
from .table_detector import detect_text_table, detect_word_table
from .table_validator import validate_table
from .camelot_parser import extract_with_camelot
from .normalizer import normalize_debug

def _smart_text(path):
    """Word-position + regex-line text extraction only, no Camelot."""
    frames, detections = [], []
    for page in extract_pages(path):
        df, meta = detect_word_table(page.get("words", []))
        if df.empty:
            df, meta = detect_text_table(page["text"])
        if not df.empty:
            frames.append(df)
            detections.append(meta)
    if not frames:
        return pd.DataFrame(), {}, {}
    raw = pd.concat(frames, ignore_index=True)
    validation = validate_table(raw)
    layout = detections[0].get("layout", {})
    method = detections[0].get("method", "Smart text")
    return raw, validation, {"layout": layout, "method": method}

def _camelot(path, flavors):
    raw, errors = extract_with_camelot(path, flavors=flavors)
    validation = validate_table(raw)
    return raw, validation, {"camelot_errors": errors}

def parse_pdf(path, mode="auto"):
    """
    mode: "auto" (smart text, fallback to camelot both flavors)
          "smart_text" (word-position/text-line only, no camelot)
          "lattice" (camelot lattice only)
          "stream" (camelot stream only)
    """
    if mode == "lattice":
        raw, validation, extra = _camelot(path, ("lattice",))
        out, debug = normalize_debug(raw)
        return out, {"method":"Camelot (lattice)","fallback":True,"layout":{},
                      "validation":validation,"debug":debug, **extra}

    if mode == "stream":
        raw, validation, extra = _camelot(path, ("stream",))
        out, debug = normalize_debug(raw)
        return out, {"method":"Camelot (stream)","fallback":True,"layout":{},
                      "validation":validation,"debug":debug, **extra}

    if mode == "smart_text":
        raw, validation, extra = _smart_text(path)
        out, debug = normalize_debug(raw) if not raw.empty else (pd.DataFrame(), {})
        return out, {"method":extra.get("method","Smart text"),"fallback":False,
                      "layout":extra.get("layout",{}),"validation":validation,"debug":debug}

    # auto: try smart text first, fall back to camelot (both flavors) if weak
    raw, validation, extra = _smart_text(path)
    if not raw.empty and validation.get("ok") and extra.get("layout",{}).get("confidence",0) >= 60:
        out, debug = normalize_debug(raw)
        return out, {"method":extra.get("method","Text-first"),"fallback":False,
                      "layout":extra.get("layout",{}),"validation":validation,"debug":debug}

    raw, validation, extra = _camelot(path, ("lattice","stream"))
    out, debug = normalize_debug(raw)
    return out, {"method":"Camelot fallback","fallback":True,"layout":{},
                  "validation":validation,"debug":debug, **extra}
