"""Developer task entry points, invoked via `uv run poe <task>`.

Keep this module thin — it only wires CLI-style dev tasks to app code.
"""

from __future__ import annotations


def create_tables() -> None:
    """Create all tables from the ORM models (dev only; no migrations yet).

    Temporary stand-in until Alembic migrations land. Run with:
        uv run poe tables
    """
    import asyncio

    import app.models  # noqa: F401  registers every table on Base.metadata
    from app.db.session import _get_engine
    from app.models.base import Base

    async def _run() -> None:
        async with _get_engine().begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        print("✅ tables created")

    asyncio.run(_run())
