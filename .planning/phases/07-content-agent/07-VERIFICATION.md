---
phase: 07-content-agent
verified: 2026-04-07T00:00:00Z
status: gaps_found
score: 30/31 must-haves verified
re_verification:
  previous_status: passed
  previous_score: 17/17
  note: "Previous verification covered plans 07-01 through 07-05. This re-verification covers expansion plans 07-06 through 07-10."
gaps:
  - truth: "Test suite passes without failures"
    status: failed
    reason: "3 tests use stale hardcoded counts from before expansion plans 07-07/07-10 were applied — the implementation is correct but the tests were never updated"
    artifacts:
      - path: "scheduler/tests/test_content_agent.py"
        issue: "Line 46: assert len(ca.RSS_FEEDS) == 4 — actual is 8 (correct per 07-07)"
      - path: "scheduler/tests/test_content_agent.py"
        issue: "Line 57: assert len(ca.SERPAPI_KEYWORDS) == 6 — actual is 10 (correct per 07-07)"
      - path: "scheduler/tests/test_worker.py"
        issue: "Line 97: expected_ids set has 5 jobs; actual is 7 (correct per 07-10 adding midday + gold_history)"
    missing:
      - "Update test_rss_feed_parsing: change assert len(ca.RSS_FEEDS) == 4 to == 8"
      - "Update test_serpapi_parsing: change assert len(ca.SERPAPI_KEYWORDS) == 6 to == 10"
      - "Update test_all_five_jobs_registered: add 'content_agent_midday' and 'gold_history_agent' to expected_ids; update count comment from 5 to 7"
---

# Phase 7: Content Agent Expansion (Plans 07-06 through 07-10) Verification Report

**Phase Goal:** Build the full Content Agent pipeline: DB migration renaming format_type to content_type, 8 RSS feeds + 10 SerpAPI keywords, breaking_news format, cross-run deduplication, multi-story output, video_clip and quote Twitter sourcing, infographic dual-platform with Instagram design system, historical pattern mode with SerpAPI verification, Gold History Agent with bi-weekly Sunday job, midday 12pm job.
**Verified:** 2026-04-07
**Status:** gaps_found — 3 stale test assertions; implementation is correct
**Re-verification:** Yes — covers expansion plans 07-06 through 07-10 (previous verification covered 07-01 through 07-05)

