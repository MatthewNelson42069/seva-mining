# Phase 5: Senior Agent Core - Research

**Researched:** 2026-04-02
**Domain:** Python APScheduler agent logic, Alembic migrations, asyncpg/async SQLAlchemy, Twilio WhatsApp, text similarity
**Confidence:** HIGH (all findings verified against live codebase; no external library research needed for core logic)

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

- Story deduplication via Jaccard text overlap (threshold ≥ 0.40, 24h lookback window) — no Claude call, no API cost
- Both duplicate cards remain in queue; newer item gets `related_id` pointing to older item
- Breaking news alert threshold: score ≥ 8.5 (config key: `senior_breaking_news_threshold`, default `"8.5"`)
- Expiry alert: ≤ 1 hour before expiry, score ≥ 7.0 (config keys: `senior_expiry_alert_score_threshold` default `"7.0"`, `senior_expiry_alert_minutes_before` default `"60"`)
- Engagement alerts dispatched by expiry sweep (30-min cycle) — Phase 4 Twitter Agent code stays unchanged
- Watchlist posts get two alerts: early signal (50 likes / 5k views), viral confirmation (500 likes / 40k views)
- Non-watchlist posts get one alert: viral threshold only (500 likes / 40k views)
- New `engagement_alert_level` column on `draft_items` (VARCHAR(20), nullable) tracks alert state: `null` = none sent, `"watchlist"` = first alert sent, `"viral"` = viral alert sent
- Alembic migration 0004 required for `engagement_alert_level` column
- WhatsApp service in scheduler: `scheduler/services/whatsapp.py` — direct mirror of `backend/app/services/whatsapp.py`
- Template SIDs: morning_digest = `HX930c2171b211acdea4d5fa0a12d6c0e0`, breaking_news = `HXc5bcef9a42a18e9071acd1d6fb0fac39`, expiry_alert = `HX45fd40f45d91e2ea54abd2298dd8bc41`
- Queue cap: 15 pending items hard cap (config key: `senior_queue_cap`, default `"15"`)
- Tiebreaking on displacement: keep item with later `expires_at`
- Priority ordering: Twitter time-sensitive (expires_at within 2h) → breaking news content → Instagram → evergreen
- `expiry_sweep` wired to `SeniorAgent.run_expiry_sweep()`, `morning_digest` wired to `SeniorAgent.run_morning_digest()`
- @sevamining own metrics deferred — not in scope for Phase 5
- Rejection reason tags deferred — free-text `rejection_reason` sufficient for Phase 5 digest stats

### Claude's Discretion

- Exact Jaccard similarity threshold (suggested: 0.40) and token extraction logic
- Stopword list for fingerprint token extraction
- SQL query structure for the expiry sweep
- Config key names and default values (follow existing `twitter_*` naming pattern)
- Error handling for WhatsApp send failures in the scheduler (match backend pattern: log + retry once)
- `DailyDigest` JSONB field structure for `top_stories`, `queue_snapshot`, etc.

### Deferred Ideas (OUT OF SCOPE)

- @sevamining scraped surface metrics in morning digest (SENR-07 partial)
- Structured rejection reason taxonomy (tags vs free text)

</user_constraints>

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| SENR-01 | Receives all drafts from sub-agents as they arrive | `process_new_item(item_id)` called by Twitter Agent after DB write; queue cap + dedup inline |
| SENR-02 | Deduplicates across agents — same story as separate cards, visually linked via `related_id` | Jaccard similarity with pure Python; `related_id` FK already on DraftItem |
| SENR-03 | Prioritizes queue: Twitter time-sensitive first, breaking news content second, Instagram third, evergreen last | `urgency` + `expires_at` + `platform` already on DraftItem — sort logic only, no new columns |
| SENR-04 | Hard cap of 15 items — lower-scoring items displaced by higher-scoring new items | Inline SELECT + compare + conditional DELETE/INSERT in same session |
| SENR-05 | Auto-expires items after platform window (Twitter 6h, Instagram 12h) | UPDATE WHERE status='pending' AND expires_at < now(); `expires_at` already indexed |
| SENR-06 | Assembles morning digest daily at 8am | `morning_digest` APScheduler job slot already registered (lock ID 1005) |
| SENR-07 | Morning digest content (top 5 stories, queue snapshot, yesterday counts, priority alert; @sevamining metrics deferred) | DailyDigest model fields match; JSONB structure decisions documented in research |
| SENR-08 | Logs every approval and rejection with reason tags | `status`, `rejection_reason`, `decided_at` already on DraftItem — read-only for digest stats |
| SENR-09 | Expiry processor runs every 30 minutes | `expiry_sweep` job slot already registered (lock ID 1004) |
| WHAT-01 | Morning digest sent at 8am via Twilio | `scheduler/services/whatsapp.py` mirror + 7-variable morning_digest template |
| WHAT-02 | Breaking gold news alert on high-scoring story | After DraftItem write, if score >= 8.5, dispatch breaking_news template — 4 variables |
| WHAT-03 | High-value draft expiry alert approaching expiration | Detected in expiry sweep; expiry_alert template — 4 variables; dedup via `alerted_expiry_at` |
| WHAT-05 | Notifications include link to dashboard | `dashboard_url` config key (default: `"https://app.sevamining.com"`) in every template's `{{4}}` variable |

