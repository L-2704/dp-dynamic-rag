"""
OCR Stage: Convert scanned standing-order PDFs to text, chunk, and embed.

Usage:
    python3 scripts/ocr_standing_order_chunks.py [--pdf-dir PATH]

Reads:  data/ocr_pending_standing_orders.json
Writes: data/ocr_standing_order_chunks.json  (new chunks, appended to qdrant)
        data/ocr_still_pending.json           (any that still fail after OCR)
"""
import sys, os, json, hashlib, argparse
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from datetime import date
import pytesseract
from pdf2image import convert_from_path

# Reuse chunking logic from build_standing_order_chunks
from scripts.build_standing_order_chunks import _split_into_chunks, _content_hash, build_chunks

MIN_TEXT_LEN = 100  # chars — discard if OCR produced almost nothing


def ocr_pdf(pdf_path: str) -> str:
    images = convert_from_path(pdf_path, dpi=200)
    pages = []
    for img in images:
        text = pytesseract.image_to_string(img, lang="eng")
        pages.append(text)
    return "\n".join(pages).strip()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--pdf-dir", default="data/standing_orders_pdfs")
    args = parser.parse_args()

    with open("data/ocr_pending_standing_orders.json") as f:
        pending = json.load(f)

    all_chunks = []
    still_pending = []
    ok = fail = 0

    for i, entry in enumerate(pending, 1):
        fname = entry["filename"]
        pdf_path = os.path.join(args.pdf_dir, fname)

        if not os.path.exists(pdf_path):
            print(f"  [MISSING] {fname}")
            still_pending.append({**entry, "reason": "file_not_found"})
            continue

        print(f"  [{i}/{len(pending)}] OCR: {fname[:55]}", end=" ... ", flush=True)
        try:
            text = ocr_pdf(pdf_path)
        except Exception as e:
            print(f"ERROR: {e}")
            still_pending.append({**entry, "reason": f"ocr_error: {e}"})
            fail += 1
            continue

        if len(text) < MIN_TEXT_LEN:
            print(f"too short ({len(text)} chars)")
            still_pending.append({**entry, "reason": "ocr_too_short"})
            fail += 1
            continue

        chunks = build_chunks(entry, text, entry.get("source_type", "current"))
        if chunks:
            all_chunks.extend(chunks)
            ok += 1
            print(f"{len(chunks)} chunks")
        else:
            print("no chunks")
            still_pending.append({**entry, "reason": "no_chunks"})
            fail += 1

    with open("data/ocr_standing_order_chunks.json", "w") as f:
        json.dump(all_chunks, f, indent=2, ensure_ascii=False)

    with open("data/ocr_still_pending.json", "w") as f:
        json.dump(still_pending, f, indent=2, ensure_ascii=False)

    print(f"""
── OCR Summary ──────────────────────────────────────
  Succeeded : {ok}  PDFs → {len(all_chunks)} chunks
  Failed     : {fail}
──────────────────────────────────────────────────────
  → data/ocr_standing_order_chunks.json
  → data/ocr_still_pending.json
""")


if __name__ == "__main__":
    main()
