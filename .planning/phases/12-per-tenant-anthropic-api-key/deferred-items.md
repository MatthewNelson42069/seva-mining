# Phase 12 — Deferred Items

Pre-existing issues surfaced during Phase 12 plan-02 execution that are out of
scope per the executor's scope boundary rule. These were verified pre-existing
via `git stash` against `main@c022a2b` (the commit at plan-02 start).

## Ruff F401 — Pre-existing unused imports

These three F401 errors exist in `main` prior to plan-02 changes. They surface
when running `uv run ruff check` against the plan-02 file set but were not
introduced by plan-02 work.

1. **`scheduler/agents/daily_summary.py`** — `agents.juno_relevance.HAIKU_MODEL`
   imported but unused (pre-existing since the Phase 10 Juno funnel landed).
2. **`scheduler/agents/weekly_sweeper.py`** — `sqlalchemy.select` imported but
   unused (pre-existing — the explicit `select(...)` calls were rewritten to
   `scoped_summaries(...)` / `scoped_weekly_sweeps(...)` helpers in v3.0 Phase 9
   but the bare `select` import was left behind).
3. **`scheduler/scripts/uat_voice_calibration.py`** — `_build_juno_world_events_section`
   imported but unused (pre-existing — Phase 10 DEF-10 calibration script
   covers Defence News + Canadian Procurement sections only; World Events
   import is dead).

**Disposition:** Leave as-is for plan-02. Recommend a quick task to clean up
all three in a single commit at next maintenance window — they are F401 only
(no behavioral risk), and removing them is a one-line edit per import.

## RuntimeWarnings — Pre-existing test infrastructure

4 RuntimeWarnings in `scheduler/tests/agents/test_daily_summary_prune.py`
(`coroutine 'AsyncMockMixin._execute_mock_call' was never awaited`) — these
were already noted in 12-01-SUMMARY.md as out-of-scope pre-existing test
infrastructure issues. Not introduced by plan-02.

---

*Logged: 2026-05-20 (plan 12-02 execution)*
