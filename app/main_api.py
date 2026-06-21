"""
FastAPI app exposing the RAG pipeline: query -> retrieve -> generate answer.
"""
from fastapi import FastAPI
from pydantic import BaseModel
from app.retrieval.retriever import retrieve
from app.retrieval.llm import generate_answer

app = FastAPI(title="dp-dynamic-rag")


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
    chunks = retrieve(request.query, top_k=request.top_k)
    answer = generate_answer(request.query, chunks)
    return QueryResponse(answer=answer, sources=chunks)
