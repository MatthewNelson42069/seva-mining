---
phase: 07-weekly-viral-sweeper
plan: 02
subsystem: scheduler
tags: [tweepy, x-api, async, quota-gate, engagement-rank, weekly-sweeper]

# Dependency graph
requires:
  - phase: 07-weekly-viral-sweeper
    provides: rescoped SWEEP-* requirements (X pivot), WeeklySweepCard schema baseline (Plan 01)
provides:
  - "async fetch_top_x_posts(query, max_results=100) -> list[dict] — X API recent-search consumer with quota gate + engagement re-rank"
  - "Per-tweet dict contract: tweet_id, text, author_username, tweet_url, likes, retweets, replies, created_at"
  - "QUOTA_SAFETY_MARGIN=500 module constant (D-08 lock)"
  - "TOP_N=10 module constant (D-07 lock)"
  - "AGENT_NAME='weekly_sweeper' (matches JOB_LOCK_IDS key)"
  - "_engagement_score(metrics) helper — likes + retweets*2 + replies*1.5"
  - "Private _get_config / _set_config_str helpers (gold_media.py parity)"
affects: [07-03, 07-04, 07-05, weekly_sweeper]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "X API consumer pattern: tweepy.asynchronous.AsyncClient + bearer_token + wait_on_rate_limit=True (mirrors gold_media.py)"
    - "Quota coordination via Config(key=twitter_monthly_tweet_count) read-then-write (naive — single-process scheduler)"
    - "Post-fetch engagement re-rank: sort_order=relevancy at API + Python sort by likes + retweets*2 + replies*1.5"
    - "Mock tweepy.asynchronous.AsyncClient via unittest.mock; patch.object for _get_config/_set_config_str"

key-files:
  created:
    - "scheduler/agents/x_ingest.py"
    - "scheduler/tests/test_x_ingest.py"
  modified: []

key-decisions:
  - "Tablename: Config model uses __tablename__='config' (not bot_config) — plan's bot_config naming is descriptive; the canonical model from gold_media.py is reused as-is"
  - "_get_config / _set_config_str redefined locally (not imported from agents.content.gold_media) — keeps the module self-contained per plan guidance"
  - "tweet_fields list shortened vs gold_media.py — no attachments/media expansions needed (weekly sweeper is text-discovery, not video discovery)"
  - "Sort tweets in result list (not response.data) — cleaner for testing, no tweepy object mutation"
  - "Counter persisted via session.commit() inside try block; early-return branches ([]) skip commit"

patterns-established:
  - "TDD test mocking strategy for tweepy: MagicMock for AsyncClient + AsyncMock for search_recent_tweets returning SimpleNamespace response"
  - "_mk_tweet / _mk_user / _mk_response test helpers — reusable across future weekly_sweeper tests"

requirements-completed: [SWEEP-04, SWEEP-05]

# Metrics
duration: 2 min
completed: 2026-05-19
---

# Phase 7 Plan 2: X API Ingest Consumer Summary

**Async fetch_top_x_posts(query, max_results=100) X API consumer with twitter_monthly_tweet_count quota gate and likes + retweets*2 + replies*1.5 engagement re-rank**

## Performance

- **Duration:** 2 min
- **Started:** 2026-05-19T05:07:56Z
- **Completed:** 2026-05-19T05:10:21Z
- **Tasks:** 2
- **Files created:** 2 (171 + 311 lines)

## Accomplishments
- `scheduler/agents/x_ingest.py` — 171-line async X API recent-search consumer mirroring `gold_media.py::_search_gold_media_clips` auth + quota-gate + result-processing shape
- `scheduler/tests/test_x_ingest.py` — 9 pytest-asyncio tests covering all four control-flow branches plus dict-shape, rank-order, and call-args forwarding
- Locked decisions from 07-CONTEXT.md operationalized in code: `sort_order="relevancy"` (D-06), `max_results=100` (D-07), `QUOTA_SAFETY_MARGIN=500` (D-08), `TOP_N=10` (D-07), engagement formula (D-06)
- Zero Reddit dependency leakage (pivot enforcement passing on both module and tests)

## Task Commits

1. **Task 1: Implement fetch_top_x_posts with quota gate + engagement re-rank** — `9ff24de` (feat)
2. **Task 2: pytest coverage for fetch_top_x_posts (4 control-flow branches)** — `f258fd0` (test)

