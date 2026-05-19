"""v2.1 Weekly Viral Sweeper — Phase 7 cron + orchestrator.

Fires every Sunday at 08:00 PT via APScheduler (registered in worker.py
by Plan 07-05 via _make_weekly_sweeper_job factory + CronTrigger).

Orchestration shape mirrors scheduler/agents/daily_summary.py exactly:
    idempotency check → agent_runs INSERT (status='running') →
    X recent-search ingest → virality compute over daily_summaries.raw_sources_jsonb.gold_news[] →
    Sonnet content-angle generation (or insufficient-signal fallback) →
    status mapping → weekly_sweeps INSERT → finally telemetry.

PIVOT NOTE: This module consumes X API (tweepy) via agents.x_ingest, NOT
Reddit (asyncpraw). See 07-CONTEXT.md decision D-03 for rationale. The
weekly_sweeps.reddit_top_md column is preserved from the Phase 5 migration
even though X posts are stored there (rename would add zero functional value).

Manual escape hatch (P13):
    If a Railway deploy lands after Sunday 08:30 PT, run from the Railway shell:
        python -m agents.weekly_sweeper
    This invokes the module's __main__ block directly, bypassing APScheduler.

Pitfall mitigations bundled here:
  P3  (NULL raw_sources_jsonb)  — _compute_virality guards (row.raw_sources_jsonb or {}).get("gold_news", [])
  P6  (Sonnet timeout missing)   — AsyncAnthropic(timeout=60.0)
  P7  (token-budget overflow)    — each X post text truncated to [:500] before Sonnet
  P8  (bearish gold angles)      — system prompt enforces gold bull thesis bias
  P10 (URL canonicalization)     — canonical_url() strips UTM/fbclid/gclid/ref/source/_ga
  P12 (reconcile_stale_runs)     — expected runtime ~25s, within 30-min threshold (no code change)
  P13 (Sunday-after-deploy miss) — manual escape hatch documented above + __main__ block at bottom
  P14 (Sonnet hallucination)     — grounding rule "use ONLY facts present in supplied inputs"
  P15 (insufficient signal)      — len(x_posts) < 3 OR len(viral_stories) < 3 → skip Sonnet, write canned fallback
  P-NEW (X API quota near cap)   — delegated to agents.x_ingest (Plan 07-02)
"""
from __future__ import annotations

import asyncio
import json
import logging
from datetime import date, datetime, timedelta, timezone
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse
from zoneinfo import ZoneInfo

from anthropic import AsyncAnthropic
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from agents.content_agent import deduplicate_stories
from agents.x_ingest import fetch_top_x_posts
from config import get_settings
from database import AsyncSessionLocal
from models.agent_run import AgentRun
from models.daily_summary import DailySummary
from models.weekly_sweep import WeeklySweep

logger = logging.getLogger(__name__)

AGENT_NAME = "weekly_sweeper"
LA_TZ = ZoneInfo("America/Los_Angeles")
SONNET_MODEL = "claude-sonnet-4-6"
SONNET_MAX_TOKENS = 1000
SONNET_TIMEOUT_S = 60.0
IDEMPOTENCY_WINDOW_MIN = 60  # SWEEP-10 — locked
VIRALITY_LOOKBACK_DAYS = 7
VIRALITY_TOP_N = 5
SUFFICIENT_SIGNAL_MIN = 3   # P15 — locked from D-13
X_POST_TRUNCATE_CHARS = 500  # P7 — locked from D-12

# Combined X recent-search query — locked in 07-CONTEXT.md D-05
X_SEARCH_QUERY = (
    '("gold price" OR "gold market" OR "gold mining" OR "central bank gold" '
    'OR $GOLD OR $GLD OR $GDX OR $NEM OR $AEM '
    'OR #gold OR #goldprice OR #goldmining) '
    '-is:retweet -is:reply lang:en'
)

INSUFFICIENT_SIGNAL_FALLBACK = "Insufficient signal this week — angles not generated"