</phase_requirements>

---

## Summary

Phase 5 builds the Senior Agent — the coordination layer between the Twitter Agent (and future sub-agents) and the operator's approval queue. It adds no new external service dependencies: all capabilities are pure Python logic, existing PostgreSQL queries, and the already-wired Twilio WhatsApp service.

The three core integration points are: (1) inline queue management (`process_new_item`) called immediately after a Twitter Agent DraftItem write, (2) the `expiry_sweep` APScheduler job (30-min interval, lock ID 1004) for expiry marking, engagement alerts, and expiry alerts, and (3) the `morning_digest` APScheduler job (8am daily, lock ID 1005) for digest assembly and dispatch.

The only schema change is Alembic migration 0004 adding `engagement_alert_level VARCHAR(20) NULLABLE` to `draft_items`. A second column for expiry alert dedup (`alerted_expiry_at TIMESTAMPTZ NULLABLE`) is also recommended to avoid a config-key-per-item approach. Both scheduler and backend model files must be updated to mirror the new column.

**Primary recommendation:** Follow the TwitterAgent structure exactly — same `AgentRun` logging, same `AsyncSessionLocal` session management, same `asyncio.to_thread` Twilio pattern. The Senior Agent is structurally identical to the Twitter Agent; it just runs different business logic.

---

## Standard Stack

### Core (all already installed — no new dependencies)

| Library | Version | Purpose | Notes |
|---------|---------|---------|-------|
| SQLAlchemy (async) | 2.0.x | DB queries for queue cap, dedup, sweep | `AsyncSessionLocal` from `scheduler/database.py` |
| asyncpg | 0.30.x | PostgreSQL async driver | Already in `scheduler/pyproject.toml` |
| APScheduler | 3.11.2 | Job scheduling for expiry_sweep + morning_digest | Already registered in `worker.py` |
| twilio | 9.x | WhatsApp notifications | Already in `scheduler/pyproject.toml` — confirm below |
| pydantic-settings | 2.x | Settings/env vars | `get_settings()` already in `scheduler/config.py` |

**Check twilio dependency in scheduler pyproject.toml** — not currently listed. Must be added:

```toml
"twilio>=9.0",
```

The backend already has it; scheduler needs it added explicitly since it is a separate process with its own dependency tree.

### No New External Dependencies

Jaccard similarity: pure Python set operations. No `scikit-learn`, `nltk`, or any NLP library. The CLAUDE.md and CONTEXT.md both require zero-API-cost deduplication.

### Installation

```bash
# In scheduler/ directory:
uv add twilio
```

---

## Architecture Patterns

### Recommended Project Structure (additions only)

```
scheduler/
├── agents/
│   ├── twitter_agent.py          # existing
│   └── senior_agent.py           # NEW — SeniorAgent class
├── services/
│   └── whatsapp.py               # NEW — mirror of backend service
├── models/
│   ├── draft_item.py             # UPDATE — add engagement_alert_level, alerted_expiry_at
│   └── daily_digest.py           # NEW — scheduler mirror of backend DailyDigest
└── worker.py                     # UPDATE — wire expiry_sweep + morning_digest jobs
```

```
backend/
├── app/models/
│   └── draft_item.py             # UPDATE — add same columns (keep in sync)
└── alembic/versions/
    └── 0004_add_engagement_alert_level.py  # NEW
```

### Pattern 1: Worker Job Wiring

The `_make_job` function in `worker.py` needs two new branches. The pattern exactly matches the twitter_agent branch:

```python
# Source: scheduler/worker.py (existing pattern)
async def job():
    async with engine.connect() as conn:
        if job_name == "twitter_agent":
            agent = TwitterAgent()
            await with_advisory_lock(conn, JOB_LOCK_IDS[job_name], job_name, agent.run)
        elif job_name == "expiry_sweep":
            agent = SeniorAgent()
            await with_advisory_lock(conn, JOB_LOCK_IDS[job_name], job_name, agent.run_expiry_sweep)
        elif job_name == "morning_digest":
            agent = SeniorAgent()
            await with_advisory_lock(conn, JOB_LOCK_IDS[job_name], job_name, agent.run_morning_digest)
        else:
            await with_advisory_lock(conn, JOB_LOCK_IDS[job_name], job_name, lambda: placeholder_job(job_name))
```

### Pattern 2: SeniorAgent Structure (mirrors TwitterAgent)

```python
# Source: scheduler/agents/twitter_agent.py (structural mirror)
class SeniorAgent:
    def __init__(self):
        self.settings = get_settings()

    async def process_new_item(self, item_id: uuid.UUID) -> None:
        """Called by Twitter Agent after writing a DraftItem. Runs dedup + queue cap."""
        async with AsyncSessionLocal() as session:
            run = AgentRun(agent_name="senior_agent_intake", status="running", ...)
            session.add(run)
            await session.flush()
            try:
                await self._run_deduplication(session, item_id)
                await self._enforce_queue_cap(session, item_id)
                await self._check_breaking_news_alert(session, item_id)
                run.status = "success"
            except Exception as exc:
                run.status = "failed"
                run.errors = str(exc)
                # Do NOT re-raise — EXEC-04
            finally:
                run.finished_at = datetime.now(timezone.utc)
                await session.commit()

    async def run_expiry_sweep(self) -> None:
        """APScheduler job: mark expired items, fire engagement + expiry alerts."""
        async with AsyncSessionLocal() as session:
            run = AgentRun(agent_name="expiry_sweep", ...)
            ...

    async def run_morning_digest(self) -> None:
        """APScheduler job: assemble and dispatch daily morning digest."""
        async with AsyncSessionLocal() as session:
            run = AgentRun(agent_name="morning_digest", ...)
            ...
```

