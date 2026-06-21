"""
Retriever: given a query string, embeds it and searches Qdrant for top-k matches.
"""
from app.retrieval.embedder import get_model, get_client, COLLECTION_NAME


def retrieve(query: str, top_k: int = 5) -> list[dict]:
    model = get_model()
    client = get_client()
    query_vector = model.encode(query).tolist()
    results = client.query_points(
        collection_name=COLLECTION_NAME,
        query=query_vector,
        limit=top_k,
    ).points
    return [{**point.payload, "score": point.score} for point in results]
