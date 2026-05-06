# Phase 4: Prune Cron + Operations Hardening - Context

**Gathered:** 2026-04-27
**Status:** Ready for planning
**Mode:** Smart-discuss (autonomous), small phase, all decisions locked from prior phases

<domain>
## Phase Boundary

Close out v2.0 with operational hardening: register the 30-day prune cron, verify daily_summary telemetry surfaces in the existing /agent-runs UI, and confirm v1.0 sub-agent retirement is dead-code-only (no source files were deleted, only crons were de-registered).

**In scope:**
- New cron job: `daily_summary_prune` registered in `scheduler/worker.py` at 03:00 PT daily (lock id 1018, already reserved in Phase 1)
- Factory function `_make_daily_summary_prune_job(engine)` mirroring the existing `_make_daily_summary_job` pattern
- Prune logic: single SQL DELETE on `daily_summaries` rows where `generated_at < NOW() - INTERVAL '30 days'`
- Wrap prune in advisory lock 1018; emit a structured agent_runs row for observability
- Tests: prune cron registration, prune SQL, advisory-lock behavior, deletion-count telemetry
- Telemetry verification: confirm `daily_summary` agent_runs rows are parseable by the existing PerAgentQueuePage UI (already shipped post-no4)
- Dead-code retirement audit: a code-search-and-document task confirming all 6 v1.0 sub-agents + approval-flow components + Phase B post-to-X route still exist as source files (no deletions in v2.0). Produces a CHECKLIST.md attesting the audit.

**Out of scope:**
- Deleting any v1.0 source files (locked in CONTEXT — dead-code-only retirement)
- Auditing the v1.0.1 archived phase docs (those are immutable history)
- Adding new telemetry fields beyond what Phases 1-3 already wrote
- Schema changes (no migration; prune is pure DELETE)
- Frontend changes (telemetry already surfaces via existing /agents endpoint, no UI work needed)

**Requirements covered (3):** OPS-01, OPS-03, OPS-04

(OPS-02 — lock-id uniqueness assertion — already shipped in Phase 1.)

</domain>

<decisions>
## Implementation Decisions

### Prune Cron Registration

