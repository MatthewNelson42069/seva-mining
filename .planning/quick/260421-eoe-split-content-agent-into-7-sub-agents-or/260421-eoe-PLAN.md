---
quick_task: 260421-eoe
mode: full
title: Split Content Agent into 7 sub-agents + cron-less review service
architecture: Phase C (review-service-only Content Agent; 7 self-contained sub-agents call content_agent.review() inline)
created: 2026-04-21
depends_on:
  - 260421-eoe-CONTEXT.md
  - 260421-eoe-RESEARCH.md
files_modified:
  scheduler:
    - scheduler/agents/content_agent.py            # shrink to fetch_stories() + review() + classify_format_lightweight
    - scheduler/agents/content/__init__.py          # NEW package marker
    - scheduler/agents/content/breaking_news.py     # NEW
    - scheduler/agents/content/threads.py           # NEW
    - scheduler/agents/content/long_form.py         # NEW
    - scheduler/agents/content/quotes.py            # NEW
    - scheduler/agents/content/infographics.py      # NEW
    - scheduler/agents/content/video_clip.py        # NEW (frontend label "Gold Media")
    - scheduler/agents/content/gold_history.py      # NEW (migrated from scheduler/agents/gold_history_agent.py)
    - scheduler/agents/gold_history_agent.py        # DELETED (moved)
    - scheduler/worker.py                           # retire content_agent + gold_history_agent crons; add 7 sub-agent crons
    - scheduler/database.py                         # pool_size 3 → 15
    - scheduler/tests/test_content_agent.py         # shrink to fetch_stories() + review() only
    - scheduler/tests/test_breaking_news.py         # NEW
    - scheduler/tests/test_threads.py               # NEW
    - scheduler/tests/test_long_form.py             # NEW
    - scheduler/tests/test_quotes.py                # NEW
    - scheduler/tests/test_infographics.py          # NEW
    - scheduler/tests/test_video_clip.py            # NEW
    - scheduler/tests/test_gold_history.py          # NEW (replaces test_gold_history_agent.py if it exists)
    - scheduler/tests/test_worker.py                # update for new cron IDs + lock IDs + stagger
  backend:
    - backend/app/routers/queue.py                  # add ?content_type= query param
    - backend/app/database.py                       # pool_size 5 → 15
    - backend/tests/routers/test_queue.py           # new case for content_type filter
  frontend:
    - frontend/src/config/agentTabs.ts              # NEW — CONTENT_AGENT_TABS config array (7 entries)
    - frontend/src/pages/PerAgentQueuePage.tsx      # NEW (adapted from PlatformQueuePage)
    - frontend/src/pages/PlatformQueuePage.tsx      # DELETED (replaced)
    - frontend/src/App.tsx                          # remove /content + /content-review; add single /agents/:slug dynamic route; redirect / → /agents/breaking-news
    - frontend/src/components/layout/Sidebar.tsx    # 7 priority-ordered agent entries, rendered from CONTENT_AGENT_TABS
    - frontend/src/components/settings/AgentRunsTab.tsx  # swap AGENT_OPTIONS to 7 sub-agent names
    - frontend/src/hooks/useQueueCounts.ts          # adjust count queries if they reference /queue without content_type
    - frontend/src/pages/PerAgentQueuePage.test.tsx # NEW
    - frontend/src/pages/ContentPage.test.tsx       # update if route refs break
  docs:
    - CLAUDE.md                                     # "single-agent system" → "7 sub-agent system + Content Agent review service"; scheduled-job count 3 → 8
validation_mode: --full
max_checker_iterations: 2
---

<objective>
Refactor the monolithic `scheduler/agents/content_agent.py` (~2000 lines) into:
(a) a **review-service-only** `content_agent` module exposing `fetch_stories()` (shared SerpAPI + RSS ingestion with TTL-30min in-memory cache) and `review(draft)` (Haiku compliance gate) — **no cron**; and
(b) **7 independent sub-agent modules** under `scheduler/agents/content/`, each with its own 2h APScheduler cron, staggered across the 2h window, calling `content_agent.fetch_stories()` then `content_agent.review()` inline before writing a `content_bundles` row in a single transaction.

Simultaneously: fold the standalone `gold_history_agent` into the 7-agent pattern (retire its cron); update the backend `/queue` endpoint with a `content_type` filter; collapse the frontend combined `/content` tab into 7 per-agent tabs under a dynamic `/agents/:slug` route; bump Neon pool_size to 15 on scheduler + backend; update CLAUDE.md narrative and scheduled-job count.

**Purpose:** Unblock per-content-type cadence tuning, remove the 30-min deferred-gate latency, eliminate the research_context migration that was flagged pre-pivot, and give the operator a clean per-agent queue UI.

**Output:** 8 registered scheduler jobs post-refactor (morning_digest + 7 sub-agents), zero content_agent cron, zero gold_history_agent cron, 7 new per-agent tabs in the frontend Sidebar, green scheduler/backend/frontend test suites.

**Functional parity is mandatory** — no new features, no new content_types, no schema changes. Anything a sub-agent drafts post-split must be bit-equivalent to what `content_agent` would have drafted pre-split for the same story.
</objective>

<context>
@.planning/quick/260421-eoe-split-content-agent-into-7-sub-agents-or/260421-eoe-CONTEXT.md
@.planning/quick/260421-eoe-split-content-agent-into-7-sub-agents-or/260421-eoe-RESEARCH.md
@CLAUDE.md
@scheduler/agents/content_agent.py
@scheduler/agents/gold_history_agent.py
@scheduler/worker.py
@scheduler/database.py
@scheduler/tests/test_content_agent.py
@backend/app/routers/queue.py
@backend/app/database.py
@backend/app/models/draft_item.py
@backend/app/models/content_bundle.py
@frontend/src/App.tsx
@frontend/src/components/layout/Sidebar.tsx
@frontend/src/components/settings/AgentRunsTab.tsx
@frontend/src/pages/PlatformQueuePage.tsx

<interfaces>
<!-- Critical contracts the executor must honor. Extracted from the codebase before planning. -->

## 1. DraftItem → ContentBundle link (NO direct FK)

`draft_items` has NO `content_bundle_id` column. The link is stored in
`draft_items.engagement_snapshot` as JSONB: `{"content_bundle_id": "<uuid>"}`.

```python
# scheduler/agents/content_agent.py:712-723 (current bundle→draft builder)
return DraftItem(
    platform="content",
    source_text=content_bundle.story_headline,
    source_url=content_bundle.story_url,
    ...
    engagement_snapshot={"content_bundle_id": str(content_bundle.id)},
)
```

**Implication for backend `/queue?content_type=X` filter:** we cannot JOIN on a
direct FK. We must either:
- join `draft_items` → `content_bundles` on `engagement_snapshot->>'content_bundle_id' = content_bundles.id::text`, OR
- subquery `content_bundles.id WHERE content_type=X` and filter `draft_items` whose JSONB key is in that set.

The executor picks the cleaner Postgres expression; either is acceptable.
Frontend sends `?content_type=thread` etc. (DB-native values, not slugs).

## 2. Sub-agent signature (all 7 modules identical shape)

```python
# scheduler/agents/content/<type>.py
from agents import content_agent

CONTENT_TYPE: str = "<db_content_type_value>"   # e.g. "breaking_news", "thread"

async def run_draft_cycle() -> None:
    """Single-tick pipeline: fetch → filter → draft → review → write."""
    stories = await content_agent.fetch_stories()
    candidates = [s for s in stories if _matches(s)]   # per-agent filter
    for story in candidates:
        draft = await _draft(story)                    # per-agent drafter
        review = await content_agent.review(draft)     # Haiku gate, inline
        await _write_bundle(story, draft, review)      # single-tx insert
```

