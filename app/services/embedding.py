from functools import lru_cache

import chromadb
from chromadb.config import Settings as ChromaSettings
from dashscope import TextEmbedding
from http import HTTPStatus

from app.config import get_settings

COLLECTION_NAME = "recruitment_docs"


@lru_cache
def _get_client() -> chromadb.PersistentClient:
    settings = get_settings()
    return chromadb.PersistentClient(
        path=settings.chroma_path,
        settings=ChromaSettings(anonymized_telemetry=False),
    )


def _get_collection():
    client = _get_client()
    return client.get_or_create_collection(
        name=COLLECTION_NAME,
        metadata={"hnsw:space": "cosine"},
    )


def _embed_texts(texts: list[str]) -> list[list[float]]:
    settings = get_settings()
    from app.services.llm import _ensure_api_key

    _ensure_api_key()
    response = TextEmbedding.call(
        model=settings.qwen_embedding_model,
        input=texts,
    )
    if response.status_code != HTTPStatus.OK:
        raise RuntimeError(f"Embedding API error: {response.code} - {response.message}")
    embeddings = [item["embedding"] for item in response.output["embeddings"]]
    return embeddings


def _doc_id(prefix: str, entity_id: int) -> str:
    return f"{prefix}_{entity_id}"


def upsert_job_embedding(job_id: int, text: str) -> None:
    collection = _get_collection()
    doc_id = _doc_id("job", job_id)
    embedding = _embed_texts([text[:8000]])[0]
    collection.upsert(
        ids=[doc_id],
        embeddings=[embedding],
        documents=[text[:8000]],
        metadatas=[{"type": "job", "entity_id": job_id}],
    )


def upsert_resume_embedding(resume_id: int, text: str) -> None:
    collection = _get_collection()
    doc_id = _doc_id("resume", resume_id)
    embedding = _embed_texts([text[:8000]])[0]
    collection.upsert(
        ids=[doc_id],
        embeddings=[embedding],
        documents=[text[:8000]],
        metadatas=[{"type": "resume", "entity_id": resume_id}],
    )


def semantic_similarity(job_id: int, resume_id: int, resume_text: str) -> float:
    collection = _get_collection()
    job_doc_id = _doc_id("job", job_id)
    try:
        job_data = collection.get(ids=[job_doc_id], include=["embeddings"])
        embeddings = job_data.get("embeddings") or []
        if not embeddings or embeddings[0] is None:
            return 50.0
        job_embedding = [float(x) for x in embeddings[0]]
    except Exception:
        return 50.0

    resume_embedding = [float(x) for x in _embed_texts([resume_text[:8000]])[0]]
    # Cosine similarity for normalized vectors
    dot = sum(a * b for a, b in zip(job_embedding, resume_embedding))
    norm_a = sum(a * a for a in job_embedding) ** 0.5
    norm_b = sum(b * b for b in resume_embedding) ** 0.5
    if norm_a == 0 or norm_b == 0:
        return 0.0
    similarity = dot / (norm_a * norm_b)
    return max(0.0, min(100.0, similarity * 100))


def build_summary_text(structured_json: str, summary: str) -> str:
    return summary or structured_json
