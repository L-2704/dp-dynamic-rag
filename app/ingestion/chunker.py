import hashlib
from datetime import date
from app.ingestion.loader import extract_pages

CHUNK_SIZE = 800
CHUNK_OVERLAP = 100

def split_text(text: str, size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP) -> list[str]:
    chunks = []
    start = 0
    while start < len(text):
        end = start + size
        chunks.append(text[start:end])
        start += size - overlap
    return chunks

def make_chunk(text, page_number, category, document_title, source_url, document_type="manual_guide"):
    content_hash = hashlib.sha256(text.encode()).hexdigest()
    return {
        "category": category,
        "source_type": "manual",
        "source_url": source_url,
        "document_title": document_title,
        "publish_date": None,
        "ingestion_date": str(date.today()),
        "content_hash": content_hash,
        "page_number": page_number,
        "document_type": document_type,
        "expiry_or_superseded_by": None,
        "text": text.strip(),
    }

def chunk_documents(pdf_path: str, category: str, document_title: str) -> list[dict]:
    pages = extract_pages(pdf_path)
    all_chunks = []
    for page in pages:
        for piece in split_text(page["text"]):
            if len(piece.strip()) < 20:
                continue
            all_chunks.append(make_chunk(piece, page["page_number"], category, document_title, pdf_path))
    return all_chunks
