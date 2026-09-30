"""Pytest configuration + fixtures partagés."""

from __future__ import annotations

import os
from collections.abc import AsyncGenerator

import pytest
import pytest_asyncio


@pytest.fixture(scope="session", autouse=True)
def _test_env() -> None:
    """Force test environment variables."""
    os.environ.setdefault("APP_ENV", "test")
    os.environ.setdefault("APP_DEBUG", "true")
    os.environ.setdefault("POSTGRES_DB", "orchestrix_test")
    os.environ.setdefault("MLFLOW_TRACKING_URI", "sqlite:///./mlruns/test.db")


@pytest_asyncio.fixture
async def async_db_session() -> AsyncGenerator:
    """Async DB session pour tests d'intégration."""
    from sqlalchemy import text
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

    from orchestrix.db import Base

    engine = create_async_engine(
        os.environ.get(
            "DATABASE_URL",
            "postgresql+asyncpg://test:test@localhost:5432/orchestrix_test",
        )
    )

    async with engine.begin() as conn:
        # pgvector ne crée pas l'extension automatiquement (cf. scripts/init_db.py)
        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        await conn.run_sync(Base.metadata.create_all)

    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with session_factory() as session:
        yield session

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest.fixture
def sample_brief() -> str:
    """Brief exemple pour les tests."""
    return (
        "Construire une application de paiement mobile avec authentification "
        "biométrique. Stack cible : React Native, backend Python (FastAPI), "
        "intégration Stripe. Équipe : 2 développeurs, 1 designer. Délai : 3 mois."
    )


@pytest.fixture
def sample_benchmark(tmp_path):
    """Charge le benchmark template dans un fichier tmp."""
    import shutil
    from pathlib import Path

    src = Path(__file__).parent / "fixtures" / "safe_unsafe_actions.json"
    if not src.exists():
        # Fallback : copier depuis data/
        alt = Path(__file__).parent.parent / "data" / "benchmarks" / "safe_unsafe_actions.json"
        if alt.exists():
            src = alt
        else:
            pytest.skip("Benchmark file not found")
    dst = tmp_path / "benchmark.json"
    shutil.copy(src, dst)
    return dst
