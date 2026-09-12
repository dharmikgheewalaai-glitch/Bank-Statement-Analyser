import re
from config.layouts import LAYOUTS

def norm(value):
    return re.sub(r"\s+", " ", str(value).lower().strip())

def detect_layout(headers):
    headers = [norm(h) for h in headers if str(h).strip()]
    scores = {}
    for key, spec in LAYOUTS.items():
        hits = 0
        for group in spec["groups"]:
            if any(norm(v) in h or h in norm(v) for h in headers for v in group):
                hits += 1
        scores[key] = hits / len(spec["groups"])
    best = max(scores, key=scores.get)
    return {
        "format": best,
        "name": LAYOUTS[best]["name"],
        "confidence": round(scores[best] * 100, 1),
        "scores": {k: round(v*100, 1) for k,v in scores.items()}
    }
