import pandas as pd

def extract_with_camelot(path):
    import camelot
    frames, errors = [], []
    for flavor in ("lattice","stream"):
        try:
            tables = camelot.read_pdf(path, pages="all", flavor=flavor)
            frames.extend([t.df for t in tables if not t.df.empty])
        except Exception as exc:
            errors.append(f"{flavor}: {exc}")
    if not frames:
        raise RuntimeError("Camelot could not extract a usable table. " + " | ".join(errors))
    return pd.concat(frames, ignore_index=True), errors
