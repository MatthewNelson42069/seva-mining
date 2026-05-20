# Architecture: v2.0 Daily Summary Feed Integration

**Domain:** Seva Mining — pivot from 6-sub-agent approval dashboard to 2x-daily summary feed
**Researched:** 2026-05-05
**Confidence:** HIGH (all findings verified against existing source files)

---

## What Changes vs What Stays

### Unchanged (reuse as-is)
- `scheduler/worker.py` — `with_advisory_lock`, `_make_sub_agent_job`, `reconcile_stale_runs`, `build_scheduler` pattern
- `scheduler/agents/content_agent.py` — `fetch_stories()` called as-is (no signature change)
- `scheduler/services/whatsapp.py` — `send_whatsapp_message(message: str)` for both delivery and failure alert
- `scheduler/models/agent_run.py` — write a row per daily_summary fire for observability
- `backend/app/main.py` — add one `include_router` call
- `frontend/src/api/client.ts` + auth wiring — no change
- Neon Postgres + Railway dual-service topology

### New Files

| File | Type |
|------|------|
| `backend/alembic/versions/0010_add_daily_summaries.py` | NEW migration |
| `backend/app/models/daily_summary.py` | NEW SQLAlchemy model (backend) |
| `scheduler/models/daily_summary.py` | NEW SQLAlchemy model (scheduler parity) |
| `backend/app/routers/summaries.py` | NEW FastAPI router |
| `backend/app/schemas/daily_summary.py` | NEW Pydantic schemas |
| `scheduler/agents/daily_summary.py` | NEW agent module |
| `scheduler/agents/ontario_law.py` | NEW ingestion module |
| `scheduler/agents/ontario_stats.py` | NEW ingestion module |
| `frontend/src/pages/SummaryFeedPage.tsx` | NEW page component |
| `frontend/src/api/summaries.ts` | NEW API + TanStack Query hook |
| `frontend/src/components/SummaryCard.tsx` | NEW card component |
| `frontend/src/components/SectionBlock.tsx` | NEW section renderer |

### Modified Files

| File | Change |
|------|--------|
| `scheduler/worker.py` | Add `daily_summary` import + tuple in `CONTENT_CRON_AGENTS`; add `daily_summary_prune` as separate scheduled job; update `JOB_LOCK_IDS` |
| `backend/app/main.py` | Add `from app.routers.summaries import router as summaries_router` + `app.include_router(summaries_router)` |
| `frontend/src/App.tsx` | Replace `/` Navigate redirect with `<SummaryFeedPage />`; add `/queue` → `/` redirect; retire `/agents/:slug` route (leave in place as dead code or redirect) |

---

## Database Layer

### `daily_summaries` Table Schema

```sql
CREATE TABLE daily_summaries (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    generated_at    TIMESTAMPTZ NOT NULL,
    period_label    VARCHAR(20) NOT NULL,       -- '08:00 PT' or '12:00 PT'
    gold_news_md    TEXT,                       -- markdown bullets, NULL if section failed
    ontario_law_md  TEXT,                       -- markdown bullets, NULL if section failed
    ontario_stats_md TEXT,                      -- markdown bullets, NULL if no data
    raw_sources_jsonb JSONB,                    -- forensics: articles + Ontario hits that fed the summary
    status          VARCHAR(20) NOT NULL,       -- 'completed' | 'failed' | 'partial'
    error_text      TEXT,                       -- NULL on success; populated if status='failed'
    agent_run_id    UUID REFERENCES agent_runs(id) ON DELETE SET NULL,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX ix_daily_summaries_generated_at ON daily_summaries (generated_at DESC);
```

**Column decisions:**

- `period_label VARCHAR(20)` — '08:00 PT' or '12:00 PT'. String (not time) because it's a display label for the card header "Summary as of 08:00 PT".
- `status` — use `VARCHAR(20)` with a `CHECK` constraint (same pattern as migration 0009, not a PG enum — easier to extend). Values: `'completed'`, `'failed'`, `'partial'`. `'partial'` = at least one section succeeded but not all.
- `raw_sources_jsonb JSONB` — store the raw `list[dict]` from each ingestion call. Shape: `{"gold_news": [story_dicts], "ontario_law": [hit_dicts], "ontario_stats": [hit_dicts]}`. Nil cost to write; forensics value is high.
- `agent_run_id UUID REFERENCES agent_runs(id)` — `daily_summaries` FK references `agent_runs`. Rationale: the `agent_runs` row is created first (at job start), then the summary row is written on completion. FK from summary → run is the natural "this summary was produced by this run" direction. The `agent_runs` row does NOT reference `daily_summaries` (that would require updating the run row after the summary is written, adding a round-trip). Set `ON DELETE SET NULL` so a cascaded agent_run purge doesn't orphan summary rows.
- No `UNIQUE` constraint on `(generated_at, period_label)` — if a cron fires twice (advisory lock normally prevents this, but edge cases exist), allow the duplicate row rather than silently swallowing an error. The feed query sorts by `generated_at DESC` and the frontend shows the first result, which is sufficient.

