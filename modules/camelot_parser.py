from pathlib import Path
import pandas as pd


def extract_with_camelot(path):
    """
    Secondary/fallback extractor.
    Camelot is imported lazily so CSV/Excel/text-first workflows do not fail
    just because Camelot is unavailable.
    """
    try:
        import camelot
    except Exception as e:
        return pd.DataFrame(), [f"Camelot unavailable: {e}"]

    frames = []
    errors = []

    for flavor in ("lattice", "stream"):
        try:
            tables = camelot.read_pdf(
                str(Path(path)),
                pages="all",
                flavor=flavor,
            )
            for table in tables:
                df = table.df
                if df is not None and not df.empty:
                    df.columns = df.iloc[0]
                    df = df[1:].reset_index(drop=True)
                    frames.append(df)
        except Exception as e:
            errors.append(f"{flavor}: {e}")

    if not frames:
        return pd.DataFrame(), errors

    return pd.concat(frames, ignore_index=True), errors
