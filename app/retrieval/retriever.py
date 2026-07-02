"""
Retriever: given a query string, embeds it and searches Qdrant for top-k matches.

Query normalisation: Hinglish / colloquial / misspelled queries are rewritten to
clean English by the LLM before embedding, so the vector search is not confused
by phonetic spellings or code-switching ("gum hua mera fone" → "my phone is lost").

Re-ranking: combines cosine similarity (70%) with keyword overlap (30%) so that
distinguishing terms like "person" vs "phone" can separate semantically close results.
"""
import re
import ollama
from app.retrieval.embedder import get_model, get_client, COLLECTION_NAME
from app.retrieval.llm import MODEL_NAME

_NORMALISE_PROMPT = (
    "Rewrite the following query in clear, standard English. "
    "Fix spelling, translate Hinglish or Hindi, and resolve abbreviations. "
    "If it is already plain English, return it unchanged. "
    "Return only the rewritten query — no explanation, no quotes.\n\nQuery: "
)


def _normalise_query(query: str) -> str:
    try:
        resp = ollama.chat(
            model=MODEL_NAME,
            messages=[{"role": "user", "content": _NORMALISE_PROMPT + query}],
        )
        return resp["message"]["content"].strip()
    except Exception:
        return query  # fall back to raw query if Ollama is unavailable

_STOP = frozenset({
    # English
    "i", "my", "me", "the", "a", "an", "is", "it", "to", "of", "and", "or",
    "have", "has", "been", "was", "were", "be", "do", "did", "can", "could",
    "will", "would", "you", "your", "in", "on", "at", "for", "with", "by",
    "this", "that", "what", "how", "when", "where", "who",
    # Hinglish / Hindi romanised
    "mera", "meri", "mere", "hai", "hain", "tha", "thi", "the", "kya", "karo",
    "chahiye", "aur", "ya", "se", "ko", "ka", "ki", "ke", "ne", "nahi", "nhi",
    "ho", "hoga", "kar", "main", "mai", "hum", "aap", "vo", "woh", "yeh", "ye",
})


def _tokens(text: str) -> set[str]:
    return {w for w in re.findall(r"[a-z]+", text.lower())
            if w not in _STOP and len(w) > 2}


def _keyword_score(query_tokens: set[str], chunk: dict) -> float:
    chunk_text = chunk.get("document_title", "") + " " + chunk.get("text", "")
    chunk_tokens = _tokens(chunk_text)
    if not query_tokens or not chunk_tokens:
        return 0.0
    # Jaccard similarity on content words
    return len(query_tokens & chunk_tokens) / len(query_tokens | chunk_tokens)


def retrieve(query: str, top_k: int = 5) -> list[dict]:
    query = _normalise_query(query)
    model = get_model()
    client = get_client()
    query_vector = model.encode(query).tolist()
    # Fetch extra candidates so keyword re-ranking has room to reorder
    candidates = client.query_points(
        collection_name=COLLECTION_NAME,
        query=query_vector,
        limit=top_k * 3,
    ).points

    query_tokens = _tokens(query)
    ranked = []
    for point in candidates:
        emb = point.score
        kw = _keyword_score(query_tokens, point.payload)
        combined = 0.7 * emb + 0.3 * kw
        ranked.append({**point.payload, "score": combined})

    ranked.sort(key=lambda x: x["score"], reverse=True)
    return ranked[:top_k]