**Index strategy:** Single index on `(generated_at DESC)`. The feed page query is:
```sql
SELECT * FROM daily_summaries ORDER BY generated_at DESC LIMIT 60;
```
(30 days × 2 per day = 60 rows max — the table will never be large.) The prune cron uses `WHERE generated_at < now() - interval '30 days'` which also benefits from this index.

### Migration 0010

Model after `0009_add_x_post_state_to_draft_items.py`. Key shape:

```python
# backend/alembic/versions/0010_add_daily_summaries.py
revision = "0010"
down_revision = "0009"

def upgrade() -> None:
    op.create_table(
        "daily_summaries",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, ...),
        sa.Column("generated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("period_label", sa.String(length=20), nullable=False),
        sa.Column("gold_news_md", sa.Text(), nullable=True),
        sa.Column("ontario_law_md", sa.Text(), nullable=True),
        sa.Column("ontario_stats_md", sa.Text(), nullable=True),
        sa.Column("raw_sources_jsonb", postgresql.JSONB(), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="completed"),
        sa.Column("error_text", sa.Text(), nullable=True),
        sa.Column("agent_run_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("agent_runs.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_check_constraint(
        "ck_daily_summaries_status",
        "daily_summaries",
        "status IN ('completed', 'failed', 'partial')",
    )
    op.create_index("ix_daily_summaries_generated_at", "daily_summaries", ["generated_at"])
```

---

## Scheduler Layer

### New Lock IDs

Current `JOB_LOCK_IDS` uses: 1005 (midday_digest), 1010, 1011, 1013, 1014, 1015, 1016.
Next free integers: **1017** for `daily_summary`, **1018** for `daily_summary_prune`.

### `CONTENT_CRON_AGENTS` Addition

The `daily_summary` job does NOT belong in `CONTENT_CRON_AGENTS` (that tuple list drives the `_make_sub_agent_job` factory). Register it the same way `midday_digest` is registered — as a dedicated job via a named factory function `_make_daily_summary_job(engine)`.

In `JOB_LOCK_IDS` (MODIFIED `scheduler/worker.py`):
```python
JOB_LOCK_IDS: dict[str, int] = {
    "midday_digest": 1005,
    "sub_breaking_news": 1010,
    "sub_threads": 1011,
    "sub_quotes": 1013,
    "sub_infographics": 1014,
    "sub_gold_media": 1015,
    "sub_gold_history": 1016,
    "daily_summary": 1017,       # NEW
    "daily_summary_prune": 1018, # NEW
}
```

In `build_scheduler()` (MODIFIED), add after the midday_digest registration:
```python
# daily_summary: fires at 08:00 and 12:00 America/Los_Angeles
scheduler.add_job(
    _make_daily_summary_job(engine),
    trigger=CronTrigger(hour="8,12", minute=0, timezone="America/Los_Angeles"),
    id="daily_summary",
    name="Daily Summary — 08:00 + 12:00 America/Los_Angeles",
)

# daily_summary_prune: fires once per day at 03:00 America/Los_Angeles
scheduler.add_job(
    _make_daily_summary_prune_job(engine),
    trigger=CronTrigger(hour=3, minute=0, timezone="America/Los_Angeles"),
    id="daily_summary_prune",
    name="Daily Summary Prune — 03:00 America/Los_Angeles",
)
```

### `_make_daily_summary_job` Factory

```python
def _make_daily_summary_job(engine):
    async def job():
        async with engine.connect() as conn:
            from agents.daily_summary import run_daily_summary
            await with_advisory_lock(
                conn,
                JOB_LOCK_IDS["daily_summary"],
                "daily_summary",
                run_daily_summary,
            )
    return job
```

