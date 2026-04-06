"""
Seed script for Twitter Agent data.
Populates watchlists, keywords, and config defaults.

Usage: DATABASE_URL=postgresql+asyncpg://... uv run python seed_twitter_data.py

This script is self-contained — it builds its own async engine directly from
the DATABASE_URL environment variable and does NOT import Settings (which
requires all env vars to be set). This matches the Phase 3 seed script pattern.

Idempotent: existing records are skipped, not overwritten.
"""
import asyncio
import os
from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy import select

from models.watchlist import Watchlist
from models.keyword import Keyword
from models.config import Config


# ---------------------------------------------------------------------------
# Watchlist accounts — 25 gold-sector Twitter accounts (all relationship_value=5)
# User decision: seed all at maximum priority; can be adjusted via dashboard.
# Handles stored WITHOUT the @ prefix.
# platform_user_id left as None — agent resolves lazily on first run.
# ---------------------------------------------------------------------------
WATCHLIST_ACCOUNTS = [
    # Media / News (5)
    ("KitcoNews",       "Kitco News — definitive gold price and market news outlet"),
    ("WGCouncil",       "World Gold Council — official industry body"),
    ("BullionVault",    "BullionVault — gold price platform with market commentary"),
    ("Reuters",         "Reuters — when covering gold/commodities"),
    ("BloombergMkts",   "Bloomberg Markets — when covering gold/commodities"),

    # Analysts & Commentators (10)
    ("PeterSchiff",     "CEO Euro Pacific Capital, prolific gold bull"),
    ("JimRickards",     "Author, gold standard advocate, macro analysis"),
    ("GoldSeekCom",     "GoldSeek — gold news aggregator covering juniors and majors"),
    ("RealVision",      "Real Vision Finance — macro/gold commentary"),
    ("TaviCosta",       "Tavi Costa — macro analyst with strong gold thesis"),
    ("Mike_maloney",    "Mike Maloney — gold/silver investor and educator"),
    ("MacleodFinance",  "Alasdair Macleod — gold and monetary theory analysis"),
    ("DanielaCambone",  "Daniela Cambone — gold/mining journalist"),
    ("RonStoeferle",    "Ronald Stoeferle — In Gold We Trust report author"),
    ("Frank_Giustra",   "Frank Giustra — mining financier and gold sector veteran"),

    # Mining Majors (6)
    ("Newmont",         "Newmont — world's largest gold miner"),
    ("Barrick",         "Barrick Gold"),
    ("AgnicoEagle",     "Agnico Eagle"),
    ("KinrossGold",     "Kinross Gold"),
    ("FrancoNevada",    "Franco-Nevada (streaming/royalty)"),
    ("WheatonPrecious", "Wheaton Precious Metals (streaming/royalty)"),

    # ETFs / Funds (2)
    ("SPDR_ETFs",       "SPDR — GLD benchmark gold ETF"),
    ("VanEck",          "VanEck — GDX/GDXJ gold miner ETFs"),

    # Gold Media / Community (2)
    ("GoldTelegraph_",  "Gold Telegraph — gold sector news and commentary"),
    ("WSBGold",         "WSBGold — retail gold community with high engagement"),
]


# ---------------------------------------------------------------------------
# Keywords — cashtags, hashtags, and keyword phrases (all platform='twitter')
# ---------------------------------------------------------------------------
KEYWORDS = [
    # Cashtags
    "$GLD",
    "$GC",
    "$GOLD",
    "$GDX",
    "$GDXJ",
    "$NEM",

    # Hashtags
    "#gold",
    "#goldmining",
    "#preciousmetals",
    "#goldprice",
    "#bullion",
    "#juniorminers",
    "#mining",

    # Keyword phrases
    "gold price",
    "central bank gold",
    "gold reserves",
    "gold ETF",
    "gold exploration",
    "junior miners",
    "gold standard",
    "gold rally",
    "gold outlook",
]


# ---------------------------------------------------------------------------
# Config defaults — quota counters for Twitter API rate management (TWIT-13)
# ---------------------------------------------------------------------------
CONFIG_DEFAULTS = [
    ("twitter_monthly_tweet_count",  "0"),
    ("twitter_monthly_reset_date",   datetime.now(timezone.utc).date().isoformat()),
    ("twitter_quota_safety_margin",  "1500"),
    ("twitter_min_likes_general",    "500"),
    ("twitter_min_views_general",    "40000"),
    ("twitter_min_likes_watchlist",  "50"),
    ("twitter_min_views_watchlist",  "5000"),
    ("twitter_interval_hours",       "2"),
]


async def seed_watchlists(session: AsyncSession) -> tuple[int, int]:
    """Seed watchlist accounts. Returns (inserted, skipped)."""
    inserted = 0
    skipped = 0

    for handle, notes in WATCHLIST_ACCOUNTS:
        result = await session.execute(
            select(Watchlist).where(
                Watchlist.account_handle == handle,
                Watchlist.platform == "twitter",
            )
        )
        existing = result.scalar_one_or_none()

        if existing is not None:
            skipped += 1
            continue

        record = Watchlist(
            platform="twitter",
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
    """Seed keywords. Returns (inserted, skipped)."""
    inserted = 0
    skipped = 0

    for term in KEYWORDS:
        result = await session.execute(
            select(Keyword).where(
                Keyword.term == term,
                Keyword.platform == "twitter",
            )
        )
        existing = result.scalar_one_or_none()

        if existing is not None:
            skipped += 1
            continue

        record = Keyword(
            term=term,
            platform="twitter",
            weight=1.0,
            active=True,
        )
        session.add(record)
        inserted += 1

    return inserted, skipped


async def seed_config(session: AsyncSession) -> tuple[int, int]:
    """Seed config defaults. Returns (inserted, skipped)."""
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