### Pattern 3: Jaccard Similarity (pure Python)

Token extraction from `source_text` + `rationale`:

```python
import re
import string

# Domain-specific stopwords for gold sector content
STOPWORDS = frozenset({
    "the", "a", "an", "and", "or", "but", "in", "on", "at", "to", "for",
    "of", "with", "by", "from", "as", "is", "are", "was", "were", "be",
    "been", "being", "have", "has", "had", "do", "does", "did", "will",
    "would", "could", "should", "may", "might", "shall", "can", "not",
    "this", "that", "these", "those", "it", "its", "they", "their",
    "he", "she", "we", "you", "i", "me", "my", "our", "your", "his", "her",
    "said", "says", "also", "via", "per", "just", "new", "today",
    "following", "after", "before", "over", "under", "about", "into",
})

def extract_fingerprint_tokens(text: str) -> frozenset[str]:
    """Extract meaningful tokens for Jaccard comparison.

    Keeps: numbers (price figures, percentages), cashtags ($GLD, $GC),
    multi-word company names (lowercased), proper nouns.
    Strips: punctuation (except $ for cashtags), stopwords.
    """
    if not text:
        return frozenset()
    # Lowercase, normalize whitespace
    text = text.lower().strip()
    # Preserve cashtags before stripping punctuation
    # Extract tokens: split on whitespace and common delimiters
    tokens = re.findall(r'\$[a-z]+|\b\w+\b', text)
    return frozenset(t for t in tokens if t not in STOPWORDS and len(t) > 1)


def jaccard_similarity(set_a: frozenset, set_b: frozenset) -> float:
    """Jaccard index: |intersection| / |union|. Returns 0.0 for empty sets."""
    if not set_a and not set_b:
        return 0.0
    intersection = len(set_a & set_b)
    union = len(set_a | set_b)
    return intersection / union if union > 0 else 0.0
```

Confidence: HIGH — pure Python standard library, no external dependencies.

### Pattern 4: Queue Cap Enforcement (inline)

The queue cap check runs in the same SQLAlchemy session immediately after a DraftItem is written. The key constraint: do it in a single session with appropriate locking to avoid TOCTOU race conditions.

```python
async def _enforce_queue_cap(self, session: AsyncSession, new_item_id: uuid.UUID) -> None:
    cap_str = await self._get_config(session, "senior_queue_cap", "15")
    cap = int(cap_str)

    # Count pending items (excluding the new item just written)
    result = await session.execute(
        select(func.count()).where(
            DraftItem.status == "pending",
            DraftItem.id != new_item_id,
        )
    )
    existing_count = result.scalar_one()

    if existing_count < cap:
        return  # Queue not full — accept new item

    # Queue full — find lowest scoring existing item
    new_item = await session.get(DraftItem, new_item_id)
    result = await session.execute(
        select(DraftItem)
        .where(DraftItem.status == "pending", DraftItem.id != new_item_id)
        .order_by(DraftItem.score.asc(), DraftItem.expires_at.asc())
        .limit(1)
        .with_for_update(skip_locked=True)
    )
    lowest = result.scalar_one_or_none()

    if lowest is None:
        return  # Concurrent modification — safe to proceed

    if float(new_item.score or 0) > float(lowest.score or 0):
        # Displace the lowest-scoring item
        await session.delete(lowest)
        # new_item stays
    else:
        # New item loses — discard it
        await session.delete(new_item)
        # Log to AgentRun.notes handled by caller
```

**Tiebreaking note:** The ORDER BY clause `DraftItem.score.asc(), DraftItem.expires_at.asc()` means: among items with the same score, the one expiring soonest (smallest `expires_at`) is displaced first, preserving items with more time remaining. This matches the CONTEXT.md requirement "prefer to keep the one with the later `expires_at`."

### Pattern 5: Expiry Sweep SQL

```python
# Step 1: Bulk-expire stale items
await session.execute(
    update(DraftItem)
    .where(DraftItem.status == "pending", DraftItem.expires_at < func.now())
    .values(status="expired", updated_at=func.now())
)

# Step 2: Expiry alerts — pending items within 1 hour of expiry, score >= threshold
threshold_score = float(await self._get_config(session, "senior_expiry_alert_score_threshold", "7.0"))
threshold_minutes = int(await self._get_config(session, "senior_expiry_alert_minutes_before", "60"))

result = await session.execute(
    select(DraftItem).where(
        DraftItem.status == "pending",
        DraftItem.score >= threshold_score,
        DraftItem.expires_at.between(func.now(), func.now() + timedelta(minutes=threshold_minutes)),
        DraftItem.alerted_expiry_at.is_(None),  # not yet alerted
    )
)
expiry_candidates = result.scalars().all()

# Step 3: Engagement alerts (see Pattern 6)
```

### Pattern 6: Engagement Alert Logic

