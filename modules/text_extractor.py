import fitz

def extract_pages(path):
    doc = fitz.open(path)
    result = []
    for n, page in enumerate(doc, 1):
        result.append({
            "page": n,
            "text": page.get_text("text"),
            "words": page.get_text("words")
        })
    return result
