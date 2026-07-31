"""Tests for RAG (Retrieval-Augmented Generation) infrastructure."""

import uuid
from datetime import datetime, timezone


def test_vector_tables_exist(db):
    from sqlalchemy import inspect
    names = set(inspect(db.bind).get_table_names())
    assert "strategy_embeddings" in names
    assert "knowledge_chunks" in names


def _seed_strategy(db, user_id, title, body):
    from services.strategies import StrategyService
    return StrategyService(db).create_strategy(user_id=user_id, title=title, body=body)


def test_embed_and_search_recalls_strategy(db, user_id):
    from services.rag import embed_strategy, search_knowledge_impl
    s = _seed_strategy(db, user_id, "Gold", "黄金日内趋势回调策略 gold intraday trend pullback")
    embed_strategy(db, user_id, s["id"], "黄金日内趋势回调策略 gold intraday trend pullback")
    out = search_knowledge_impl(db, user_id, "黄金 趋势", scope="mine", top_k=5)
    assert any("黄金" in r["content"] for r in out)
    assert all(r["source"] == "strategy" for r in out)


def test_search_user_isolation(db, user_id):
    from models import User
    from services.rag import embed_strategy, search_knowledge_impl
    other = str(uuid.uuid4())
    db.add(User(id=other, email="o@t.test", password="x", name="O",
                created_at=datetime.now(timezone.utc).isoformat()))
    db.flush()
    s = _seed_strategy(db, other, "Gold", "黄金日内趋势 gold")
    embed_strategy(db, other, s["id"], "黄金日内趋势 gold")
    out = search_knowledge_impl(db, user_id, "黄金 趋势", scope="mine", top_k=5)
    assert out == []


def test_search_shared_corpus(db, user_id):
    from models import KnowledgeChunk
    from services.rag import create_embeddings, search_knowledge_impl
    vec = create_embeddings().embed_query("黄金 风险管理")
    db.add(KnowledgeChunk(id=str(uuid.uuid4()), source="doc.md", title="风控",
                          chunk_index=0, content="黄金 风险管理 要点", embedding=vec,
                          created_at=datetime.now(timezone.utc).isoformat()))
    db.flush()
    out = search_knowledge_impl(db, user_id, "黄金 风险", scope="shared", top_k=5)
    assert any("风险管理" in r["content"] for r in out)
    assert all(r["source"] == "knowledge" for r in out)
