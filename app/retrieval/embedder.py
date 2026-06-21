"""
Embedder: takes chunks (matching CONTRACT.md schema) and stores them in Qdrant.
"""
from qdrant_client import QdrantClient
from qdrant_client.models import VectorParams, Distance, PointStruct
from sentence_transformers import SentenceTransformer
import hashlib

EMBEDDING_MODEL_NAME = "all-MiniLM-L6-v2"
QDRANT_PATH = "data/qdrant_db"
COLLECTION_NAME = "dp_dynamic_rag"

_model = None
_client = None


def get_model():
    global _model
    if _model is None:
        _model = SentenceTransformer(EMBEDDING_MODEL_NAME)
    return _model


def get_client():
    global _client
    if _client is None:
        _client = QdrantClient(path=QDRANT_PATH)
    return _client


def ensure_collection(vector_size: int):
    client = get_client()
    existing = [c.name for c in client.get_collections().collections]
    if COLLECTION_NAME not in existing:
        client.create_collection(
            collection_name=COLLECTION_NAME,
            vectors_config=VectorParams(size=vector_size, distance=Distance.COSINE),
        )


def chunk_to_point_id(chunk: dict) -> int:
    key = f"{chunk.get('content_hash')}-{chunk.get('page_number')}"
    return int(hashlib.sha256(key.encode()).hexdigest()[:16], 16)


def embed_chunks(chunks: list[dict]) -> int:
    if not chunks:
        return 0
    model = get_model()
    texts = [c["text"] for c in chunks]
    vectors = model.encode(texts, show_progress_bar=False)
    ensure_collection(vector_size=len(vectors[0]))
    client = get_client()
    points = [
        PointStruct(id=chunk_to_point_id(chunk), vector=vector.tolist(), payload=chunk)
        for chunk, vector in zip(chunks, vectors)
    ]
    client.upsert(collection_name=COLLECTION_NAME, points=points)
    return len(points)
