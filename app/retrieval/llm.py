"""
LLM layer: takes a user query + retrieved chunks, calls local Ollama (llama3),
returns a generated answer grounded in the retrieved context.
"""
import ollama

MODEL_NAME = "llama3"


def build_prompt(query: str, chunks: list[dict]) -> str:
    context_blocks = []
    for c in chunks:
        source = c.get("document_title", "Unknown source")
        page = c.get("page_number", "?")
        context_blocks.append(f"[{source}, page {page}]\n{c['text']}")
    context = "\n\n---\n\n".join(context_blocks)
    return f"""You are a helpful assistant. Answer the question using ONLY the context below.
If the context doesn't contain the answer, say you don't know.

Context:
{context}

Question: {query}

Answer:"""


def generate_answer(query: str, chunks: list[dict]) -> str:
    prompt = build_prompt(query, chunks)
    response = ollama.chat(model=MODEL_NAME, messages=[{"role": "user", "content": prompt}])
    return response["message"]["content"]
