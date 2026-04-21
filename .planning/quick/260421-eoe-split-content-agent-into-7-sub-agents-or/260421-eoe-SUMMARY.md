# Quick Task 260421-eoe — SUMMARY

**Task:** Split monolithic Content Agent into 7 independent sub-agents; Content Agent becomes a cron-less review service (Phase C architecture).

**Mode:** `/gsd:quick --discuss --research --full`
**Date:** 2026-04-21
**Branch:** `quick/260421-eoe-content-agent-split`
**Status:** Verified PASS — ready for merge to main.

---

## Outcome

The monolithic `scheduler/agents/content_agent.py` (~2000 lines) is now a 1040-line review-service module exposing only two public entry points — `fetch_stories()` (shared SerpAPI+RSS ingestion with 30-min in-memory cache) and `review(draft)` (Haiku compliance gate) — plus the `classify_format_lightweight` helper. It no longer registers a cron job.

Seven new sub-agent modules live under `scheduler/agents/content/`, each self-contained within a single tick: fetch via the shared cache → filter to own content_type → draft via Sonnet → call `content_agent.review()` inline → write `content_bundles` row with `compliance_passed` set. All seven run on independent 2h `IntervalTrigger` cron jobs, staggered `[0, 17, 34, 51, 68, 85, 102]` minutes across the 2h window to prevent DB/API contention.

The scheduler now registers **8 jobs total**: 7 sub-agents + the existing `morning_digest` daily cron. The standalone `scheduler/agents/gold_history_agent.py` was deleted; its logic was folded into `scheduler/agents/content/gold_history.py`.

On the frontend, the combined `/content` queue route is gone, replaced by a single dynamic `<Route path="/agents/:slug">` element fed by a `CONTENT_AGENT_TABS` config array. The Sidebar renders the same 7 entries in operator-priority order (Breaking News → Threads → Long-form → Quotes → Infographics → Gold Media → Gold History) and the default redirect lands on `/agents/breaking-news`.

No DB migrations. No new dependencies. No new features — this was functional parity with the pre-split Content Agent, just re-organized for per-agent iteration later.

---

## Architecture — before vs after

### Before (post-sn9)
```
┌─────────────┐   cron 3h   ┌──────────────────────────────────────┐
│ APScheduler │────────────►│ ContentAgent.run()                    │
│             │             │  INGEST → CLASSIFY → DRAFT → GATE →   │
│             │             │  WRITE (one monolith, all 7 types)    │
│             │   cron 2h   ├──────────────────────────────────────┤
│             │────────────►│ gold_history_agent.run()              │
│             │   daily     ├──────────────────────────────────────┤
│             │────────────►│ morning_digest                        │
└─────────────┘             └──────────────────────────────────────┘
```

### After (quick-260421-eoe)
```
┌─────────────┐
│ APScheduler │     ┌───── morning_digest (daily)
│  8 jobs     │─────┼───── sub_breaking_news (2h, +0min, lock 1010)
│             │     ├───── sub_threads      (2h, +17min, lock 1011)
│             │     ├───── sub_long_form    (2h, +34min, lock 1012)
│             │     ├───── sub_quotes       (2h, +51min, lock 1013)
│             │     ├───── sub_infographics (2h, +68min, lock 1014)
│             │     ├───── sub_video_clip   (2h, +85min, lock 1015)
│             │     └───── sub_gold_history (2h, +102min, lock 1016)
└─────────────┘           │
                          │ each sub-agent tick:
                          ▼
                    ┌───────────────────────────────────┐
                    │ 1. content_agent.fetch_stories()  │
                    │    (30-min cache; 5 of 7 use it)  │
                    │ 2. filter to own content_type     │
                    │ 3. draft via Sonnet               │
                    │ 4. content_agent.review()  ◄──────┼── library call
                    │ 5. INSERT content_bundles row     │    (no cron)
                    └───────────────────────────────────┘
```

`content_agent.py` is now imported as a library by each sub-agent; it has no scheduled job of its own.

---

## Commits (on `quick/260421-eoe-content-agent-split`)

| # | SHA | Task | Message |
|---|---|---|---|
| 1 | `2fe94bf` | T01 | test(scheduler): add Wave-0 stubs for 7 content sub-agent tests |
| 2 | `a247cd1` | T02 | refactor(scheduler): shrink content_agent.py to review-service-only module |
| 3 | `762b08b` | T03 | refactor(scheduler): add 7 content sub-agent modules + retire gold_history_agent |
| 4 | `979b69c` | T04 | refactor(scheduler): rewire worker.py to 8-job topology + bump pool_size to 15 |
| 5 | `2e43fd2` | T05 | test(scheduler): update tests for 7-sub-agent split |
| 6 | `f25faec` | T06 | feat(backend): add /queue?content_type= filter + pool_size=15 |
| 7 | `d20f515` | T07 | feat(frontend): per-sub-agent queue route /agents/:slug |
| 8 | `d7613b4` | T08 | feat(frontend): 7-sub-agent Sidebar + AgentRunsTab rewire |
| 9 | `45dcbc6` | T09 | docs(claude): reflect 7-sub-agent architecture |
| 10 | `a8d512e` | T10 | style(scheduler): drop unused patch import in test_gold_history |
| 11 | `047ef1d` | post | chore(scheduler): remove defunct cron config keys from seed script |

