---
phase: 01-gold-news-card-web-feed
verified: 2026-05-06T09:50:00Z
status: human_needed
score: 19/19 must-haves verified
human_verification:
  - test: "Confirm WhatsApp teaser and failure-alert arrive on device after first cron fire"
    expected: "Within minutes of 08:00 PT cron fire, receive a WhatsApp message with format '📊 Summary 08:00 PT: [lead sentence]. Read full → https://seva-mining-smm.vercel.app'"
    why_human: "WHATSAPP_DELIVERY_ENABLED=false in prod until manually flipped; Twilio sandbox requires opt-in session; cannot automate against production Twilio from local env"
  - test: "Open https://seva-mining-smm.vercel.app in browser — verify SummaryFeedPage renders at /"
    expected: "Shows either the empty-state 'Waiting for first summary. Next fire at HH:MM PT.' or populated summary cards after first cron fire; no stale /queue or approval-queue page visible"
    why_human: "Visual rendering, auth gate, and production data flow require browser + live session"
  - test: "After first cron fire, verify a card renders with correct Gold News markdown content (lead + 3-5 bullets with source citations)"
    expected: "Card title 'Summary as of 08:00 PT — May N', Gold News section contains a 1-sentence lead followed by bullet points with (Source Name) inline citations; no raw markdown characters visible"
    why_human: "Markdown rendering quality and Sonnet output structure require visual inspection; rehype-sanitize XSS behaviour confirmed by automated tests only on synthetic input"
---

# Phase 1: Gold News Card + Web Feed Verification Report

**Phase Goal:** Operator can read a gold-news summary card in a browser and receive a WhatsApp teaser within minutes of the 08:00 PT cron firing; Ontario sections render as stubs.
**Verified:** 2026-05-06T09:50:00Z
**Status:** human_needed
**Re-verification:** No — initial verification

