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
  P6  (Sonnet timeout missing)   — anthropic_client constructed with timeout=60.0
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
from sqlalchemy.ext.asyncio import AsyncSession

from agents.content_agent import deduplicate_stories
from agents.x_ingest import fetch_top_x_posts
from anthropic_client import get_anthropic_client
from database import AsyncSessionLocal
from models.agent_run import AgentRun
from models.daily_summary import DailySummary
from models.weekly_sweep import WeeklySweep
# v3.0 Phase 9 (TENANT-03) — scheduler-side scoped helpers. The CI grep gate
# at scripts/verify-tenant-isolation.sh requires every multi-tenant select to
# route through this module; lines 131 (DailySummary virality scan) + 320
# (WeeklySweep idempotency) below have been rewritten accordingly.
from queries.scoped import scoped_summaries, scoped_weekly_sweeps

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
    # v3.0 Phase 9 (TENANT-03): scope to Seva. Weekly Viral Sweeper is a
    # Seva-only job in v3.0 — D-01 reserves lock ID 1021 for juno_weekly_sweeper
    # but defers its registration to v3.1+ (slot-only). When Juno Sweeper
    # ships, this helper becomes parameterized on company_id.
    stmt = (
        scoped_summaries("seva")
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


# ---------------------------------------------------------------------------
# Sonnet content-angle generation (D-11, D-12, P6, P7, P8, P14, P15)
# ---------------------------------------------------------------------------

SONNET_SYSTEM_PROMPT = """\
You are a tactical content strategist for a senior gold-sector analyst. The audience is a gold-focused social media account whose voice is data-driven, Bloomberg commodities-desk energy. You generate exactly 3 content angles each week, each connecting an X (Twitter) signal from the gold conversation with a mainstream news signal that the operator's audience is also seeing this week.

Every content angle MUST support the gold bull thesis ("gold price goes higher"). Reframe bearish-leaning X chatter through the bull lens (e.g., "Bitcoin replacing gold" -> flip to "this skepticism is the contrarian signal — flows tell a different story") or DISCARD bearish signals entirely. Do NOT produce a balanced "both sides" angle.

Grounding rule: Use ONLY facts, figures, claims, and source names present in the supplied inputs (X posts + cross-referenced news stories). Do NOT invent quotes, statistics, source attributions, or events. If you cannot ground an angle in the supplied inputs, do not generate it — return fewer than 3 angles rather than hallucinate.

Output MUST be markdown in this exact structure (no preamble, no postamble):

### Angle 1: {short headline tying X signal + news signal}

**Hook (1-2 sentences):** {opening that connects the X chatter to the news event}

**Bullets:**
* X signal: {what the X chatter is showing} (@{author_username})
* News signal: {what the news story is showing} ({source_name})
* Bull connection: {why this is bullish for gold}

### Angle 2: {headline}
{same structure}

### Angle 3: {headline}
{same structure}
"""


async def _build_x_posts_md(x_posts: list[dict]) -> str:
    """Format X posts as Markdown for weekly_sweeps.reddit_top_md column.

    Section header per D-19 / SWEEP-13: "Top X Posts This Week".
    """
    if not x_posts:
        return "### Top X Posts This Week\n\nNo X posts surfaced this week."

    lines = ["### Top X Posts This Week", ""]
    for p in x_posts:
        engagement = p["likes"] + p["retweets"] * 2 + int(p["replies"] * 1.5)
        text_preview = p["text"][:200].replace("\n", " ")
        lines.append(
            f"* **[@{p['author_username']}]({p['tweet_url']})** "
            f"(♥{p['likes']} ⟲{p['retweets']} 💬{p['replies']}, score={engagement}): "
            f"{text_preview}"
        )
    return "\n".join(lines)


async def _build_virality_md(viral_stories: list[dict]) -> str:
    """Format virality stories as Markdown for weekly_sweeps.story_virality_md.

    Section header per D-19 / SWEEP-13: "Most Cross-Referenced Stories".
    """
    if not viral_stories:
        return "### Most Cross-Referenced Stories\n\nNo cross-referenced stories this week."

    lines = ["### Most Cross-Referenced Stories", ""]
    for s in viral_stories:
        sources_str = ", ".join(s["source_names"][:5])
        lines.append(
            f"* **{s['title']}** — {s['distinct_source_count']} distinct sources "
            f"({sources_str}) — [link]({s['canonical_url']})"
        )
    return "\n".join(lines)


async def _call_sonnet_for_angles(
    x_posts: list[dict],
    viral_stories: list[dict],
    anthropic_client: AsyncAnthropic,
) -> str | None:
    """Build user prompt + call Sonnet for 3 content angles. Returns None on failure."""
    prompt_parts = [
        "Generate exactly 3 content angles connecting an X signal with a mainstream news signal.",
        "",
        "## Top X posts this week (top 10 by engagement, ranked):",
    ]
    for i, p in enumerate(x_posts, start=1):
        truncated = p["text"][:X_POST_TRUNCATE_CHARS].replace("\n", " ")  # P7
        prompt_parts.append(
            f"\n[X Post {i}] @{p['author_username']} (♥{p['likes']} ⟲{p['retweets']} 💬{p['replies']})\n"
            f"URL: {p['tweet_url']}\n"
            f"Text: {truncated}"
        )

    prompt_parts.append("\n\n## Most cross-referenced stories this week (top 5 by distinct-source count):")
    for i, s in enumerate(viral_stories, start=1):
        sources = ", ".join(s["source_names"][:5])
        prompt_parts.append(
            f"\n[Story {i}] {s['title']}\n"
            f"URL: {s['canonical_url']}\n"
            f"Distinct sources: {s['distinct_source_count']} ({sources})"
        )

    user_prompt = "\n".join(prompt_parts)

    try:
        response = await anthropic_client.messages.create(
            model=SONNET_MODEL,
            max_tokens=SONNET_MAX_TOKENS,
            system=SONNET_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_prompt}],
        )
        return response.content[0].text.strip()
    except Exception as exc:
        logger.exception("weekly_sweeper: Sonnet content-angle call failed: %s", exc)
        return None


