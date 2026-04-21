# Quick Task 260421-eoe: Split Content Agent into 7 sub-agents — Context

**Gathered:** 2026-04-21
**Status:** Ready for planning (Phase C architecture — cron-less Content Agent)

<domain>
## Task Boundary

Refactor the monolithic `scheduler/agents/content_agent.py` (~2000 lines) into a **review-service-only module** + 7 independent sub-agent modules, one per existing `content_type` value. Content Agent loses its cron entirely — it becomes a pure utility exposing two methods: `fetch_stories()` (shared ingestion with in-memory cache) and `review(draft)` (Haiku compliance gate). Each sub-agent runs its own APScheduler cron at 2h cadence, self-contained: fetch → type-filter → draft → call review() inline → write to `content_bundles` with `compliance_passed` already set.

**All 7 content types already exist** as values in `content_bundles.content_type` (`breaking_news`, `thread`, `long_form`, `quote`, `infographic`, `gold_history`, `video_clip`). This is purely an execution-layer refactor — no new features, **no schema changes**, no new prompts. Functional parity with current `content_agent.py` behavior is mandatory.

The existing standalone `scheduler/agents/gold_history_agent.py` folds into the same pattern (moves to `scheduler/agents/content/gold_history.py`).

Frontend: the existing combined `/content` queue tab is replaced by 7 per-agent tabs under the "Agents" sidebar section. Each tab queries `/queue?content_type=<type>`. No combined "all drafts" view.

Post-refactor scheduler runs **8 jobs**: `morning_digest` + 7 sub-agents. **No content_agent cron.** Content Agent is imported as a library by each sub-agent.

</domain>

<decisions>
## Implementation Decisions

### Content Agent's post-split role (PHASE C — cron-less review service)
- **DECISION: Content Agent has NO cron. It is a pure Python module/class exposing two services:**
  1. `fetch_stories() -> list[Story]` — shared SerpAPI + RSS ingestion with in-memory cache (TTL 30min). Called by each sub-agent at the start of its tick; first caller within a 30-min window pays the fetch cost, subsequent callers reuse the cache.
  2. `review(draft: dict) -> ReviewResult` — Haiku compliance gate. Called inline by each sub-agent after drafting, before writing the `content_bundles` row. Returns pass/fail + rationale; sub-agent writes `compliance_passed` directly.
- **Rationale:** Acts "like the Senior Agent" — a review layer that other agents consult, not a scheduled actor. Removes the 30-min gate-latency problem. Removes the need for a `draft_content IS NULL` handoff column. Removes the DB migration that was flagged by research (`research_context` JSONB column) since each sub-agent is now self-contained within a single tick.

### Sub-agent execution pattern (self-contained)
- **DECISION: 7 independent APScheduler cron jobs, every 2 hours each, staggered.** Each sub-agent on its own tick:
  1. Calls `content_agent.fetch_stories()` (shared cache hit or miss)
  2. Filters / classifies to its own content_type
  3. Drafts via Sonnet (existing `_draft_*` logic extracted)
  4. Calls `content_agent.review(draft)` inline
  5. Writes `content_bundles` row with `content_type`, `draft_content`, and `compliance_passed` all set in one transaction
- Cadence (2h) locked for now — operator will revisit later per "we'll go into the infrastructure of each agent later."
- **Stagger offsets (from research):** `+0 / +17 / +34 / +51 / +68 / +85 / +102` minutes across the 2h window. Prevents all 7 sub-agents from hammering the DB + Anthropic API simultaneously while keeping each on a clean 2h interval.

### Compliance gate placement (inline, not deferred)
- **DECISION: Inline via `content_agent.review()` call from each sub-agent.** Sub-agents call the gate synchronously after drafting, before writing. No cross-tick handoff, no ungated-draft limbo state.
- **Rationale:** Cleaner than deferred pattern; no 30-min latency; no need for a separate `compliance_passed IS NULL` polling step. Content Agent's `review()` is a pure function (no DB I/O), so circular-import and state-coupling risks are minimal.

