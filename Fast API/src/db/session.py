import asyncio
import time
import logging
from typing import AsyncGenerator, Any
from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from .config import settings

logger = logging.getLogger("db.session")

_engine: AsyncEngine | None = None
_engine_loop: asyncio.AbstractEventLoop | None = None
_session_factory: async_sessionmaker[AsyncSession] | None = None


def get_async_engine() -> AsyncEngine:
    """Creates or returns the cached SQLAlchemy AsyncEngine with configured connection pool."""
    global _engine, _session_factory, _engine_loop

    current_loop: asyncio.AbstractEventLoop | None = None
    try:
        current_loop = asyncio.get_running_loop()
    except RuntimeError:
        pass

    # If the active event loop changed or was closed (e.g. across pytest async tests), re-initialize engine
    if _engine is not None and _engine_loop is not None and current_loop is not None:
        if _engine_loop != current_loop or _engine_loop.is_closed():
            _engine = None
            _session_factory = None

    if _engine is None:
        _engine_loop = current_loop
        logger.info(
            "Initializing AsyncEngine (pool_size=%d, max_overflow=%d, pre_ping=%s)",
            settings.db_pool_size,
            settings.db_max_overflow,
            settings.db_pool_pre_ping,
        )
        _engine = create_async_engine(
            settings.async_database_url,
            pool_size=settings.db_pool_size,
            max_overflow=settings.db_max_overflow,
            pool_timeout=settings.db_pool_timeout,
            pool_recycle=settings.db_pool_recycle,
            pool_pre_ping=settings.db_pool_pre_ping,
            echo=settings.db_echo,
            connect_args={
                "server_settings": {
                    "application_name": "rag_fastapi",
                }
            },
        )
    return _engine


def get_session_factory() -> async_sessionmaker[AsyncSession]:
    """Returns the async session factory bound to the async engine."""
    global _session_factory
    engine = get_async_engine()
    if _session_factory is None:
        _session_factory = async_sessionmaker(
            bind=engine,
            class_=AsyncSession,
            expire_on_commit=False,
            autoflush=False,
        )
    return _session_factory



async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency and context-usable async generator for database sessions."""
    session_factory = get_session_factory()
    async with session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


async def close_db_engine() -> None:
    """Gracefully shuts down connection pool and releases connections."""
    global _engine, _session_factory, _engine_loop
    if _engine is not None:
        logger.info("Disposing AsyncEngine connection pool")
        await _engine.dispose()
        _engine = None
        _session_factory = None
        _engine_loop = None


async def check_database_health() -> dict[str, Any]:
    """Verifies PostgreSQL connection, measures query latency, and validates pgvector extension."""
    engine = get_async_engine()
    start_time = time.perf_counter()

    try:
        async with engine.connect() as conn:
            # Check basic connection and postgres version
            pg_res = await conn.execute(text("SELECT version();"))
            version_str = pg_res.scalar() or "Unknown"

            # Check pgvector extension status
            ext_res = await conn.execute(
                text("SELECT extname, extversion FROM pg_extension WHERE extname = 'vector';")
            )
            ext_row = ext_res.first()
            has_pgvector = ext_row is not None
            pgvector_version = ext_row[1] if ext_row else None

            # Test vector arithmetic directly
            if has_pgvector:
                vec_test = await conn.execute(
                    text("SELECT '[1,2,3]'::vector <=> '[1,2,3]'::vector AS distance;")
                )
                dist = vec_test.scalar()
                vector_operational = (dist is not None and abs(dist) < 1e-6)
            else:
                vector_operational = False

            latency_ms = (time.perf_counter() - start_time) * 1000.0

            return {
                "status": "healthy" if (has_pgvector and vector_operational) else "degraded",
                "database": "postgresql",
                "pg_version": version_str,
                "pgvector_installed": has_pgvector,
                "pgvector_version": pgvector_version,
                "pgvector_operational": vector_operational,
                "latency_ms": round(latency_ms, 2),
            }
    except Exception as exc:
        latency_ms = (time.perf_counter() - start_time) * 1000.0
        logger.exception("Database health check failed")
        return {
            "status": "unhealthy",
            "error": str(exc),
            "latency_ms": round(latency_ms, 2),
        }
