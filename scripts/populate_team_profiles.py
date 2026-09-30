"""Peuple la table team_profiles avec 3-4 profils synthétiques.

⚠️ Profils FICTIFS documentés comme tels.
"""
import asyncio

from orchestrix.db import AsyncSessionLocal
from orchestrix.db.models import TeamProfileORM


TEAM_PROFILES = [
    {
        "name": "Alice (synthetic)",
        "role": "Senior Backend Developer",
        "skills": ["python", "fastapi", "postgres", "ml", "mlops"],
        "weekly_capacity_hours": 35,
    },
    {
        "name": "Bob (synthetic)",
        "role": "Frontend Developer",
        "skills": ["react", "typescript", "css", "ux"],
        "weekly_capacity_hours": 30,
    },
    {
        "name": "Charlie (synthetic)",
        "role": "DevOps / MLOps Engineer",
        "skills": ["docker", "kubernetes", "github-actions", "mlflow", "monitoring"],
        "weekly_capacity_hours": 40,
    },
    {
        "name": "Diana (synthetic)",
        "role": "Product Designer",
        "skills": ["figma", "user-research", "prototyping"],
        "weekly_capacity_hours": 25,
    },
]


async def populate() -> None:
    async with AsyncSessionLocal() as session:
        for profile in TEAM_PROFILES:
            session.add(TeamProfileORM(is_synthetic=True, **profile))
        await session.commit()
        print(f"✓ Inserted {len(TEAM_PROFILES)} synthetic team profiles")


if __name__ == "__main__":
    asyncio.run(populate())
