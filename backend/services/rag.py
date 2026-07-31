"""RAG: embeddings factory, chunking, strategy embedding, knowledge search."""

import hashlib
import logging
import math
import re
from datetime import datetime, timezone
from uuid import uuid4

from langchain_core.embeddings import Embeddings
from sqlalchemy import delete as sa_delete, select

logger = logging.getLogger(__name__)

_DIM = 1536
_TOKEN_RE = re.compile(r"[a-z0-9]+|[一-鿿]")


def _tokenize(text: str) -> list[str]:
    return _TOKEN_RE.findall((text or "").lower())


class _FakeEmbeddings(Embeddings):
    """Deterministic hashing bag-of-words embedding (offline/tests)."""

    def _vec(self, text: str) -> list[float]:
        v = [0.0] * _DIM
        for tok in _tokenize(text):
            idx = int(hashlib.md5(tok.encode("utf-8")).hexdigest(), 16) % _DIM
            v[idx] += 1.0
        norm = math.sqrt(sum(x * x for x in v)) or 1.0
        return [x / norm for x in v]

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [self._vec(t) for t in texts]

    def embed_query(self, text: str) -> list[float]:
        return self._vec(text)


def create_embeddings() -> Embeddings:
    from config import (
        EMBEDDINGS_PROVIDER, EMBEDDINGS_MODEL, EMBEDDINGS_BASE_URL, EMBEDDINGS_API_KEY,
        LLM_BASE_URL, LLM_API_KEY,
    )

    if EMBEDDINGS_PROVIDER == "demo":
        return _FakeEmbeddings()
    if EMBEDDINGS_PROVIDER == "openai":
        from langchain_openai import OpenAIEmbeddings
        # Embeddings endpoint is decoupled from chat; fall back to the chat endpoint
        # (LLM_BASE_URL / LLM_API_KEY) when the dedicated vars are unset.
        return OpenAIEmbeddings(
            model=EMBEDDINGS_MODEL,
            base_url=EMBEDDINGS_BASE_URL or LLM_BASE_URL,
            api_key=EMBEDDINGS_API_KEY or LLM_API_KEY,
        )
    raise ValueError(f"Unknown EMBEDDINGS_PROVIDER: {EMBEDDINGS_PROVIDER}")


def chunk_text(text: str, size: int = 800, overlap: int = 100) -> list[str]:
    from langchain_text_splitters import RecursiveCharacterTextSplitter
    splitter = RecursiveCharacterTextSplitter(chunk_size=size, chunk_overlap=overlap)
    return [c for c in splitter.split_text(text or "") if c.strip()]


def embed_strategy(session, user_id: str, strategy_id: str, body: str) -> None:
    """Re-embed one strategy, replacing old chunks only after vectors are ready."""
    from models import StrategyEmbedding
    embeddings = create_embeddings()
    chunks = chunk_text(body)
    vecs = embeddings.embed_documents(chunks) if chunks else []
    try:
        session.execute(
            sa_delete(StrategyEmbedding).where(StrategyEmbedding.strategy_id == strategy_id)
        )
        now = datetime.now(timezone.utc).isoformat()
        for i, (chunk, vec) in enumerate(zip(chunks, vecs)):
            session.add(StrategyEmbedding(
                id=str(uuid4()), strategy_id=strategy_id, user_id=user_id,
                chunk_index=i, content=chunk, embedding=vec, created_at=now,
            ))
        session.commit()
    except Exception:
        session.rollback()
        raise


def search_knowledge_impl(session, user_id: str, query: str,
                          scope: str = "all", top_k: int = 6) -> list[dict]:
    from models import StrategyEmbedding, KnowledgeChunk
    embeddings = create_embeddings()
    qvec = embeddings.embed_query(query)
    results: list[dict] = []
    if scope in ("mine", "all"):
        rows = session.execute(
            select(StrategyEmbedding.content, StrategyEmbedding.strategy_id,
                   StrategyEmbedding.embedding.cosine_distance(qvec).label("dist"))
            .where(StrategyEmbedding.user_id == user_id)
            .order_by("dist").limit(top_k)
        ).all()
        results += [{"source": "strategy", "content": r.content,
                     "strategy_id": r.strategy_id, "dist": float(r.dist)} for r in rows]
    if scope in ("shared", "all"):
        rows = session.execute(
            select(KnowledgeChunk.content, KnowledgeChunk.title,
                   KnowledgeChunk.embedding.cosine_distance(qvec).label("dist"))
            .order_by("dist").limit(top_k)
        ).all()
        results += [{"source": "knowledge", "content": r.content,
                     "title": r.title, "dist": float(r.dist)} for r in rows]
    results.sort(key=lambda x: x["dist"])
    return results[:top_k]
