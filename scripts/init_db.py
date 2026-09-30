"""Initialise la base de données : crée toutes les tables + extensions."""
import asyncio
import logging

from sqlalchemy import text

from orchestrix.config import get_settings
from orchestrix.db import Base, engine

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def init_db() -> None:
    settings = get_settings()
    logger.info("Connecting to %s", settings.database_url.split("@")[-1])

    async with engine.begin() as conn:
        # Activer extensions
        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        await conn.execute(text('CREATE EXTENSION IF NOT EXISTS "uuid-ossp"'))
        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS pg_trgm"))
        logger.info("Extensions enabled: vector, uuid-ossp, pg_trgm")

        # Créer toutes les tables
        await conn.run_sync(Base.metadata.create_all)
        logger.info("Tables created")


async def drop_all() -> None:
    """⚠️ DROP toutes les tables — uniquement pour dev/test."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        logger.info("All tables dropped")


if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1 and sys.argv[1] == "drop":
        asyncio.run(drop_all())
    else:
        asyncio.run(init_db())