### `daily_summary_prune` — Separate Job

Keep it separate (its own lock ID 1018, its own `CronTrigger`). The prune job has no dependency on the summary job. Sharing the summary lock would block prune if a summary is running at 03:00, which is impossible in practice but creates needless coupling. The prune job is trivially simple — a single `DELETE WHERE generated_at < now() - interval '30 days'` — so it warrants its own factory rather than squeezing into the summary job's try/finally.

---

## `scheduler/agents/daily_summary.py` — New Agent Module

**File:** `scheduler/agents/daily_summary.py`

**Key functions:**

```python
async def run_daily_summary() -> None:
    """
    Entry point called by with_advisory_lock in worker.py.

    1. Create agent_run row (status='running')
    2. Determine period_label from current local time ('08:00 PT' or '12:00 PT')
    3. Call _build_gold_news_section()   → gold_news_md, gold_raw
    4. Call _build_ontario_law_section() → ontario_law_md, law_raw
    5. Call _build_ontario_stats_section() → ontario_stats_md, stats_raw
    6. Assemble DailySummary row (status='completed'|'partial'|'failed')
    7. Send WhatsApp message via send_whatsapp_message()
    8. Update agent_run row (status='completed'|'failed', ended_at=now)
    On any unhandled exception: update agent_run to failed, send failure alert.
    """

async def _build_gold_news_section(config: dict) -> tuple[str, list[dict]]:
    """
    Call fetch_stories() → filter to score >= 6.0 → take top 5 by score.
    Call Sonnet to produce a markdown bullet summary.
    Returns (gold_news_md, raw_stories_list).
    Falls back to "No major gold news in this window." on empty result.
    """

async def _build_ontario_law_section() -> tuple[str, list[dict]]:
    """
    Call ontario_law.fetch_ontario_law_hits() → Sonnet relevance filter
    → produce markdown bullets.
    Returns (ontario_law_md, raw_hits_list).
    Falls back to "No new mining-favourable legislation detected." on empty.
    """

async def _build_ontario_stats_section() -> tuple[str, list[dict]]:
    """
    Call ontario_stats.fetch_ontario_stats_hits() → produce markdown.
    Returns (ontario_stats_md, raw_hits_list).
    Falls back to "No new statistics released since [last_date]." on empty.
    """
```

**`fetch_stories()` consumption pattern:**

`fetch_stories()` returns `list[dict]`, each dict having: `title`, `link`, `published` (datetime), `summary`, `source_name`, `score` (0-10), `predicted_format`. The daily_summary agent uses this directly:

```python
from agents.content_agent import fetch_stories

stories = await fetch_stories()
# Filter: keep scores >= 6.0 (gold-relevant signal; below this is noise)
# This is NOT the 7.0 quality threshold used by sub-agents for drafting —
# for a summary we want broader coverage, not drafting selectivity.
relevant = [s for s in stories if s.get("score", 0) >= 6.0]
top5 = sorted(relevant, key=lambda s: s["score"], reverse=True)[:5]
```

No refactor to `fetch_stories()` is needed. The 30-min TTL cache means if a sub-agent cron fired in the same bucket, the daily_summary agent gets its result for free.

**WhatsApp delivery pattern** (reuse `send_whatsapp_message` directly):

```python
from services.whatsapp import send_whatsapp_message

# Success delivery
message = _format_whatsapp_message(period_label, gold_news_md, ontario_law_md, ontario_stats_md)
await send_whatsapp_message(message)

# Failure alert
await send_whatsapp_message(f"[daily_summary FAILED at {period_label}] {error_text[:200]}")
```

`send_whatsapp_message` already handles missing credentials gracefully (returns `None`, logs ERROR) and retries once on `TwilioRestException`. No wrapper needed.

**`agent_runs` telemetry:** Write one `AgentRun` row per fire with `agent_name="daily_summary"`. Use `items_found` = total stories ingested, `items_queued` = sections produced (0-3), `errors` = JSONB array of per-section error strings (empty on full success). This makes existing observability (Settings > Agent Runs tab) show daily_summary history without any backend changes.

---

## Backend / API Layer

### New Router: `backend/app/routers/summaries.py`

Model after `backend/app/routers/digests.py` — it's a GET-only, auth-gated router.