---

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | Cron fires at 08:00 PT and 12:00 PT via APScheduler CronTrigger | VERIFIED | `worker.py:418` `CronTrigger(hour="8,12", minute=0, timezone="America/Los_Angeles")` registered as `daily_summary`; `test_daily_summary_trigger_fires_at_0800_and_1200_la` PASSED |
| 2 | Advisory lock 1017 prevents duplicate daily_summary fires | VERIFIED | `JOB_LOCK_IDS["daily_summary"] = 1017` at `worker.py:115`; `with_advisory_lock()` wraps call; test `test_daily_summary_lock_id_is_1017` PASSED |
| 3 | Idempotency guard inside run_daily_summary() prevents double-write within 30-min window | VERIFIED | `daily_summary.py:92-102` queries `DailySummary.status.in_(["running","completed"])` within `IDEMPOTENCY_WINDOW_MIN=30` cutoff before any write; test `test_idempotency_skip_*` in test_daily_summary.py PASSED |
| 4 | Gold News section produced from fetch_stories() + Sonnet (score >= 6.0, top 5) | VERIFIED | `daily_summary.py:122-124` applies `score >= GOLD_SCORE_FLOOR(6.0)` + `top[:GOLD_TOP_N(5)]`; `_build_gold_news_section()` calls `fetch_stories()` (shared cache); tests pass |
| 5 | Gold News markdown has 1-sentence lead + 3-5 bullets with source citations | VERIFIED | `GOLD_NEWS_SYSTEM_PROMPT` at `daily_summary.py:53-74` mandates exact structure; MOD-5 grounding (published_at injected); prompt structure enforced in test |
| 6 | Empty state renders "No major moves in gold today — prices ranging $X–$Y." | VERIFIED | `_gold_empty_state()` at `daily_summary.py:172-187` pulls from `fetch_market_snapshot()`; fallback constant defined; test_daily_summary passes |
| 7 | SummaryFeedPage renders at `/` showing summary cards | VERIFIED | `App.tsx:17` `<Route path="/" element={<SummaryFeedPage />} />`; `SummaryFeedPage.tsx` calls `useSummaries(60)` and maps to `<SummaryCard>`; 5 SummaryFeedPage tests PASSED |
| 8 | /queue and /agents/:slug redirect to / | VERIFIED | `App.tsx:20-21` both routes use `<Navigate to="/" replace />`; confirmed in App.tsx file |
| 9 | /login, /digest, /settings routes preserved | VERIFIED | App.tsx lines 13, 24-25; DigestPage uses `/digest` (internal date state, no param); routes intact |
| 10 | react-markdown ^10.1.0 + rehype-sanitize ^6.0.0 installed; no dangerouslySetInnerHTML | VERIFIED | `package.json`: `"react-markdown": "^10.1.0"`, `"rehype-sanitize": "^6.0.0"`; zero `dangerouslySetInnerHTML` occurrences in frontend/src; 3 XSS tests (script/iframe/javascript:) PASSED |
| 11 | WhatsApp teaser < 400 chars asserted at write time | VERIFIED | `whatsapp.py:246` `assert len(teaser) < SUMMARY_TEASER_MAX_CHARS`; `SUMMARY_TEASER_MAX_CHARS=400`; budget math accounts for prefix/suffix |
| 12 | WhatsApp failure alert is isolated in independent try/except | VERIFIED | `deliver_summary_failure_alert()` at `whatsapp.py:320-354` wraps entire body in `try/except Exception` that never re-raises (MOD-6); `deliver_summary_failure_alert` called from `daily_summary.py:370` in outer `except` block |
| 13 | Failure alert always sends regardless of WHATSAPP_DELIVERY_ENABLED | VERIFIED | `deliver_summary_failure_alert()` has NO check of `settings.whatsapp_delivery_enabled`; only `deliver_summary_teaser()` is gated |
| 14 | GET /summaries is auth-gated and returns SummaryFeedResponse | VERIFIED | `summaries.py:18-22` `APIRouter(dependencies=[Depends(get_current_user)])`; 401 test PASSED; endpoint registered in `main.py:63` |
| 15 | Migration 0010 is hand-written, chains from 0009, creates daily_summaries with correct schema | VERIFIED | `0010_add_daily_summaries.py`: `revision="0010"`, `down_revision="0009"`, `op.create_table`, `ck_daily_summaries_status IN ('completed','failed','partial')`, `ix_daily_summaries_generated_at`, `ondelete="SET NULL"`, no autogenerate/enum DDL |
| 16 | midday_digest add_job() removed from build_scheduler() (CRIT-1) | VERIFIED | `worker.py:407-411` explicit comment confirms removal; grep for `midday_digest.*add_job` returns zero results in `build_scheduler()`; test `test_build_scheduler_registers_daily_summary_and_omits_midday_digest` PASSED |
| 17 | Lock-ID uniqueness assertion at module scope (CRIT-2/OPS-02) | VERIFIED | `worker.py:122-124` `assert len(set(JOB_LOCK_IDS.values())) == len(JOB_LOCK_IDS)` runs at import time; test `test_lock_ids_unique_after_v2_additions` PASSED |
| 18 | Ontario sections render as stubs (not errors) | VERIFIED | `_build_ontario_law_section()` returns `ONTARIO_LAW_STUB_MD`; `_build_ontario_stats_section()` returns `ONTARIO_STATS_STUB_MD`; both always return non-None strings so `sections_completed` always gets `"ontario_law"` and `"ontario_stats"` appended |
| 19 | v1.0 sub-agent files preserved intact (brownfield dead-code-only retirement) | VERIFIED | All 6 files present: `content/breaking_news.py`, `content/threads.py`, `content/quotes.py`, `content/infographics.py`, `content/gold_media.py`, `content/gold_history.py`; approval-flow components in `frontend/src/components/approval/` intact |

**Score:** 19/19 truths verified

---

## Critical Pitfall Verification

