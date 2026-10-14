import asyncio
import os
from pathlib import Path
import pytest
import pytest_asyncio
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.config import DatabaseSettings, settings
from src.db.session import (
    get_async_engine,
    get_session_factory,
    get_db_session,
    check_database_health,
    close_db_engine,
)
from src.db.models import DocumentModel, DocumentChunkModel
from src.db.migrate import run_migrations


@pytest.fixture(scope="module")
def compose_file_content():
    compose_path = Path(__file__).resolve().parent.parent / "docker-compose.yml"
    assert compose_path.exists(), "docker-compose.yml not found"
    return compose_path.read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def migration_file_content():
    mig_path = Path(__file__).resolve().parent.parent / "migrations" / "01_init.sql"
    assert mig_path.exists(), "migrations/01_init.sql not found"
    return mig_path.read_text(encoding="utf-8")


def test_docker_compose_configuration(compose_file_content):
    """Verify docker-compose.yml satisfies Day 21 specifications."""
    assert "pgvector/pgvector:pg16" in compose_file_content
    assert "shared_buffers=256MB" in compose_file_content
    assert "work_mem=16MB" in compose_file_content
    assert "maintenance_work_mem=128MB" in compose_file_content
    assert "POSTGRES_DB" in compose_file_content
    assert "healthcheck:" in compose_file_content


def test_sql_migration_ddl_structure(migration_file_content):
    """Verify 01_init.sql contains required vector extension and table definitions."""
    assert "CREATE EXTENSION IF NOT EXISTS vector" in migration_file_content
    assert "CREATE TABLE IF NOT EXISTS documents" in migration_file_content
    assert "CREATE TABLE IF NOT EXISTS document_chunks" in migration_file_content
    assert "vector(1536)" in migration_file_content
    assert "REFERENCES documents(doc_id)" in migration_file_content
    assert "tsvector GENERATED ALWAYS AS" in migration_file_content


def test_database_settings_and_pool_config():
    """Verify connection pool and async database settings."""
    cfg = DatabaseSettings()
    assert cfg.postgres_port == 5432
    assert cfg.async_database_url.startswith("postgresql+asyncpg://")
    assert cfg.db_pool_size >= 5
    assert cfg.db_max_overflow >= 10
    assert cfg.db_pool_pre_ping is True


@pytest.mark.asyncio
async def test_migration_and_health_check():
    """Run migration verification and assert database health check returns healthy."""
    report = await run_migrations()
    assert report["status"] == "success"
    assert "document_chunks" in report["tables"]
    assert "documents" in report["tables"]
    assert report["test_vector_distance"] < 1e-5

    health = await check_database_health()
    assert health["status"] == "healthy"
    assert health["pgvector_installed"] is True
    assert health["pgvector_operational"] is True
    assert health["latency_ms"] > 0


@pytest.mark.asyncio
async def test_sqlalchemy_async_session_crud():
    """Verify asynchronous session CRUD operations using SQLAlchemy AsyncEngine and Models."""
    doc_id = "test_doc_async_crud"
    chunk_1_id = "a" * 64
    chunk_2_id = "b" * 64

    # Dummy 1536-dimension embeddings
    embedding_1 = [0.0] * 1536
    embedding_1[0] = 1.0  # Unit vector along dimension 0

    embedding_2 = [0.0] * 1536
    embedding_2[1] = 1.0  # Unit vector along dimension 1

    session_gen = get_db_session()
    session: AsyncSession = await anext(session_gen)

    try:
        # 1. Clean existing test records if any
        await session.execute(
            text("DELETE FROM documents WHERE doc_id = :d"),
            {"d": doc_id},
        )
        await session.flush()

        # 2. Insert parent document
        doc = DocumentModel(
            doc_id=doc_id,
            title="Efficacy of Immunotherapy in Advanced Oncology",
            total_pages=12,
            total_chunks=2,
            metadata_={"study_phase": "Phase III", "year": 2024},
        )
        session.add(doc)
        await session.flush()

        # 3. Insert child document chunks
        chunk1 = DocumentChunkModel(
            chunk_id=chunk_1_id,
            doc_id=doc_id,
            page_number=1,
            section_path=["Introduction", "Background"],
            content="Immune checkpoint inhibitors have altered clinical outcomes substantially.",
            token_count=10,
            embedding=embedding_1,
            metadata_={"section": "Background"},
        )
        chunk2 = DocumentChunkModel(
            chunk_id=chunk_2_id,
            doc_id=doc_id,
            page_number=2,
            section_path=["Methods", "Dosage"],
            content="Patients received 200mg infusions every three weeks.",
            token_count=8,
            embedding=embedding_2,
            metadata_={"section": "Dosage"},
        )
        session.add_all([chunk1, chunk2])
        await session.commit()

        # 4. Read back and test relationships
        stmt = (
            select(DocumentModel)
            .where(DocumentModel.doc_id == doc_id)
        )
        result = await session.execute(stmt)
        queried_doc = result.scalar_one_or_none()
        assert queried_doc is not None
        assert queried_doc.title == "Efficacy of Immunotherapy in Advanced Oncology"

        # 5. Query chunks and test pgvector cosine distance ordering
        # Query closest to query vector [1.0, 0, 0, ...] -> chunk1 distance should be 0.0
        query_vector = [0.0] * 1536
        query_vector[0] = 1.0
        q_vec_str = "[" + ",".join(str(x) for x in query_vector) + "]"

        search_stmt = text("""
            SELECT chunk_id, content, (embedding <=> CAST(:q_vec AS vector)) AS distance
            FROM document_chunks
            WHERE doc_id = :doc_id
            ORDER BY embedding <=> CAST(:q_vec AS vector) ASC;
        """)

        search_res = await session.execute(
            search_stmt,
            {"q_vec": q_vec_str, "doc_id": doc_id},
        )
        ranked = search_res.mappings().all()
        assert len(ranked) == 2
        # chunk1 should be rank 1 with distance ~0.0
        assert ranked[0]["chunk_id"] == chunk_1_id
        assert ranked[0]["distance"] < 1e-5
        # chunk2 should have orthogonal distance ~1.0
        assert ranked[1]["chunk_id"] == chunk_2_id
        assert abs(ranked[1]["distance"] - 1.0) < 1e-5

        # 6. Verify cascade delete
        await session.delete(queried_doc)
        await session.commit()

        # Confirm chunks are also deleted
        chunk_check = await session.execute(
            select(DocumentChunkModel).where(DocumentChunkModel.doc_id == doc_id)
        )
        assert len(chunk_check.scalars().all()) == 0

    finally:
        try:
            await anext(session_gen)
        except StopAsyncIteration:
            pass


@pytest.mark.asyncio
async def test_fastapi_health_db_endpoint():
    """Verify FastAPI /health/db endpoint returns healthy status and pgvector metadata."""
    from httpx import AsyncClient, ASGITransport
    from src.main import app

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        resp = await client.get("/health/db")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "healthy"
        assert data["database"] == "postgresql"
        assert data["pgvector_installed"] is True
        assert data["pgvector_operational"] is True
        assert data["latency_ms"] > 0