```python
# backend/app/routers/summaries.py
from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_user
from app.models.daily_summary import DailySummary
from app.schemas.daily_summary import SummaryCardResponse, SummaryFeedResponse

router = APIRouter(
    prefix="/summaries",
    tags=["summaries"],
    dependencies=[Depends(get_current_user)],  # single-user auth — always required
)

@router.get("", response_model=SummaryFeedResponse)
async def list_summaries(
    limit: int = Query(60, ge=1, le=120),
    db: AsyncSession = Depends(get_db),
):
    """Return up to 60 summaries ordered by generated_at DESC (30 days × 2/day = 60 max)."""
    stmt = (
        select(DailySummary)
        .order_by(DailySummary.generated_at.desc())
        .limit(limit)
    )
    result = await db.execute(stmt)
    rows = result.scalars().all()
    return SummaryFeedResponse(
        summaries=[SummaryCardResponse.model_validate(r) for r in rows],
        total=len(rows),
    )
```

**Auth:** `dependencies=[Depends(get_current_user)]` at the router level (same pattern as `digests.py` line 14-18). Every endpoint in the router is automatically protected.

**Registration in `backend/app/main.py`** (MODIFIED, after existing includes):
```python
from app.routers.summaries import router as summaries_router
# ...
app.include_router(summaries_router)
```

### Pydantic Schemas: `backend/app/schemas/daily_summary.py`

```python
from datetime import datetime
from pydantic import BaseModel, ConfigDict

class SummaryCardResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    generated_at: datetime
    period_label: str
    gold_news_md: str | None
    ontario_law_md: str | None
    ontario_stats_md: str | None
    status: str
    error_text: str | None
    # raw_sources_jsonb intentionally omitted from the list response
    # (large forensics blob; add a /summaries/{id} detail endpoint in a later phase if needed)

class SummaryFeedResponse(BaseModel):
    summaries: list[SummaryCardResponse]
    total: int
```

---

## Frontend Layer

### Route Wiring: `frontend/src/App.tsx` (MODIFIED)

```tsx
import { SummaryFeedPage } from '@/pages/SummaryFeedPage'

// Replace the / redirect with the real feed page:
<Route path="/" element={<SummaryFeedPage />} />

// Bookmark grace redirect (keeps /queue working for 30 days):
<Route path="/queue" element={<Navigate to="/" replace />} />

// Retire (keep as redirect, don't delete — single-user tool, bookmarks acceptable to break):
<Route path="/agents/:slug" element={<Navigate to="/" replace />} />
<Route path="/digest" element={<Navigate to="/" replace />} />
```

### New API Module: `frontend/src/api/summaries.ts`

```typescript
import { useQuery } from '@tanstack/react-query'
import { apiFetch } from './client'

export interface SummaryCard {
  id: string
  generated_at: string      // ISO datetime
  period_label: string      // '08:00 PT' | '12:00 PT'
  gold_news_md: string | null
  ontario_law_md: string | null
  ontario_stats_md: string | null
  status: 'completed' | 'failed' | 'partial'
  error_text: string | null
}

export interface SummaryFeedResponse {
  summaries: SummaryCard[]
  total: number
}

export async function getSummaries(limit = 60): Promise<SummaryFeedResponse> {
  return apiFetch<SummaryFeedResponse>(`/summaries?limit=${limit}`)
}

export function useSummaries(limit = 60) {
  return useQuery({
    queryKey: ['summaries', limit],
    queryFn: () => getSummaries(limit),
    staleTime: 5 * 60 * 1000,   // 5 min — summaries only update 2x/day
    refetchOnWindowFocus: false,
  })
}
```

### New Page: `frontend/src/pages/SummaryFeedPage.tsx`

```tsx
// Structure:
// - useSummaries() hook
// - Loading / error states (same pattern as DigestPage)
// - Vertical scroll of SummaryCard components, newest first
// - No approval flow, no actions — read-only feed

import { useSummaries } from '@/api/summaries'
import { SummaryCard } from '@/components/SummaryCard'

export function SummaryFeedPage() {
  const { data, isLoading, error } = useSummaries()
  // ...
  return (
    <div className="max-w-2xl mx-auto py-6 space-y-4">
      {data?.summaries.map(s => <SummaryCard key={s.id} summary={s} />)}
    </div>
  )
}
```

### New Components