| Pitfall | Check | Status | Evidence |
|---------|-------|--------|----------|
| CRIT-1 | midday_digest `scheduler.add_job()` removed from `build_scheduler()` | PASSED | No `add_job` call referencing `midday_digest` in `build_scheduler()` body; factory function retained as dead code per CONTEXT |
| CRIT-2 | `assert len(set(JOB_LOCK_IDS.values())) == len(JOB_LOCK_IDS)` at module scope | PASSED | `worker.py:122` — runs at import time, process refuses to start on duplicate |
| CRIT-3 | Idempotency guard queries `status IN ('running','completed')` within 30-min window | PASSED | `daily_summary.py:98` `DailySummary.status.in_(["running","completed"])` + `generated_at >= cutoff` (cutoff = now - 30 min) |
| CRIT-4 | `fetch_stories()` reused via shared `_STORIES_CACHE` (no separate cache key) | PASSED | `daily_summary.py:114` calls `fetch_stories()` directly; `content_agent.py:1028` `_STORIES_CACHE` keyed on `_cache_bucket()` (30-min bucket); same function, same cache shared with sub-agents |

---

## Lock ID Verification

| Job | Lock ID | Status |
|-----|---------|--------|
| daily_summary | 1017 | VERIFIED — `worker.py:115` |
| daily_summary_prune | 1018 | VERIFIED — `worker.py:116` |
| midday_digest (dead code) | 1005 | PRESENT as dead code per CONTEXT — intentional |

---

## Required Artifacts

| Artifact | Status | Details |
|----------|--------|---------|
| `backend/alembic/versions/0010_add_daily_summaries.py` | VERIFIED | Hand-written, revision=0010, down_revision=0009, 11 columns, CHECK constraint, index, FK ON DELETE SET NULL, no autogenerate/enum DDL |
| `backend/app/models/daily_summary.py` | VERIFIED | DailySummary class, `__tablename__="daily_summaries"`, 11 columns, exported in `__init__.py` |
| `scheduler/models/daily_summary.py` | VERIFIED | Byte-for-byte parity with backend model (differs only in Base import path); exported in `__init__.py` |
| `backend/app/schemas/daily_summary.py` | VERIFIED | RawSources, GoldNewsSource, OntarioLawState, OntarioStatsState, SummaryCardResponse, SummaryFeedResponse all present; `raw_sources_jsonb` absent from SummaryCardResponse |
| `scheduler/tests/test_daily_summary_model.py` | VERIFIED | 12 parity tests (tablename + 11 hasattr); all pass |
| `backend/tests/test_daily_summary_schema.py` | VERIFIED | 7 schema tests including RawSources rejection, score bounds, round-trip, raw_sources_jsonb omission; all pass |
| `scheduler/agents/daily_summary.py` | VERIFIED | `run_daily_summary()` with CRIT-3 idempotency, GOLD-01/02/03, SUM-04/05, WHA-01, MOD-6 |
| `scheduler/tests/agents/test_daily_summary.py` | VERIFIED | 26 tests; all pass within 237-test scheduler suite |
| `scheduler/worker.py` | VERIFIED | daily_summary registered, midday_digest de-registered, lock IDs 1017/1018 in JOB_LOCK_IDS, OPS-02 assertion at line 122 |
| `scheduler/tests/test_worker.py` | VERIFIED | 7 new worker tests (lock IDs, daily_summary registration, trigger times, midday_digest omission); all pass |
| `scheduler/services/whatsapp.py` | VERIFIED | build_summary_teaser, build_summary_failure_alert, deliver_summary_teaser, deliver_summary_failure_alert; <400 char assertion present; failure alert isolated try/except |
| `scheduler/config.py` | VERIFIED | `whatsapp_delivery_enabled: bool = False`, `feed_base_url: str` declared |
| `backend/app/config.py` | VERIFIED | `whatsapp_delivery_enabled: bool = False`, `feed_base_url: str` declared (parity with scheduler) |
| `backend/app/routers/summaries.py` | VERIFIED | `GET /summaries`, router-level auth, limit(1..120, default 60), DESC order, SummaryFeedResponse |
| `backend/app/main.py` | VERIFIED | `summaries_router` imported and registered |
| `frontend/src/api/summaries.ts` | VERIFIED | SummaryCard, SummaryFeedResponse types; getSummaries(); useSummaries() with refetchInterval=5min, refetchOnWindowFocus=false |
| `frontend/src/components/summary/SectionBlock.tsx` | VERIFIED | ReactMarkdown + rehypeSanitize; no dangerouslySetInnerHTML |
| `frontend/src/components/summary/SummaryCard.tsx` | VERIFIED | Title format, conditional badge (hidden on completed, amber on partial, red on failed), 3 SectionBlocks |
| `frontend/src/pages/SummaryFeedPage.tsx` | VERIFIED | useSummaries(60); loading/error/empty/populated states; empty state shows next cron fire time |
| `frontend/src/App.tsx` | VERIFIED | / → SummaryFeedPage; /queue + /agents/:slug → Navigate to /; /login, /digest, /settings preserved |
| `frontend/package.json` | VERIFIED | react-markdown@^10.1.0, rehype-sanitize@^6.0.0 in dependencies |