The engagement alert check requires knowing whether a DraftItem originated from a watchlist account. `engagement_snapshot` stores `likes` and `views` at capture time. `is_watchlist` is NOT stored on DraftItem — the expiry sweep must determine it from the `watchlists` table.

```python
# Source: engagement_snapshot JSONB structure (from twitter_agent.py lines 923-929)
# {
#   "likes": <int>,
#   "retweets": <int>,
#   "replies": <int>,
#   "views": <int or null>,
#   "captured_at": "<ISO timestamp>"
# }

async def _check_engagement_alerts(self, session: AsyncSession) -> None:
    # Load watchlist account usernames for fast lookup
    result = await session.execute(
        select(Watchlist.username).where(Watchlist.platform == "twitter")
    )
    watchlist_usernames = {row[0].lstrip("@").lower() for row in result}

    # Items that have never been alerted (null) OR watchlist items awaiting viral confirmation
    result = await session.execute(
        select(DraftItem).where(
            DraftItem.status == "pending",
            DraftItem.platform == "twitter",
            DraftItem.engagement_alert_level != "viral",  # "viral" is terminal state
        )
    )
    candidates = result.scalars().all()

    for item in candidates:
        snap = item.engagement_snapshot or {}
        likes = snap.get("likes", 0) or 0
        views = snap.get("views", 0) or 0
        account = (item.source_account or "").lstrip("@").lower()
        is_watchlist = account in watchlist_usernames

        current_level = item.engagement_alert_level  # None, "watchlist", or "viral"

        if is_watchlist:
            if current_level is None and likes >= 50 and views >= 5000:
                # First alert: early signal
                await self._send_engagement_alert(item)
                item.engagement_alert_level = "watchlist"
            elif current_level == "watchlist" and likes >= 500 and views >= 40000:
                # Second alert: viral confirmation
                await self._send_engagement_alert(item)
                item.engagement_alert_level = "viral"
        else:
            if current_level is None and likes >= 500 and views >= 40000:
                # Single alert: viral threshold only
                await self._send_engagement_alert(item)
                item.engagement_alert_level = "viral"
```

**Critical note:** `engagement_snapshot` captures metrics at the time Twitter Agent runs (every 2h). The expiry sweep checks the same snapshot values — it does NOT re-query the X API. This means engagement alerts fire based on already-captured data, which is the intended design (the sweep cycle detects items the Twitter Agent wrote in the previous 2h window).

### Pattern 7: WhatsApp Service Mirror in Scheduler

The scheduler has no access to the backend package. The `scheduler/services/whatsapp.py` file is a verbatim mirror of `backend/app/services/whatsapp.py` with one change: the import path for settings.

```python
# scheduler/services/whatsapp.py
# DIFFERENCE from backend: import from scheduler's config module
from config import get_settings  # NOT from app.config

# Everything else is identical — same TEMPLATE_SIDS dict,
# same _send_sync function, same asyncio.to_thread pattern,
# same retry-once logic
```

All env vars (`TWILIO_ACCOUNT_SID`, `TWILIO_AUTH_TOKEN`, `TWILIO_WHATSAPP_FROM`, `DIGEST_WHATSAPP_TO`) are already declared in `scheduler/config.py` Settings class. No new env vars needed.

### Pattern 8: Alembic Migration 0004

Pattern is identical to migration 0003 (`op.add_column`). No ENUM changes needed — `VARCHAR(20)` is a plain string column.

```python
# backend/alembic/versions/0004_add_engagement_alert_level.py
from alembic import op
import sqlalchemy as sa

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None

def upgrade() -> None:
    op.add_column(
        "draft_items",
        sa.Column("engagement_alert_level", sa.String(20), nullable=True),
    )
    op.add_column(
        "draft_items",
        sa.Column("alerted_expiry_at", sa.DateTime(timezone=True), nullable=True),
    )

def downgrade() -> None:
    op.drop_column("draft_items", "alerted_expiry_at")
    op.drop_column("draft_items", "engagement_alert_level")
```

**No async required in migration files.** Alembic migrations run synchronously via `alembic upgrade head` at deploy time, even with an async app. The existing pattern in migrations 0001-0003 confirms this — all use standard `op.add_column`/`op.create_table` with no async/await. This is correct and expected for Alembic + asyncpg setups.

### Pattern 9: DailyDigest JSONB Structure

Based on the DailyDigest model (`digest_date`, `top_stories`, `queue_snapshot`, `yesterday_approved`, `yesterday_rejected`, `yesterday_expired`, `priority_alert`, `whatsapp_sent_at`):

```python
# top_stories: list of up to 5 items, sorted by score descending
# from items created/updated in the previous calendar day
top_stories = [
    {
        "headline": "first sentence of rationale",  # truncated to ~100 chars
        "source_account": "@KitcoNews",
        "platform": "twitter",
        "score": 8.7,
        "source_url": "https://x.com/i/web/status/...",
    },
    ...  # up to 5
]

# queue_snapshot: current pending count by platform
queue_snapshot = {
    "twitter": 4,
    "instagram": 0,
    "content": 1,
    "total": 5,
}

# yesterday_approved: count + summary
yesterday_approved = {
    "count": 3,
    "items": [
        {"platform": "twitter", "score": 8.2, "decided_at": "2026-04-01T14:23:00Z"}
    ]
}

# yesterday_rejected: count only
yesterday_rejected = {"count": 1}

# yesterday_expired: count only
yesterday_expired = {"count": 2}

# priority_alert: single highest-scoring currently-pending item
priority_alert = {
    "id": "<uuid>",
    "platform": "twitter",
    "score": 9.1,
    "source_account": "@WGC_Research",
    "headline": "first sentence of rationale",
    "expires_at": "2026-04-02T10:15:00Z",
    "source_url": "https://x.com/i/web/status/...",
}
```