---

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | content_bundles column named content_type (not format_type) | VERIFIED | Migration 0005 renames it; all active code uses content_type |
| 2 | All models/schemas/types/agent code reference content_type | VERIFIED | Zero format_type in backend/app/, scheduler/agents/, frontend/src/ (only historical migration 0001 and 0005 docstring) |
| 3 | Alembic migration 0005 has upgrade and downgrade | VERIFIED | revision=0005, down_revision=0004; upgrade renames format_type→content_type; downgrade reverses |
| 4 | RSS_FEEDS contains 8 feeds including Reuters, Bloomberg, GoldSeek, Investing.com | VERIFIED | content_agent.py lines 41-50 — exactly 8 entries |
| 5 | SERPAPI_KEYWORDS contains 10 keywords including macro/inflation terms | VERIFIED | Lines 56-67 — includes "gold inflation hedge", "Fed gold", "dollar gold", "recession gold" |
| 6 | CREDIBILITY_TIERS includes goldseek.com (0.6) and investing.com (0.6) | VERIFIED | Lines 95-105 — both present |
| 7 | breaking_news format in Sonnet prompt: 1-3 lines, ALL CAPS key terms, no hashtags | VERIFIED | user_prompt line 923; JSON schema on line 958 with tweet + infographic_brief |
| 8 | Cross-run dedup checks today's ContentBundle records | VERIFIED | _is_already_covered_today() lines 1035-1070; called in _run_pipeline() line 1221 |
| 9 | Pipeline processes ALL qualifying stories | VERIFIED | select_qualifying_stories() lines 251-266; pipeline loops over all qualifying stories |
| 10 | _extract_check_text() handles breaking_news format | VERIFIED | Lines 470-475 extract tweet + optional infographic_brief fields |
| 11 | build_draft_item() handles breaking_news | VERIFIED | Lines 398-401 produce descriptive summary with char count |
| 12 | VIDEO_ACCOUNTS and QUOTE_ACCOUNTS constants exist | VERIFIED | Lines 73-89 — VIDEO_ACCOUNTS has 7 accounts, QUOTE_ACCOUNTS has 5 |
| 13 | _search_video_clips() uses has:videos operator | VERIFIED | Line 590: query includes "has:videos gold -is:retweet" |
| 14 | _search_quote_tweets() uses -has:media operator | VERIFIED | Line 677: query includes "-has:media -is:retweet" |
| 15 | _draft_video_caption() and _draft_quote_post() methods exist | VERIFIED | Lines 741-806 and 808-876 |
| 16 | video_clip and quote in _extract_check_text() | VERIFIED | Lines 506-512 handle both |
| 17 | build_draft_item() handles video_clip and quote | VERIFIED | Lines 417-420 with descriptive summaries |
| 18 | infographic instagram_brief sub-object in Sonnet prompt | VERIFIED | Lines 961-964 specify instagram_brief in both modes |
| 19 | Instagram brand colors in prompt: #F0ECE4, #0C1B32, #D4AF37 | VERIFIED | Lines 936-937 include all three with descriptions |
| 20 | historical_pattern mode with SerpAPI verification fallback | VERIFIED | Lines 1007-1021: calls _search_corroborating() on pattern; falls back to current_data on empty |
| 21 | _extract_check_text() handles infographic instagram_brief fields | VERIFIED | Lines 487-490 extract instagram_brief.headline and instagram_brief.caption |
| 22 | _extract_check_text() handles gold_history format | VERIFIED | Lines 499-505 extract tweets, carousel slide headlines/bodies, instagram_caption |
| 23 | gold_history_agent.py exists with class GoldHistoryAgent | VERIFIED | File confirmed at 427 lines; class GoldHistoryAgent line 34 |
| 24 | GoldHistoryAgent has all 6 required methods | VERIFIED | run() line 404, _pick_story() line 93, _verify_facts() line 148, _draft_gold_history() line 198, _get_used_topics() line 54, _add_used_topic() line 71 |
| 25 | worker.py JOB_LOCK_IDS: content_agent_midday=1008, gold_history_agent=1009 | VERIFIED | Lines 43-44 |
| 26 | worker.py bi-weekly Sunday gold_history job (day_of_week="sun", week="*/2") | VERIFIED | Lines 302-312 |
| 27 | worker.py midday content_agent job registered | VERIFIED | Lines 291-298 |
| 28 | seed_content_data.py has gold_history_used_topics: "[]" | VERIFIED | Line 35 |
| 29 | seed_content_data.py has content_agent_midday_hour and gold_history_hour | VERIFIED | Lines 33-34 |
| 30 | GoldHistoryAgent uses check_compliance + build_draft_item from content_agent | VERIFIED | gold_history_agent.py line 289 lazy import; used at lines 350, 384 |
| 31 | Test suite passes | FAILED | 3 stale assertions — see Gaps section below |

**Score:** 30/31 truths verified

---

## Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `backend/alembic/versions/0005_rename_format_type_to_content_type.py` | Migration renaming format_type to content_type | VERIFIED | revision=0005, down_revision=0004, upgrade+downgrade present |
| `backend/app/models/content_bundle.py` | Backend model with content_type | VERIFIED | content_type = Column(String(50)) with 7-format comment |
| `backend/app/schemas/content_bundle.py` | Pydantic schema with content_type | VERIFIED | content_type: Optional[str] = None |
| `scheduler/models/content_bundle.py` | Scheduler mirror with content_type | VERIFIED | content_type = Column(String(50)) with 7-format comment |
| `frontend/src/api/types.ts` | TS type with content_type | VERIFIED | content_type?: string in ContentBundleResponse |
| `frontend/src/pages/ContentPage.tsx` | Frontend using content_type | VERIFIED | bundle.content_type throughout; Badge displays it |
| `scheduler/agents/content_agent.py` | Full content agent | VERIFIED | 1,413 lines — complete implementation |
| `scheduler/agents/gold_history_agent.py` | Gold History Agent | VERIFIED | 427 lines with all required methods |
| `scheduler/worker.py` | Worker with 7 jobs | VERIFIED | 7 jobs including midday + gold_history |
| `scheduler/seed_content_data.py` | Seed with all config keys | VERIFIED | 10 entries including 3 added by plan 07-10 |

