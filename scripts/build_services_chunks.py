"""
scripts/build_services_chunks.py

Converts data/all_services.json (Delhi Police citizen services directory)
into chunks matching the same schema used by build_pcc_cvr_chunks.py,
so the existing embed pipeline can process both without modification.

Unlike PDF content, each service is already a self-contained unit —
no sub-chunking/splitting is performed. One service = one chunk.
"""

import json
import hashlib
from datetime import date
from pathlib import Path

INPUT_FILE = Path("data/all_services.json")
OUTPUT_FILE = Path("data/services_chunks.json")


def compute_hash(text: str) -> str:
    """Match the same hashing approach used for PCC/CVR chunks (sha256 hex)."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def service_to_text(service: dict) -> str:
    """
    Build the embeddable text for one service.
    Includes: name, description, steps, documents.
    Deliberately EXCLUDES the keywords array (not useful for embeddings,
    and would bloat/skew the vector).
    """
    parts = [service["name"], service["description"]]

    if service.get("steps"):
        parts.append("Steps:")
        parts.extend(f"- {s}" for s in service["steps"])

    if service.get("documents"):
        parts.append("Required documents:")
        parts.extend(f"- {d}" for d in service["documents"])

    return "\n".join(parts)


def build_chunk(service: dict) -> dict:
    text = service_to_text(service)

    return {
        # --- fields matching the existing pcc_cvr_chunks.json schema ---
        "category": "citizen_services",
        "source_type": "service_directory",
        "source_url": service.get("url"),
        "document_title": service.get("name"),
        "publish_date": None,
        "ingestion_date": str(date.today()),
        "content_hash": compute_hash(text),
        "page_number": None,
        "document_type": "service_info",
        "expiry_or_superseded_by": None,
        "text": text,

        # --- extra fields, additive only, used for routing/flow logic ---
        "service_id": service.get("id"),
        "requires_login": service.get("requires_login"),
    }


def main():
    with open(INPUT_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)

    services = data["services"]
    chunks = [build_chunk(s) for s in services]

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(chunks, f, indent=2, ensure_ascii=False)

    print(f"Loaded {len(services)} services")
    print(f"Wrote {len(chunks)} chunks to {OUTPUT_FILE}")
    print("\n--- Sample chunk[0] ---")
    print(json.dumps(chunks[0], indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()