### Ingestion plumbing (shared fetch via Content Agent)
- **DECISION: Content Agent exposes `fetch_stories()` with module-level in-memory cache, TTL 30min.**
- First sub-agent tick in any 30-min window triggers the real SerpAPI + RSS fetch + scoring; stores result in cache keyed by timestamp bucket.
- Subsequent sub-agent ticks within the same window reuse the cached list (near-zero latency, zero duplicate API calls).
- Cache is process-local; Railway's single scheduler worker means no cross-process invalidation needed.
- Cache-miss fallback: if a sub-agent ticks and fetch fails (SerpAPI outage, RSS timeout), it logs a warning and skips this cycle (same behavior as today's content_agent on fetch failure).

### Gold History Agent
- **DECISION: Fold into the 7-agent pattern.** Existing `scheduler/agents/gold_history_agent.py` moves to `scheduler/agents/content/gold_history.py`, adopts the same `async def run_draft_cycle()` signature as the other 6 sub-agents. Its existing 2-hour cadence is already compatible. Gold History does NOT use `fetch_stories()` (it has its own historical-story source); it still calls `review()` inline before writing.

### Video clip naming
- **DECISION: Keep `content_type='video_clip'` in DB; module named `video_clip.py`.** Frontend tab labeled "Gold Media". Rationale: avoids DB migration, keeps grep-ability with existing `_search_video_clips`/`_draft_video_caption` function names.

### Queue tabs data model
- **DECISION: Filter on `content_type` inside `platform='content'`.** No schema change. Frontend routes: `/agents/breaking-news`, `/agents/threads`, `/agents/long-form`, `/agents/quotes`, `/agents/infographics`, `/agents/gold-media`, `/agents/gold-history`. Each tab queries backend with `?content_type=<type>`.

### Directory structure
- **DECISION: Grouped namespace** `scheduler/agents/content/`:
  ```
  scheduler/agents/
  ├── content_agent.py              # review-service module: fetch_stories() + review()
  └── content/
      ├── __init__.py
      ├── breaking_news.py
      ├── threads.py
      ├── long_form.py
      ├── quotes.py
      ├── infographics.py
      ├── video_clip.py              # "Gold Media" tab; preserves tweepy pipeline
      └── gold_history.py            # moved from scheduler/agents/gold_history_agent.py
  ```

### Sidebar structure
- **DECISION: Combined queue removed entirely.** The existing single `/content` tab is replaced by 7 per-agent tabs under the "Agents" sidebar section. No combined "all drafts" view. The "Queue" sidebar section itself disappears (or is repurposed if it has any remaining logical grouping — planner decides).

### Sidebar ordering (user-confirmed: By Priority)
- **DECISION: Priority ordering in sidebar:**
  1. Breaking News
  2. Threads
  3. Long-form
  4. Quotes
  5. Infographics
  6. Gold Media
  7. Gold History
- Rationale: matches content importance; highest-frequency drafters (breaking/threads) first.

### Claude's Discretion

**Review method surface:**
- `content_agent.review(draft: dict) -> dict` — pure in-process function. Takes the drafted text + metadata; returns `{"compliance_passed": bool, "rationale": str}`. No DB I/O inside `review()`; sub-agent owns the write.

**Fetch cache implementation:**
- Simple module-level `dict` keyed by 30-min timestamp bucket (e.g., `int(time.time() // 1800)`); value is the story list + fetch timestamp. No external cache library; process-local is sufficient.
- Thread-safety: APScheduler uses asyncio; all sub-agent ticks run on the same event loop. No lock needed if fetch is `async` and awaited idempotently (planner to verify; can use `asyncio.Lock()` on the cache-miss path if needed).

**Cron registration pattern in worker.py:**
- Data-driven: define a `CONTENT_SUB_AGENTS` list of tuples `(module_path, class_name, cron_id, job_lock_id, offset_minutes)` at the top of `worker.py`, then loop to register. Cleaner than 7 explicit `scheduler.add_job(...)` calls; easier to add/remove in the future.
- **JOB_LOCK_IDS allocation:** existing `content_agent=1003` slot is retired (no cron). New sub-agent lock IDs `1010`-`1016` allocated sequentially per the 7 sub-agents. `gold_history_agent=1005` (existing standalone) also retired in favor of the new `gold_history.py` under the sub-agent slot.

**Test file split strategy:**
- One test file per new agent module (`test_breaking_news.py`, `test_threads.py`, etc.). Drafting tests move with the functions (git mv where possible). `test_content_agent.py` shrinks to cover only `fetch_stories()` cache behavior + `review()` gate behavior.
- Rationale: easier to navigate, matches module structure 1:1, better for future per-agent evolution.

**Frontend route prefix:**
- All 7 agent tabs use `/agents/<slug>` route convention. No flat routes (`/breaking-news` etc.). Matches the existing `/agents/*` namespace expected from CLAUDE.md.

**Breaking news event-mode:**
- Out of scope. `breaking_news.py` runs the same 2h cron as the others for this task. Operator can add a faster-cadence event-mode trigger in a follow-up.

**Combined queue removal — cleanup scope:**
- Delete `frontend/src/pages/QueuePage.tsx` if it exists as a separate route. Delete the `/content` route. Update `App.tsx` default redirect to `/agents/breaking-news` (first in priority order) so the app lands somewhere useful on login.

**Worker `max_instances` / concurrency:**
- Follow existing `with_advisory_lock` pattern already in worker.py — each sub-agent gets its own lock ID (1010-1016). Planner confirms that 8 concurrent jobs (7 sub-agents + morning_digest) with per-job advisory locks is safe on the Railway single-worker-process deployment. Research recommends Neon pool bump to `pool_size=15` to accommodate peak concurrency with headroom.

</decisions>

<specifics>
## Specific Ideas

**Extraction targets from `content_agent.py`:**
- `_draft_breaking_news_post` → `content/breaking_news.py`
- `_draft_thread` (or equivalent) → `content/threads.py`
- `_draft_long_form_post` → `content/long_form.py`
- `_draft_quote_post` → `content/quotes.py`
- `_draft_infographic_brief` → `content/infographics.py`
- `_search_video_clips` + `_draft_video_caption` → `content/video_clip.py`
- Plus all per-format helper functions currently inside `content_agent.py`

**Preserved in `content_agent.py` (post-refactor, no cron):**
- News feed ingestion (SerpAPI + RSS) — wrapped in `fetch_stories()` with TTL-30min cache
- Story scoring (recency + quality) — invoked inside `fetch_stories()`
- `classify_format_lightweight` (Haiku format classifier) — exposed as a helper for sub-agents that need it (breaking_news, threads, long_form, quote, infographic all classify off the shared story stream)
- Compliance/gate Haiku filter — exposed as `review(draft)` — called inline by each sub-agent
- **Removed:** `run()` / `_run_pipeline()` orchestrator loop; the INGEST → CLASSIFY → GATE cycle is no longer a scheduled thing. Each sub-agent runs its own pipeline end-to-end.

**Preserved tweepy read-only:**
- `VIDEO_ACCOUNTS` constant moves with `video_clip.py`
- `tweepy.asynchronous.AsyncClient` import moves with `video_clip.py`
- `X_API_BEARER_TOKEN` env stays critical in `worker.py::_validate_env`

**Sub-agent skeleton (all 7 follow this pattern):**
```python
# scheduler/agents/content/<type>.py
from agents import content_agent

async def run_draft_cycle() -> None:
    stories = await content_agent.fetch_stories()           # cached SerpAPI/RSS
    candidates = [s for s in stories if s.type == "<type>"] # type-filter
    for story in candidates:
        draft = await _draft_<type>_post(story)             # Sonnet drafting
        review = await content_agent.review(draft)          # Haiku gate (inline)
        await _write_bundle(story, draft, review)           # single-tx insert
```

**Frontend sidebar copy (final):**
```
Agents
├── Breaking News    → /agents/breaking-news
├── Threads          → /agents/threads
├── Long-form        → /agents/long-form
├── Quotes           → /agents/quotes
├── Infographics     → /agents/infographics
├── Gold Media       → /agents/gold-media
└── Gold History     → /agents/gold-history
```

**Scheduler job list (post-refactor, 8 jobs total):**
1. `morning_digest` (existing, unchanged)
2. `breaking_news` sub-agent cron (2h, offset +0 min, lock 1010)
3. `threads` sub-agent cron (2h, offset +17 min, lock 1011)
4. `long_form` sub-agent cron (2h, offset +34 min, lock 1012)
5. `quotes` sub-agent cron (2h, offset +51 min, lock 1013)
6. `infographics` sub-agent cron (2h, offset +68 min, lock 1014)
7. `video_clip` sub-agent cron (2h, offset +85 min, lock 1015)
8. `gold_history` sub-agent cron (2h, offset +102 min, lock 1016)

**Retired cron jobs:**
- `content_agent` (was id=1003, 3h interval) — module survives as a library, cron removed
- `gold_history_agent` (was id=1005, standalone 2h) — merged into `content/gold_history.py`

</specifics>

<canonical_refs>
## Canonical References

- `scheduler/agents/content_agent.py` — extraction source (~2000 lines); shrinks to review-service-only
- `scheduler/agents/gold_history_agent.py` — folds into new pattern (moves to `content/gold_history.py`)
- `scheduler/worker.py` — cron registration + JOB_LOCK_IDS + `_validate_env`; remove content_agent + gold_history_agent cron; add 7 sub-agent crons
- `scheduler/tests/test_content_agent.py` — test split target
- `backend/app/routers/queue.py` — add `content_type` filter parameter
- `backend/app/models/content_bundle.py` — `content_type` column already supports all 7 values (no migration)
- `frontend/src/App.tsx` — 7 new routes + remove `/content`; default redirect → `/agents/breaking-news`
- `frontend/src/components/layout/Sidebar.tsx` — 7 new `agentItems` entries in priority order
- `frontend/src/pages/PlatformQueuePage.tsx` — adapt for per-agent content_type filter
- `frontend/src/components/settings/AgentRunsTab.tsx` — `AGENT_OPTIONS` gets 7 new entries; removes `content_agent` + `gold_history_agent`
- `CLAUDE.md` — update "single-agent system" narrative → "7 sub-agent system + Content Agent review service"; update scheduled-job count (3 → 8)
- `.planning/quick/260421-eoe-split-content-agent-into-7-sub-agents-or/260421-eoe-RESEARCH.md` — research findings (stagger strategy, lock IDs, pool bump, frontend routing still valid; research_context migration now moot per Phase C)
- `.planning/quick/260420-sn9-full-purge-twitter-agent-trim-senior-to-/260420-sn9-SUMMARY.md` — prior sn9 context (Twitter purge; single-agent description we're now superseding)
- `.planning/STATE.md` — add eoe quick-task row after execution

</canonical_refs>
