import pdfplumber

def extract_pages(pdf_path: str) -> list[dict]:
    pages = []
    with pdfplumber.open(pdf_path) as pdf:
        for i, page in enumerate(pdf.pages, start=1):
            text = page.extract_text() or ""
            if len(text.strip()) < 50:
                continue
            pages.append({"page_number": i, "text": text})
    return pages