# ---------------------------------------------------------------------------
# Idempotency + week-bounds helpers (SWEEP-10)
# ---------------------------------------------------------------------------

def _sunday_of_this_week(now_utc: datetime) -> date:
    """Return the date of the Sunday of the current week in America/Los_Angeles.

    Cron fires Sunday 08:00 PT, so "this week's Sunday" is today (in LA tz).
    For idempotency purposes we want the LA-tz Sunday date.
    """
    now_la = now_utc.astimezone(LA_TZ)
    return now_la.date()


async def _idempotency_skip(session: AsyncSession, now_utc: datetime) -> bool:
    """SWEEP-10 — return True if a recent Seva row already exists in 60-min window.

    v3.0 Phase 9 (TENANT-03): tenant-scoped to 'seva' via scoped_weekly_sweeps.
    The Juno Weekly Sweeper (D-01: lock 1021 slot-only) lands in v3.1+ and
    will get its own per-company idempotency check independently.
    """
    sunday = _sunday_of_this_week(now_utc)
    cutoff = now_utc - timedelta(minutes=IDEMPOTENCY_WINDOW_MIN)
    stmt = (
        scoped_weekly_sweeps("seva")
        .with_only_columns(WeeklySweep.id)
        .where(WeeklySweep.week_start == sunday)
        .where(WeeklySweep.generated_at >= cutoff)
        .where(WeeklySweep.status.in_(["running", "completed"]))
        .limit(1)
    )
    result = await session.execute(stmt)
    return result.scalar_one_or_none() is not None


# ---------------------------------------------------------------------------
# run_weekly_sweeper — orchestration entry point (SWEEP-06)
# ---------------------------------------------------------------------------