### Anti-Patterns to Avoid

- **Async in Alembic migration files:** Alembic runs migrations synchronously. The existing 0001-0003 migrations are all synchronous. Do not add `async def upgrade()` — it will fail.
- **Re-querying X API in expiry sweep for current engagement:** The system uses snapshot data only. Never add live API calls to the sweep — it would exhaust the X Basic API quota.
- **Calling `process_new_item` from inside TwitterAgent directly:** Integration point should be a function call at the end of the TwitterAgent run, after the session is committed — or better, TwitterAgent calls a module-level `process_new_items(item_ids)` function. This avoids circular imports between agent modules.
- **Using a single `Config` key per item for expiry alert dedup:** The CONTEXT.md suggests either `alerted_expiry_at` column OR a config key `expiry_alert_sent:{item_id}`. Use the column approach — a config key per item would pollute the config table and create orphaned keys when items expire.
- **Setting `related_id` on both items:** Only the newer item gets `related_id` set pointing to the older item. The older item's `related_id` stays NULL.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Text similarity | Custom word frequency / TF-IDF | Pure Python Jaccard (set intersection) | Jaccard is O(n) per comparison, sufficient for ≤15 pending items vs ≤15 pending items; no corpus needed |
| Async-safe Twilio calls | Async Twilio wrapper | `asyncio.to_thread(_send_sync, ...)` | Twilio SDK is sync-only; `to_thread` offloads to thread pool without blocking event loop — already proven pattern in backend |
| Scheduled job dedup | Custom process lock | `pg_try_advisory_lock` | Already implemented in `with_advisory_lock()` in worker.py — reuse directly |
| Config value reads | Hardcoded constants | `Config` table via SQLAlchemy | All thresholds (queue cap, alert scores, alert minutes) must be runtime-configurable — read from DB at start of each job run |

---

## Runtime State Inventory

> Not applicable — this is a greenfield phase adding new agent code and a schema column. No rename/refactor.

None — verified by phase description and CONTEXT.md review.

---

## Common Pitfalls

### Pitfall 1: `engagement_snapshot` does not store `is_watchlist`

**What goes wrong:** Planner/implementer assumes `engagement_snapshot` JSONB has an `is_watchlist` field and writes alert logic reading it directly. The field is not there.

**Why it happens:** The `is_watchlist` flag exists in the tweet dict during TwitterAgent processing but is NOT persisted to `engagement_snapshot` when the DraftItem is written (confirmed by reading `twitter_agent.py` lines 923-929: only `likes`, `retweets`, `replies`, `views`, `captured_at` are stored).

**How to avoid:** Senior Agent must join against `watchlists` table on `source_account` to determine if an account is a watchlist account. Load all watchlist usernames once per sweep run, build a Python set, then check membership for each candidate item.

**Warning signs:** Any code doing `item.engagement_snapshot.get("is_watchlist")` is wrong.

### Pitfall 2: Alembic migration must be synchronous

**What goes wrong:** Developer writes `async def upgrade()` in the migration file because the rest of the project is async.

**Why it happens:** The SQLAlchemy + asyncpg stack is async at runtime, so developers assume migrations are too.

**How to avoid:** Alembic migrations always use synchronous `op.` functions. The existing migrations 0001-0003 all use `def upgrade() -> None:` (synchronous). Use the same pattern. The `asyncpg` driver is only engaged by the async application — Alembic uses its own synchronous connection.

### Pitfall 3: Twilio dependency missing from scheduler pyproject.toml

**What goes wrong:** `scheduler/services/whatsapp.py` is created but `twilio` is not in `scheduler/pyproject.toml` dependencies. Works locally if twilio is globally installed but fails on Railway deploy.

**Why it happens:** The twilio package exists in `backend/` but the scheduler is a separate process with its own dependency file.

**How to avoid:** Wave 0 must add `"twilio>=9.0"` to `scheduler/pyproject.toml` `[project.dependencies]` and run `uv add twilio` in the scheduler directory.

### Pitfall 4: Backend and scheduler models diverge after migration

**What goes wrong:** Migration 0004 adds `engagement_alert_level` and `alerted_expiry_at` to the DB, but only `backend/app/models/draft_item.py` is updated. `scheduler/models/draft_item.py` still lacks the columns — SQLAlchemy reflection will still work but ORM attribute access will fail.

**Why it happens:** The two model files are manual mirrors (STATE.md decision: "Backend models must be kept in sync with scheduler models manually"). Easy to miss the scheduler copy.

**How to avoid:** Any model change to `backend/app/models/draft_item.py` must be mirrored to `scheduler/models/draft_item.py` in the same commit. The migration 0004 plan wave must include both files.

### Pitfall 5: `process_new_item` circular import if TwitterAgent imports SeniorAgent

