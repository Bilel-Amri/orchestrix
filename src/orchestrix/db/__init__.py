"""ORCHESTRIX — Database (SQLAlchemy async + pgvector)."""

from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from orchestrix.config import get_settings

settings = get_settings()

engine = create_async_engine(
    settings.database_url,
    echo=settings.app_debug,
    pool_size=10,
    max_overflow=20,
)

AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


class Base(DeclarativeBase):
    """Base pour tous les modèles SQLAlchemy."""


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Dependency FastAPI pour obtenir une session DB."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


# IMPORTANT: importer models ici pour que Base.metadata connaisse toutes les tables.
# Sans cet import, create_all() ne crée rien car la Base est vide.
# Placé EN BAS du module : models fait `from orchestrix.db import Base`, donc
# Base doit déjà exister (sinon import circulaire sur module partiellement initialisé).
from orchestrix.db import models  # noqa: E402,F401