_TDD note: Plan-prescribed ordering was implementation-first (Task 1) then tests (Task 2). Task 2 verified Task 1 via 9 isolated tests with mocked tweepy + mocked Config helpers._

## Files Created/Modified
- `scheduler/agents/x_ingest.py` (CREATED, 171 lines) — public `fetch_top_x_posts` + private `_get_config` / `_set_config_str` / `_engagement_score` + module constants `AGENT_NAME`, `TOP_N`, `QUOTA_SAFETY_MARGIN`
- `scheduler/tests/test_x_ingest.py` (CREATED, 311 lines) — 9 async tests + `_mk_tweet` / `_mk_user` / `_mk_response` factory helpers

## Decisions Made
- **Config table identity:** The Config model uses `__tablename__ = "config"`, not `bot_config` (the plan's reference). The model class is the same one `gold_media.py` queries, so the existing quota counter rows are read transparently. Plan terminology adjusted in code comments to "Config table (bot_config row set)" for clarity.
- **Module-local config helpers:** `_get_config` / `_set_config_str` are redefined verbatim from `gold_media.py:57-72` rather than imported. Trade-off: tiny duplication for module self-containment, which simplifies future testing and avoids tight coupling to the sub-agent module structure.
- **tweet_fields trimmed:** Removed `attachments`/`expansions=media_keys`/`media_fields` from the tweepy call — weekly sweeper is content-text discovery, not video discovery (no `has:videos` filter per plan).

## Function Signature & Constants

```python
# In scheduler/agents/x_ingest.py
AGENT_NAME = "weekly_sweeper"
TOP_N = 10
QUOTA_SAFETY_MARGIN = 500

async def fetch_top_x_posts(query: str, max_results: int = 100) -> list[dict]
```

Engagement formula: `score = likes + retweets*2 + replies*1.5`

## Test Coverage

| Test | Branch covered |
|------|----------------|
| `test_happy_path` | 50 tweets → top 10 ranked desc; counter incremented +50 |
| `test_quota_near_cap` | counter=9600/10000 (delta=400) → []; tweepy NOT called; counter unchanged |
| `test_quota_at_safety_margin` | counter=9500/10000 (delta=500 exact boundary) → proceeds; tweepy called |
| `test_x_api_exception` | `ConnectionError("boom")` → []; counter unchanged |
| `test_empty_response` | `response.data=None` → []; counter unchanged |
| `test_fewer_than_top_n` | 5 tweets → all 5 returned ranked; counter +5 |
| `test_engagement_rank_order` | t3 (replies*1.5=15) ranks above t1/t2 (10 each) |
| `test_dict_shape` | Exact 8-key contract; `tweet_url = https://twitter.com/{user}/status/{id}` |
| `test_query_and_sort_order_forwarded` | tweepy called with query=<input>, sort_order="relevancy", max_results=100 |

**Test count:** 9 (plan minimum was 7); **pass rate:** 9/9 (100%); **runtime:** 0.27s.

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None.

## User Setup Required

None - no external service configuration required. X API bearer token already in Railway env (set up in v1.0 Phase 4-twitter-agent; reused by `gold_media.py` and now by `x_ingest.py`).

## Next Phase Readiness

- `agents.x_ingest.fetch_top_x_posts(query, max_results=100)` ready to be called by `scheduler/agents/weekly_sweeper.py` (07-04) as a black box.
- Returns engagement-ranked top-10 dicts conforming to the contract documented in the module docstring.
- Quota gate and exception handling are internal — caller does not need to wrap.

Ready for 07-03 (running in parallel as Wave 2) and 07-04 (Wave 3, the weekly_sweeper.py orchestration).

## Self-Check: PASSED

- FOUND: scheduler/agents/x_ingest.py (171 lines)
- FOUND: scheduler/tests/test_x_ingest.py (311 lines)
- FOUND: .planning/phases/07-weekly-viral-sweeper/07-02-SUMMARY.md
- FOUND: 9ff24de (Task 1: feat 07-02 fetch_top_x_posts)
- FOUND: f258fd0 (Task 2: test 07-02 pytest coverage)

---
*Phase: 07-weekly-viral-sweeper*
*Completed: 2026-05-19*