**`frontend/src/components/SummaryCard.tsx`**
- Props: `summary: SummaryCard`
- Header: "Summary as of {period_label}" + formatted date (use `date-fns format`)
- Status badge: green (completed), yellow (partial), red (failed)
- Three `<SectionBlock>` instances for the three sections
- On `status='failed'`: show `error_text` in a red callout instead of sections

**`frontend/src/components/SectionBlock.tsx`**
- Props: `title: string`, `markdown: string | null`
- Renders markdown as formatted HTML (use `react-markdown` if already in deps, or a simple whitespace/newline renderer for bullet points)
- Empty state: renders a muted italic placeholder ("No new data." etc.)

**Reuse from retired components:** Check `PerAgentQueuePage.tsx` and any `ContentSummaryCard` — the approval-flow components have no direct transferable UI. The `DigestPage.tsx` date formatting pattern (`date-fns`, relative time) transfers directly to `SummaryCard.tsx`.

---

## Build Order (Phase Decomposition)

### Phase 1: Database + API Skeleton (returns mock data)

**Goal:** End-to-end wiring is proven before any agent work begins.

1. Write `backend/alembic/versions/0010_add_daily_summaries.py`
2. Write `backend/app/models/daily_summary.py`
3. Write `scheduler/models/daily_summary.py` (parity copy — same columns, `scheduler/models/base.py` import)
4. Write `backend/app/schemas/daily_summary.py`
5. Write `backend/app/routers/summaries.py` (real query, will return 0 rows until Phase 2)
6. MODIFY `backend/app/main.py` — add router
7. Run `alembic upgrade head` — table exists in Neon

**Dependency unblocked:** Frontend can now call `GET /summaries` and receive `{"summaries": [], "total": 0}`.

### Phase 2: `daily_summary` Agent + Ingestion Stub

**Goal:** The cron fires, writes real rows to `daily_summaries`, WhatsApp delivers.

1. Write `scheduler/agents/daily_summary.py` — `run_daily_summary()` + `_build_gold_news_section()` (uses real `fetch_stories()`). `_build_ontario_law_section()` and `_build_ontario_stats_section()` are stubs that return hardcoded placeholder markdown and empty raw lists.
2. MODIFY `scheduler/worker.py` — add lock IDs 1017/1018, add `_make_daily_summary_job` factory, register `daily_summary` in `build_scheduler()`
3. Deploy scheduler worker — verify Railway logs show job registered, fires at 08:00/12:00 PT
4. Verify `daily_summaries` row written, `agent_runs` row written, WhatsApp sent

**Dependency unblocked:** Frontend feed page can show real cards after Phase 3.

### Phase 3: Frontend Feed Page

**Goal:** Web feed is usable — the primary daily-use surface.

1. Write `frontend/src/api/summaries.ts`
2. Write `frontend/src/components/SectionBlock.tsx`
3. Write `frontend/src/components/SummaryCard.tsx`
4. Write `frontend/src/pages/SummaryFeedPage.tsx`
5. MODIFY `frontend/src/App.tsx` — wire `/` route, add `/queue` redirect

**Rationale for Phase 3 before Ontario sources:** The feed page can show real gold-news sections (from Phase 2) while Ontario sections show placeholder text. User gets immediate value; Ontario sources are a Phase 4 enhancement.

### Phase 4: Ontario Law Ingestion

**Goal:** Replace ontario_law stub with real source + Sonnet relevance filter.

1. Research source (Ontario Gazette RSS at `https://www.ontario.ca/laws/rss` or equivalent — confirm the actual feed URL; this is the open research question)
2. Write `scheduler/agents/ontario_law.py` — `fetch_ontario_law_hits() -> list[dict]` — fetch + Sonnet "is this mining-favourable?" binary classification
3. Wire into `_build_ontario_law_section()` in `daily_summary.py`

**Why deferred:** Source selection requires a research sub-task (PROJECT.md flags this as "no clean machine-readable feed exists"). Building the plumbing first (Phases 1-3) means Ontario law can be dropped in without touching anything else.

### Phase 5: Ontario Stats Ingestion

**Goal:** Replace ontario_stats stub with real StatCan / OGS source.

1. Research source (StatCan mineral production table, Ontario Geological Survey releases)
2. Write `scheduler/agents/ontario_stats.py` — `fetch_ontario_stats_hits() -> list[dict]`
3. Design the "no new data since {date}" empty state in `_build_ontario_stats_section()`
4. Wire into `daily_summary.py`

