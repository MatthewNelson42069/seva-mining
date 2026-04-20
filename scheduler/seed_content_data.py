"""
Seed script for Content Agent data.
Populates config defaults for the content agent runtime parameters.

Usage: DATABASE_URL=postgresql+asyncpg://... uv run python seed_content_data.py

This script is self-contained — it builds its own async engine directly from
the DATABASE_URL environment variable and does NOT import Settings (which
requires all env vars to be set).

Idempotent: existing records are skipped, not overwritten.

-- DB migration — run once against production DB to remove old keys ----------
-- Remove old content agent cron config keys
DELETE FROM config WHERE key IN ('content_agent_schedule_hour', 'content_agent_midday_hour');

-- Insert new interval config key (skip if already seeded by updated seed script)
INSERT INTO config (key, value) VALUES ('content_agent_interval_hours', '2')
ON CONFLICT (key) DO NOTHING;
-- ---------------------------------------------------------------------------
"""
import asyncio
import os

from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy import select

from models.config import Config


# ---------------------------------------------------------------------------
# Config defaults — Content Agent runtime parameters
# ---------------------------------------------------------------------------
CONFIG_DEFAULTS = [
    ("content_relevance_weight",          "0.40"),
    ("content_recency_weight",            "0.40"),
    ("content_credibility_weight",        "0.30"),
    ("content_quality_threshold",         "7.0"),
    ("content_agent_interval_hours",       "3"),
    ("morning_digest_schedule_hour",      "15"),
    ("gold_history_hour",                 "9"),
    ("gold_history_used_topics",          "[]"),
    ("content_gold_gate_enabled",            "true"),
    ("content_gold_gate_model",              "claude-3-5-haiku-latest"),
]


async def seed_config(session: AsyncSession) -> tuple[int, int]:
    """Seed Content Agent config defaults. Returns (inserted, skipped)."""
    inserted = 0
    skipped = 0

    for key, value in CONFIG_DEFAULTS:
        result = await session.execute(
            select(Config).where(Config.key == key)
        )
        existing = result.scalar_one_or_none()

        if existing is not None:
            skipped += 1
            continue

        record = Config(key=key, value=value)
        session.add(record)
        inserted += 1

    return inserted, skipped


async def main() -> None:
    db_url = os.environ["DATABASE_URL"]
    # asyncpg uses ssl=require not sslmode=require — strip and pass via connect_args
    db_url = db_url.replace("?sslmode=require", "").replace("&sslmode=require", "")
    engine = create_async_engine(
        db_url,
        pool_pre_ping=True,
        connect_args={"ssl": "require"},
    )
    Session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with Session() as session:
        cfg_inserted, cfg_skipped = await seed_config(session)
        await session.commit()

    await engine.dispose()

    print(
        f"Seeded {cfg_inserted} config entries (skipped {cfg_skipped} existing)."
    )
    print("Seed complete.")


if __name__ == "__main__":
    asyncio.run(main())