**What goes wrong:** TwitterAgent imports SeniorAgent at module level to call `process_new_item`, creating a circular import (`twitter_agent.py` → `senior_agent.py` → models → possibly back).

**Why it happens:** Direct class-to-class imports are tempting for readability.

**How to avoid:** Use one of two safe patterns:
1. TwitterAgent calls a module-level function `from agents.senior_agent import process_new_item` (the function, not the class) — works if the function uses lazy import of the class inside.
2. Keep `process_new_item` as a standalone async function in `senior_agent.py` at module level (not a class method) — same pattern as `draft_for_post` in twitter_agent.py.

### Pitfall 6: WhatsApp template character limits

**What goes wrong:** The morning_digest template variable `{{2}}` (top story headlines joined by "; ") can exceed the Meta-approved template body limit if many long headlines are concatenated.

**Why it happens:** The approved template body is:
`"Daily gold sector digest for {{1}}. Top stories: {{2}}. Queue: {{3}} items pending review. Yesterday: {{4}} approved, {{5}} rejected, {{6}} expired. View dashboard: {{7}}"`

Total template body with all variables filled could exceed 1024 chars if `{{2}}` is not truncated.

**How to avoid:** The morning digest assembly must truncate `{{2}}` so the total filled message stays under 1024 chars. The static template text is ~130 chars. `{{2}}` should be capped at ~200 chars (leaving room for all other variables). Implementation: truncate the joined headlines string to 200 chars max, ending at a word boundary or with "...".

### Pitfall 7: Queue cap race condition

**What goes wrong:** Two sub-agents write DraftItems simultaneously. Both see `count < 15` and both insert, resulting in 16 items.

**Why it happens:** `process_new_item` reads count then conditionally inserts/deletes. Without a row lock, concurrent calls can both read `count=14` before either commits.

**How to avoid:** Use `SELECT ... FOR UPDATE` on the count query, or use a PostgreSQL advisory lock specific to queue cap operations (lock ID not yet assigned — use 1006). The `with_for_update()` on the lowest-scored item query (Pattern 4 above) partially addresses this. For production correctness, the queue cap check should run under the same `pg_try_advisory_lock` as the calling agent, or use a dedicated lock.

**Practical approach for Phase 5:** Since Phase 5 only has one active sub-agent (Twitter), the race condition cannot occur yet. Document the limitation and address in Phase 6 (Instagram Agent). Add a comment in code.

---

## Code Examples

### Jaccard with gold-sector dedup query

```python
# Source: pure Python (no external library)
async def _run_deduplication(
    self,
    session: AsyncSession,
    new_item_id: uuid.UUID,
) -> None:
    """Set related_id on new_item if it overlaps >= threshold with any recent pending item."""
    config_thresh = await self._get_config(session, "senior_dedup_threshold", "0.40")
    threshold = float(config_thresh)

    new_item = await session.get(DraftItem, new_item_id)
    if new_item is None:
        return

    new_tokens = extract_fingerprint_tokens(
        (new_item.source_text or "") + " " + (new_item.rationale or "")
    )
    if not new_tokens:
        return

    cutoff = datetime.now(timezone.utc) - timedelta(hours=24)
    result = await session.execute(
        select(DraftItem).where(
            DraftItem.status == "pending",
            DraftItem.id != new_item_id,
            DraftItem.created_at >= cutoff,
        ).order_by(DraftItem.created_at.asc())  # oldest first — related_id points to older
    )
    existing_items = result.scalars().all()

    best_match: DraftItem | None = None
    best_score = 0.0

    for item in existing_items:
        tokens = extract_fingerprint_tokens(
            (item.source_text or "") + " " + (item.rationale or "")
        )
        score = jaccard_similarity(new_tokens, tokens)
        if score >= threshold and score > best_score:
            best_score = score
            best_match = item

    if best_match is not None:
        new_item.related_id = best_match.id
```

### Config helper (mirrors pattern from TwitterAgent)

```python
async def _get_config(
    self, session: AsyncSession, key: str, default: str
) -> str:
    result = await session.execute(
        select(Config.value).where(Config.key == key)
    )
    value = result.scalar_one_or_none()
    return value if value is not None else default
```

### Morning digest assembly query pattern

```python
from datetime import date, timedelta
from sqlalchemy import func, case

async def _assemble_digest(self, session: AsyncSession) -> dict:
    today = date.today()
    yesterday_start = datetime.combine(today - timedelta(days=1), datetime.min.time()).replace(tzinfo=timezone.utc)
    yesterday_end = datetime.combine(today, datetime.min.time()).replace(tzinfo=timezone.utc)

    # Yesterday stats — single query with conditional aggregation
    result = await session.execute(
        select(
            func.count().filter(DraftItem.status.in_(["approved", "edited_approved"])).label("approved"),
            func.count().filter(DraftItem.status == "rejected").label("rejected"),
            func.count().filter(DraftItem.status == "expired").label("expired"),
        ).where(
            DraftItem.decided_at.between(yesterday_start, yesterday_end)
            | DraftItem.expires_at.between(yesterday_start, yesterday_end)
        )
    )
    # Note: expired items use expires_at, decided items use decided_at — may need two queries
    # for precision. Single-query approach is acceptable for v1 digest stats.

    # Top 5 stories from yesterday (by score)
    result = await session.execute(
        select(DraftItem)
        .where(DraftItem.created_at >= yesterday_start)
        .order_by(DraftItem.score.desc().nulls_last())
        .limit(5)
    )
    top_items = result.scalars().all()

    # Current queue snapshot
    result = await session.execute(
        select(DraftItem.platform, func.count().label("count"))
        .where(DraftItem.status == "pending")
        .group_by(DraftItem.platform)
    )
    platform_counts = {row.platform: row.count for row in result}
```

