"""
Manual smoke test: embed fake chunks, retrieve, generate answer.
Run directly: python3 tests/test_pipeline_manual.py
"""
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.retrieval.embedder import embed_chunks
from app.retrieval.retriever import retrieve
from app.retrieval.llm import generate_answer
from tests.fixtures.fake_chunks import FAKE_CHUNKS

if __name__ == "__main__":
    print("Embedding fake chunks...")
    count = embed_chunks(FAKE_CHUNKS)
    print(f"Embedded {count} chunks.")

    query = "How many leave days do employees get?"
    print(f"\nQuery: {query}")
    chunks = retrieve(query, top_k=2)
    print(f"Retrieved {len(chunks)} chunks.")

    print("\nGenerating answer via Ollama (llama3)...")
    answer = generate_answer(query, chunks)
    print(f"\nAnswer:\n{answer}")
