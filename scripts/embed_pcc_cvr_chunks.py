import sys, os, json
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from app.retrieval.embedder import embed_chunks

if __name__ == "__main__":
    with open("data/pcc_cvr_chunks.json") as f:
        chunks = json.load(f)
    count = embed_chunks(chunks)
    print(f"Embedded {count} PCC/CVR chunks into Qdrant.")
