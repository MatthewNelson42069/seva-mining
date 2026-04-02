"""
Seed script for Instagram Agent data.
Populates watchlists, keywords, and config defaults.

Usage: DATABASE_URL=postgresql+asyncpg://... uv run python seed_instagram_data.py

This script is self-contained — it builds its own async engine directly from
the DATABASE_URL environment variable and does NOT import Settings (which
requires all env vars to be set). This matches the seed_twitter_data.py pattern.

Idempotent: existing records are skipped, not overwritten.

Instagram watchlist: best-effort mapping of the 25 Twitter watchlist entities
to their Instagram handles. Accounts without active Instagram presence are
skipped (JimRickards, MacleodFinance, RonStoeferle, TaviCosta, Frank_Giustra,
GoldSeekCom, WSBGold, GoldTelegraph_, SPDR_ETFs — no clear active IG presence).
"""
import asyncio
import os

from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy import select

from models.watchlist import Watchlist
from models.keyword import Keyword
from models.config import Config


# ---------------------------------------------------------------------------
# Watchlist accounts — confirmed/likely Instagram handles for gold-sector entities.
# Source: 25 Twitter watchlist entities in seed_twitter_data.py.
# Handles stored WITHOUT the @ prefix.
# platform_user_id left as None — agent resolves lazily on first run.
# Skipped (no clear active Instagram presence): JimRickards, MacleodFinance,
#   RonStoeferle, TaviCosta, Mike_maloney, Frank_Giustra, GoldSeekCom,
#   SPDR_ETFs, WSBGold, GoldTelegraph_
# ---------------------------------------------------------------------------
WATCHLIST_ACCOUNTS = [
    # Media / News
    ("kitco",               "Kitco News — gold price and market news outlet"),
    ("goldcouncil",         "World Gold Council — official industry body"),
    ("bullionvault",        "BullionVault — gold price platform with market commentary"),
    ("reuters",             "Reuters — when covering gold/commodities"),
    ("bloombergbusiness",   "Bloomberg Business — when covering gold/commodities"),

    # Analysts & Commentators
    ("peterschiff",         "Peter Schiff — CEO Euro Pacific Capital, prolific gold bull"),
    ("realvisionfinance",   "Real Vision Finance — macro/gold commentary"),
    ("danielacambone",      "Daniela Cambone — gold/mining journalist"),

    # Mining Majors
    ("newmont",             "Newmont — world's largest gold miner"),
    ("barrick",             "Barrick Gold"),
    ("agnicoeaglemines",    "Agnico Eagle Mines"),
    ("kinrossgold",         "Kinross Gold"),
    ("franconevada",        "Franco-Nevada (streaming/royalty)"),
    ("wheatonpreciousmetals", "Wheaton Precious Metals (streaming/royalty)"),

    # ETFs / Funds
    ("vaneck_investments",  "VanEck — GDX/GDXJ gold miner ETFs"),
]


# ---------------------------------------------------------------------------
# Keywords — 10 gold-sector Instagram hashtags (all platform='instagram')
# ---------------------------------------------------------------------------
KEYWORDS = [
    "#gold",
    "#goldmining",
    "#preciousmetals",
    "#goldprice",
    "#bullion",
    "#juniorminers",
    "#goldstocks",
    "#goldsilver",
    "#goldnugget",
    "#mininglife",
]


# ---------------------------------------------------------------------------
# Config defaults — Instagram Agent runtime parameters
# ---------------------------------------------------------------------------
CONFIG_DEFAULTS = [
    ("instagram_max_posts_per_hashtag",  "50"),
    ("instagram_max_posts_per_account",  "10"),
    ("instagram_top_n",                  "3"),
    ("instagram_health_baseline_runs",   "3"),
]


async def seed_watchlists(session: AsyncSession) -> tuple[int, int]:
    """Seed Instagram watchlist accounts. Returns (inserted, skipped)."""
    inserted = 0
    skipped = 0

    for handle, notes in WATCHLIST_ACCOUNTS:
        result = await session.execute(
            select(Watchlist).where(
                Watchlist.account_handle == handle,
                Watchlist.platform == "instagram",
            )
        )
        existing = result.scalar_one_or_none()

        if existing is not None:
            skipped += 1
            continue

        record = Watchlist(
            platform="instagram",
            account_handle=handle,
            platform_user_id=None,
            relationship_value=5,
            notes=notes,
            active=True,
        )
        session.add(record)
        inserted += 1

    return inserted, skipped


async def seed_keywords(session: AsyncSession) -> tuple[int, int]:
    """Seed Instagram hashtag keywords. Returns (inserted, skipped)."""
    inserted = 0
    skipped = 0

    for term in KEYWORDS:
        result = await session.execute(
            select(Keyword).where(
                Keyword.term == term,
                Keyword.platform == "instagram",
            )
        )
        existing = result.scalar_one_or_none()

        if existing is not None:
            skipped += 1
            continue

        record = Keyword(
            term=term,
            platform="instagram",
            weight=1.0,
            active=True,
        )
        session.add(record)
        inserted += 1

    return inserted, skipped


async def seed_config(session: AsyncSession) -> tuple[int, int]:
    """Seed Instagram config defaults. Returns (inserted, skipped)."""
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
        wl_inserted, wl_skipped = await seed_watchlists(session)
        kw_inserted, kw_skipped = await seed_keywords(session)
        cfg_inserted, cfg_skipped = await seed_config(session)
        await session.commit()

    await engine.dispose()

    total_skipped = wl_skipped + kw_skipped + cfg_skipped
    print(
        f"Seeded {wl_inserted} watchlists, {kw_inserted} keywords, "
        f"{cfg_inserted} config entries (skipped {total_skipped} existing)."
    )
    print("Seed complete.")


if __name__ == "__main__":
    asyncio.run(main())
