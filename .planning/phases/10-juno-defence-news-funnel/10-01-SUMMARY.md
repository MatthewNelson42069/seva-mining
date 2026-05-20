---
phase: 10-juno-defence-news-funnel
plan: 01
subsystem: testing
tags: [pytest, vitest, feedparser, anthropic, haiku, refusal-detector, rss, defence, juno, tdd, red-green]

# Dependency graph
requires:
  - phase: 09-multi-tenant-foundation
    provides: company_id columns, scoped_summaries('juno') helper, JUNO_DEFENCE_FEEDS skeleton, run_juno_daily_summary stub, SummaryCard interface
provides:
  - "scripts/verify-juno-rss.sh — Phase-0 RSS endpoint probe (16 endpoints)"
  - "phase-10-feed-verification.md — Wave 1 source-of-truth for JUNO_DEFENCE_FEEDS (13 working) + SerpAPI fallbacks (3)"
  - "5 NEW Wave 0 RED test files + 1 EXTENDED test file scaffolding DEF-01..DEF-08 contracts"
  - "frontend/src/config/companySectionConfig.ts — production per-tenant section title + emptyFallback map for Seva (gold) + Juno (defence) via Phase 9 D-08 semantic column reuse"
affects: [10-02, 10-03, 10-04, 10-05]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Module-level pytest.skip(allow_module_level=True) for RED scaffolds awaiting downstream wave (Phase 8/9 precedent)"
    - "Per-function pytest.skip() inside an extended GREEN test file (preserves existing passing tests, scaffolds new contracts)"
    - "describe.skip('...') for frontend Vitest RED scaffolds"
    - "Per-company section config — single Record<CompanyId, SectionConfig[]> consumed via useParams (Wave 3 wires)"
    - "Phase-0 endpoint verification via inline `cd scheduler && uv run python -c \"import feedparser\"` so probe runs in production dep environment"

key-files:
  created:
    - "scripts/verify-juno-rss.sh"
    - ".planning/phases/10-juno-defence-news-funnel/phase-10-feed-verification.md"
    - "scheduler/tests/agents/test_juno_relevance.py"
    - "scheduler/tests/agents/test_juno_refusal_detector.py"
    - "scheduler/tests/agents/test_juno_health_check.py"
    - "scheduler/tests/companies/__init__.py"
    - "scheduler/tests/companies/test_juno_prompts.py"
    - "frontend/src/config/companySectionConfig.ts"
  modified:
    - "scheduler/tests/agents/test_juno_daily_summary.py"
    - "frontend/src/components/summary/__tests__/SummaryCard.test.tsx"

key-decisions:
  - "Wave 0 lands all 8 RED scaffold files in three atomic commits (RSS probe + scheduler scaffolds + frontend scaffold), matching Phase 9 09-01 cadence."
  - "Module-level skip vs per-function skip — NEW Wave 0 files use module-level; EXTENDED test_juno_daily_summary.py uses per-function so Phase 9 GREEN tests stay GREEN."
  - "companySectionConfig.ts ships as production code in Wave 0 (not skipped) so Wave 3's SummaryCard.tsx edit is a single-file ~15-line diff."
  - "war.gov + nato.int + canada.ca defence endpoints all return bozo=1 / 0 entries → Wave 1 must route them through SerpAPI `site:` queries (no DROPPED endpoints)."

patterns-established:
  - "Phase-0 endpoint verification artifact (phase-10-feed-verification.md): pipe-delimited probe → human-curated markdown table; becomes Wave 1 source-of-truth"
  - "8-file Wave 0 RED scaffold pattern (5 scheduler module-skipped + 1 scheduler per-function-skipped extension + 1 production frontend config + 1 frontend describe.skip extension) — extensible to future tenant onboarding waves"

requirements-completed:
  - DEF-01
  - DEF-02
  - DEF-03
  - DEF-04
  - DEF-05
  - DEF-06
  - DEF-07
  - DEF-08

# Metrics
duration: 7min
completed: 2026-05-20
---

# Phase 10 Plan 01: Wave 0 RED Scaffolds + Phase-0 RSS Verification Summary

**13/16 Juno defence RSS endpoints verified live (all Tier-1 WORKING, 3 TBD → SerpAPI fallback); 8 RED test files + 1 production per-tenant SectionConfig module shipped so Wave 1/2/3 only have to remove skip lines to turn modules GREEN**

## Performance

- **Duration:** 7 min
- **Started:** 2026-05-20T01:54:01Z
- **Completed:** 2026-05-20T02:01:43Z
- **Tasks:** 3
- **Files modified:** 10 (8 created + 2 extended)

## Accomplishments