- `gold_history.py` DOES NOT call `content_agent.fetch_stories()` — it retains
  its own historical-story source (used_topics guard). It DOES still call
  `content_agent.review()` before writing.
- `video_clip.py` keeps its tweepy async-client pipeline (`_search_video_clips`,
  `_draft_video_caption`) and its X API quota pre-check.
- Each sub-agent writes its own `content_bundles` row with `content_type`,
  `draft_content`, AND `compliance_passed` set in one transaction (no
  cross-tick handoff, no `draft_content IS NULL` polling).

## 3. content_agent public surface (post-refactor)

```python
# scheduler/agents/content_agent.py — POST-SPLIT
async def fetch_stories() -> list[Story]:
    """Shared SerpAPI + RSS ingestion with TTL-30min in-memory cache.
    Keyed on int(time.time() // 1800). Process-local cache; Railway is single-worker."""

async def review(draft: dict) -> dict:
    """Haiku compliance gate. Returns {compliance_passed: bool, rationale: str}.
    Pure function — no DB I/O."""

def classify_format_lightweight(...) -> str:
    """Retained as helper export for sub-agents (unchanged behavior)."""

# DELETED:
# - class ContentAgent with run() / _run_pipeline() orchestrator loop
# - _draft_breaking_news_post, _draft_thread, _draft_long_form_post,
#   _draft_quote_post, _draft_infographic_brief, _search_video_clips,
#   _draft_video_caption  → all migrated to sub-agents
# - any _gate_draft() / compliance-only orchestration path
```

## 4. worker.py JOB_LOCK_IDS (post-refactor)

```python
JOB_LOCK_IDS: dict[str, int] = {
    "morning_digest":    1005,   # unchanged
    "sub_breaking_news": 1010,   # NEW
    "sub_threads":       1011,   # NEW
    "sub_long_form":     1012,   # NEW
    "sub_quotes":        1013,   # NEW
    "sub_infographics":  1014,   # NEW
    "sub_video_clip":    1015,   # NEW
    "sub_gold_history":  1016,   # NEW
    # RETIRED: content_agent=1003, gold_history_agent=1009
}
```

## 5. Stagger offsets (per RESEARCH ✅ STILL VALID)

7 sub-agents × 2h cadence, `IntervalTrigger(hours=2, start_date=now+offset)`:

| sub-agent        | offset_minutes | lock_id |
|------------------|----------------|---------|
| breaking_news    | 0              | 1010    |
| threads          | 17             | 1011    |
| long_form        | 34             | 1012    |
| quotes           | 51             | 1013    |
| infographics     | 68             | 1014    |
| video_clip       | 85             | 1015    |
| gold_history     | 102            | 1016    |

APScheduler job_defaults: `{"max_instances": 1, "misfire_grace_time": 300, "coalesce": True}`.

## 6. Frontend route + tabs config (7 entries, priority order)

```ts
// frontend/src/config/agentTabs.ts
export const CONTENT_AGENT_TABS = [
  { slug: "breaking-news", contentType: "breaking_news", label: "Breaking News", priority: 1 },
  { slug: "threads",       contentType: "thread",        label: "Threads",       priority: 2 },
  { slug: "long-form",     contentType: "long_form",     label: "Long-form",     priority: 3 },
  { slug: "quotes",        contentType: "quote",         label: "Quotes",        priority: 4 },
  { slug: "infographics",  contentType: "infographic",   label: "Infographics",  priority: 5 },
  { slug: "gold-media",    contentType: "video_clip",    label: "Gold Media",    priority: 6 },
  { slug: "gold-history",  contentType: "gold_history",  label: "Gold History",  priority: 7 },
];
```

Single React Router v6 dynamic route `<Route path="/agents/:slug" element={<PerAgentQueuePage />} />`; root `/` redirects to `/agents/breaking-news`. TanStack Query v5 queryKey `["queue", "content", tab.contentType]` — contentType MUST be in the key.
</interfaces>
</context>

<tasks>

<!-- ============================================================= -->
<!-- WAVE 0 — Test scaffolding so missing-module imports don't ERROR -->
<!-- ============================================================= -->

<task id="T01" type="auto">
  <name>Task 1: Create empty content/ package + Wave-0 test stubs</name>
  <files>
    scheduler/agents/content/__init__.py
    scheduler/tests/test_breaking_news.py
    scheduler/tests/test_threads.py
    scheduler/tests/test_long_form.py
    scheduler/tests/test_quotes.py
    scheduler/tests/test_infographics.py
    scheduler/tests/test_video_clip.py
    scheduler/tests/test_gold_history.py
  </files>
  <action>
    Create the new package folder and 7 Wave-0 test stubs so `pytest` collects
    cleanly while the sub-agent modules don't yet exist (per RESEARCH pitfall #8).

    1. `scheduler/agents/content/__init__.py` — empty marker file (single-line
       docstring OK).
    2. Each of the 7 test_<name>.py files contains EXACTLY this skeleton (substitute
       module name):
       ```python
       """Wave-0 stub for sub-agent tests. Real tests added once module exists."""
       import pytest

       pytest.importorskip("agents.content.<module_name>",
                           reason="Sub-agent module not yet created (Wave 0)")

       # NOTE: lazy-import inside tests, not at module top, so pytest collection
       # never fails even when the module is absent. Real test bodies replace
       # this file in Task 7 (per-agent split).

       def test_module_placeholder():
           pytest.skip("Replaced in Task 7 per-agent test split")
       ```
    3. Ensure `scheduler/tests/__init__.py` exists (it likely already does — don't
       overwrite if so).

    Do NOT delete `scheduler/tests/test_content_agent.py` or any existing test
    in this task — those come later.
  </action>
  <verify>
    <automated>cd scheduler && uv run pytest scheduler/tests/test_breaking_news.py scheduler/tests/test_threads.py scheduler/tests/test_long_form.py scheduler/tests/test_quotes.py scheduler/tests/test_infographics.py scheduler/tests/test_video_clip.py scheduler/tests/test_gold_history.py -x</automated>
    Expected: all 7 files collect; 7 tests SKIPPED (not ERROR); exit 0.
  </verify>
  <done>
    `ls scheduler/agents/content/__init__.py` returns the file; `ls scheduler/tests/test_{breaking_news,threads,long_form,quotes,infographics,video_clip,gold_history}.py` lists 7 files; pytest collects + skips without errors.
  </done>
</task>

<!-- =============================================================== -->
<!-- WAVE 1 — Scheduler module extraction (the big move, low blast)  -->
<!-- =============================================================== -->

