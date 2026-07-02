"""
FastAPI app exposing the RAG pipeline: query -> retrieve -> generate answer.
"""
import json, os, re
from fastapi import FastAPI
from pydantic import BaseModel
from app.retrieval.retriever import retrieve
from app.retrieval.llm import generate_answer

app = FastAPI(title="dp-dynamic-rag")

_STANDING_ORDERS_PATH = "data/standing_orders.json"

_BROWSE_PATTERNS = re.compile(
    r"\b(show|list|give|tell|what are|display|see|view|browse)\b.{0,30}"
    r"\bstanding\s*order",
    re.IGNORECASE,
)
_BROWSE_SHORT = re.compile(
    r"^standing\s*orders?\s*$",
    re.IGNORECASE,
)
_RECENT_PATTERN = re.compile(
    r"\b(recent|latest|new|newest)\b.{0,20}\bstanding\s*order",
    re.IGNORECASE,
)


def _is_browse_query(query: str) -> bool:
    q = query.strip()
    return bool(_BROWSE_PATTERNS.search(q) or _BROWSE_SHORT.match(q) or _RECENT_PATTERN.search(q))


def _browse_standing_orders() -> str:
    if not os.path.exists(_STANDING_ORDERS_PATH):
        return "Standing orders data is not available right now."
    with open(_STANDING_ORDERS_PATH) as f:
        orders = json.load(f)

    # Sort by date descending; entries with missing/malformed dates go last
    def _date_key(o):
        d = o.get("date") or ""
        return d if re.match(r"\d{4}-\d{2}-\d{2}", d) else "0000-00-00"

    sorted_orders = sorted(orders, key=_date_key, reverse=True)
    top5 = sorted_orders[:5]

    lines = ["**5 most recent standing orders:**\n"]
    for o in top5:
        title = o.get("title", "Untitled")
        dt    = o.get("date", "date unknown")
        url   = o.get("pdf_url", "")
        lines.append(f"- **{title}** ({dt})  \n  [View PDF]({url})")

    lines.append(
        f"\n*There are {len(orders)} standing orders in total — "
        "ask me about a specific topic (e.g. 'missing person squad', "
        "'PCC procedure', 'arrest guidelines') and I'll pull the relevant one.*"
    )
    return "\n".join(lines)


class QueryRequest(BaseModel):
    query: str
    top_k: int = 5


class QueryResponse(BaseModel):
    answer: str
    sources: list[dict]


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/query", response_model=QueryResponse)
def query_endpoint(request: QueryRequest):
    # Stage 4B: fast browse path — no retrieval, no LLM
    if _is_browse_query(request.query):
        return QueryResponse(answer=_browse_standing_orders(), sources=[])

    # Normal RAG path — unchanged
    chunks = retrieve(request.query, top_k=request.top_k)
    answer = generate_answer(request.query, chunks)
    return QueryResponse(answer=answer, sources=chunks)
