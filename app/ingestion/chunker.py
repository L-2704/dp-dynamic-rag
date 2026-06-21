import re
from datetime import date
from pathlib import Path

from app.core.config import ingestion_config
from app.ingestion.state_tracker import compute_hash

BASE_DIR = Path(__file__).resolve().parent.parent.parent
EXTRACTED_DIR = BASE_DIR / "data" / "extracted_text"

CHUNK_SIZE = ingestion_config.get("chunking", {}).get("chunk_size_tokens", 500)
CHUNK_OVERLAP = ingestion_config.get("chunking", {}).get("chunk_overlap_tokens", 80)
MIN_WORDS = 150

PROTECTED_PATTERN = re.compile(r"(helpline|contact|emergency)", re.IGNORECASE)


def _word_chunks(text: str, size: int, overlap: int):
    words = text.split()
    if not words:
        return []
    step = max(size - overlap, 1)
    chunks = []
    for i in range(0, len(words), step):
        chunk_words = words[i:i + size]
        if not chunk_words:
            break
        chunks.append(" ".join(chunk_words))
        if i + size >= len(words):
            break
    return chunks


def _is_toc_noise(block: str) -> bool:
    if not block:
        return True
    return block.count(".") / len(block) > 0.15


def _merge_small_chunks(chunks: list[str]) -> list[str]:
    merged, buffer = [], ""
    for chunk in chunks:
        if PROTECTED_PATTERN.search(chunk):
            if buffer:
                merged.append(buffer)
                buffer = ""
            merged.append(chunk)
            continue
        combined = (buffer + "\n\n" + chunk) if buffer else chunk
        if len(combined.split()) <= CHUNK_SIZE:
            buffer = combined
        else:
            if buffer:
                merged.append(buffer)
            buffer = chunk
        if len(buffer.split()) >= MIN_WORDS:
            merged.append(buffer)
            buffer = ""
    if buffer:
        merged.append(buffer)
    return merged


def _split_text(text: str):
    blocks = re.split(r"\n\s*\n", text)
    final_chunks = []
    for block in blocks:
        block = block.strip()
        if not block:
            continue
        if PROTECTED_PATTERN.search(block):
            final_chunks.append(block)
            continue
        if _is_toc_noise(block):
            continue
        if len(block.split()) <= CHUNK_SIZE:
            final_chunks.append(block)
        else:
            final_chunks.extend(_word_chunks(block, CHUNK_SIZE, CHUNK_OVERLAP))
    return _merge_small_chunks(final_chunks)


def chunk_documents() -> list[dict]:
    documents = ingestion_config.get("documents", {})
    all_chunks = []

    for category, doc in documents.items():
        text_path = EXTRACTED_DIR / f"{category}.txt"
        if not text_path.exists():
            continue

        with open(text_path, "r") as f:
            text = f.read()

        for chunk_text in _split_text(text):
            all_chunks.append({
                "category": category,
                "source_type": doc["source_type"],
                "source_url": doc.get("file_path") or doc.get("download_url"),
                "document_title": doc.get("document_title", category),
                "publish_date": None,
                "ingestion_date": date.today().isoformat(),
                "content_hash": compute_hash(chunk_text),
                "page_number": None,
                "document_type": doc.get("document_type", "form_guide"),
                "expiry_or_superseded_by": None,
                "text": chunk_text,
            })

    return all_chunks


if __name__ == "__main__":
    chunks = chunk_documents()
    print(f"Total chunks: {len(chunks)}")
    for c in chunks[:3]:
        print(c)

        