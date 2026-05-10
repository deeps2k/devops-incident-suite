import os
from typing import Any

import chromadb
from chromadb.api.types import EmbeddingFunction
from dotenv import load_dotenv

from utils.embeddings import get_embedding_model

load_dotenv()


class _LangChainEmbeddingFn(EmbeddingFunction):
    """Adapter so Chroma calls the same OpenAI-compatible embeddings as the app."""

    def __init__(self, embedder: Any) -> None:
        self._embedder = embedder

    def __call__(self, input: list) -> list:
        return self._embedder.embed_documents(list(input))


def _persist_dir() -> str:
    return os.getenv("CHROMA_PERSIST_DIR", os.path.join("data", "chroma"))


def _collection_name() -> str:
    return os.getenv("CHROMA_COLLECTION_NAME", "incident_resolutions")


def get_collection():
    """Return Chroma collection with LangChain-backed embeddings, or None if not configured."""
    embedder = get_embedding_model()
    if embedder is None:
        return None

    os.makedirs(_persist_dir(), exist_ok=True)
    client = chromadb.PersistentClient(path=_persist_dir())
    ef = _LangChainEmbeddingFn(embedder)
    return client.get_or_create_collection(
        name=_collection_name(),
        embedding_function=ef,
        metadata={"hnsw:space": "cosine"},
    )


def search_similar(query: str, k: int = 5) -> list[dict[str, Any]]:
    """Return top-k chunks with text and metadata; empty list if KB unavailable."""
    q = query.strip()
    if not q:
        return []

    # RAG is optional: Chroma init, disk, embeddings, or query must not break remediation.
    try:
        collection = get_collection()
        if collection is None:
            return []

        result = collection.query(query_texts=[q], n_results=k)

        out: list[dict[str, Any]] = []
        ids = result.get("ids") or [[]]
        docs = result.get("documents") or [[]]
        metas = result.get("metadatas") or [[]]
        dists = result.get("distances") or [[]]

        row_ids = ids[0] if ids and ids[0] is not None else []
        row_docs = docs[0] if docs and docs[0] is not None else []
        row_metas = metas[0] if metas and metas[0] is not None else []
        row_dists = dists[0] if dists and dists[0] is not None else []

        # Iterate by id row length; each parallel field is indexed only when in bounds.
        for i in range(len(row_ids)):
            raw_meta = row_metas[i] if i < len(row_metas) else {}
            meta = raw_meta if isinstance(raw_meta, dict) else {}
            out.append(
                {
                    "id": row_ids[i],
                    "document": row_docs[i] if i < len(row_docs) else "",
                    "metadata": meta,
                    "distance": row_dists[i] if i < len(row_dists) else None,
                }
            )
        return out
    except Exception:
        return []


def upsert_resolution_document(
    doc_id: str,
    text: str,
    metadata: dict[str, Any],
) -> bool:
    """Add or replace one KB document by id."""
    collection = get_collection()
    if collection is None or not text.strip():
        return False

    try:
        collection.delete(ids=[doc_id])
    except Exception:
        pass

    try:
        collection.add(
            ids=[doc_id],
            documents=[text.strip()],
            metadatas=[metadata],
        )
        return True
    except Exception:
        return False