---

## State of the Art

| Area | Current Approach | Notes |
|------|-----------------|-------|
| Text dedup | Jaccard set similarity (pure Python) | Sufficient for ≤15-item queue; no semantic/embedding approach needed at this scale |
| WhatsApp dispatch | `asyncio.to_thread` wrapping sync Twilio SDK | Industry pattern for sync SDK in async context; already proven in backend |
| Alembic async | Migrations are always synchronous | Async Alembic migration drivers (alembic-asyncio, etc.) exist but are NOT needed here — `op.add_column` is DDL, runs synchronously |

---

## Open Questions

1. **`process_new_item` integration point with TwitterAgent**
   - What we know: CONTEXT.md says "queue cap + deduplication → called by sub-agents after writing DraftItem, OR implemented as `SeniorAgent.process_new_item(item_id)` function called by Twitter Agent"
   - What's unclear: Should TwitterAgent import and call `process_new_item` directly, or should the Senior Agent sweep the DB for unprocessed items instead?
   - Recommendation: The direct-call approach is simpler and more immediate. TwitterAgent calls `await process_new_item(item_id)` after `session.commit()`. Use a module-level function (not class method) in `senior_agent.py` to avoid circular imports. If this creates coupling concerns in Phase 6+, switch to a polling approach then.

2. **`alerted_expiry_at` vs `alerted_expiry` boolean**
   - What we know: CONTEXT.md suggests a timestamp column; a boolean column is simpler
   - What's unclear: Is the timestamp needed by the dashboard (Phase 8) or digest stats?
   - Recommendation: Use `DateTime(timezone=True)` — stores when the alert was sent, which is more useful for debugging and audit than a boolean. Minimal overhead.

3. **Scheduler `daily_digest.py` model — does it already exist?**
   - What we know: `ls scheduler/models/` shows: `agent_run.py`, `base.py`, `config.py`, `draft_item.py`, `keyword.py`, `watchlist.py` — no `daily_digest.py`
   - What's unclear: Whether Wave 0 creates this file or whether a migration should handle it
   - Recommendation: `daily_digest.py` must be created in scheduler/models/ as a mirror of `backend/app/models/daily_digest.py` (with `from models.base import Base` import path). This is a code task, not a migration task — the table already exists in the DB from migration 0001.

---

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| PostgreSQL (Neon) | All DB queries | Yes (deployed) | 16 managed | — |
| twilio SDK | scheduler/services/whatsapp.py | Needs `uv add twilio` in scheduler | 9.x (in backend already) | — |
| APScheduler 3.11.2 | expiry_sweep + morning_digest jobs | Yes (in scheduler pyproject.toml) | 3.11.2 | — |
| anthropic SDK | Not needed for Phase 5 | Yes | 0.86.0 | — |

**Missing dependencies with no fallback:**
- `twilio` in `scheduler/pyproject.toml` — must be added in Wave 0 before any WhatsApp code is written. The Railway deploy will fail without it.

**Missing dependencies with fallback:**
- None.

---

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest 8.0+ with pytest-asyncio 0.23+ |
| Config file | `scheduler/pyproject.toml` — `[tool.pytest.ini_options]` with `asyncio_mode = "auto"` |
| Quick run command | `cd /Users/matthewnelson/seva-mining/scheduler && uv run pytest tests/test_senior_agent.py -x` |
| Full suite command | `cd /Users/matthewnelson/seva-mining/seva-mining/scheduler && uv run pytest tests/ -x` |

