"""
LLM layer: takes a user query + retrieved chunks, calls local Ollama (llama3),
returns a generated answer grounded in the retrieved context.
"""
import ollama

MODEL_NAME = "llama3"


def _has_standing_orders(chunks: list[dict]) -> bool:
    return any(c.get("category") == "standing_order" for c in chunks)


def build_prompt(query: str, chunks: list[dict]) -> str:
    so_present = _has_standing_orders(chunks)

    # Sort standing-order chunks newest-first within the context so the LLM
    # naturally reads the most current version first.
    def _sort_key(c):
        if c.get("category") == "standing_order":
            return c.get("publish_date") or "0000-00-00"
        return "9999-99-99"  # keep non-SO chunks at the end

    ordered = sorted(chunks, key=_sort_key, reverse=True)

    context_blocks = []
    for c in ordered:
        if c.get("category") == "standing_order":
            title = c.get("document_title", "Unknown")
            dt    = c.get("publish_date") or "date unknown"
            url   = c.get("source_url", "")
            label = f"[Standing Order: {title!r}, dated {dt}, PDF: {url}]"
        else:
            source = c.get("document_title", "Unknown source")
            page   = c.get("page_number")
            label  = f"[{source}, page {page}]" if page else f"[{source}]"
        context_blocks.append(f"{label}\n{c['text']}")

    context = "\n\n---\n\n".join(context_blocks)

    if so_present:
        citation_instruction = (
            "When your answer draws on a Standing Order, you MUST cite it inline: "
            "include the order title, its date, and the PDF link. "
            "If multiple standing orders cover the same topic, prefer the most recent one "
            "and note if an older order may have been superseded."
        )
    else:
        citation_instruction = ""

    return f"""You are a helpful Delhi Police assistant. The content below has already been retrieved as relevant to the user's query — use it to answer helpfully and directly.

Tell the user what applies, what it means, and how to act on it. Respond in the same language the user wrote in. Only say you cannot help if the retrieved content is genuinely unrelated to what the user is asking.
{citation_instruction}

Retrieved content:
{context}

User query: {query}

Answer:"""


def generate_answer(query: str, chunks: list[dict]) -> str:
    prompt = build_prompt(query, chunks)
    response = ollama.chat(model=MODEL_NAME, messages=[{"role": "user", "content": prompt}])
    return response["message"]["content"]
