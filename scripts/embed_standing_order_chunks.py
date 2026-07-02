"""
Stage 3: Embed standing_order_chunks.json into Qdrant.
Usage:
    python3 scripts/embed_standing_order_chunks.py
"""
import sys, os, json
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from app.retrieval.embedder import embed_chunks

if __name__ == "__main__":
    input_file = sys.argv[1] if len(sys.argv) > 1 else "data/standing_order_chunks.json"
    if not os.path.exists(input_file):
        print(f"ERROR: {input_file} not found. Run build_standing_order_chunks.py first.")
        sys.exit(1)
    with open(input_file) as f:
        chunks = json.load(f)
    count = embed_chunks(chunks)
    print(f"Embedded {count} standing-order chunks from {input_file} into Qdrant.")