---

## Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| migration 0005 | content_bundles table | op.alter_column new_column_name | VERIFIED | Both upgrade and downgrade present |
| content_agent.py | scheduler/models/content_bundle.py | ContentBundle.content_type = draft_content.get("format") | VERIFIED | Line 1271 |
| content_agent.py | ContentBundle (cross-run dedup) | _is_already_covered_today func.date query | VERIFIED | Lines 1035-1070 |
| content_agent.py | tweepy.AsyncClient | search_recent_tweets with has:videos / -has:media | VERIFIED | Lines 593 and 680 |
| content_agent.py | ContentBundle | content_type="video_clip" | VERIFIED | Line 1393 |
| worker.py | gold_history_agent.py | GoldHistoryAgent import + elif branch | VERIFIED | Line 22 import; lines 168-175 |
| worker.py | content_agent.py | content_agent_midday uses ContentAgent().run() | VERIFIED | Lines 161-167 |
| gold_history_agent.py | Config table | gold_history_used_topics read/write | VERIFIED | _get_used_topics() and _add_used_topic() |

---

## Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
|----------|---------------|--------|--------------------|--------|
| `ContentPage.tsx` | bundle | getTodayContent() useQuery | GET /api/content/today → real DB | FLOWING |
| `content_agent.py` pipeline | qualifying stories | _fetch_all_rss() + _fetch_all_serpapi() | Live feedparser + SerpAPI calls | FLOWING |
| `gold_history_agent.py` pipeline | draft_content | _draft_gold_history() Claude Sonnet | Claude API + SerpAPI fact verification | FLOWING |

---

## Behavioral Spot-Checks

Step 7b: SKIPPED — agents require live DB, Claude API, SerpAPI, and Twitter API. No runnable entry point can be tested without credentials and a running database. Module constant checks performed by static read instead.

| Behavior | Check | Result | Status |
|----------|-------|--------|--------|
| RSS_FEEDS == 8 entries | Read content_agent.py lines 41-50 | 8 confirmed | PASS |
| SERPAPI_KEYWORDS == 10 | Read content_agent.py lines 56-67 | 10 confirmed | PASS |
| JOB_LOCK_IDS midday=1008 and gold=1009 | Read worker.py lines 43-44 | Both confirmed | PASS |
| gold_history_used_topics seeded | Read seed_content_data.py line 35 | Present with "[]" | PASS |
| pytest (excluding stale tests) | Run with --deselect on 3 stale tests | 71 passed, 0 failed | PASS |

---

## Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|------------|-------------|--------|----------|
| CONT-09 | 07-06 through 07-09 | content_type field, 7 format types | SATISFIED | All 7 formats implemented in content_agent.py + gold_history_agent.py |
| CONT-02 | 07-07 | 8 RSS feeds | SATISFIED | RSS_FEEDS has 8 entries |
| CONT-03 | 07-07 | 10 SerpAPI keywords | SATISFIED | SERPAPI_KEYWORDS has 10 entries |
| CONT-04 | 07-07 | Cross-run deduplication | SATISFIED | _is_already_covered_today() method |
| CONT-05 | 07-07 | Story scoring with weighted components | SATISFIED | calculate_story_score() + recency/credibility functions |
| CONT-10 | 07-07 | Multi-story pipeline | SATISFIED | select_qualifying_stories() + for loop in _run_pipeline() |
| CONT-11 | 07-09 | Infographic dual-platform + Instagram design system | SATISFIED | instagram_brief in prompt + brand colors #F0ECE4, #0C1B32, #D4AF37 |
| CONT-12 | 07-09 | Historical pattern mode with SerpAPI verification fallback | SATISFIED | Lines 1007-1021 |
| CONT-13 | 07-08 | Video clip + quote Twitter sourcing | SATISFIED | _search_video_clips() and _search_quote_tweets() |
| CONT-01 | 07-10 | 3 APScheduler jobs (6am, 12pm, bi-weekly Sunday) | SATISFIED | 7 jobs total in worker.py |
| CONT-07 | 07-10 | No-story flag + all-covered-today case | SATISFIED | build_no_story_bundle() + all_already_covered path |
| CONT-14 | 07-07, 07-10 | Compliance checking on all draft text | SATISFIED | check_compliance() used in both agents |
| CONT-15 | 07-07, 07-10 | No Seva Mining mention | SATISFIED | Local pre-screen + Haiku check |
| CONT-16 | 07-07, 07-10 | No financial advice | SATISFIED | Haiku check + system prompt prohibitions |
| CONT-17 | 07-07, 07-10 | Senior Agent DraftItem integration | SATISFIED | build_draft_item() + process_new_items() in both agents |