- **Phase-0 RSS endpoint verification complete (D-13/D-14):** All 13 Tier-1 defence feeds returned bozo=0 with healthy entry counts (8 Defense News sub-feeds × 25 entries, Breaking Defense 15, DefenseScoop 10, RUSI Commentary 20, RUSI Publications 20, SIPRI Combined 10). Total Defence News substrate ≈ 275 entries/fire pre-dedup. 0 DROPPED endpoints; 3 TBD endpoints (war.gov, nato.int, canada.ca defence) route to SerpAPI `site:` fallbacks per Wave 1 integration plan in the artifact.
- **8 Wave 0 RED test files scaffold DEF-01..DEF-08 contracts:** test_juno_relevance.py (12 tests; Haiku classifier Pydantic shape + 5 golden classify_story inputs + 5 survives_threshold gate cases), test_juno_refusal_detector.py (10 tests; 7-pattern parametrized substring detection, first-500-chars scan, FRAMING_NUDGE + SECTION_UNAVAILABLE_COPY constants, retry-once + second-refusal-fallback paths), test_juno_health_check.py (10 tests; bozo flag, history threshold, status='partial' on 3+ flags, 'failed' on zero entries, telemetry shape), test_juno_prompts.py (10 tests; anti-tactical clause, 7 FORBID keywords, 3 section markers, voice anchor, bullet rule, no-stub, no-gold-bull-language).
- **test_juno_daily_summary.py EXTENDED preserving Phase 9 GREEN tests:** 2 Phase 9 tests still pass; 5 new tests scaffold Wave 2 contracts (defence_news_section, serpapi_canadian_procurement, canadian_procurement_section, world_events_section_with_haiku_filter, idempotency_window_with_partial) — each guarded by per-function pytest.skip() citing 10-03-PLAN.md.
- **companySectionConfig.ts production module + SummaryCard.test.tsx RED extension:** Wave 3 (10-04-PLAN.md) only edits SummaryCard.tsx ~15 lines and flips describe.skip→describe; no further frontend file creation needed.
- **Test suites green throughout:** Scheduler 269 passed + 10 skipped (5 Wave 1 modules + 5 Wave 2 per-function), 6.4s; Frontend 165 passed + 3 skipped, 28 files, 4.0s.

## Task Commits

Each task was committed atomically:

1. **Task 1: Phase-0 RSS verification script + artifact** — `f876363` (chore)
2. **Task 2: Scheduler RED test scaffolding (Juno classifier, refusal-detector, health-check, prompts, daily_summary extension)** — `3dec343` (test)
3. **Task 3: Frontend companySectionConfig production module + SummaryCard RED test extension** — `f765f16` (feat)

**Plan metadata commit:** appended after this SUMMARY.md is written.

## Files Created/Modified

### Created (8)
- `scripts/verify-juno-rss.sh` — chmod +x; pipe-delimited probe of 16 Juno endpoints via `cd scheduler && uv run python -c "import feedparser"`. Output verdicts: WORKING | DROPPED | FALLBACK_TO_SERPAPI.
- `.planning/phases/10-juno-defence-news-funnel/phase-10-feed-verification.md` — markdown table of all 16 probe results + Wave 1 integration plan (13 WORKING into JUNO_DEFENCE_FEEDS, 3 FALLBACK into JUNO_SERPAPI_QUERIES site: queries).
- `scheduler/tests/agents/test_juno_relevance.py` — DEF-06 Haiku classifier RED tests (12 functions, module-level skip cites 10-02-PLAN.md).
- `scheduler/tests/agents/test_juno_refusal_detector.py` — DEF-07 refusal-detector RED tests (10 functions, module-level skip cites 10-03-PLAN.md).
- `scheduler/tests/agents/test_juno_health_check.py` — DEF-04 health-check RED tests (10 functions, module-level skip cites 10-03-PLAN.md).
- `scheduler/tests/companies/__init__.py` — empty file (pytest collection enabler for new tests/companies subdirectory).
- `scheduler/tests/companies/test_juno_prompts.py` — DEF-03 DEFENCE_NEWS_SYSTEM_PROMPT string-match RED tests (10 functions; parametrized FORBID keywords; voice anchor; no-stub guard; no-gold-bull-language guard).
- `frontend/src/config/companySectionConfig.ts` — PRODUCTION module exporting SectionConfig interface + companySectionConfig: Record<'seva' | 'juno', SectionConfig[]>. Seva → gold titles; Juno → defence titles via Phase 9 D-08 semantic column reuse.

