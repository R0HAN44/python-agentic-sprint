import asyncio
import logging
from pathlib import Path
from typing import Any
import asyncpg
from sqlalchemy import text
from .config import settings
from .session import get_async_engine, close_db_engine

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s - %(message)s",
)
logger = logging.getLogger("db.migrate")

MIGRATIONS_DIR = Path(__file__).resolve().parent.parent.parent / "migrations"


async def run_migrations(migration_sql_path: Path | None = None) -> dict[str, Any]:
    """Applies SQL migration file to PostgreSQL and verifies schema and pgvector extension."""
    if migration_sql_path is None:
        migration_sql_path = MIGRATIONS_DIR / "01_init.sql"

    if not migration_sql_path.exists():
        raise FileNotFoundError(f"Migration file not found at: {migration_sql_path}")

    sql_content = migration_sql_path.read_text(encoding="utf-8")
    logger.info("Executing migration from: %s", migration_sql_path.name)

    # Use asyncpg directly for multi-statement DDL execution
    conn = await asyncpg.connect(
        user=settings.postgres_user,
        password=settings.postgres_password,
        database=settings.postgres_db,
        host=settings.postgres_host,
        port=settings.postgres_port,
    )

    try:
        # Execute the migration script
        await conn.execute(sql_content)
        logger.info("Migration DDL executed successfully")

        # 1. Verify pgvector extension
        ext_row = await conn.fetchrow(
            "SELECT extname, extversion FROM pg_extension WHERE extname = 'vector';"
        )
        if not ext_row:
            raise RuntimeError("pgvector extension was not created!")
        pgvector_version = ext_row["extversion"]
        logger.info("Verified pgvector extension version: %s", pgvector_version)

        # 2. Verify tables exist
        table_rows = await conn.fetch(
            """
            SELECT table_name 
            FROM information_schema.tables 
            WHERE table_schema = 'public' 
              AND table_name IN ('documents', 'document_chunks')
            ORDER BY table_name;
            """
        )
        tables_found = [r["table_name"] for r in table_rows]
        if "documents" not in tables_found or "document_chunks" not in tables_found:
            raise RuntimeError(f"Expected tables missing. Found: {tables_found}")
        logger.info("Verified tables in database: %s", tables_found)

        # 3. Verify columns in document_chunks
        col_rows = await conn.fetch(
            """
            SELECT column_name, data_type, udt_name 
            FROM information_schema.columns 
            WHERE table_name = 'document_chunks';
            """
        )
        columns = {r["column_name"]: (r["data_type"], r["udt_name"]) for r in col_rows}
        logger.info("Verified document_chunks columns: %s", list(columns.keys()))

        if "embedding" not in columns or columns["embedding"][1] != "vector":
            raise RuntimeError(f"Column 'embedding' is missing or not type 'vector': {columns.get('embedding')}")

        # 4. End-to-end vector test: insert dummy document, chunk with 1536-dim vector, and test cosine distance
        test_doc_id = "__migration_verification_doc__"
        test_chunk_id = "0" * 64
        test_embedding = [0.0] * 1536
        test_embedding[0] = 1.0

        await conn.execute(
            """
            INSERT INTO documents (doc_id, title, total_pages, total_chunks, metadata)
            VALUES ($1, $2, 1, 1, '{"env": "test"}'::jsonb)
            ON CONFLICT (doc_id) DO UPDATE SET updated_at = CURRENT_TIMESTAMP;
            """,
            test_doc_id,
            "Migration Test Document",
        )

        test_vector_str = "[" + ",".join(str(x) for x in test_embedding) + "]"
        await conn.execute(
            """
            INSERT INTO document_chunks (chunk_id, doc_id, page_number, section_path, content, token_count, embedding, metadata)
            VALUES ($1, $2, 1, '["Test"]'::jsonb, 'Test vector content', 3, $3::vector, '{"test": true}'::jsonb)
            ON CONFLICT (chunk_id) DO UPDATE SET content = EXCLUDED.content;
            """,
            test_chunk_id,
            test_doc_id,
            test_vector_str,
        )

        # Test distance calculation with pgvector cosine distance operator <=>
        res = await conn.fetchrow(
            """
            SELECT chunk_id, (embedding <=> $1::vector) AS cosine_distance
            FROM document_chunks
            WHERE chunk_id = $2;
            """,
            test_vector_str,
            test_chunk_id,
        )

        if res is None:
            raise RuntimeError("Failed to query test vector row")

        distance = float(res["cosine_distance"])
        if abs(distance) > 1e-5:
            raise RuntimeError(f"Vector cosine distance unexpected: {distance}")
        logger.info("pgvector cosine distance test PASSED (<=> distance = %f)", distance)

        # Clean up test rows
        await conn.execute("DELETE FROM documents WHERE doc_id = $1;", test_doc_id)
        logger.info("Cleaned up verification records successfully")

        return {
            "status": "success",
            "pgvector_version": pgvector_version,
            "tables": tables_found,
            "test_vector_distance": distance,
        }
    finally:
        await conn.close()


async def main():
    try:
        report = await run_migrations()
        print("\n" + "=" * 55)
        print("         PGVECTOR MIGRATION VERIFICATION")
        print("=" * 55)
        print(f"Status:               {report['status'].upper()}")
        print(f"pgvector version:     {report['pgvector_version']}")
        print(f"Verified tables:      {', '.join(report['tables'])}")
        print(f"Vector test (<=>):    distance = {report['test_vector_distance']:.6f} (PASSED)")
        print("=" * 55)
    finally:
        await close_db_engine()


if __name__ == "__main__":
    asyncio.run(main())