---

## Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `worker.py:build_scheduler()` | `agents/daily_summary:run_daily_summary()` | `_make_daily_summary_job()` lazy import inside job closure | WIRED | `worker.py:300` `from agents.daily_summary import run_daily_summary` inside async def |
| `daily_summary.py` | `content_agent:fetch_stories()` | direct import at `daily_summary.py:30` | WIRED | `from agents.content_agent import fetch_stories`; called at line 114 |
| `daily_summary.py` | `services/whatsapp:deliver_summary_teaser`, `deliver_summary_failure_alert` | imports at lines 36-39 | WIRED | Both helpers called in `run_daily_summary()` |
| `frontend/src/api/summaries.ts:useSummaries()` | `GET /summaries` | `apiFetch('/summaries?limit=...')` | WIRED | `summaries.ts:24` |
| `SummaryFeedPage.tsx` | `SummaryCard.tsx` | import + JSX map | WIRED | `SummaryFeedPage.tsx:71-73` |
| `SummaryCard.tsx` | `SectionBlock.tsx` | import + 3× JSX | WIRED | `SummaryCard.tsx:61-75` |
| `SectionBlock.tsx` | `rehype-sanitize` | rehypePlugins prop | WIRED | `SectionBlock.tsx:33` |
| `backend/app/main.py` | `backend/app/routers/summaries.py` | `app.include_router(summaries_router)` | WIRED | `main.py:63` |
| `scheduler/config.py` | `whatsapp_delivery_enabled + feed_base_url` | `get_settings()` called in `deliver_summary_teaser()` | WIRED | `whatsapp.py:303` |

---

## Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
|----------|---------------|--------|--------------------|--------|
| `SummaryFeedPage.tsx` | `summaries` | `useSummaries(60)` → `GET /summaries` → `DailySummary` ORM → `daily_summaries` table | Yes — DB query `select(DailySummary).order_by(generated_at.desc()).limit(limit)` | FLOWING |
| `SummaryCard.tsx` | `summary.gold_news_md` | passed as prop from SummaryFeedPage; populated by `run_daily_summary()` + Sonnet | Yes — Sonnet response or GOLD-03 empty-state string | FLOWING |
| `run_daily_summary()` | `gold_news_md` | `_build_gold_news_section()` → `fetch_stories()` + `AsyncAnthropic.messages.create()` | Yes — real SerpAPI+RSS fetch then Sonnet call | FLOWING |

Note: SummaryFeedPage will show empty-state on first load because `daily_summaries` table is empty until the first cron fire. This is correct by design (FEED-01: "max 60 rows", no pre-seeded data).

---

## Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| Scheduler module imports without error (OPS-02 assertion runs) | `cd scheduler && python -c "import worker; print('OK')"` | Skipped — requires live DB connection (DATABASE_URL); assertion confirmed by test `test_lock_ids_unique_after_v2_additions` (PASSED) | SKIP |
| Ruff lint — scheduler | `uv run ruff check .` | `All checks passed!` | PASS |
| Ruff lint — backend | `uv run ruff check .` | `All checks passed!` | PASS |
| Scheduler test suite | `uv run pytest -x` | 237 passed, 63 warnings (0 failures) | PASS |
| Backend test suite | `uv run pytest -x` | 106 passed, 5 skipped, 15 warnings (0 failures) | PASS |
| Frontend test suite | `npm test` | 81 passed, 13 files (0 failures) | PASS |

---

## Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|-------------|-------------|--------|----------|
| SUM-01 | 01-05 | daily_summary cron at 08:00 PT + 12:00 PT | SATISFIED | `worker.py:418` CronTrigger(hour="8,12"); test PASSED |
| SUM-02 | 01-05 | Advisory lock 1017 prevents concurrent duplicate fires | SATISFIED | `JOB_LOCK_IDS["daily_summary"]=1017`; `with_advisory_lock()` wrap |
| SUM-03 | 01-05 | Idempotency guard — skip if running/completed row in 30-min window | SATISFIED | `_idempotency_skip()` at `daily_summary.py:92` |
| SUM-04 | 01-05 | agent_runs notes with 6-key telemetry JSON | SATISFIED | `daily_summary.py:379-385` writes `{candidates_gold, candidates_law, candidates_stats, sections_completed, sections_failed, whatsapp_sent}` |
| SUM-05 | 01-01, 01-05 | status = completed/partial/failed based on section success count | SATISFIED | `daily_summary.py:293-299` maps 0 failed→completed, 1-2→partial, 3→failed |
| SUM-06 | 01-05 | midday_digest add_job() removed from build_scheduler() in same commit | SATISFIED | CRIT-1 confirmed; test `test_build_scheduler_registers_daily_summary_and_omits_midday_digest` PASSED |
| GOLD-01 | 01-05 | fetch_stories() + score >= 6.0, top 5 | SATISFIED | `daily_summary.py:122-124` |
| GOLD-02 | 01-05 | 1-sentence lead + 3-5 bullets, each ≤ 25 words + (Source Name) | SATISFIED | GOLD_NEWS_SYSTEM_PROMPT enforces structure; Sonnet produces markdown |
| GOLD-03 | 01-05 | Empty-state "No major moves in gold today — prices ranging $X–$Y." | SATISFIED | `_gold_empty_state()` with market_snapshot fallback |
| FEED-01 | 01-06 | Summary cards readable at `/`, newest first, max 60 rows | SATISFIED | `SummaryFeedPage.tsx`; `GET /summaries` limit=60 default DESC |
| FEED-02 | 01-06 | Card title "Summary as of {time PT}", 3 SectionBlocks, status badge | SATISFIED | `SummaryCard.tsx:39-78`; SummaryCard tests PASSED |
| FEED-03 | 01-06 | react-markdown + rehype-sanitize; no dangerouslySetInnerHTML | SATISFIED | `SectionBlock.tsx:33`; XSS tests PASSED; zero dangerouslySetInnerHTML hits |
| FEED-04 | 01-06 | /queue + /agents/:slug redirect to / | SATISFIED | `App.tsx:20-21` |
| FEED-05 | 01-04 | GET /summaries auth-gated via Depends(get_current_user) | SATISFIED | `summaries.py:18-22`; 401 test PASSED |
| FEED-06 | 01-02 | TanStack Query refetchInterval = 5 min; refetchOnWindowFocus = false | SATISFIED | `summaries.ts:36-37`; Vitest tests for hook behaviour PASSED |
| WHA-01 | 01-03, 01-05 | WhatsApp teaser < 400 chars sent on successful fire | SATISFIED | `deliver_summary_teaser()` + `build_summary_teaser()` + assert; gated by WHATSAPP_DELIVERY_ENABLED |
| WHA-02 | 01-03, 01-05 | Failure-alert in isolated try/except; always attempts send | SATISFIED | `deliver_summary_failure_alert()` never re-raises; no gate check |
| WHA-03 | 01-03 | len(teaser) < 400 asserted at write time | SATISFIED | `whatsapp.py:246` assert; also in `build_summary_failure_alert()` |
| OPS-02 | 01-05 | assert len(set(JOB_LOCK_IDS.values())) == len(JOB_LOCK_IDS) at module import | SATISFIED | `worker.py:122-124` |

