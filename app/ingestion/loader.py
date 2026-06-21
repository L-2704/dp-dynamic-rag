import json
import hashlib
from pathlib import Path
import pdfplumber

from app.core.config import ingestion_config
from app.ingestion.state_tracker import compute_hash, load_state, update_state

BASE_DIR = Path(__file__).resolve().parent.parent.parent
DATA_DIR = BASE_DIR / "data"
EXTRACTED_DIR = DATA_DIR / "extracted_text"
OCR_PENDING_PATH = DATA_DIR / "ocr_pending.json"

MIN_CHARS = ingestion_config.get("chunking", {}).get("min_chars_for_text_page", 50)


def _file_hash(path: Path) -> str:
    with open(path, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()


def _flag_scanned_page(category: str, page_num: int):
    pending = []
    if OCR_PENDING_PATH.exists():
        with open(OCR_PENDING_PATH, "r") as f:
            pending = json.load(f)
    if any(p["category"] == category and p["page"] == page_num for p in pending):
        return
    pending.append({"category": category, "page": page_num, "likely_scanned": True})
    with open(OCR_PENDING_PATH, "w") as f:
        json.dump(pending, f, indent=2)


def _extract_pdf_text(pdf_path: Path, category: str) -> str:
    pages_text = []
    with pdfplumber.open(pdf_path) as pdf:
        for i, page in enumerate(pdf.pages, start=1):
            text = page.extract_text() or ""
            if len(text.strip()) < MIN_CHARS:
                _flag_scanned_page(category, i)
                continue
            pages_text.append(text)
    return "\n\n".join(pages_text)


def load_documents():
    EXTRACTED_DIR.mkdir(parents=True, exist_ok=True)
    documents = ingestion_config.get("documents", {})
    state = load_state()

    for category, doc in documents.items():
        source_type = doc["source_type"]

        if source_type == "manual":
            pdf_path = BASE_DIR / doc["file_path"].lstrip("./")
            if not pdf_path.exists():
                print(f"[SKIP] {category}: file not found at {pdf_path}")
                update_state(category, "", "failed")
                continue
        elif source_type == "scraped":
            print(f"[SKIP] {category}: scraped loader not implemented yet")
            continue
        else:
            print(f"[SKIP] {category}: unknown source_type {source_type}")
            continue

        file_hash = _file_hash(pdf_path)
        prev = state.get(category, {})
        if prev.get("content_hash") == file_hash and prev.get("status") == "extracted":
            print(f"[SKIP] {category}: unchanged since last run")
            continue

        try:
            text = _extract_pdf_text(pdf_path, category)
            if not text.strip():
                update_state(category, file_hash, "skipped_needs_ocr")
                print(f"[OCR-NEEDED] {category}: no extractable text")
                continue

            out_path = EXTRACTED_DIR / f"{category}.txt"
            with open(out_path, "w") as f:
                f.write(text)

            update_state(category, file_hash, "extracted")
            print(f"[OK] {category}: extracted -> {out_path}")

        except Exception as e:
            update_state(category, "", "failed")
            print(f"[FAIL] {category}: {e}")


if __name__ == "__main__":
    load_documents()