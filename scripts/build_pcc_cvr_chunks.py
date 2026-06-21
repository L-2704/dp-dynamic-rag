import sys, os, json
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from app.ingestion.chunker import chunk_documents

if __name__ == "__main__":
    pcc_chunks = chunk_documents("data/manual_pdfs/UserManual_PCC.pdf", "pcc_cvr", "PCC User Manual")
    cvr_chunks = chunk_documents("data/manual_pdfs/UserManual_CVR.pdf", "pcc_cvr", "CVR User Manual")

    all_chunks = pcc_chunks + cvr_chunks
    print(f"PCC chunks: {len(pcc_chunks)}, CVR chunks: {len(cvr_chunks)}, total: {len(all_chunks)}")

    os.makedirs("data", exist_ok=True)
    with open("data/pcc_cvr_chunks.json", "w") as f:
        json.dump(all_chunks, f, indent=2)
    print("Saved to data/pcc_cvr_chunks.json")