### Modified (2)
- `scheduler/tests/agents/test_juno_daily_summary.py` — Phase 9 tests preserved (2 passing); 5 new per-function-skipped Wave 2 contracts appended (defence_news_section, serpapi_canadian_procurement, canadian_procurement_section, world_events_section_with_haiku_filter, idempotency_window_with_partial).
- `frontend/src/components/summary/__tests__/SummaryCard.test.tsx` — Phase 1-8 GREEN tests preserved (7 passing); describe.skip block with 3 it-tests added (Seva titles at /seva/, Juno titles at /juno/, Juno empty-fallback copy). Imports companySectionConfig for type-check coverage.

## Decisions Made

- **Sub-shell pattern `cd scheduler && uv run python -c` chosen over a venv-activated bash session:** isolates the feedparser call inside the scheduler venv (matches production code path); single-line invocation per feed; no global venv pollution.
- **Tightened bash script (set -u, NOT set -e):** lets one bad endpoint emit a `-1|0` row instead of aborting the entire 16-endpoint sweep — matches the verify-tenant-isolation.sh idiom.
- **TBD endpoint URLs probed verbatim from research:** war.gov/news/rss/?feedtype=press-releases, nato.int/cps/en/natohq/news.htm?_=feed, canada.ca/en/news/web-feeds.html. All three returned bozo=1 / 0 entries — confirms research suspicion that these are not real RSS feeds. Wave 1 will replace them with SerpAPI `site:` queries.
- **8 ≠ 9 endpoints:** plan calls for "16 endpoints (13 Tier-1 + 3 TBD)" which matches the FEEDS array exactly. RESEARCH.md §Example 4 had "15 endpoints" copy-paste artifact from earlier draft (12 Tier-1 + 3 TBD); plan reconciled to 13+3=16 (8 Defense News sub-feeds explicitly enumerated rather than collapsed). Verification artifact uses the 16-endpoint count.
- **Per-function skip in extended test_juno_daily_summary.py vs module-level:** chosen so the 2 Phase 9 GREEN tests stay collected as PASS rather than being skipped wholesale alongside the new Wave 2 contracts.
- **describe.skip block guarded with MemoryRouter + Routes:** simulates Wave 3's useParams<{company}>() consumption pattern so when describe.skip flips to describe, the tests will exercise the real route → params → config path.

## Deviations from Plan

None — plan executed exactly as written. All 3 tasks completed with their full acceptance criteria met. No Rule 1/2/3 auto-fixes triggered.

The plan called for "16 endpoints (13 Tier-1 + 3 TBD)" while RESEARCH.md §Example 4 still had a "15 endpoints" header copy-pasted from an earlier draft (12 Tier-1 collapsed). The plan body and the verification script both use 16 endpoints (8 Defense News sub-feeds enumerated explicitly), so this was tracked as a doc inconsistency in RESEARCH.md header only — not a substantive deviation. The artifact uses the 16-endpoint count.

## Issues Encountered

- None. SerpAPI Client import is not exercised in Wave 0 (Wave 2 test patches it directly); no anthropic SDK structured-output runtime resolution either (mocked).

## Wave 0 Test Counts (Pre-Wave-1)

**Scheduler:**
- 269 passed (all pre-Wave-0 GREEN tests preserved)
- 10 skipped:
  - 4 module-level (test_juno_relevance.py, test_juno_refusal_detector.py, test_juno_health_check.py, test_juno_prompts.py — turn GREEN when Wave 1/2 production code lands)
  - 5 per-function in test_juno_daily_summary.py (Wave 2 production synthesis path)
  - 1 pre-existing skip from prior phases

**Frontend:**
- 165 passed (28 files)
- 3 skipped (per-tenant section title block — turns GREEN when Wave 3 wires useParams<{company}>() into SummaryCard.tsx)

## Wave 1 Integration Inputs

From `phase-10-feed-verification.md`:

**JUNO_DEFENCE_FEEDS (13 tuples — all WORKING, populate in 10-02-PLAN.md):**
```python
JUNO_DEFENCE_FEEDS: list[tuple[str, str]] = [
    ("defense_news_industry", "https://www.defensenews.com/arc/outboundfeeds/rss/category/industry/?outputType=xml"),
    ("defense_news_pentagon", "https://www.defensenews.com/arc/outboundfeeds/rss/category/pentagon/?outputType=xml"),
    ("defense_news_global", "https://www.defensenews.com/arc/outboundfeeds/rss/category/global/?outputType=xml"),
    ("defense_news_air", "https://www.defensenews.com/arc/outboundfeeds/rss/category/air/?outputType=xml"),
    ("defense_news_land", "https://www.defensenews.com/arc/outboundfeeds/rss/category/land/?outputType=xml"),
    ("defense_news_naval", "https://www.defensenews.com/arc/outboundfeeds/rss/category/naval/?outputType=xml"),
    ("defense_news_space", "https://www.defensenews.com/arc/outboundfeeds/rss/category/space/?outputType=xml"),
    ("defense_news_unmanned", "https://www.defensenews.com/arc/outboundfeeds/rss/category/unmanned/?outputType=xml"),
    ("breaking_defense", "https://breakingdefense.com/feed/"),
    ("defense_scoop", "https://defensescoop.com/feed/"),
    ("rusi_commentary", "https://www.rusi.org/rss/latest-commentary.xml"),
    ("rusi_publications", "https://www.rusi.org/rss/latest-publications.xml"),
    ("sipri_combined", "https://www.sipri.org/rss/combined.xml"),
]
```