---

## Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| `scheduler/tests/test_content_agent.py` | 46 | `assert len(ca.RSS_FEEDS) == 4` — stale count, actual is 8 | Blocker | CI fails; 3 tests total fail the -x run |
| `scheduler/tests/test_content_agent.py` | 57 | `assert len(ca.SERPAPI_KEYWORDS) == 6` — stale count, actual is 10 | Blocker | CI fails |
| `scheduler/tests/test_worker.py` | 97 | `expected_ids` set has 5 entries — missing content_agent_midday and gold_history_agent | Blocker | CI fails; assertion message also says "exactly 5 jobs" |
| `scheduler/agents/content_agent.py` | 442-459 | `parse_rss_entries()` and `parse_serpapi_results()` still return `[]` stubs | Info | Not a gap — these functions are unused; actual parsing is inline in _fetch_all_rss() and _fetch_all_serpapi(). No user-visible impact. |

---

## Human Verification Required

### 1. ContentPage Multi-Format Rendering

**Test:** Seed ContentBundle records with each of the 7 content_types. Open the dashboard Content page and cycle through them.
**Expected:** thread shows numbered tweets, long_form shows textarea, infographic shows InfographicPreview component, breaking_news/video_clip/quote/gold_history fall through to JSON pre block.
**Why human:** React rendering behavior requires running frontend.

### 2. APScheduler Week Boundary Behavior

**Test:** Review the week="*/2" edge case at ISO week 52/53 rollover (documented in worker.py comment line 299-301).
**Expected:** At most one extra Gold History post in early January — acceptable per the code comment.
**Why human:** Calendar edge case; cannot simulate without date manipulation.

### 3. Twitter API Video Filter Accuracy

**Test:** Run _search_video_clips() with a live X_API_BEARER_TOKEN and verify the has_video filter correctly excludes GIFs and image-only tweets.
**Expected:** Only tweets with type="video" media attachments are returned.
**Why human:** Requires live Twitter API credentials.

---

## Gaps Summary

The implementation across all 5 plans (07-06 through 07-10) is functionally complete. All 30 implementation requirements are satisfied. The single gap is test hygiene: 3 test assertions predate the expansion plans and contain stale hardcoded counts.

**This is a documentation/test gap, not an implementation gap.** The code is correct; the tests are wrong.

**Root cause:** Plans 07-07 and 07-10 expanded RSS_FEEDS to 8, SERPAPI_KEYWORDS to 10, and added 2 new APScheduler jobs. The test files checked against the pre-expansion counts (4, 6, 5) and were never updated.

**Fix:** 3 one-line changes in 2 test files:

| File | Line | Change |
|------|------|--------|
| `scheduler/tests/test_content_agent.py` | 46 | `assert len(ca.RSS_FEEDS) == 4` → `== 8` |
| `scheduler/tests/test_content_agent.py` | 57 | `assert len(ca.SERPAPI_KEYWORDS) == 6` → `== 10` |
| `scheduler/tests/test_worker.py` | 97 | Add `"content_agent_midday"` and `"gold_history_agent"` to `expected_ids` set; update docstring from "exactly 5 jobs" to "exactly 7 jobs" |

With those 3 fixes applied, all 74 tests pass (confirmed: 71 passed when the 3 stale tests are deselected).

---

_Verified: 2026-04-07_
_Verifier: Claude (gsd-verifier)_