Net change: **~2000-line monolith → 1 review-service module + 7 sub-agent modules (~5200 lines total across scheduler + backend + frontend + docs)**.

---

## Validation

All gates green on final Wave-5 sweep **and** re-run by verifier:

| Gate | Result |
|---|---|
| `scheduler` ruff | clean |
| `scheduler` pytest | **74 passed** |
| `backend` ruff | clean |
| `backend` pytest | **69 passed, 5 skipped** (pre-existing skips) |
| `frontend` eslint | clean |
| `frontend` vitest | **61 passed** (9 files) |
| `frontend` npm build | 541 kB → 163 kB gzip, OK |

All 22 goal-backward invariants in `VERIFICATION.md` → **PASS**.

---

## Key design decisions

1. **Cron-less Content Agent (Phase C pivot)** — mid-workflow, the operator pivoted from the original design (Content Agent running a cron that does INGEST + CLASSIFY + GATE) to a pure review-service module. This removed the cross-tick `draft_content IS NULL` handoff pattern, eliminated a 30-min gate latency, and dissolved a proposed `research_context` JSONB migration — sub-agents are now self-contained within a single tick.

2. **Shared fetch with in-memory TTL cache** — `content_agent.fetch_stories()` keys on a 30-min timestamp bucket. First sub-agent tick in a window pays the SerpAPI + RSS cost; the next six reuse the cache. Single Railway worker process = cache is process-local; no distributed invalidation needed.

3. **Stagger via `start_date` offsets, not `jitter`** — `[0, 17, 34, 51, 68, 85, 102]` minutes across the 2h window. Deterministic and log-predictable; every sub-agent's firing time is a clean function of deploy time + offset. Per-sub-agent advisory locks (1010–1016) are defense-in-depth for deploy overlap, not intra-scheduler serialization.

4. **Video clip + gold history skip `fetch_stories()`** — `video_clip.py` uses its own X API read path (`_search_video_clips` via tweepy async); `gold_history.py` has a curated historical-story source. Both still call `review()` inline.

5. **Inline review, not deferred** — sub-agents call `content_agent.review(draft)` synchronously before writing. No drafts ever sit in an ungated state in the DB.

6. **Frontend: single dynamic route + config-driven sidebar** — rather than 7 hard-coded `<Route>` elements and 7 hard-coded sidebar entries, `CONTENT_AGENT_TABS` config drives both. Adding / reordering tabs is a one-line change.

---

## Pre-existing deviations retained (all pre-cleared with verifier)

1. **T02 `_draft_` grep returns 3 matches, not 0** — the surviving matches are legitimate references to `build_draft_item` / `run_draft_cycle`. No `_draft_<type>` drafter functions remain. Intent of the check is satisfied.

2. **Shared `run_text_story_cycle` helper** — pre-split code had one combined `_research_and_draft` function, not 5 separate `_draft_<type>` helpers the plan assumed. Extracted into a shared `agents/content/__init__.py::run_text_story_cycle()` helper with 5 format-specialized Sonnet prompts, preserving functional parity. Net result: 5 text sub-agents delegate through the helper; `video_clip` and `gold_history` call `review()` directly; every persistence path still goes through `review()`.

3. **T06 plan path typo** — PLAN.md said `backend/tests/routers/test_queue.py`; actual file lives at `backend/tests/test_queue.py`. New filter tests were added to the existing file.

4. **T05 env-leak fix** — `@lru_cache` on `config.get_settings()` made market-snapshot tests order-sensitive; centralized `setdefault()`s in `scheduler/tests/conftest.py` fixed the flakiness (commit 2e43fd2).

5. **T07 `/content-review` route removed** — orphan route (no sidebar link, no internal caller). Plan permitted removal; executor confirmed dead and removed the route registration only. `ContentPage.tsx` + test files retained in case the route is re-added later.

6. **Follow-up seed-script cleanup (047ef1d)** — `scheduler/seed_content_data.py` still listed defunct `content_agent_interval_hours` and `gold_history_hour` keys in its default-insert list. Removed + added a DELETE clause in the DB-migration docstring. `max_stories_per_run` + `breaking_window_hours` left intact; they're still read by the shared ingest path via `fetch_stories()`.

---

## Dead code flagged (not removed — follow-up candidates)

- `scheduler/agents/content_agent.py` parameter `breaking_window_hours` in the ingestion path is no longer passed by any sub-agent. Candidate for removal in a cleanup pass if confirmed unused post-deploy.
- `frontend/src/pages/ContentPage.tsx` + its test file are orphaned (no route, no sidebar link). Kept in place but eligible for deletion.
- `scheduler/seed_content_data.py` still lists `content_agent_max_stories_per_run` and `content_agent_breaking_window_hours` — if the two config keys are truly unread post-deploy, these can be dropped in the same cleanup pass as the `breaking_window_hours` parameter.

---

## Canonical references

- Plan: `.planning/quick/260421-eoe-split-content-agent-into-7-sub-agents-or/260421-eoe-PLAN.md`
- Context: `.planning/quick/260421-eoe-split-content-agent-into-7-sub-agents-or/260421-eoe-CONTEXT.md`
- Research: `.planning/quick/260421-eoe-split-content-agent-into-7-sub-agents-or/260421-eoe-RESEARCH.md`
- Verification: `.planning/quick/260421-eoe-split-content-agent-into-7-sub-agents-or/VERIFICATION.md`