**Why after Ontario law:** Law and stats are independent; defer stats because releases are monthly/quarterly (lower urgency than law monitoring).

### Phase 6: Prune Cron + Cleanup

**Goal:** 30-day retention enforced; dead code decommissioned.

1. Write `_make_daily_summary_prune_job(engine)` in `scheduler/worker.py`
2. Register `daily_summary_prune` cron (03:00 PT) in `build_scheduler()`
3. Tag retired routes/components in frontend as dead code (or delete if safe)

**Why last:** Prune is the most independent concern. Nothing blocks on it; retention can also be enforced manually until this phase ships.

---

## Integration Points and Surprises

### `fetch_stories()` Score Filter

`fetch_stories()` returns stories with `score` in 0-10 range. The sub-agents use a 7.0 threshold for drafting selectivity. For a summary, use **6.0** — broader coverage is better for a news digest than for a social post. No refactor to `fetch_stories()` needed; just filter in the daily_summary agent.

### `period_label` Derivation

The cron fires at 08:00 and 12:00 PT. Derive the label inside `run_daily_summary()`:

```python
from datetime import datetime, timezone
import zoneinfo

la_tz = zoneinfo.ZoneInfo("America/Los_Angeles")
now_la = datetime.now(la_tz)
period_label = "08:00 PT" if now_la.hour < 11 else "12:00 PT"
```

This is robust to minor clock skew (APScheduler `misfire_grace_time=1800`).

### WhatsApp Message Length

`send_whatsapp_message` sends a single message. Twilio's 1600-char hard cap applies. The `build_chunks` helper in `whatsapp.py` chunks at 1500 chars. For daily_summary delivery, use `build_chunks` with a synthetic agent name if the assembled summary exceeds 1500 chars. More likely: cap each section to 3-5 bullets in the Sonnet prompt so the total message stays under 1500 chars. No structural change to `whatsapp.py` needed.

### Dual-Model Parity (Scheduler + Backend)

The existing pattern (confirmed in CLAUDE.md) requires the same table to have SQLAlchemy models in BOTH `scheduler/models/` and `backend/app/models/`. The scheduler model needs `scheduler/models/daily_summary.py` to write rows; the backend model needs `backend/app/models/daily_summary.py` to read them. They must define identical columns. Phase 1 must create both together.

### Slow 12:00 PT Summary

The 12:00 PT summary fires 4 hours after the 08:00 PT one. On slow news days, the gold news section may be identical (same top-5 stories in cache, since the 30-min TTL expired long before noon). The Sonnet prompt for `_build_gold_news_section()` should receive the `generated_at` of the last summary as context and instruct: "If the same stories appeared in the prior summary, note 'No major moves since 08:00 summary.'" Pass `last_summary_generated_at` as a parameter from `run_daily_summary()` (query the most recent row before writing the new one).

### Advisory Lock on a Multi-Fire CronTrigger

`CronTrigger(hour="8,12", minute=0)` registers one job that fires twice daily. The advisory lock ID 1017 is the same for both fires — this is correct and intentional. Each fire acquires and releases the lock independently. No collision is possible because the fires are 4 hours apart.

---

## Confidence Assessment

| Area | Confidence | Basis |
|------|------------|-------|
| CONTENT_CRON_AGENTS tuple shape | HIGH | Read `scheduler/worker.py` lines 141-184 directly |
| Lock ID allocation (1017, 1018) | HIGH | Read `JOB_LOCK_IDS` dict, confirmed 1012 unused, 1017/1018 next free |
| `fetch_stories()` return shape | HIGH | Read `content_agent.py` — score + predicted_format confirmed on scored dict |
| `send_whatsapp_message` signature | HIGH | Read `whatsapp.py` — single `message: str` arg, returns `str | None` |
| `agent_runs` model columns | HIGH | Read `scheduler/models/agent_run.py` — full column list confirmed |
| Digests router pattern | HIGH | Read `backend/app/routers/digests.py` — exact auth pattern confirmed |
| Migration 0009 style | HIGH | Read migration file — `op.create_check_constraint`, index pattern confirmed |
| App.tsx route registration | HIGH | Read `frontend/src/App.tsx` — current routes confirmed |
| Ontario law source selection | LOW | Flagged in PROJECT.md as an open question; requires separate research |
| Ontario stats source selection | LOW | Same — StatCan / OGS feed URLs need verification |
