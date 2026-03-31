"""Seed mock data for dashboard development and testing.

Usage: cd backend && python -m scripts.seed_mock_data
Requires DATABASE_URL environment variable set to a postgresql+asyncpg:// URL.

Creates 13 realistic gold sector draft items across Twitter, Instagram, and Content
platforms to enable immediate dashboard testing without running the agents.
"""

import asyncio
import os
import uuid
from datetime import datetime, timezone, timedelta

from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy import select, func

from app.models.draft_item import DraftItem, DraftStatus


def _get_engine():
    """Build an async engine from DATABASE_URL env var."""
    database_url = os.environ.get("DATABASE_URL")
    if not database_url:
        raise RuntimeError("DATABASE_URL environment variable is required")
    # Strip sslmode from URL and use connect_args instead (asyncpg requirement)
    url = database_url
    if "sslmode=" in url:
        from urllib.parse import urlparse, urlencode, parse_qs, urlunparse
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


now = datetime.now(timezone.utc)


def _dt(minutes_ago: int) -> datetime:
    return now - timedelta(minutes=minutes_ago)


# UUIDs for cross-linking related items
TWITTER_GOLDMAN_ID = uuid.uuid4()
INSTAGRAM_GOLD_CHART_ID = uuid.uuid4()


MOCK_ITEMS = [
    # ── TWITTER ITEMS ──────────────────────────────────────────────────────────

    DraftItem(
        id=TWITTER_GOLDMAN_ID,
        platform="twitter",
        status=DraftStatus.pending,
        source_url="https://x.com/GoldmanSachs/status/1872345678901234567",
        source_text=(
            "Central bank gold purchases hit a record 1,037 tonnes in 2023. "
            "We're now tracking 2024 YTD at 857 tonnes through Q3, suggesting "
            "another year above the 1,000-tonne threshold is possible. "
            "The structural bid beneath spot is real — this isn't speculative flow."
        ),
        source_account="@GoldmanSachs",
        follower_count=3_200_000,
        score=8.7,
        quality_score=8.9,
        alternatives=[
            {
                "text": (
                    "857 tonnes in 9 months puts 2024 central bank demand on pace to "
                    "match 2023's record. The bid beneath spot isn't speculative — it's "
                    "structural. Worth watching whether Turkey and China resume their "
                    "pace in Q4 after the Q3 pause."
                ),
                "type": "reply",
                "label": "Draft A",
            },
            {
                "text": (
                    "The 2023 record was driven by emerging market central banks "
                    "diversifying away from USD reserves. 2024's trajectory suggests "
                    "that thesis hasn't changed. The buyers are patient and the volumes "
                    "are large enough to matter at the margin."
                ),
                "type": "reply",
                "label": "Draft B",
            },
            {
                "text": (
                    "Structural central bank demand is the least-discussed driver of "
                    "the multi-year gold bull market. 857 tonnes YTD through Q3 2024 "
                    "tells you this isn't going away."
                ),
                "type": "retweet",
                "label": "RT Quote",
            },
        ],
        rationale=(
            "Goldman's central bank gold data point is highly relevant context for "
            "understanding the structural demand story. High engagement from a credible "
            "institutional source; the data is verifiable and material to gold's price "
            "outlook."
        ),
        urgency="high",
        related_id=INSTAGRAM_GOLD_CHART_ID,
        created_at=_dt(18),
        expires_at=_dt(18) + timedelta(hours=6),
    ),

    DraftItem(
        id=uuid.uuid4(),
        platform="twitter",
        status=DraftStatus.pending,
        source_url="https://x.com/PeterSchiff/status/1872456789012345678",
        source_text=(
            "Gold just broke $2,500 for the first time. The Fed has lost control "
            "of the inflation narrative and real rates are going negative again. "
            "This move is only getting started."
        ),
        source_account="@PeterSchiff",
        follower_count=1_050_000,
        score=7.9,
        quality_score=7.2,
        alternatives=[
            {
                "text": (
                    "The $2,500 break coincides with a meaningful shift in real rate "
                    "expectations — 10yr TIPS yield is back below 2% for the first "
                    "time since March. Historically that correlation has been tight. "
                    "Worth monitoring whether it holds as CPI prints come in."
                ),
                "type": "reply",
                "label": "Draft A",
            },
            {
                "text": (
                    "Breaking $2,500 removes the March 2024 all-time high as overhead "
                    "resistance. The next significant technical level is around $2,600 "
                    "based on the measured move from the February base. Price action "
                    "is being driven by macro, not just sentiment."
                ),
                "type": "reply",
                "label": "Draft B",
            },
        ],
        rationale=(
            "Schiff's commentary is widely followed in the gold community. The $2,500 "
            "break is a technically and psychologically significant level — good hook "
            "for adding analytical context around real rates."
        ),
        urgency="high",
        created_at=_dt(45),
        expires_at=_dt(45) + timedelta(hours=6),
    ),

    DraftItem(
        id=uuid.uuid4(),
        platform="twitter",
        status=DraftStatus.pending,
        source_url="https://x.com/WGCouncil/status/1872567890123456789",
        source_text=(
            "New data: Global gold ETF holdings rose 18.5 tonnes in September, "
            "the third consecutive month of inflows. Total holdings now stand at "
            "3,200 tonnes, still well below the 2020 peak of 3,900 tonnes. "
            "Western investment demand is coming back."
        ),
        source_account="@WGCouncil",
        follower_count=287_000,
        score=8.2,
        quality_score=8.5,
        alternatives=[
            {
                "text": (
                    "Three consecutive months of ETF inflows signals the turn in "
                    "Western investment demand that the bull case needed. At 3,200 "
                    "tonnes total, there's 700 tonnes of room before we're back at "
                    "2020 highs — that's significant potential buying if the macro "
                    "backdrop continues to support."
                ),
                "type": "reply",
                "label": "Draft A",
            },
            {
                "text": (
                    "The September WGC data matters because ETF demand was the missing "
                    "piece. Central bank buying has been strong since 2022, but Western "
                    "retail and institutional was flat. Three positive months changes "
                    "the demand composition story meaningfully."
                ),
                "type": "reply",
                "label": "Draft B",
            },
            {
                "text": (
                    "18.5 tonnes of ETF inflows in September — third consecutive month. "
                    "Western demand is rejoining the central bank bid. Gap to 2020 peak "
                    "holdings still represents significant latent buying potential."
                ),
                "type": "retweet",
                "label": "RT Quote",
            },
        ],
        rationale=(
            "WGC ETF data is primary source material. The three-month inflow trend is "
            "a meaningful data point that adds to the central bank demand story from a "
            "different segment of the market."
        ),
        urgency="medium",
        created_at=_dt(90),
        expires_at=_dt(90) + timedelta(hours=6),
    ),

    DraftItem(
        id=uuid.uuid4(),
        platform="twitter",
        status=DraftStatus.pending,
        source_url="https://x.com/MiningWeekly/status/1872678901234567890",
        source_text=(
            "BREAKING: Newmont acquires Newcrest in $19.2B deal, creating the "
            "world's largest gold miner with 100M oz in reserves. Deal closes Q1 2024. "
            "Combined entity produces 8.2M oz annually."
        ),
        source_account="@MiningWeekly",
        follower_count=93_000,
        score=6.8,
        quality_score=7.1,
        alternatives=[
            {
                "text": (
                    "The Newmont-Newcrest combination creates a tier-1 producer at a "
                    "scale the industry hasn't seen. 100M oz in reserves and 8.2M oz "
                    "annual production concentrates significant market power. "
                    "The question is whether integration complexity at this scale "
                    "delivers on the synergy projections."
                ),
                "type": "reply",
                "label": "Draft A",
            },
            {
                "text": (
                    "M&A at this scale typically signals a sector in late-cycle "
                    "consolidation. The strategic rationale is reserve replacement — "
                    "majors have underinvested in exploration for a decade. "
                    "Acquiring proved ounces in the ground is cheaper than finding "
                    "new ones at current drill costs."
                ),
                "type": "reply",
                "label": "Draft B",
            },
        ],
        rationale=(
            "Major M&A events reshape competitive dynamics in the sector. The reserve "
            "concentration and production scale angle provides genuine analytical value "
            "beyond the headline number."
        ),
        urgency="medium",
        created_at=_dt(120),
        expires_at=_dt(120) + timedelta(hours=6),
    ),

    DraftItem(
        id=uuid.uuid4(),
        platform="twitter",
        status=DraftStatus.pending,
        source_url="https://x.com/NickTimiraos/status/1872789012345678901",
        source_text=(
            "Fed holds rates at 5.25-5.50% as expected. Dot plot now shows only "
            "one cut in 2024, down from three projected in March. Powell: 'We need "
            "more evidence that inflation is moving sustainably toward 2%.' "
            "Market pricing one cut by December."
        ),
        source_account="@NickTimiraos",
        follower_count=720_000,
        score=9.1,
        quality_score=9.0,
        alternatives=[
            {
                "text": (
                    "The dot plot revision from three cuts to one is more hawkish "
                    "than futures markets had priced. Real rates stay elevated for "
                    "longer — the headwind to gold from rate differential persists. "
                    "Spot holding $2,450 despite this is the more interesting signal; "
                    "the market may be looking through the short-term rate path."
                ),
                "type": "reply",
                "label": "Draft A",
            },
            {
                "text": (
                    "Gold's resilience at $2,450 through a hawkish Fed surprise "
                    "speaks to how much structural buying (central banks, EM demand) "
                    "is absorbing what would previously have been a significant "
                    "headwind. The rate-sensitivity of gold appears to have declined "
                    "in this cycle."
                ),
                "type": "reply",
                "label": "Draft B",
            },
            {
                "text": (
                    "Powell takes one cut off the 2024 table. Gold at $2,450 doesn't "
                    "flinch. The decoupling from real rates is the story of this cycle."
                ),
                "type": "retweet",
                "label": "RT Quote",
            },
        ],
        rationale=(
            "Fed decisions are the single most-watched macro event for gold. The "
            "observation that gold is holding through hawkish surprises is a genuinely "
            "useful analytical point that most commentators will miss."
        ),
        urgency="high",
        created_at=_dt(25),
        expires_at=_dt(25) + timedelta(hours=6),
    ),

    # ── INSTAGRAM ITEMS ────────────────────────────────────────────────────────

    DraftItem(
        id=uuid.uuid4(),
        platform="instagram",
        status=DraftStatus.pending,
        source_url="https://www.instagram.com/p/C8AbCdEfGhI/",
        source_text=(
            "400-oz London Good Delivery bars at the Bank of England vault. "
            "Each bar weighs 12.4kg and contains 99.5% pure gold. "
            "The BoE holds ~400,000 bars — roughly £400bn at current prices."
        ),
        source_account="@bankofengland",
        follower_count=185_000,
        score=7.5,
        quality_score=7.8,
        alternatives=[
            {
                "text": (
                    "Each bar 12.4kg, 99.5% purity. The Bank of England custodies "
                    "~400,000 of them for central banks worldwide — roughly £400bn "
                    "at today's spot. The London vault system remains the primary "
                    "settlement point for the global OTC gold market."
                ),
                "type": "comment",
                "label": "Draft A",
            },
            {
                "text": (
                    "400-oz Good Delivery bars — the unit of account for central "
                    "bank gold. The BoE has held gold in custody here since 1694. "
                    "The 400,000 bars they hold today represent a significant share "
                    "of all above-ground monetary gold ever mined."
                ),
                "type": "comment",
                "label": "Draft B",
            },
        ],
        rationale=(
            "Visual of iconic gold bars generates strong engagement from the gold "
            "community. Adding specific data points (weight, purity, vault scale) "
            "elevates the comment above generic praise."
        ),
        urgency="low",
        created_at=_dt(200),
        expires_at=_dt(200) + timedelta(hours=12),
    ),

    DraftItem(
        id=uuid.uuid4(),
        platform="instagram",
        status=DraftStatus.pending,
        source_url="https://www.instagram.com/p/C8BcDeFgHiJ/",
        source_text=(
            "Aerial shot of the Cadia Valley gold-copper mine, Australia. "
            "Operated by Newcrest, produces ~450,000 oz gold annually. "
            "The open pit is 3km across and visible from space."
        ),
        source_account="@newcrестmining",
        follower_count=42_000,
        score=6.9,
        quality_score=7.0,
        alternatives=[
            {
                "text": (
                    "Cadia Valley — one of the world's largest gold-copper porphyry "
                    "deposits. At ~450,000 oz/year, it's a tier-1 asset by any "
                    "definition. The gold-copper byproduct credit structure means the "
                    "all-in sustaining cost is among the lowest in the industry."
                ),
                "type": "comment",
                "label": "Draft A",
            },
            {
                "text": (
                    "The scale only reads correctly from the air. Cadia processes "
                    "around 35 million tonnes of ore per year to produce those "
                    "450,000 gold ounces — the grade is low but the volume is "
                    "staggering. Economics work because copper credits offset "
                    "most of the mining cost."
                ),
                "type": "comment",
                "label": "Draft B",
            },
        ],
        rationale=(
            "Aerial mining photography consistently drives strong engagement. "
            "The AISC angle (copper byproduct credits) is a genuine differentiator "
            "that mining-focused followers will find insightful."
        ),
        urgency="low",
        created_at=_dt(240),
        expires_at=_dt(240) + timedelta(hours=12),
    ),

    DraftItem(
        id=INSTAGRAM_GOLD_CHART_ID,
        platform="instagram",
        status=DraftStatus.pending,
        source_url="https://www.instagram.com/p/C8CdEfGhIjK/",
        source_text=(
            "Gold price chart showing the breakout above $2,000 resistance in Dec 2023, "
            "the consolidation through Q1 2024, and the acceleration to $2,500 in Q3 2024. "
            "Central bank demand annotated at each major accumulation phase."
        ),
        source_account="@kitcometal",
        follower_count=95_000,
        score=8.1,
        quality_score=8.3,
        alternatives=[
            {
                "text": (
                    "Three phases: breakout ($2,000 Dec 2023), base-building (Q1 2024), "
                    "acceleration ($2,500 Q3 2024). Each phase coincided with documented "
                    "central bank accumulation. The bid isn't speculative — it's "
                    "institutions building strategic reserves at scale."
                ),
                "type": "comment",
                "label": "Draft A",
            },
            {
                "text": (
                    "The chart shows what happens when a structural buyer with multi-year "
                    "conviction enters a market. Central banks bought through the $2,000 "
                    "breakout, the Q1 consolidation, and the Q3 run to $2,500. "
                    "They're not chasing price — they're building positions."
                ),
                "type": "comment",
                "label": "Draft B",
            },
            {
                "text": (
                    "This is the cleanest visual representation of the central bank "
                    "bid thesis. Each major accumulation phase documented against price "
                    "action — the correlation is hard to argue with."
                ),
                "type": "comment",
                "label": "Draft C",
            },
        ],
        rationale=(
            "Chart posts with educational context outperform raw price charts. "
            "This ties directly to the Goldman Sachs central bank tweet — same "
            "underlying story, different format and platform."
        ),
        urgency="high",
        related_id=TWITTER_GOLDMAN_ID,
        created_at=_dt(30),
        expires_at=_dt(30) + timedelta(hours=12),
    ),

    DraftItem(
        id=uuid.uuid4(),
        platform="instagram",
        status=DraftStatus.pending,
        source_url="https://www.instagram.com/p/C8DeFgHiJkL/",
        source_text=(
            "Interview clip: Agnico Eagle CEO Ammar Al-Joundi on costs, margins, "
            "and the outlook for tier-1 gold producers in a $2,400+ environment. "
            "'At these prices, the industry generates significant free cash flow — "
            "the challenge is deploying it wisely.'"
        ),
        source_account="@agnicoeagle",
        follower_count=31_000,
        score=7.3,
        quality_score=7.5,
        alternatives=[
            {
                "text": (
                    "Al-Joundi's point is the right one. Agnico's AISC runs ~$1,200-1,250/oz. "
                    "At $2,400 spot, that's $1,150+ of margin per ounce. "
                    "The free cash flow question is real — M&A, returns to shareholders, "
                    "or reinvestment in growth? The capital allocation decisions made "
                    "in this cycle will define the next decade."
                ),
                "type": "comment",
                "label": "Draft A",
            },
            {
                "text": (
                    "Agnico has consistently been one of the best-run senior producers "
                    "on capital allocation discipline. Worth listening to Al-Joundi's "
                    "full take on where they see the best return on that free cash flow "
                    "at current gold prices."
                ),
                "type": "comment",
                "label": "Draft B",
            },
        ],
        rationale=(
            "CEO commentary from a respected tier-1 producer provides credible "
            "industry perspective. The AISC vs. spot margin context adds analytical "
            "value that generic 'great interview' comments don't."
        ),
        urgency="medium",
        created_at=_dt(150),
        expires_at=_dt(150) + timedelta(hours=12),
    ),

    DraftItem(
        id=uuid.uuid4(),
        platform="instagram",
        status=DraftStatus.pending,
        source_url="https://www.instagram.com/p/C8EfGhIjKlM/",
        source_text=(
            "Time-lapse of Fort Knox exterior with caption: '147.3 million troy ounces "
            "stored here as of 2024. The US has not conducted a full audit since 1953.' "
            "Video has 2.1M views."
        ),
        source_account="@goldhistory",
        follower_count=220_000,
        score=7.8,
        quality_score=7.4,
        alternatives=[
            {
                "text": (
                    "147.3M oz at $2,400 spot = $354bn. The audit question is genuinely "
                    "interesting from a transparency standpoint — not conspiracy, just "
                    "standard fiduciary practice. The US Treasury hasn't published a "
                    "full independent audit since Eisenhower was president."
                ),
                "type": "comment",
                "label": "Draft A",
            },
            {
                "text": (
                    "Fort Knox holds about 4% of all gold ever mined in human history. "
                    "The 1953 audit figure is worth contextualizing — gold holdings are "
                    "reported monthly via the US Treasury's International Reserve position, "
                    "but a full physical count and assay verification is a different thing."
                ),
                "type": "comment",
                "label": "Draft B",
            },
        ],
        rationale=(
            "2.1M views indicates viral potential. The audit angle is factually "
            "grounded (not conspiratorial) and the Treasury transparency framing "
            "elevates it from clickbait to legitimate commentary."
        ),
        urgency="medium",
        created_at=_dt(60),
        expires_at=_dt(60) + timedelta(hours=12),
    ),

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
            select(func.count()).select_from(DraftItem).where(DraftItem.status == DraftStatus.pending)
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