async def run_weekly_sweeper() -> None:
    """Weekly sweeper entry point. Called from worker.py via _make_weekly_sweeper_job.

    Status mapping (SWEEP-11):
      completed: all 3 sections succeeded (insufficient-signal fallback counts as designed-completion)
      partial:   at least one section failed unexpectedly but the row can render
      failed:    no markdown could be assembled at all

    Manual escape hatch (P13):
      python -m agents.weekly_sweeper
    """
    now_utc = datetime.now(timezone.utc)
    sunday = _sunday_of_this_week(now_utc)
    week_start = sunday
    week_end = sunday + timedelta(days=6)

    async with AsyncSessionLocal() as session:
        if await _idempotency_skip(session, now_utc):
            logger.info(
                "weekly_sweeper idempotency_skip — recent row exists for week_start=%s within %d min window",
                sunday, IDEMPOTENCY_WINDOW_MIN,
            )
            return

    agent_run = AgentRun(
        agent_name=AGENT_NAME,
        started_at=now_utc,
        items_found=0,
        items_queued=0,
        items_filtered=0,
        status="running",
    )
    async with AsyncSessionLocal() as session:
        session.add(agent_run)
        await session.commit()
        await session.refresh(agent_run)

    agent_run_id = agent_run.id
    x_posts: list[dict] = []
    viral_stories: list[dict] = []
    x_md: str | None = None
    virality_md: str | None = None
    angles_md: str | None = None
    sections_failed: list[str] = []
    per_section_errors: list[str] = []
    insufficient_signal_path = False
    run_status = "failed"
    error_text: str | None = None

    # v3.1 Phase 12 — Seva sweeper Sonnet routes through per-tenant resolver (D-07, D-09).
    # Resolver internally calls get_settings(); no need to load it here.
    anthropic_client = get_anthropic_client("seva", timeout=SONNET_TIMEOUT_S)

    try:
        # --- Section 1: X ingest ---
        try:
            x_posts = await fetch_top_x_posts(query=X_SEARCH_QUERY, max_results=100)
            x_md = await _build_x_posts_md(x_posts)
            if not x_posts:
                sections_failed.append("x_ingest")
                per_section_errors.append("x_ingest: returned 0 posts (quota cap or empty result)")
        except Exception as exc:
            logger.exception("weekly_sweeper: x_ingest crashed")
            per_section_errors.append(f"x_ingest: {type(exc).__name__}: {str(exc)[:200]}")
            sections_failed.append("x_ingest")
            x_md = "### Top X Posts This Week\n\nX ingest failed this week."

        # --- Section 2: Virality compute ---
        try:
            async with AsyncSessionLocal() as session:
                viral_stories = await _compute_virality(session)
            virality_md = await _build_virality_md(viral_stories)
            if not viral_stories:
                sections_failed.append("virality")
                per_section_errors.append("virality: 0 cross-referenced stories in last 7 days")
        except Exception as exc:
            logger.exception("weekly_sweeper: virality compute crashed")
            per_section_errors.append(f"virality: {type(exc).__name__}: {str(exc)[:200]}")
            sections_failed.append("virality")
            virality_md = "### Most Cross-Referenced Stories\n\nVirality compute failed this week."

        # --- Section 3: Sonnet content angles (or P15 fallback) ---
        if len(x_posts) < SUFFICIENT_SIGNAL_MIN or len(viral_stories) < SUFFICIENT_SIGNAL_MIN:
            angles_md = f"### 3 Content Angles\n\n{INSUFFICIENT_SIGNAL_FALLBACK}"
            insufficient_signal_path = True
            logger.info(
                "weekly_sweeper: insufficient signal (x_posts=%d, viral_stories=%d) — skipping Sonnet, writing fallback",
                len(x_posts), len(viral_stories),
            )
        else:
            angles_raw = await _call_sonnet_for_angles(x_posts, viral_stories, anthropic_client)
            if angles_raw is None:
                sections_failed.append("sonnet")
                per_section_errors.append("sonnet: Sonnet call returned None (see logs for traceback)")
                angles_md = "### 3 Content Angles\n\nContent angle generation failed this week."
            else:
                angles_md = angles_raw

        # --- Status mapping (SWEEP-11) ---
        # The insufficient-signal path is a DESIGNED completion (P15), not a failure;
        # x_ingest/virality being empty are still flagged in sections_failed, so we
        # need to special-case: if ONLY (x_ingest + virality empty) AND we took the
        # insufficient-signal path, status is 'completed' (sparse week is normal).
        if insufficient_signal_path and set(sections_failed) <= {"x_ingest", "virality"}:
            # Sparse-week designed completion — angles_md has fallback copy
            run_status = "completed"
        elif not sections_failed:
            run_status = "completed"
        elif x_md or virality_md or angles_md:
            run_status = "partial"
        else:
            run_status = "failed"

        # --- Write weekly_sweeps row ---
        raw_sources = {
            "x_posts": [dict(p) for p in x_posts[:10]],
            "viral_stories": viral_stories,
            "x_search_query": X_SEARCH_QUERY,
        }
        # JSON-safety: convert datetimes (P3-mirror — daily_summary.py:204-217)
        for p in raw_sources["x_posts"]:
            if hasattr(p.get("created_at"), "isoformat"):
                p["created_at"] = p["created_at"].isoformat()

        async with AsyncSessionLocal() as session:
            sweep_row = WeeklySweep(
                # v3.0 Phase 9 (TENANT-01) — explicit Seva tenant on every write.
                company_id="seva",
                generated_at=now_utc,
                week_start=week_start,
                week_end=week_end,
                reddit_top_md=x_md,            # column name kept from Phase 5; stores X posts under pivot
                story_virality_md=virality_md,
                content_angles_md=angles_md,
                raw_sources_jsonb=raw_sources,
                status=run_status,
                error_text=None,
                agent_run_id=agent_run_id,
            )
            session.add(sweep_row)
            await session.commit()

    except Exception as run_exc:
        logger.exception("weekly_sweeper run failed catastrophically: %s", run_exc)
        error_text = f"{type(run_exc).__name__}: {str(run_exc)[:500]}"
        run_status = "failed"
        try:
            async with AsyncSessionLocal() as session:
                failure_row = WeeklySweep(
                    # v3.0 Phase 9 (TENANT-01) — explicit Seva tenant.
                    company_id="seva",
                    generated_at=now_utc,
                    week_start=week_start,
                    week_end=week_end,
                    reddit_top_md=None,
                    story_virality_md=None,
                    content_angles_md=None,
                    raw_sources_jsonb={"error": error_text},
                    status="failed",
                    error_text=error_text,
                    agent_run_id=agent_run_id,
                )
                session.add(failure_row)
                await session.commit()
        except Exception:
            logger.exception("weekly_sweeper failure-row write ALSO failed")

    finally:
        try:
            notes_payload = {
                "x_posts_count": len(x_posts),
                "viral_stories_count": len(viral_stories),
                "sections_failed": sections_failed,
                "insufficient_signal": insufficient_signal_path,
            }
            async with AsyncSessionLocal() as session:
                fresh = await session.get(AgentRun, agent_run_id)
                if fresh is not None:
                    fresh.status = run_status
                    fresh.ended_at = datetime.now(timezone.utc)
                    fresh.items_found = len(x_posts)
                    fresh.items_queued = 3 - len(sections_failed)
                    fresh.items_filtered = len(sections_failed)
                    fresh.notes = json.dumps(notes_payload)
                    combined_errors = [e for e in ([error_text] + per_section_errors) if e]
                    if combined_errors:
                        fresh.errors = combined_errors
                    await session.commit()
        except Exception:
            logger.exception("weekly_sweeper agent_runs telemetry update failed")


# ---------------------------------------------------------------------------
# Manual escape hatch (P13) — python -m agents.weekly_sweeper
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    asyncio.run(run_weekly_sweeper())
