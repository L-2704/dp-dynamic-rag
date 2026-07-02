"""
Interactive query tool — type questions, see retrieved chunks + LLM answer.
Run: python3 tests/ask.py
Type 'exit' to quit.
"""
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.retrieval.embedder import embed_chunks
from app.retrieval.retriever import retrieve
from app.retrieval.llm import generate_answer
import json

CHUNKS_PATH = "data/services_chunks.json"

if __name__ == "__main__":
    with open(CHUNKS_PATH, "r") as f:
        real_chunks = json.load(f)
    print(f"Embedding {len(real_chunks)} chunks (one-time, may take a few seconds)...")
    embed_chunks(real_chunks)
    print("Ready. Type your question (or 'exit' to quit).\n")

    while True:
        query = input("Q: ").strip()
        if query.lower() in ("exit", "quit"):
            break
        if not query:
            continue

        chunks = retrieve(query, top_k=3)
        print("\n--- Retrieved chunks ---")
        for c in chunks:
            print(f"  score={c['score']:.3f} | {c.get('document_title')} | {c['text'][:80]}...")

        answer = generate_answer(query, chunks)
        print(f"\n--- Answer ---\n{answer}\n")
