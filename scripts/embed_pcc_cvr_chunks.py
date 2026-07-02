import sys, os, json
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from app.retrieval.embedder import embed_chunks

if __name__ == "__main__":
    input_file = sys.argv[1] if len(sys.argv) > 1 else "data/pcc_cvr_chunks.json"
    with open(input_file) as f:
        chunks = json.load(f)
    count = embed_chunks(chunks)
    print(f"Embedded {count} chunks from {input_file} into Qdrant.")