<task id="T02" type="auto">
  <name>Task 2: Extract content_agent.py → review-service-only module</name>
  <files>
    scheduler/agents/content_agent.py
  </files>
  <action>
    Shrink `scheduler/agents/content_agent.py` (~2000 lines) to a review-service-only
    module exposing EXACTLY these public symbols:

    1. `async def fetch_stories() -> list[Story]` — shared SerpAPI + RSS ingestion
       with module-level in-memory cache keyed on `int(time.time() // 1800)`
       (30-min timestamp bucket). Value is `(timestamp, stories_list)`. On cache
       hit within the same bucket, return cached list. On cache miss, invoke
       the current fetch + scoring pipeline (the exact code paths already used
       by `_run_pipeline`'s ingestion stage) and store under the bucket key.
       Use a module-level `asyncio.Lock()` on the cache-miss path to prevent
       duplicate simultaneous fetches. Cache-miss fetch failures log a warning
       and return an empty list (preserves current skip-cycle-on-fetch-failure
       behavior).

    2. `async def review(draft: dict) -> dict` — Haiku compliance gate. Returns
       `{"compliance_passed": bool, "rationale": str}`. Extract the EXACT logic
       from the current compliance-gate code in `content_agent.py` (the Haiku
       classifier that reads the extracted text from `_extract_check_text`).
       No DB I/O inside `review()` — it's a pure function over the draft dict.

    3. `classify_format_lightweight(...)` — retained unchanged. Exported for
       sub-agents that need it (breaking_news, threads, long_form, quote,
       infographic). Verify its return strings exactly match the CONTENT_TYPE
       values sub-agents will filter on: `"breaking_news"`, `"thread"`,
       `"long_form"`, `"quote"`, `"infographic"` (per RESEARCH pitfall #6).

    4. `_extract_check_text(draft_content)` — retained as private helper, still
       used by `review()`.

    DELETE from this module:
    - `class ContentAgent` and its `run()` / `_run_pipeline()` methods
    - All `_draft_*` functions (breaking_news, thread, long_form, quote,
      infographic) — these move to sub-agents in subsequent tasks
    - `_search_video_clips`, `_draft_video_caption` — move to video_clip.py
    - `VIDEO_ACCOUNTS` constant + tweepy imports (move to video_clip.py)
    - The pre-split bundle-writer `DraftItem(platform="content", ...)` builder
      at line ~712 (each sub-agent writes its own bundle)
    - Any `_gate_draft()` / cross-tick polling logic
    - Any references to `content_agent_interval_hours` config key (deleted
      entirely in Task 3)

    **Do NOT touch `scheduler/worker.py` in this task** — worker still imports
    `ContentAgent` from here. The build will temporarily be broken between
    Task 2 commit and Task 3 commit. This is deliberate: commit Task 2 first,
    then Task 3 re-wires the worker to the new surface (no import of
    `ContentAgent`). Sequential execution required.

    Functional-parity rule: post-split `fetch_stories()` must produce byte-identical
    output to what `_run_pipeline`'s ingestion+scoring stage produces today, given
    the same SerpAPI + RSS responses. Preserve story ordering and scoring weights.

    Addresses CONTEXT `<decisions>` "Content Agent's post-split role" and
    `<specifics>` "Preserved in content_agent.py".
  </action>
  <verify>
    <automated>cd scheduler && uv run ruff check agents/content_agent.py && uv run pytest scheduler/tests/test_content_agent.py -x -k "not deprecated" || true</automated>
    Expected:
    - ruff clean on content_agent.py.
    - Existing test_content_agent.py may fail on deleted methods — this is
      expected and T07 shrinks that test file. Non-blocking here.
    - `grep "_draft_" scheduler/agents/content_agent.py` returns 0 matches.
    - `grep -E "^class ContentAgent|async def _run_pipeline" scheduler/agents/content_agent.py` returns 0 matches.
    - `grep -E "^async def fetch_stories|^async def review" scheduler/agents/content_agent.py` returns 2 matches.
  </verify>
  <done>
    `scheduler/agents/content_agent.py` contains only `fetch_stories()`, `review()`, `classify_format_lightweight`, `_extract_check_text`, and supporting helpers; all `_draft_*` functions and the `ContentAgent` class are removed; ruff passes on the file.
  </done>
</task>

<task id="T03" type="auto">
  <name>Task 3: Create the 7 sub-agent modules (breaking_news, threads, long_form, quotes, infographics, video_clip, gold_history)</name>
  <files>
    scheduler/agents/content/breaking_news.py
    scheduler/agents/content/threads.py
    scheduler/agents/content/long_form.py
    scheduler/agents/content/quotes.py
    scheduler/agents/content/infographics.py
    scheduler/agents/content/video_clip.py
    scheduler/agents/content/gold_history.py
    scheduler/agents/gold_history_agent.py
  </files>
  <action>
    Create all 7 sub-agent modules, each following the skeleton in the
    `<interfaces>` block above. Per-module specifics:

    **All 7 modules share this top-level shape:**
    ```python
    """<Module Name> sub-agent — self-contained drafter.
    Part of the 7-agent split (quick-260421-eoe).
    """
    from __future__ import annotations
    import logging
    from agents import content_agent
    from database import AsyncSessionLocal
    from models.content_bundle import ContentBundle  # adjust import path if differs

    logger = logging.getLogger(__name__)
    CONTENT_TYPE: str = "<db_value>"

    async def run_draft_cycle() -> None:
        ...
    ```

    ### 3.1 `content/breaking_news.py` (CONTENT_TYPE="breaking_news")
    Migrate `_draft_breaking_news_post` from the old content_agent.py as the
    private `_draft(story)` function. Filter: stories whose
    `classify_format_lightweight` result == "breaking_news" (or the existing
    eligibility predicate used by the current pipeline). Calls
    `content_agent.fetch_stories()` + `content_agent.review()` per skeleton.

    ### 3.2 `content/threads.py` (CONTENT_TYPE="thread")
    Migrate `_draft_thread` (or equivalent thread-drafting function) from
    old content_agent.py.

    ### 3.3 `content/long_form.py` (CONTENT_TYPE="long_form")
    Migrate `_draft_long_form_post`.

    ### 3.4 `content/quotes.py` (CONTENT_TYPE="quote")
    Migrate `_draft_quote_post`.

    ### 3.5 `content/infographics.py` (CONTENT_TYPE="infographic")
    Migrate `_draft_infographic_brief`.

    ### 3.6 `content/video_clip.py` (CONTENT_TYPE="video_clip")
    Migrate `_search_video_clips` + `_draft_video_caption` + `VIDEO_ACCOUNTS`
    constant + the tweepy `AsyncClient` import. **Also migrate the X API quota
    pre-check** (`twitter_monthly_tweet_count` + `twitter_monthly_quota_limit`
    read from Config before querying X API — RESEARCH pitfall #7).

    ### 3.7 `content/gold_history.py` (CONTENT_TYPE="gold_history")
    Port the producer + drafter currently in `scheduler/agents/gold_history_agent.py`.
    Per RESEARCH pitfall #1 resolution (option a): keep producer + drafter fused
    — `run_draft_cycle()` runs every 2h but only writes a bundle when a new
    story is due per `gold_history_used_topics` guard. Most ticks no-op.
    **This module does NOT call `content_agent.fetch_stories()`** (it has its
    own historical-story source); it DOES call `content_agent.review()` inline
    before writing.

    After creating `content/gold_history.py`, **DELETE** `scheduler/agents/gold_history_agent.py`
    (git mv/rm). The worker.py cron registration for the old path is
    retired in Task 4 — do NOT remove the worker.py import here (sequential
    ordering rule: module moves in one commit, worker.py rewires in the next,
    so intermediate state is recoverable).

    **Shared bundle-writer pattern (all 7 sub-agents):**
    Each module's `_write_bundle(story, draft, review_result)` opens an
    `AsyncSessionLocal()`, constructs a `ContentBundle` row with:
    - `story_headline`, `story_url`, `source_name` (from story)
    - `content_type=CONTENT_TYPE`
    - `score`, `quality_score` (from story scoring)
    - `draft_content` (JSONB payload from the drafter)
    - `compliance_passed` (from `review_result["compliance_passed"]`)
    - `no_story_flag=False`
    and `await session.commit()` in one transaction. No DraftItem row is
    written here — the existing DraftItem pipeline (which reads from
    content_bundles) is unchanged. If the current `content_agent.py` ALSO wrote
    a `DraftItem` row (it did, at line ~712), mirror that write inside
    `_write_bundle` so the Draft queue keeps populating. Match the existing
    `DraftItem(platform="content", ..., engagement_snapshot={"content_bundle_id": str(bundle.id)})`
    pattern exactly — this preserves the frontend's JSONB link.

    **Functional parity:** draft JSONB shape produced by each sub-agent must
    match what `content_agent._draft_<type>` produced pre-split, bit-for-bit,
    for the same story input.

    Addresses CONTEXT `<decisions>` "Sub-agent execution pattern" + `<specifics>`
    "Extraction targets" + "Sub-agent skeleton".
  </action>
  <verify>
    <automated>cd scheduler && uv run ruff check agents/content/ && ls scheduler/agents/content/*.py | wc -l</automated>
    Expected:
    - ruff clean across the 7 files + __init__.py.
    - `ls scheduler/agents/content/*.py` returns 8 files (7 modules + __init__.py).
    - `test -e scheduler/agents/gold_history_agent.py` returns 1 (file does NOT exist).
    - `grep -lE "async def run_draft_cycle" scheduler/agents/content/*.py | wc -l` returns 7.
    - `grep -c "content_agent.review(" scheduler/agents/content/*.py` returns ≥7 (one per module).
    - `grep -c "content_agent.fetch_stories(" scheduler/agents/content/*.py` returns 6 (all except gold_history).
  </verify>
  <done>
    7 sub-agent modules exist under `scheduler/agents/content/`, each exports `async def run_draft_cycle()`, each calls `content_agent.review()` inline, 6 of 7 call `content_agent.fetch_stories()`, the old `scheduler/agents/gold_history_agent.py` is deleted, ruff passes.
  </done>
</task>

<!-- ================================================================ -->
<!-- WAVE 2 — Wire new modules into the scheduler (ties it together)  -->
<!-- ================================================================ -->

<task id="T04" type="auto">
  <name>Task 4: Rewire scheduler/worker.py (retire old crons, register 7 sub-agent crons, update lock IDs)</name>
  <files>
    scheduler/worker.py
    scheduler/database.py
  </files>
  <action>
    Update `scheduler/worker.py` for the new 8-job topology (morning_digest + 7
    sub-agents). Remove dead references to `ContentAgent` and `GoldHistoryAgent`.

    ### 4.1 Imports
    - Remove `from agents.content_agent import ContentAgent`.
    - Remove `from agents.gold_history_agent import GoldHistoryAgent`.
    - Add imports for the 7 sub-agent modules:
      ```python
      from agents.content import (
          breaking_news, threads, long_form, quotes,
          infographics, video_clip, gold_history,
      )
      ```

    ### 4.2 JOB_LOCK_IDS
    Replace the current dict with:
    ```python
    JOB_LOCK_IDS: dict[str, int] = {
        "morning_digest":    1005,
        "sub_breaking_news": 1010,
        "sub_threads":       1011,
        "sub_long_form":     1012,
        "sub_quotes":        1013,
        "sub_infographics":  1014,
        "sub_video_clip":    1015,
        "sub_gold_history":  1016,
    }
    ```
    Retire `content_agent=1003` and `gold_history_agent=1009`.

    ### 4.3 CONTENT_SUB_AGENTS data-driven registration list
    Add this module-level constant:
    ```python
    from apscheduler.triggers.interval import IntervalTrigger
    from datetime import datetime, timedelta, timezone

    CONTENT_SUB_AGENTS: list[tuple[str, callable, str, int, int]] = [
        # (job_id,              run_fn,                              name,                lock_id, offset_min)
        ("sub_breaking_news",   breaking_news.run_draft_cycle,       "Breaking News",     1010,   0),
        ("sub_threads",         threads.run_draft_cycle,             "Threads",           1011,   17),
        ("sub_long_form",       long_form.run_draft_cycle,           "Long-form",         1012,   34),
        ("sub_quotes",          quotes.run_draft_cycle,              "Quotes",            1013,   51),
        ("sub_infographics",    infographics.run_draft_cycle,        "Infographics",      1014,   68),
        ("sub_video_clip",      video_clip.run_draft_cycle,          "Gold Media",        1015,   85),
        ("sub_gold_history",    gold_history.run_draft_cycle,        "Gold History",      1016,   102),
    ]
    ```

    ### 4.4 build_scheduler()
    - Remove the current `content_agent` and `gold_history_agent`
      `scheduler.add_job(...)` calls.
    - Keep the `morning_digest` cron job exactly as-is.
    - Add AsyncIOScheduler `job_defaults`:
      ```python
      scheduler = AsyncIOScheduler(
          job_defaults={
              "coalesce": True,
              "max_instances": 1,
              "misfire_grace_time": 300,
          },
          timezone="UTC",
      )
      ```
    - Loop over `CONTENT_SUB_AGENTS` and register each:
      ```python
      now = datetime.now(timezone.utc)
      for job_id, run_fn, name, lock_id, offset in CONTENT_SUB_AGENTS:
          start_date = now + timedelta(minutes=offset)
          scheduler.add_job(
              _make_sub_agent_job(job_id, lock_id, run_fn, engine),
              trigger=IntervalTrigger(hours=2, start_date=start_date),
              id=job_id,
              name=f"{name} — every 2h (offset +{offset}m)",
          )
      ```
    - Add a new helper `_make_sub_agent_job(job_id, lock_id, run_fn, engine)`
      (mirror the existing `_make_job` pattern but parameterized on `run_fn`
      directly so each sub-agent's `run_draft_cycle()` executes under its own
      advisory lock).
    - Delete the `content_agent` branch and the `gold_history_agent` branch
      from `_make_job` (or delete `_make_job` entirely if only
      `morning_digest` remains — keep whatever is cleaner).

    ### 4.5 _read_schedule_config
    - REMOVE `"content_agent_interval_hours": "3"` from the defaults dict.
    - REMOVE `"gold_history_hour": "9"` from the defaults dict.
    - Keep `"morning_digest_schedule_hour": "8"`.
    - Delete the `int(cfg["content_agent_interval_hours"])` and
      `int(cfg["gold_history_hour"])` reads.

    ### 4.6 upsert_agent_config()
    - REMOVE `"content_agent_interval_hours": "3"` from the overrides dict.
      (Leave the other content_* config keys — they're still read by sub-agents.)

    ### 4.7 scheduler/database.py
    Bump `pool_size=3` → `pool_size=15`, `max_overflow=2` → `max_overflow=10`
    to match research recommendation. Update the comment accordingly.

    **Do NOT delete the `content_agent_interval_hours` DB row itself** —
    that's operator-facing cleanup best done manually or in a follow-up quick
    task. Just stop reading/writing it from code.
  </action>
  <verify>
    <automated>cd scheduler && uv run ruff check worker.py database.py && uv run python -c "import worker; assert len(worker.CONTENT_SUB_AGENTS) == 7; assert 'content_agent' not in worker.JOB_LOCK_IDS; assert 'gold_history_agent' not in worker.JOB_LOCK_IDS; assert 'sub_breaking_news' in worker.JOB_LOCK_IDS; print('OK')"</automated>
    Expected:
    - ruff clean on both files.
    - `CONTENT_SUB_AGENTS` has 7 entries.
    - `JOB_LOCK_IDS` has exactly: morning_digest, sub_breaking_news, sub_threads, sub_long_form, sub_quotes, sub_infographics, sub_video_clip, sub_gold_history (8 entries total).
    - `grep 'from agents.content\.' scheduler/worker.py | wc -l` ≥ 1 (imports, single-line grouped import also counts).
    - `grep -cE 'content_agent_interval_hours' scheduler/worker.py` returns 0.
    - `grep 'pool_size=15' scheduler/database.py | wc -l` returns 1.
  </verify>
  <done>
    worker.py registers 8 jobs (morning_digest + 7 sub-agents), retires content_agent + gold_history_agent, uses CONTENT_SUB_AGENTS data-driven registration with stagger offsets [0,17,34,51,68,85,102] and lock IDs [1010-1016]; scheduler/database.py pool_size=15; `content_agent_interval_hours` no longer read or written by code.
  </done>
</task>

<task id="T05" type="auto">
  <name>Task 5: Update scheduler tests (worker + per-agent + shrink content_agent test)</name>
  <files>
    scheduler/tests/test_content_agent.py
    scheduler/tests/test_worker.py
    scheduler/tests/test_breaking_news.py
    scheduler/tests/test_threads.py
    scheduler/tests/test_long_form.py
    scheduler/tests/test_quotes.py
    scheduler/tests/test_infographics.py
    scheduler/tests/test_video_clip.py
    scheduler/tests/test_gold_history.py
  </files>
  <action>
    Populate the real per-agent test bodies (replacing the Wave-0 stubs) and
    shrink test_content_agent.py to cover only the new public surface.

    ### 5.1 Per-agent tests (test_<agent>.py × 7)
    For each of the 7 sub-agent modules, replace the Wave-0 stub with tests
    that cover:
    - `run_draft_cycle()` happy path: mock `content_agent.fetch_stories()` (or
      the module's own source for gold_history) to return one eligible story;
      mock `content_agent.review()` to return `{"compliance_passed": True}`;
      assert a `ContentBundle` row is written with `content_type=<expected>`,
      `compliance_passed=True`, `draft_content` populated.
    - `run_draft_cycle()` review-fail path: mock `review()` to return
      `{"compliance_passed": False, "rationale": "..."}`; assert bundle written
      with `compliance_passed=False`.
    - `run_draft_cycle()` fetch-empty: mock `fetch_stories()` to return `[]`;
      assert no bundle is written and function returns cleanly.
    - **Migrate** any pre-existing relevant tests from the old
      `test_content_agent.py` (drafting tests for that specific content_type)
      into the new file. Use `git mv`-equivalent logic or copy-then-adapt.

    Minimum 3 tests per new test file; all async (use `pytest.mark.asyncio`
    or `anyio`).

    ### 5.2 test_worker.py
    Add (or extend existing):
    - `test_sub_agent_staggering` — import `CONTENT_SUB_AGENTS` and assert
      offsets are `[0, 17, 34, 51, 68, 85, 102]` in the correct order.
    - `test_sub_agent_lock_ids` — assert `JOB_LOCK_IDS` contains all 7
      `sub_*` keys mapping to `1010–1016` and does NOT contain `content_agent`
      or `gold_history_agent`.
    - `test_scheduler_registers_8_jobs` — call `build_scheduler(engine)` with
      a test engine (or mock the config read) and assert
      `len(scheduler.get_jobs()) == 8` with the expected job IDs.

    ### 5.3 test_content_agent.py (SHRINK)
    Delete all existing tests that cover deleted methods (`_draft_*`,
    `ContentAgent.run`, `_run_pipeline`, `_gate_draft`). Keep OR add:
    - `test_fetch_stories_cache_hit` — call `fetch_stories()` twice within
      the same 30-min bucket; assert the underlying SerpAPI/RSS mock is
      called only once.
    - `test_fetch_stories_cache_miss_new_bucket` — advance the time mock
      past the 30-min boundary; assert a second fetch occurs.
    - `test_fetch_stories_fetch_failure` — mock the underlying fetch to
      raise; assert `fetch_stories()` returns `[]` and logs a warning
      (doesn't raise).
    - `test_review_pass` — call `review({...draft...})`; mock Haiku client
      to return compliance-passed; assert return dict shape.
    - `test_review_fail` — mock Haiku to return non-compliance; assert
      `compliance_passed=False` and rationale populated.
    - `test_classify_format_lightweight_returns_expected_strings` — sanity-check
      that classifier returns EXACTLY the strings sub-agents filter on
      (per RESEARCH pitfall #6).

    ### 5.4 Old gold_history test file
    If `scheduler/tests/test_gold_history_agent.py` exists, migrate its
    tests into `scheduler/tests/test_gold_history.py` (produced in this task)
    and delete the old file.
  </action>
  <verify>
    <automated>cd scheduler && uv run pytest -x</automated>
    Expected:
    - All scheduler tests pass (green).
    - No SKIPPED Wave-0 stubs remain (all replaced).
    - `grep -l 'pytest.importorskip' scheduler/tests/test_{breaking_news,threads,long_form,quotes,infographics,video_clip,gold_history}.py` returns 0 files (stubs gone).
  </verify>
  <done>
    Scheduler pytest suite green; each per-agent test file has ≥3 real tests; test_worker.py validates stagger + lock IDs + 8-job registration; test_content_agent.py covers cache + review + classifier only; no Wave-0 stubs remain.
  </done>
</task>

<!-- =========================================================== -->
<!-- WAVE 3 — Backend: /queue?content_type= filter + pool bump   -->
<!-- =========================================================== -->

<task id="T06" type="auto">
  <name>Task 6: Backend /queue endpoint — add content_type filter + pool bump</name>
  <files>
    backend/app/routers/queue.py
    backend/app/database.py
    backend/tests/routers/test_queue.py
  </files>
  <action>
    ### 6.1 backend/app/routers/queue.py
    Add a `content_type: str | None = Query(None)` parameter to `list_queue`.

    When provided, filter `draft_items` to only those whose
    `engagement_snapshot->>'content_bundle_id'` points at a `content_bundles`
    row with the matching `content_type`. Because there's no direct FK, use:

    ```python
    from sqlalchemy import select, cast, String
    from sqlalchemy.dialects.postgresql import JSONB
    from app.models.content_bundle import ContentBundle

    if content_type:
        bundle_ids_subq = select(cast(ContentBundle.id, String)).where(
            ContentBundle.content_type == content_type
        )
        # JSONB ->> returns text; compare to uuid-as-text subquery
        conditions.append(
            DraftItem.engagement_snapshot["content_bundle_id"].astext.in_(bundle_ids_subq)
        )
    ```

    (The executor picks whichever SQLAlchemy 2.0 idiom reads cleanest — a
    correlated subquery or a join on the JSONB text comparison. Both are
    acceptable as long as the resulting SQL filters correctly.)

    Update the docstring to mention the new filter.

    ### 6.2 backend/app/database.py
    Bump `pool_size=5` → `pool_size=15`, keep `max_overflow=10`. Update the
    inline comment to reflect the new peak-concurrency target (7 sub-agents +
    morning_digest + user-triggered API calls).

    ### 6.3 backend/tests/routers/test_queue.py
    Extend (or create) the test file with:
    - `test_queue_content_type_filter_returns_only_matching` — seed 3 content
      bundles (content_type: breaking_news, thread, long_form) + 3 matching
      DraftItems with the JSONB pointer set; call
      `GET /queue?platform=content&content_type=thread` and assert only the
      thread DraftItem returns.
    - `test_queue_content_type_filter_omitted_returns_all` — omit
      `content_type`; assert all 3 return.
    - `test_queue_content_type_filter_unknown_type_returns_empty` — pass
      `content_type=bogus`; assert empty list, not 500.

    **Do NOT change** the cursor-pagination logic or the existing
    `platform`/`status` filter behavior — only ADD `content_type` as an
    orthogonal filter.
  </action>
  <verify>
    <automated>cd backend && uv run ruff check app/routers/queue.py app/database.py && uv run pytest tests/routers/test_queue.py -x</automated>
    Expected:
    - ruff clean on both files.
    - All three new test cases pass.
    - `grep "content_type" backend/app/routers/queue.py | wc -l` returns ≥2.
    - `grep "pool_size=15" backend/app/database.py | wc -l` returns 1.
  </verify>
  <done>
    `/queue?content_type=X` returns only drafts whose linked content_bundle has that content_type; backend pool_size=15; 3 new tests green.
  </done>
</task>

<!-- ============================================================= -->
<!-- WAVE 4 — Frontend routing/sidebar/agent-options               -->
<!-- ============================================================= -->

<task id="T07" type="auto">
  <name>Task 7: Frontend — CONTENT_AGENT_TABS config + PerAgentQueuePage + App.tsx route rewire</name>
  <files>
    frontend/src/config/agentTabs.ts
    frontend/src/pages/PerAgentQueuePage.tsx
    frontend/src/pages/PlatformQueuePage.tsx
    frontend/src/App.tsx
    frontend/src/pages/PerAgentQueuePage.test.tsx
  </files>
  <action>
    ### 7.1 Create `frontend/src/config/agentTabs.ts`
    Export the 7-entry `CONTENT_AGENT_TABS` array exactly as shown in the
    `<interfaces>` block (section 6 above). Export the `AgentTab` TypeScript
    type.

    ### 7.2 Create `frontend/src/pages/PerAgentQueuePage.tsx`
    Rename/replace `PlatformQueuePage.tsx`. The new page:
    - Reads `slug` from `useParams<{ slug: string }>()`.
    - Looks up the matching tab in `CONTENT_AGENT_TABS`.
    - Unknown slug → `<Navigate to="/agents/breaking-news" replace />`.
    - `useQuery` with queryKey `["queue", "content", tab.contentType]` and
      queryFn calling the existing queue API with `platform: "content",
      contentType: tab.contentType`.
    - Updates `frontend/src/api/queue.ts` (or wherever `getQueue` lives) to
      pass `content_type` through as a query param when provided — EXECUTOR:
      confirm the API helper signature and add the optional arg; this is a
      small orthogonal change, include it in this task.
    - Renders the existing ContentSummaryCard list UI for the returned items
      (preserve the run-grouping logic from PlatformQueuePage — users expect
      it). Page H1 = `tab.label`.

    DELETE `frontend/src/pages/PlatformQueuePage.tsx` — no remaining callers
    after App.tsx rewire. Also delete `frontend/src/pages/PlatformQueuePage.test.tsx`
    if present.

    ### 7.3 Update `frontend/src/App.tsx`
    - Remove `import { PlatformQueuePage }` line.
    - Add `import { PerAgentQueuePage } from '@/pages/PerAgentQueuePage'`.
    - Remove `<Route path="/content" element={<PlatformQueuePage platform="content" />} />`.
    - Remove `<Route path="/content-review" element={<ContentPage />} />`
      only if `ContentPage` is dead code (verify: no sidebar link + no other
      internal links). If live, leave it.
    - Change root redirect: `<Route path="/" element={<Navigate to="/agents/breaking-news" replace />} />`.
    - Add `<Route path="/agents/:slug" element={<PerAgentQueuePage />} />`
      (single dynamic route — NOT 7 static routes).

    ### 7.4 Create `frontend/src/pages/PerAgentQueuePage.test.tsx`
    Cover with vitest + MSW (or existing test scaffold):
    - Renders queue for `breaking-news` slug and queries the API with
      `content_type=breaking_news`.
    - Renders queue for `threads` slug → `content_type=thread`.
    - Unknown slug (`/agents/foobar`) redirects to `/agents/breaking-news`.
    - TanStack queryKey includes contentType (verify via query cache probe
      or MSW request assertion).

    **Deploy-order note (RESEARCH pitfall #10):** the executor MUST commit
    Task 6 (backend) before Task 7 (frontend) — already enforced by sequential
    task order.
  </action>
  <verify>
    <automated>cd frontend && npm run lint && npm run test -- --run PerAgentQueuePage</automated>
    Expected:
    - eslint clean.
    - PerAgentQueuePage.test.tsx passes.
    - `grep -c '/content' frontend/src/App.tsx` returns 0 for standalone `/content` route string (may still appear in `/agents/*` or comments — tolerate).
    - `grep -c 'PlatformQueuePage' frontend/src/App.tsx` returns 0.
    - `test -e frontend/src/pages/PlatformQueuePage.tsx` returns 1 (file does not exist).
    - `test -e frontend/src/config/agentTabs.ts` returns 0 (file exists).
  </verify>
  <done>
    `/agents/:slug` single dynamic route serves all 7 per-agent queues; root redirects to `/agents/breaking-news`; PlatformQueuePage deleted; CONTENT_AGENT_TABS is the single source of truth for tab config; PerAgentQueuePage tests green.
  </done>
</task>

<task id="T08" type="auto">
  <name>Task 8: Frontend — Sidebar + AgentRunsTab + queue-counts hook</name>
  <files>
    frontend/src/components/layout/Sidebar.tsx
    frontend/src/components/settings/AgentRunsTab.tsx
    frontend/src/hooks/useQueueCounts.ts
  </files>
  <action>
    ### 8.1 Sidebar.tsx
    Replace the single-item `agentItems` array with a data-driven render over
    `CONTENT_AGENT_TABS` (sorted by `priority`):

    ```tsx
    import { CONTENT_AGENT_TABS } from '@/config/agentTabs'
    const agentItems = [...CONTENT_AGENT_TABS]
      .sort((a, b) => a.priority - b.priority)
      .map(tab => ({
        to: `/agents/${tab.slug}`,
        label: tab.label,
        icon: <FileText className="size-4" />,    // reuse existing icon or pick per-tab
        badge: countLabel(counts[tab.contentType] ?? 0, counts[`${tab.contentType}HasMore`] ?? false),
      }))
    ```

    Update the "Single-agent" comment to `7 sub-agents post quick-260421-eoe`.
    Leave bottom nav (Digest, Settings) unchanged.

    ### 8.2 useQueueCounts.ts
    Update the hook to return counts keyed by content_type (not just platform).
    If the hook currently returns `{content: number, contentHasMore: boolean}`,
    extend to `{[contentType]: number}` for all 7 types OR make the hook
    parameter-driven (`useQueueCounts(contentType)`). Pick whichever fits the
    existing call shape.

    If this requires a separate request per content_type (7 queries vs. 1),
    that's acceptable — TanStack Query dedupes and the payload is tiny.
    Alternatively, add a single `/queue/counts` aggregation endpoint — BUT
    only if trivial; don't balloon this task. Default: 7 `useQuery` calls
    with distinct queryKeys.

    ### 8.3 AgentRunsTab.tsx
    Replace `AGENT_OPTIONS`:
    ```ts
    const AGENT_OPTIONS = [
      { value: '', label: 'All agents' },
      { value: 'sub_breaking_news', label: 'breaking_news' },
      { value: 'sub_threads',       label: 'threads' },
      { value: 'sub_long_form',     label: 'long_form' },
      { value: 'sub_quotes',        label: 'quotes' },
      { value: 'sub_infographics',  label: 'infographics' },
      { value: 'sub_video_clip',    label: 'video_clip (Gold Media)' },
      { value: 'sub_gold_history',  label: 'gold_history' },
      { value: 'morning_digest',    label: 'morning_digest' },
    ]
    ```

    The `value` field must match the agent_run row's `agent_name` column —
    verify by grepping how sub-agents record their runs. If sub-agents record
    `agent_name="breaking_news"` (not `"sub_breaking_news"`), use that instead.
    **EXECUTOR: grep `agent_run` creation in the new sub-agent modules; the
    `value` must match exactly what gets written.**

    Remove `content_agent` and `gold_history_agent` from the options list
    entirely (those names no longer appear in new agent_runs rows — historical
    rows still exist but users filtering by dropdown won't need them).

    Update the comment at top of file to reference quick-260421-eoe.
  </action>
  <verify>
    <automated>cd frontend && npm run lint && npm run test</automated>
    Expected:
    - eslint clean.
    - vitest suite green (existing tests may need minor updates for 7-item sidebar or new agent names).
    - `grep -c "CONTENT_AGENT_TABS" frontend/src/components/layout/Sidebar.tsx` returns ≥1.
    - `grep -cE "content_agent'|gold_history_agent'" frontend/src/components/settings/AgentRunsTab.tsx` returns 0.
    - Sidebar renders 7 agent NavLinks matching the priority order.
  </verify>
  <done>
    Sidebar renders 7 agent tabs in priority order from CONTENT_AGENT_TABS; AgentRunsTab dropdown lists the 7 new sub-agent names + morning_digest; `content_agent` and `gold_history_agent` removed from dropdown; useQueueCounts provides per-content_type counts; frontend vitest + lint green.
  </done>
</task>

<!-- ============================================================= -->
<!-- WAVE 5 — Documentation + final validation sweep               -->
<!-- ============================================================= -->

<task id="T09" type="auto">
  <name>Task 9: Update CLAUDE.md narrative + scheduled-job count</name>
  <files>
    CLAUDE.md
  </files>
  <action>
    Update `CLAUDE.md` to reflect the 7-sub-agent system. Scope the edits
    narrowly — do NOT rewrite historical notes.

    ### 9.1 Opening paragraph (line ~3)
    Replace:
    > "A single-agent AI system that monitors the gold sector via news feeds 24/7, drafts engagement content, and surfaces everything to a web dashboard for manual approval. The Content Agent handles research, scoring, and drafting — you review, approve, copy, and post."

    With:
    > "A 7-sub-agent AI system that monitors the gold sector via news feeds 24/7, drafts engagement content across 7 content types (breaking news, threads, long-form, quotes, infographics, gold media, gold history), and surfaces everything to a web dashboard for manual approval. Each sub-agent runs its own APScheduler cron every 2 hours (staggered across the 2h window). A shared Content Agent review service provides compliance gating and news ingestion for the sub-agents to call into — it is not itself scheduled. You review, approve, copy, and post."

    ### 9.2 Scheduled job count
    Find the sentence (end of the post-sn9 note) that says:
    > "The scheduler runs just `content_agent` + a trimmed `morning_digest` job + the opportunistic `gold_history_agent`."

    Replace with:
    > "The scheduler runs 8 jobs: 7 sub-agents (`sub_breaking_news`, `sub_threads`, `sub_long_form`, `sub_quotes`, `sub_infographics`, `sub_video_clip`, `sub_gold_history`) each on a staggered 2h interval, plus a trimmed `morning_digest` daily cron. Content Agent (`scheduler/agents/content_agent.py`) is a library module — NOT a scheduled job — exposing `fetch_stories()` (shared SerpAPI+RSS ingestion, 30-min cache) and `review(draft)` (Haiku compliance gate) for sub-agents to call inline."

    Also update the Stack summary row:
    > "APScheduler in separate worker process (three scheduled jobs: `content_agent`, `morning_digest`, `gold_history_agent`)"

    To:
    > "APScheduler in separate worker process (eight scheduled jobs: 7 sub-agents + `morning_digest`)"

    ### 9.3 Do NOT edit
    - The Instagram historical note (2026-04-19)
    - The Twitter / Senior purge historical note (2026-04-20) — except the
      one "scheduler runs just" sentence called out above
    - The Tech Stack, Installation, Alternatives, What NOT to Use, Version
      Compatibility, Sources sections
    - The Constraints bullets (budget, X API, News, etc.)

    Keep edits minimal and surgical. If the executor is uncertain whether
    a sentence needs updating, err on the side of leaving it alone.

    ### 9.4 STATE.md
    **Do NOT update STATE.md in this task.** STATE.md is updated by the executor
    after all tasks complete (standard quick-task flow — not part of the plan
    itself).
  </action>
  <verify>
    <automated>grep -c "7 sub-agent\|7-sub-agent" CLAUDE.md</automated>
    Expected:
    - ≥2 matches for "7 sub-agent" phrasing in CLAUDE.md.
    - `grep -c "single-agent system" CLAUDE.md` returns ≤2 (the two historical notes reference "single-agent system" in past tense — those stay).
    - `grep -c "three scheduled jobs" CLAUDE.md` returns 0.
    - `grep -c "eight scheduled jobs\|8 jobs\|7 sub-agents" CLAUDE.md` returns ≥1.
  </verify>
  <done>
    CLAUDE.md opening paragraph reflects 7-sub-agent + review service architecture; scheduled-job count reads 8; historical notes (Instagram purge, Twitter/Senior purge) left intact; no unrelated sections touched.
  </done>
</task>

<task id="T10" type="auto">
  <name>Task 10: Full validation sweep (scheduler + backend + frontend + ruff + lint + build)</name>
  <files>
    <!-- No file changes — this is a verification-only task. -->
  </files>
  <action>
    Run the full validation suite to confirm the 15 verifier checks (from
    CONTEXT.md and this plan's `<success_criteria>`) pass. Do NOT commit in
    this task (nothing changed). If any check fails, open the relevant
    previous task's scope to patch.

    Run these commands in sequence and record outputs:

    1. `cd scheduler && uv run ruff check .`
    2. `cd scheduler && uv run pytest`
    3. `cd backend && uv run ruff check .`
    4. `cd backend && uv run pytest`
    5. `cd frontend && npm run lint`
    6. `cd frontend && npm run test -- --run`
    7. `cd frontend && npm run build`

    Then run the structural greps listed in `<success_criteria>` and compare
    expected vs actual.

    If any structural grep returns unexpected output, stop and report which
    task needs a patch. Otherwise, report validation GREEN.
  </action>
  <verify>
    <automated>cd scheduler && uv run ruff check . && uv run pytest && cd ../backend && uv run ruff check . && uv run pytest && cd ../frontend && npm run lint && npm run test -- --run && npm run build</automated>
    Expected: exit 0 end-to-end. All 15 structural/grep checks from `<success_criteria>` satisfied.
  </verify>
  <done>
    All 15 verifier checks pass; scheduler + backend + frontend suites green; npm build succeeds; no regressions.
  </done>
</task>

</tasks>

<success_criteria>
## The 15 Verifier Checks (from CONTEXT.md `<task_boundary>` + this plan)

1. **Sub-agent files exist:** `ls scheduler/agents/content/*.py` → 8 files (7 sub-agents + `__init__.py`).
2. **No `_draft_*` remnants in content_agent:** `grep "_draft_" scheduler/agents/content_agent.py` → 0 matches.
3. **worker.py imports 7 sub-agents:** `grep "from agents.content\." scheduler/worker.py` → ≥1 line (grouped import counts as one line; the import statement must reference all 7 modules).
4. **Scheduler registers 8 jobs:** `build_scheduler(engine)` → `len(scheduler.get_jobs()) == 8` (morning_digest + 7 sub-agents). No `content_agent` job id. No `gold_history_agent` job id.
5. **Old gold_history_agent module deleted:** `test -e scheduler/agents/gold_history_agent.py` returns 1 (non-zero: file does not exist).
6. **Frontend has no `/content` route:** `grep -E '"/content"|\\spath="/content"' frontend/src/App.tsx` → 0 matches (only `/agents/*` paths remain).
7. **Frontend has no combined `PlatformQueuePage`:** `test -e frontend/src/pages/PlatformQueuePage.tsx` returns 1.
8. **7 `/agents/<slug>` routes mounted** via single dynamic route: `grep '/agents/:slug' frontend/src/App.tsx` → 1 match; `CONTENT_AGENT_TABS.length === 7` in `frontend/src/config/agentTabs.ts`.
9. **7 sidebar entries, priority order:** `frontend/src/components/layout/Sidebar.tsx` renders from `CONTENT_AGENT_TABS` sorted by priority; vitest snapshot/test asserts 7 NavLinks in order Breaking News → Threads → Long-form → Quotes → Infographics → Gold Media → Gold History.
10. **Scheduler ruff clean:** `cd scheduler && uv run ruff check .` → exit 0.
11. **Backend ruff clean:** `cd backend && uv run ruff check .` → exit 0.
12. **Scheduler pytest green:** `cd scheduler && uv run pytest` → exit 0.
13. **Backend pytest green:** `cd backend && uv run pytest` → exit 0.
14. **Frontend vitest + build green:** `cd frontend && npm run test -- --run && npm run build` → exit 0.
15. **CLAUDE.md updated:** `grep -c "7 sub-agent\|7-sub-agent" CLAUDE.md` ≥ 2; scheduled-job count text reads 8 jobs; Instagram and Twitter/Senior historical notes preserved.

## Architectural invariants (enforced by code structure)

- `content_agent.review()` called INLINE by each sub-agent (not deferred) — `grep -c "content_agent.review(" scheduler/agents/content/*.py` returns 7.
- `content_agent.fetch_stories()` uses TTL-30min in-memory cache keyed on `int(time.time() // 1800)` — enforced by `test_fetch_stories_cache_hit`.
- 6 of 7 sub-agents call `content_agent.fetch_stories()`; `gold_history.py` has its own source — enforced by `grep -c "content_agent.fetch_stories(" scheduler/agents/content/*.py` returns 6.
- `JOB_LOCK_IDS` has exactly 8 entries: morning_digest(1005) + sub_* (1010-1016); no 1003, no 1009 — enforced by `test_sub_agent_lock_ids`.
- Stagger offsets are `[0, 17, 34, 51, 68, 85, 102]` minutes — enforced by `test_sub_agent_staggering`.
- Neon pool_size=15 on BOTH `scheduler/database.py` AND `backend/app/database.py`.
- `content_agent_interval_hours` config key no longer read or written by code (DB row may remain for manual cleanup).

## Out of scope (explicitly NOT changed by this plan)

- No DB migrations (no new columns, no renames).
- No new content_type values.
- Prompts for drafting / review are preserved verbatim (functional parity).
- `/content-review` route + `ContentPage` component are left alone unless orphaned (executor verifies).
- `watchlists` table stays untouched.
- `X_API_BEARER_TOKEN` critical-env validation in `_validate_env` stays (video_clip still calls tweepy).
- Breaking-news event-mode faster cadence — deferred.
- `morning_digest` cron behavior — unchanged.
</success_criteria>

<verification>
## Per-wave verification gates

- **After Wave 0 (T01):** `cd scheduler && uv run pytest scheduler/tests/test_{breaking_news,threads,long_form,quotes,infographics,video_clip,gold_history}.py -x` → 7 SKIPPED, 0 ERROR.
- **After Wave 1 (T02-T03):** scheduler module structure complete. `ls scheduler/agents/content/*.py | wc -l` = 8. `test -e scheduler/agents/gold_history_agent.py` = 1 (deleted). `grep "_draft_" scheduler/agents/content_agent.py` = 0. (Note: scheduler worker.py still imports old classes at this point — deliberate intermediate state; verify after T04.)
- **After Wave 2 (T04-T05):** `cd scheduler && uv run pytest && uv run ruff check .` green. 8 jobs registered by build_scheduler. All 7 per-agent test files have real assertions.
- **After Wave 3 (T06):** `cd backend && uv run pytest tests/routers/test_queue.py -x && uv run ruff check .` green. `/queue?content_type=thread` returns only threads.
- **After Wave 4 (T07-T08):** `cd frontend && npm run lint && npm run test -- --run` green. 7 routes reachable. Sidebar shows 7 items.
- **After Wave 5 (T09):** CLAUDE.md reads "7 sub-agent system". All 15 verifier checks green (T10).

## Plan-check constraint awareness

Each task has an explicit `<files>` list, an atomic `<action>` scope, automated
`<verify>` commands, and measurable `<done>` criteria. Task ordering is strict
sequential (T01 → T10) because:

- T02 breaks worker.py imports mid-flight; T03 creates the modules worker.py
  will need; T04 rewires worker.py to the new surface. Intermediate commits
  between T02 and T04 are build-broken — acceptable because each commit is
  atomic and revertible, and the task executor commits between tasks.
- T06 (backend `content_type` filter) MUST land before T07 (frontend) so the
  first frontend request with `?content_type=` doesn't 400 on prod deploy.
- Per RESEARCH pitfall #10: Railway deploy order is backend → frontend.
  Sequential commits respect this.

No task assumes a DB migration. The `draft_items.engagement_snapshot`
JSONB link pattern is pre-existing (seen at `content_agent.py:712-723` in
the pre-split code).

`gold_history_agent.py` is gracefully retired:
1. T03 creates `content/gold_history.py` with full parity and deletes the old
   module file.
2. T04 removes the worker.py cron registration + lock ID + import.
3. T09 updates CLAUDE.md so the historical "gold_history_agent" reference
   correctly reads as retired.
</verification>

<output>
After T10 completes GREEN, the executor:
1. Commits T10 as the final plan task (no file changes — validation only commit or skip if empty).
2. Appends an entry to `.planning/STATE.md` noting `260421-eoe` completion + the 8-job topology + the retired `content_agent`/`gold_history_agent` crons.
3. Writes `.planning/quick/260421-eoe-split-content-agent-into-7-sub-agents-or/260421-eoe-SUMMARY.md` using the quick-task summary template.
4. Runs `/gsd:verify-work` which re-executes the 15 verifier checks in `<success_criteria>`.

No Railway deploy is part of this plan — deployment is the operator's decision post-merge. When deploying: backend service FIRST, then frontend, scheduler any time after.
</output>