**JUNO_SERPAPI_QUERIES (3 site: fallback queries for the 3 TBD endpoints + D-09 Canadian Procurement queries from 10-CONTEXT):**
```python
JUNO_SERPAPI_QUERIES: list[str] = [
    "site:war.gov defence",
    "site:nato.int press release",
    "site:canada.ca defence",
    # (Wave 1 also adds the D-09 Canadian Procurement queries:
    #  site:canadiandefencereview.com, site:pspc-spac.gc.ca, etc.)
]
```

**TBD endpoints summary:** 0 of 3 returned valid RSS; all 3 require SerpAPI `site:` fallback (Wave 1 must add `site:war.gov defence`, `site:nato.int press release`, `site:canada.ca defence` to JUNO_SERPAPI_QUERIES).

## Next Phase Readiness

- **Wave 1 (10-02-PLAN.md) ready:** has phase-10-feed-verification.md as source-of-truth; 4 RED test files (test_juno_relevance.py + test_juno_prompts.py module-skipped + 2 of 5 per-function-skipped tests in test_juno_daily_summary.py) become GREEN when 10-02 production code lands. Test contract import paths (`from agents.juno_relevance import DefenceRelevance, classify_story, ...` and `from companies.juno.prompts import DEFENCE_NEWS_SYSTEM_PROMPT`) are pre-encoded.
- **Wave 2 (10-03-PLAN.md) ready:** 3 RED test files (test_juno_refusal_detector.py + test_juno_health_check.py module-skipped + 3 of 5 per-function-skipped tests in test_juno_daily_summary.py) await Wave 2 production code. Import paths pre-encoded (`from agents.juno_refusal_detector import REFUSAL_PATTERN, FRAMING_NUDGE, SECTION_UNAVAILABLE_COPY, is_refusal, call_with_refusal_guard`).
- **Wave 3 (10-04-PLAN.md) ready:** companySectionConfig.ts ships production-ready; SummaryCard.test.tsx has 3 describe.skip tests pre-written. Wave 3's only frontend edit is ~15 lines in SummaryCard.tsx (read useParams, map config, render SectionBlock per entry) + flip describe.skip → describe.
- **Cron stays in Phase 9 partial-row state throughout Wave 0** — no production scheduler code touched.
- **No blockers** for advancing to 10-02-PLAN.md.

## Self-Check: PASSED

- `scripts/verify-juno-rss.sh` exists and chmod +x — verified via `ls -la`
- `.planning/phases/10-juno-defence-news-funnel/phase-10-feed-verification.md` exists with all 16 endpoint rows — verified via grep `WORKING|DROPPED|FALLBACK_TO_SERPAPI` count = 20 (≥ 13 minimum)
- All 5 new scheduler test files exist (`tests/agents/test_juno_relevance.py`, `tests/agents/test_juno_refusal_detector.py`, `tests/agents/test_juno_health_check.py`, `tests/companies/__init__.py`, `tests/companies/test_juno_prompts.py`)
- `tests/companies/__init__.py` is 0 bytes (verified `wc -l = 0`)
- `frontend/src/config/companySectionConfig.ts` exists, type-checks clean (`npx tsc --noEmit` exit 0), contains all 3 Juno literals: "Defence News", "Canadian Procurement", "World Events Relevant to Defence"
- `describe.skip` block present in `SummaryCard.test.tsx`
- Scheduler suite: 269 passed + 10 skipped — all Wave 0 RED scaffolds skipped at collection (no failed tests)
- Frontend suite: 165 passed + 3 skipped — all 3 new tests inside describe.skip block (no failed tests)
- Commit f876363 (Task 1) exists — verified via `git log --oneline | grep f876363`
- Commit 3dec343 (Task 2) exists — verified via `git log --oneline | grep 3dec343`
- Commit f765f16 (Task 3) exists — verified via `git log --oneline | grep f765f16`
- No production code changes in scheduler/companies/juno/{feeds,prompts,serpapi}.py or frontend/src/components/summary/SummaryCard.tsx — verified via `git diff HEAD~3..HEAD --stat` returning no entries for those paths

---
*Phase: 10-juno-defence-news-funnel*
*Plan: 01 (Wave 0)*
*Completed: 2026-05-20*
