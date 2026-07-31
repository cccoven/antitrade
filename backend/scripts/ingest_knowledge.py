"""Ingest .md/.txt files from a directory into knowledge_chunks (shared corpus).

Run from backend/:  ./.venv/bin/python scripts/ingest_knowledge.py <dir> [--replace]
"""
import sys
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from db import SessionLocal  # noqa: E402
from models import KnowledgeChunk  # noqa: E402
from services.rag import chunk_text, create_embeddings  # noqa: E402
from sqlalchemy import delete as sa_delete  # noqa: E402


def main() -> int:
    if len(sys.argv) < 2:
        print("usage: ingest_knowledge.py <dir> [--replace]", file=sys.stderr)
        return 1
    root = Path(sys.argv[1])
    replace = "--replace" in sys.argv
    embeddings = create_embeddings()
    session = SessionLocal()
    try:
        files = [p for p in root.rglob("*") if p.suffix in (".md", ".txt")]
        inserted = 0
        for p in files:
            source = str(p.relative_to(root))
            text = p.read_text(encoding="utf-8")
            title = text.splitlines()[0].strip()[:120] if text.strip() else p.name
            if replace:
                session.execute(sa_delete(KnowledgeChunk).where(KnowledgeChunk.source == source))
            chunks = chunk_text(text)
            if not chunks:
                continue
            vecs = embeddings.embed_documents(chunks)
            now = datetime.now(timezone.utc).isoformat()
            for i, (chunk, vec) in enumerate(zip(chunks, vecs)):
                session.add(KnowledgeChunk(id=str(uuid4()), source=source, title=title,
                                           chunk_index=i, content=chunk, embedding=vec, created_at=now))
                inserted += 1
            print(f"  + {source} ({len(chunks)} chunks)")
        session.commit()
        print(f"Ingested {inserted} chunks from {len(files)} files.")
        return 0
    finally:
        session.close()


if __name__ == "__main__":
    raise SystemExit(main())