# URL tracking-param strip set (P10). Lowercase match against query param name.
_STRIPPED_QUERY_PARAMS = frozenset({
    "utm_source", "utm_medium", "utm_campaign", "utm_term", "utm_content",
    "fbclid", "gclid", "ref", "source", "_ga",
})


def canonical_url(url: str) -> str:
    """Canonicalize a URL for cross-source virality grouping (P10).

    - Lowercase host
    - Strip tracking query params (UTM/fbclid/gclid/ref/source/_ga)
    - Sort remaining query params (deterministic order)
    - Strip trailing slash from path (unless path is just "/")
    - Preserve scheme, port, fragment-free

    Defensive: returns the input unchanged if urlparse fails.
    """
    try:
        parsed = urlparse(url)
        host = parsed.netloc.lower()
        path = parsed.path
        if path.endswith("/") and len(path) > 1:
            path = path[:-1]

        params = parse_qsl(parsed.query, keep_blank_values=True)
        kept = [(k, v) for (k, v) in params if k.lower() not in _STRIPPED_QUERY_PARAMS]
        kept.sort(key=lambda kv: kv[0])
        query = urlencode(kept)

        return urlunparse((parsed.scheme.lower(), host, path, "", query, ""))
    except Exception as exc:
        logger.warning("canonical_url failed for %r: %s — returning input as-is", url, exc)
        return url


async def _compute_virality(session: AsyncSession) -> list[dict]:
    """SWEEP-07 — compute top-5 most-cross-referenced stories from last 7 days of daily_summaries.

    Algorithm:
      1. SELECT all daily_summaries where generated_at >= now - 7 days AND status IN ('completed', 'partial')
      2. For each row: extract raw_sources_jsonb.gold_news[] (guard P3: row.raw_sources_jsonb or {})
      3. Per-row pre-dedup via deduplicate_stories (P9 — same-row duplicates count once)
      4. For each story: canonicalize link, group by canonical_url
      5. For each canonical_url: count distinct source_name values (NOT total occurrences)
      6. Sort by distinct_source_count DESC; return top 5 as
         [{canonical_url, title, distinct_source_count, source_names, sample_published_at}]

    Returns:
        List of up to 5 dicts (may be empty on no data or all-NULL rows).
    """
    cutoff = datetime.now(timezone.utc) - timedelta(days=VIRALITY_LOOKBACK_DAYS)
    stmt = (
        select(DailySummary)
        .where(DailySummary.generated_at >= cutoff)
        .where(DailySummary.status.in_(["completed", "partial"]))
    )
    result = await session.execute(stmt)
    rows = result.scalars().all()

    # canonical_url → {"title": str, "source_names": set, "sample_published_at": str|None}
    agg: dict[str, dict] = {}

    for row in rows:
        # P3 guard — failed rows may have raw_sources_jsonb=None
        raw = row.raw_sources_jsonb or {}
        stories = raw.get("gold_news", []) or []
        if not stories:
            continue

        # P9 — per-row dedup BEFORE cross-summary counting
        # Build dicts with the shape deduplicate_stories expects: link, title, source_name
        row_stories = [
            {
                "link": s.get("link", ""),
                "title": s.get("title", ""),
                "source_name": s.get("source_name", ""),
                "published_at": s.get("published_at"),
            }
            for s in stories if s.get("link")
        ]
        deduped = deduplicate_stories(row_stories)

        for s in deduped:
            canonical = canonical_url(s["link"])
            if not canonical:
                continue
            entry = agg.setdefault(canonical, {
                "canonical_url": canonical,
                "title": s["title"],
                "source_names": set(),
                "sample_published_at": s.get("published_at"),
            })
            if s["source_name"]:
                entry["source_names"].add(s["source_name"])

    # Build result list with serializable source_names (list, not set)
    ranked = [
        {
            "canonical_url": v["canonical_url"],
            "title": v["title"],
            "distinct_source_count": len(v["source_names"]),
            "source_names": sorted(v["source_names"]),
            "sample_published_at": v["sample_published_at"],
        }
        for v in agg.values()
        if v["source_names"]
    ]
    ranked.sort(key=lambda r: r["distinct_source_count"], reverse=True)
    return ranked[:VIRALITY_TOP_N]