- **Job ID:** `daily_summary_prune`
- **Lock ID:** `1018` (already reserved in Phase 1's `JOB_LOCK_IDS` dict)
- **Schedule:** `CronTrigger(hour=3, minute=0, timezone="America/Los_Angeles")` — 03:00 PT daily. Outside both summary fire times (08:00 + 12:00) so locks never contend.
- **Factory pattern:** `_make_daily_summary_prune_job(engine)` mirrors `_make_daily_summary_job(engine)` — same advisory-lock-then-work-then-finally pattern.
- **No `coalesce`/`max_instances` overrides** — inherit the worker's existing job defaults (max_instances=1, coalesce=True, misfire_grace_time=1800).
- **Registration:** added to `build_scheduler()` directly (NOT in `CONTENT_CRON_AGENTS` since the prune job has different signature — no `run_fn()` shape).

### Prune SQL

```python
result = await session.execute(
    delete(DailySummary).where(
        DailySummary.generated_at < datetime.now(UTC) - timedelta(days=30)
    )
)
deleted_count = result.rowcount
await session.commit()
```

- Single transaction. No batching needed — table max ~60 rows, deletion is trivial.
- Uses Postgres `now()` semantics via Python `datetime.now(UTC)` — both consistent.
- `delete()` is the SQLAlchemy 2.0 statement (not the deprecated `Query.delete()`).
- `result.rowcount` is the number of rows deleted (used for telemetry).

### Telemetry

`agent_runs` row for the prune job:
- `agent_name = "daily_summary_prune"`
- `started_at` / `ended_at` / `status` follow the standard pattern (kqa-era reconcile_stale_runs sweeps this row if process dies mid-prune)
- `notes` JSONB:
  ```json
  {"deleted_count": 3, "cutoff_at": "2026-04-26T10:30:00Z"}
  ```
- `items_found = deleted_count`, `items_queued = 0` (prune produces no items)

### Dead-Code Retirement Audit

A code-search task that produces `.planning/phases/04-prune-cron-operations-hardening/04-RETIREMENT-AUDIT.md`. The audit:

1. Confirms all 6 v1.0 sub-agent source files exist (NOT deleted):
   - `scheduler/agents/content/breaking_news.py`
   - `scheduler/agents/content/threads.py`
   - `scheduler/agents/content/quotes.py`
   - `scheduler/agents/content/infographics.py`
   - `scheduler/agents/content/gold_media.py`
   - `scheduler/agents/content/gold_history.py`
2. Confirms approval-flow frontend components exist (NOT deleted):
   - `frontend/src/components/approval/ContentDetailModal.tsx`
   - `frontend/src/components/approval/ContentSummaryCard.tsx`
   - `frontend/src/components/approval/RejectPanel.tsx`
   - `frontend/src/components/approval/InlineEditor.tsx`
   - `frontend/src/components/approval/DraftTabBar.tsx`
   - `frontend/src/components/approval/PostToXConfirmModal.tsx`
3. Confirms Phase B post-to-X route exists (NOT deleted):
   - `backend/app/routers/post_to_x.py`
   - `backend/app/services/x_poster.py`
4. Confirms NONE of these are wired to the active scheduler or routes:
   - `scheduler/worker.py` does NOT register any of the 6 sub-agent crons (`grep -c "scheduler.add_job(_make_sub_breaking_news_job\|sub_breaking_news\|sub_threads\|sub_quotes\|sub_infographics\|sub_gold_media\|sub_gold_history" scheduler/worker.py` returns 0 for the active `add_job` calls)
   - `frontend/src/App.tsx` does NOT route to `/queue` or `/agents/:slug` (already redirected to `/` in Phase 1's route swap)
5. Produces a markdown checklist with each file path + "exists ✓" / "wired ✗" attestation.

This audit is a Bash-driven verification, not a code change. Output is one markdown file.

### Test Strategy

- **Prune cron registration test:** Add to `scheduler/tests/test_worker.py`. Call `build_scheduler()` (mocked engine), assert `scheduler.get_job("daily_summary_prune")` exists, assert its `trigger` is a `CronTrigger` with `hour=3, minute=0, timezone='America/Los_Angeles'`.
- **Prune SQL test:** Insert 5 fake `daily_summaries` rows with `generated_at` spanning 0d, 15d, 31d, 45d, 90d ago. Call the prune function. Assert exactly 3 rows remain (the 0d, 15d, 31d → wait, 31d > 30d so it gets deleted; correct count is 2: 0d, 15d). Recompute carefully in test.
- **Advisory lock test:** Mock the lock acquisition to return `False` (already-held). Assert prune logs the skip and returns without DELETE.
- **Telemetry test:** Assert `agent_runs` row has correct fields populated post-prune.
- **Idempotent prune:** Running twice in quick succession should produce 0 deletions on the second call (since the 30-day cutoff hasn't moved meaningfully).
- **No regression:** Phases 1-3 functionality intact; 295+ scheduler tests + 119+ backend tests still green.

### Cross-cutting (locked from prior phases)

- Lock ID 1018 already reserved (Phase 1's JOB_LOCK_IDS uniqueness assertion enforces no collision)
- AsyncSessionLocal pattern (post-m51)
- All async, no blocking I/O
- Tests in `scheduler/tests/test_worker.py` (prune cron registration) + new `scheduler/tests/agents/test_daily_summary_prune.py` (prune logic)
- Ruff clean + pytest -x green
- No DB migration
- No new pip packages
- No frontend changes

</decisions>

<code_context>
## Existing Code Insights

### Reusable Assets

- `scheduler/worker.py` — `_make_daily_summary_job(engine)` factory (Phase 1) is the exact pattern to mirror for `_make_daily_summary_prune_job(engine)`.
- `scheduler/worker.py:JOB_LOCK_IDS` already contains `"daily_summary_prune": 1018`. The startup uniqueness assertion (Phase 1) protects against duplicates.
- `scheduler/db.py:AsyncSessionLocal` — same async session helper as Phase 1.
- `scheduler/models/daily_summary.py` — DailySummary ORM model with `generated_at: TIMESTAMPTZ`.
- `scheduler/models/agent_run.py` — telemetry write target (existing pattern from Phase 1).

### Established Patterns

- **Cron registration via factory:** `_make_*_job(engine)` returns an async function that the scheduler calls. The async function: (1) acquires advisory lock, (2) creates agent_runs row, (3) does work, (4) updates agent_runs row, (5) releases lock — all in a try/finally.
- **Reconcile_stale_runs:** orphan sweeper handles process kills mid-prune; no special handling needed.
- **Test pattern:** `scheduler/tests/test_worker.py` already has `test_build_scheduler_registers_daily_summary_and_omits_midday_digest` (Phase 1) — extend with a parallel test for daily_summary_prune.

### Integration Points

- `scheduler/worker.py`: add `_make_daily_summary_prune_job` factory, add `scheduler.add_job(_make_daily_summary_prune_job(engine), trigger=CronTrigger(hour=3, minute=0, timezone="America/Los_Angeles"), id="daily_summary_prune", name="daily_summary_prune", max_instances=1)` in `build_scheduler()`.
- New file: `scheduler/agents/daily_summary_prune.py` (or fold the prune function into `daily_summary.py` — your call). Recommendation: separate file for cleanliness.
- New tests: `scheduler/tests/agents/test_daily_summary_prune.py`.
- New audit doc: `.planning/phases/04-prune-cron-operations-hardening/04-RETIREMENT-AUDIT.md`.

</code_context>

<specifics>
## Specific Ideas

- **Why 03:00 PT?** Quietest hour, no contention with any summary fire (08:00 + 12:00). Also outside the 22:00-06:00 PT Twilio "off hours" if we ever add scheduled WhatsApp.
- **Deletion volume in production:** With 2 fires/day × 30 days = 60 rows max, the rolling prune deletes ~2/day after steady state. Sub-millisecond SQL.
- **30-day cutoff is from `generated_at`, NOT `created_at`:** The summary's authored time, not the row's insertion time. They are usually identical, but the semantics matter.
- **OPS-03 verification path:** Operator opens `/agents/daily_summary` in the dashboard, sees the run history with structured `notes` (post-no4 UI parses `candidates_gold`, `sections_completed`, `whatsapp_sent`, etc.). No code changes — purely a verification step in the audit.

</specifics>

<deferred>
## Deferred Ideas

- **Soft-delete instead of hard-delete** — research PITFALLS.md HIGH-3 mentioned the prune-vs-read race. With a 30-day cutoff and the feed page reading max 60 rows ordered DESC, races are theoretically possible (read fetches a row that gets deleted between SELECT and rendering) but the consequence is purely cosmetic (row vanishes from feed before next refresh). Soft-delete adds complexity without benefit; keep hard-delete. Defer revisiting until evidence of UX issue.
- **Configurable retention** — locked at 30 days. If the user later wants 60 or 90, single constant change in the prune function. Defer to a quick task when needed.
- **Prune metrics dashboard** — the agent_runs row gives us per-day deletion counts via the existing /agent-runs UI. No new dashboard needed.

</deferred>
