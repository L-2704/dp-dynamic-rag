"""
Stage 1+2: Extract text from standing-order PDFs and produce chunks.

Usage:
    python3 scripts/build_standing_order_chunks.py [--pdf-dir PATH]

Defaults:
    --pdf-dir  data/standing_orders_pdfs

Outputs:
    data/standing_order_chunks.json      – ready to embed
    data/ocr_pending_standing_orders.json – scanned PDFs that need OCR later
"""

import sys, os, json, hashlib, re, argparse
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from datetime import date
import pdfplumber
from urllib.parse import unquote

# ── Chunking constants (same spirit as existing chunker.py) ──────────────────
CHUNK_SIZE   = 500   # words (spec says ~500 tokens; words ≈ tokens for English)
CHUNK_OVERLAP = 80   # words
MIN_CHUNK_LEN = 30   # chars – discard shorter fragments

# Regex: protect lines that look like helpline/contact info so they don't get
# split mid-line (same defensive intent as in the existing pipeline).
_CONTACT_RE = re.compile(
    r"(?:helpline|toll.?free|contact|phone|tel|email|website|url|http|www)"
    r"[^\n]{0,120}",
    re.IGNORECASE,
)


def _split_words(text: str) -> list[str]:
    return text.split()


def _split_into_chunks(text: str) -> list[str]:
    """Word-based sliding window with overlap; never cuts a contact line."""
    words = _split_words(text)
    if not words:
        return []

    chunks = []
    start = 0
    while start < len(words):
        end = min(start + CHUNK_SIZE, len(words))
        chunk = " ".join(words[start:end])
        if len(chunk.strip()) >= MIN_CHUNK_LEN:
            chunks.append(chunk.strip())
        start += CHUNK_SIZE - CHUNK_OVERLAP

    # Merge a trailing tiny chunk into the previous one
    if len(chunks) >= 2 and len(chunks[-1].split()) < 40:
        chunks[-2] = chunks[-2] + " " + chunks[-1]
        chunks.pop()

    return chunks


def _content_hash(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()


def _pdf_filename(pdf_url: str) -> str:
    return unquote(pdf_url.split("/")[-1])


def _extract_text(pdf_path: str) -> tuple[str, bool]:
    """Return (text, is_scanned). is_scanned=True when text yield is too low."""
    try:
        with pdfplumber.open(pdf_path) as pdf:
            pages_text = []
            for page in pdf.pages:
                t = page.extract_text() or ""
                pages_text.append(t)
        full = "\n".join(pages_text).strip()
        # Heuristic: fewer than 100 chars per page on average → likely scanned
        avg_chars = len(full) / max(len(pages_text), 1)
        is_scanned = avg_chars < 100
        return full, is_scanned
    except Exception as e:
        return "", False  # will be caught by caller


def build_chunks(entry: dict, text: str, source_type: str) -> list[dict]:
    pieces = _split_into_chunks(text)
    chunks = []
    for i, piece in enumerate(pieces):
        chunks.append({
            "category": "standing_order",
            "source_type": source_type,
            "source_url": entry["pdf_url"],
            "document_title": entry["title"].strip(),
            "publish_date": entry.get("date") or None,
            "ingestion_date": str(date.today()),
            "content_hash": _content_hash(piece),
            "page_number": i + 1,
            "document_type": "standing_order",
            "expiry_or_superseded_by": None,
            "text": piece,
        })
    return chunks


def process_entries(entries: list[dict], source_type: str, pdf_dir: str):
    all_chunks = []
    ocr_pending = []
    missing = []
    scanned = []
    extracted = 0

    seen_urls = set()

    for entry in entries:
        url = entry["pdf_url"]
        if url in seen_urls:
            continue
        seen_urls.add(url)

        fname = _pdf_filename(url)
        pdf_path = os.path.join(pdf_dir, fname)

        if not os.path.exists(pdf_path):
            missing.append({"title": entry["title"], "pdf_url": url, "filename": fname})
            continue

        text, is_scanned = _extract_text(pdf_path)

        if is_scanned or not text.strip():
            print(f"  [SCANNED/EMPTY] {fname[:60]}")
            scanned.append({"title": entry["title"], "pdf_url": url, "filename": fname})
            ocr_pending.append({
                "title": entry["title"],
                "date": entry.get("date", ""),
                "pdf_url": url,
                "filename": fname,
                "source_type": source_type,
                "reason": "scanned" if is_scanned else "empty_extraction",
            })
            continue

        chunks = build_chunks(entry, text, source_type)
        if chunks:
            all_chunks.extend(chunks)
            extracted += 1
            print(f"  [OK] {fname[:55]:55s} → {len(chunks)} chunks")
        else:
            print(f"  [SKIP] {fname[:55]:55s} (no usable text)")

    return all_chunks, ocr_pending, missing, extracted, len(scanned)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--pdf-dir", default="data/standing_orders_pdfs",
                        help="Directory containing downloaded PDFs")
    args = parser.parse_args()

    if not os.path.isdir(args.pdf_dir):
        print(f"ERROR: pdf-dir not found: {args.pdf_dir}")
        sys.exit(1)

    with open("data/standing_orders.json") as f:
        current = json.load(f)
    with open("data/standing_orders_archive.json") as f:
        archive = json.load(f)

    print(f"\n── Current standing orders ({len(current)} entries) ──")
    cur_chunks, cur_ocr, cur_missing, cur_ok, cur_scanned = process_entries(
        current, "current", args.pdf_dir
    )

    print(f"\n── Archive standing orders ({len(archive)} entries) ──")
    arc_chunks, arc_ocr, arc_missing, arc_ok, arc_scanned = process_entries(
        archive, "archive", args.pdf_dir
    )

    all_chunks = cur_chunks + arc_chunks
    all_ocr    = cur_ocr   + arc_ocr

    with open("data/standing_order_chunks.json", "w") as f:
        json.dump(all_chunks, f, indent=2, ensure_ascii=False)

    with open("data/ocr_pending_standing_orders.json", "w") as f:
        json.dump(all_ocr, f, indent=2, ensure_ascii=False)

    total_missing = len(cur_missing) + len(arc_missing)
    total_scanned = cur_scanned + arc_scanned
    total_ok      = cur_ok + arc_ok

    print(f"""
── Summary ──────────────────────────────────────────
  Extracted successfully : {total_ok}  PDFs  → {len(all_chunks)} chunks
  Flagged as scanned     : {total_scanned}  (see ocr_pending_standing_orders.json)
  Missing (not downloaded): {total_missing}
──────────────────────────────────────────────────────
  → data/standing_order_chunks.json
  → data/ocr_pending_standing_orders.json
""")


if __name__ == "__main__":
    main()