### Phase Requirements to Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| SENR-02 | Jaccard similarity returns correct value for known token sets | unit | `pytest tests/test_senior_agent.py::test_jaccard_similarity -x` | Wave 0 |
| SENR-02 | extract_fingerprint_tokens strips stopwords, keeps cashtags | unit | `pytest tests/test_senior_agent.py::test_extract_fingerprint_tokens -x` | Wave 0 |
| SENR-02 | dedup sets related_id when overlap >= 0.40 | unit | `pytest tests/test_senior_agent.py::test_dedup_sets_related_id -x` | Wave 0 |
| SENR-02 | dedup does NOT set related_id when overlap < 0.40 | unit | `pytest tests/test_senior_agent.py::test_dedup_no_match_below_threshold -x` | Wave 0 |
| SENR-04 | queue cap accepts item when count < 15 | unit | `pytest tests/test_senior_agent.py::test_queue_cap_accepts_below_cap -x` | Wave 0 |
| SENR-04 | queue cap displaces lowest-score item when full and new item scores higher | unit | `pytest tests/test_senior_agent.py::test_queue_cap_displaces_lowest -x` | Wave 0 |
| SENR-04 | queue cap discards new item when full and new item scores equal or lower | unit | `pytest tests/test_senior_agent.py::test_queue_cap_discards_new_item -x` | Wave 0 |
| SENR-04 | tiebreaking keeps item with later expires_at | unit | `pytest tests/test_senior_agent.py::test_queue_cap_tiebreak_expires_at -x` | Wave 0 |
| SENR-05 | expiry sweep marks expired items as status='expired' | unit | `pytest tests/test_senior_agent.py::test_expiry_sweep_marks_expired -x` | Wave 0 |
| WHAT-02 | breaking news alert fires when score >= 8.5 | unit | `pytest tests/test_senior_agent.py::test_breaking_news_alert_fires -x` | Wave 0 |
| WHAT-02 | breaking news alert does NOT fire when score < 8.5 | unit | `pytest tests/test_senior_agent.py::test_breaking_news_alert_no_fire -x` | Wave 0 |
| WHAT-03 | expiry alert fires once for qualifying item within 1h of expiry | unit | `pytest tests/test_senior_agent.py::test_expiry_alert_fires -x` | Wave 0 |
| WHAT-03 | expiry alert does NOT fire twice for same item (alerted_expiry_at dedup) | unit | `pytest tests/test_senior_agent.py::test_expiry_alert_no_double_send -x` | Wave 0 |
| SENR-06/SENR-07 | morning digest assembles correct JSONB structure | unit | `pytest tests/test_senior_agent.py::test_morning_digest_assembly -x` | Wave 0 |
| WHAT-01 | morning digest WhatsApp send called with 7 variables | unit | `pytest tests/test_senior_agent.py::test_morning_digest_whatsapp_send -x` | Wave 0 |
| Engagement alert | watchlist item gets early signal alert at 50 likes/5k views | unit | `pytest tests/test_senior_agent.py::test_engagement_alert_watchlist_early -x` | Wave 0 |
| Engagement alert | watchlist item gets viral confirmation alert when crossing 500/40k | unit | `pytest tests/test_senior_agent.py::test_engagement_alert_watchlist_viral -x` | Wave 0 |
| Engagement alert | non-watchlist item gets single alert at 500 likes/40k views | unit | `pytest tests/test_senior_agent.py::test_engagement_alert_nonwatchlist_viral -x` | Wave 0 |
| Engagement alert | watchlist item does NOT get viral alert if already at "viral" level | unit | `pytest tests/test_senior_agent.py::test_engagement_alert_no_repeat_viral -x` | Wave 0 |

### Sampling Rate

- **Per task commit:** `uv run pytest tests/test_senior_agent.py -x`
- **Per wave merge:** `uv run pytest tests/ -x`
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps

- [ ] `scheduler/tests/test_senior_agent.py` — 19 test stubs covering all requirements above
- [ ] `scheduler/models/daily_digest.py` — scheduler mirror of backend DailyDigest model (table already in DB)
- [ ] `scheduler/services/__init__.py` — new services directory needs init file
- [ ] `scheduler/services/whatsapp.py` — WhatsApp service mirror (Wave 0 stub with correct import)
- [ ] `twilio>=9.0` added to `scheduler/pyproject.toml` dependencies + `uv add twilio`
- [ ] `backend/alembic/versions/0004_add_engagement_alert_level.py` — migration file (run before Wave 1 DB work)

---

## Sources

### Primary (HIGH confidence — verified against live codebase)

- `scheduler/worker.py` — `_make_job` pattern, `JOB_LOCK_IDS`, advisory lock wiring
- `scheduler/agents/twitter_agent.py` (lines 923-929) — `engagement_snapshot` JSONB field structure confirmed
- `scheduler/agents/twitter_agent.py` (lines 460-464, 540-542) — `is_watchlist` NOT persisted to DraftItem confirmed
- `backend/app/services/whatsapp.py` — exact mirror target for scheduler service
- `backend/app/models/draft_item.py` — DraftItem schema, confirmed columns
- `backend/app/models/daily_digest.py` — DailyDigest schema, confirmed JSONB field names
- `scheduler/models/draft_item.py` — scheduler mirror confirmed matching backend
- `backend/alembic/versions/0003_add_config_table_and_watchlist_platform_user_id.py` — migration pattern for `op.add_column`
- `backend/alembic/versions/0001_initial_schema.py` — synchronous migration pattern confirmed
- `scheduler/pyproject.toml` — twilio NOT listed in dependencies (confirmed missing)
- `scheduler/config.py` — all Twilio env vars present in Settings class
- `.planning/phases/01-infrastructure-and-foundation/01-01-PLAN.md` — exact WhatsApp template body text and variable counts confirmed

### Secondary (MEDIUM confidence)

- CONTEXT.md §WhatsApp Service in Scheduler — architectural decision for scheduler/services/whatsapp.py mirror
- CONTEXT.md §Engagement Alert Timing — engagement_snapshot re-check logic confirmed

### Tertiary (LOW confidence)

None — all critical claims verified against live codebase.

---

## Metadata

**Confidence breakdown:**

- Standard stack: HIGH — all packages verified against live pyproject.toml files
- Architecture: HIGH — all patterns derived from live code, not assumptions
- Pitfalls: HIGH — engagement_snapshot gap, twilio missing dep, and migration sync pattern all verified against actual files
- Test plan: HIGH — test structure matches existing test_twitter_agent.py patterns

**Research date:** 2026-04-02
**Valid until:** 2026-05-02 (stable codebase — no fast-moving external dependencies for this phase)
