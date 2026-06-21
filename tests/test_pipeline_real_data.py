"""
Real-data smoke test: embed real chunks from sample_chunks.json, retrieve, generate answer.
Run directly: python3 tests/test_pipeline_real_data.py
"""
import sys
import os
import json

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.retrieval.embedder import embed_chunks
from app.retrieval.retriever import retrieve
from app.retrieval.llm import generate_answer

CHUNKS_PATH = "data/sample_chunks.json"

if __name__ == "__main__":
    with open(CHUNKS_PATH, "r") as f:
        real_chunks = json.load(f)

    print(f"Loaded {len(real_chunks)} real chunks.")

    print("Embedding real chunks...")
    count = embed_chunks(real_chunks)
    print(f"Embedded {count} chunks.")

    query = "How does a Station House Officer assign a duty officer?"
    print(f"\nQuery: {query}")
    chunks = retrieve(query, top_k=3)
    print(f"Retrieved {len(chunks)} chunks.")
    for c in chunks:
        print(f"  - score={c['score']:.3f} | {c.get('document_title')} | {c['text'][:80]}...")

    print("\nGenerating answer via Ollama (llama3)...")
    answer = generate_answer(query, chunks)
    print(f"\nAnswer:\n{answer}")