**All 19 requirements SATISFIED.**

---

## Deviation Note: /digest vs /digest/:date Route

The CONTEXT.md spec text (`01-CONTEXT.md:122`) references `/digest/:date` as a route to preserve. The actual pre-existing route is `/digest` (DigestPage manages date navigation via internal component state, not URL params). This was the pre-phase shape (`git show 704d7b3:frontend/src/App.tsx` confirms `/digest`). Plan 06 SUMMARY (`01-06-SUMMARY.md:74,103`) correctly documents `/digest` as preserved. The CONTEXT.md reference to `/digest/:date` was a minor documentation inaccuracy — the actual behaviour is correct and the route is intact.

---

## Anti-Patterns Found

| File | Pattern | Severity | Assessment |
|------|---------|----------|------------|
| `daily_summary.py:80-81` | `ONTARIO_LAW_STUB_MD = "(stub) Ontario law section..."` | INFO | Intentional Phase 1 stub per CONTEXT; stubs return non-None strings so sections_completed always includes them; no production data flow gap |
| `backend/app/models/daily_summary.py:318` | `default=datetime.utcnow` (deprecated) | INFO | DeprecationWarning also present in existing models; non-blocking; utcnow is not removed yet in Python 3.12 |

No blocker or warning-level anti-patterns. Ontario stubs are the documented Phase 1 scope (Phase 2/3 will replace `_build_ontario_law_section()` and `_build_ontario_stats_section()`).

---

## Human Verification Required

### 1. WhatsApp Delivery End-to-End

**Test:** Wait for (or manually trigger by setting system clock or directly calling `run_daily_summary()` in a staging environment) the 08:00 PT cron fire with `WHATSAPP_DELIVERY_ENABLED=true` and valid Twilio credentials set.
**Expected:** Receive a WhatsApp message of format `📊 Summary 08:00 PT: [1-sentence lead]. Read full → https://seva-mining-smm.vercel.app` with total length under 400 characters. Separately, if the run fails, receive `⚠️ Summary 08:00 PT FAILED: section(s) [names]. agent_run_id: [8 chars]`.
**Why human:** `WHATSAPP_DELIVERY_ENABLED` defaults to `false`. Twilio sandbox requires an active opt-in session. Cannot automate against production Twilio from CI.

### 2. Browser Feed Rendering After First Cron Fire

**Test:** Open the Vercel frontend at `/` in a browser, log in, wait for or observe the first cron fire.
**Expected:** SummaryFeedPage renders a card titled "Summary as of 08:00 PT — [date]" with a real Gold News section (lead sentence + bullet points) and two Ontario stub sections. Status badge absent (status=completed expected if gold news succeeds).
**Why human:** Visual rendering of markdown content (font, spacing, bullet styles), card layout, badge colour, and production data flow require browser + live session. The rehype-sanitize behaviour on real Sonnet markdown output (not just test fixtures) needs visual confirmation.

### 3. Confirm /digest and /settings Routes Still Functional

**Test:** While logged in, navigate to `/digest` and `/settings`.
**Expected:** DigestPage loads with prev/next date navigation intact; SettingsPage loads with scoring, keywords, schedule tabs intact.
**Why human:** Route preservation is verified in code, but end-to-end browser navigation (including auth guard pass-through) needs confirmation after the App.tsx route swap.

---

## Gaps Summary

No gaps. All 19 requirements are satisfied by the actual codebase (not just SUMMARY claims). All test gates pass clean. The 3 human verification items relate to production delivery (WhatsApp, Vercel rendering) and cannot be automated — they are not code gaps.

---

_Verified: 2026-05-06T09:50:00Z_
_Verifier: Claude (gsd-verifier)_
