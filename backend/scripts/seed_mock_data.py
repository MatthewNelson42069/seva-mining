"""Seed mock data for dashboard development and testing.

Usage: cd backend && python -m scripts.seed_mock_data
Requires DATABASE_URL environment variable set to a postgresql+asyncpg:// URL.

Creates realistic gold sector draft items on the content platform to enable
immediate dashboard testing without running the agents.

Updated in quick-260420-sn9: Twitter agent purged, Instagram agent already purged
in quick-260419-lvy. Sevamining is now a single-agent system (content only), so
this script seeds only ``platform="content"`` draft items.
"""

import asyncio
import os
import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.models.draft_item import DraftItem, DraftStatus


def _get_engine():
    """Build an async engine from DATABASE_URL env var."""
    database_url = os.environ.get("DATABASE_URL")
    if not database_url:
        raise RuntimeError("DATABASE_URL environment variable is required")
    # Strip sslmode from URL and use connect_args instead (asyncpg requirement)
    url = database_url
    if "sslmode=" in url:
        from urllib.parse import parse_qs, urlencode, urlparse, urlunparse
        parsed = urlparse(url)
        qs = parse_qs(parsed.query)
        qs.pop("sslmode", None)
        new_query = urlencode({k: v[0] for k, v in qs.items()})
        url = urlunparse(parsed._replace(query=new_query))

    return create_async_engine(
        url,
        pool_pre_ping=True,
        connect_args={"ssl": True} if "neon.tech" in database_url else {},
    )


now = datetime.now(UTC)


def _dt(minutes_ago: int) -> datetime:
    return now - timedelta(minutes=minutes_ago)


MOCK_ITEMS = [
    # ── CONTENT ITEMS ──────────────────────────────────────────────────────────

    DraftItem(
        id=uuid.uuid4(),
        platform="content",
        status=DraftStatus.pending,
        source_url="https://www.gold.org/goldhub/research/gold-demand-trends/gold-demand-trends-q3-2024",
        source_text=(
            "Central bank gold reserves — Q3 2024 deep research piece. "
            "Covers: which central banks are accumulating and at what pace, "
            "the geopolitical drivers behind de-dollarization, reserve diversification "
            "trends across EM vs. DM central banks, and what the current trajectory "
            "implies for gold demand over the next 3-5 years. "
            "Sources: WGC demand data, IMF reserve reports, BIS statistics, "
            "individual central bank annual reports."
        ),
        source_account="World Gold Council",
        follower_count=None,
        score=8.5,
        quality_score=8.7,
        alternatives=[
            {
                "text": (
                    "Central banks bought more gold in 2023 than in any year since "
                    "Nixon closed the gold window in 1971. That sentence deserves "
                    "unpacking.\n\n"
                    "The 1,037 tonnes purchased wasn't driven by one or two outliers — "
                    "it was distributed across 24 separate central banks, with Poland, "
                    "Singapore, and China leading the EM cohort.\n\n"
                    "The motivation isn't mysterious. Reserve managers watched Russia's "
                    "$300bn in foreign reserves get frozen overnight in February 2022. "
                    "Gold can't be frozen. Gold held domestically can't be seized.\n\n"
                    "The policy implication: gold's role as a neutral reserve asset "
                    "is being reestablished after 50 years of declining relevance. "
                    "This isn't a momentum trade — it's a structural reallocation "
                    "that could take a decade to play out.\n\n"
                    "2024 YTD (through Q3): 857 tonnes. On pace for another record.\n\n"
                    "The buyers are patient. The volumes are large. The bid is real."
                ),
                "type": "thread",
                "label": "Thread",
            },
            {
                "text": (
                    "Central banks bought 1,037 tonnes of gold in 2023 — the most "
                    "since 1971. Understanding why requires looking at February 2022, "
                    "when $300 billion in Russian reserves were frozen overnight. "
                    "That event demonstrated that foreign exchange reserves held in "
                    "another sovereign's jurisdiction carry political risk that gold "
                    "does not. The subsequent surge in central bank gold accumulation "
                    "is a rational policy response, not speculation. Twenty-four central "
                    "banks participated in 2023 purchases, with Poland (130 tonnes), "
                    "Singapore (76 tonnes), and China (225 tonnes) leading. At 857 "
                    "tonnes through Q3 2024, the pace hasn't slowed. For gold demand "
                    "analysis, this is the most important structural development in "
                    "five decades."
                ),
                "type": "long_post",
                "label": "Long Post",
            },
        ],
        rationale=(
            "The central bank accumulation story is the structural thesis underlying "
            "the entire gold bull market. This is a thread/post format decision because "
            "the topic has enough depth to justify extended treatment — but the thread "
            "format keeps individual points digestible. The Russia-reserves angle is "
            "the most compelling explanation for why this cycle is different."
        ),
        urgency="medium",
        created_at=_dt(75),
        expires_at=_dt(75) + timedelta(hours=24),
    ),

    DraftItem(
        id=uuid.uuid4(),
        platform="content",
        status=DraftStatus.pending,
        source_url="https://www.kitco.com/news/article/2024-09-15/gold-etf-inflows",
        source_text=(
            "Gold ETF inflows analysis: Q3 2024 saw the first sustained period of "
            "positive inflows since 2020. Total holdings rose 52 tonnes over the "
            "quarter. North American funds led (+38t), European funds turned positive "
            "for the first time in two years (+11t), Asian funds flat (+3t). "
            "This reversal follows 18 months of consistent outflows."
        ),
        source_account="Kitco News",
        follower_count=None,
        score=7.6,
        quality_score=7.8,
        alternatives=[
            {
                "text": (
                    "The ETF inflow reversal matters because it signals a change in "
                    "Western investor positioning — the cohort that had been selling "
                    "gold since rates started rising in 2022 is now a buyer again. "
                    "Combined with persistent central bank demand, the demand composition "
                    "is becoming more constructive. The 52-tonne Q3 inflow is modest "
                    "against the 700-tonne gap to 2020 peak holdings, but three "
                    "consecutive months of positive flow is a meaningful signal of "
                    "trend change. Worth noting that this happened while real rates "
                    "were still elevated — the traditional relationship between ETF "
                    "demand and real yields appears to be weakening."
                ),
                "type": "long_post",
                "label": "Long Post",
            },
        ],
        rationale=(
            "ETF flow data is a leading indicator of Western institutional sentiment. "
            "The reversal after 18 months of outflows is analytically significant — "
            "it suggests the rate-sensitivity narrative may be overstated. "
            "Long-form format appropriate for an audience that wants data over "
            "quick takes."
        ),
        urgency="low",
        created_at=_dt(300),
        expires_at=_dt(300) + timedelta(hours=24),
    ),
]


async def main() -> None:
    engine = _get_engine()
    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with session_factory() as session:
        # Idempotency check — skip if pending items already exist
        result = await session.execute(
            select(func.count())
            .select_from(DraftItem)
            .where(DraftItem.status == DraftStatus.pending)
        )
        existing_count = result.scalar_one()

        if existing_count > 0:
            print(f"Seed data already exists ({existing_count} pending items), skipping.")
            return

        session.add_all(MOCK_ITEMS)
        await session.commit()
        print(f"Seeded {len(MOCK_ITEMS)} mock draft items successfully.")

    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
