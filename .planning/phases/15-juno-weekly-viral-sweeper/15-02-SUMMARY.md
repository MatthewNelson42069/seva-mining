---
phase: 15-juno-weekly-viral-sweeper
plan: 02
subsystem: scheduler
tags: [anthropic, sonnet, x-api, defence, prompt-engineering, tweepy]

# Dependency graph
requires:
  - phase: 10-juno-defence-news-funnel
    provides: "DEFENCE_NEWS_SYSTEM_PROMPT with verbatim FORBID anti-tactical clause (string-equality contract source)"
  - phase: 07-weekly-viral-sweeper
    provides: "Seva SONNET_SYSTEM_PROMPT '3 content angles' template + grounding rule (reference shape only)"
provides:
  - "JUNO_SWEEPER_SYSTEM_PROMPT constant in scheduler/companies/juno/prompts.py (Janes/CSIS voice + verbatim FORBID + 3-angles framing + neutral-on-conflict)"
  - "JUNO_SWEEPER_X_QUERY constant in scheduler/companies/juno/x_queries.py (11 corrected handles + 2 hashtags + -is:retweet lang:en, 261 chars)"
  - "8 new prompt-contract tests + 8 new x-query invariant tests (16 tests total)"
  - "String-equality contract honored — FORBID block appears verbatim in BOTH DEFENCE_NEWS_SYSTEM_PROMPT and JUNO_SWEEPER_SYSTEM_PROMPT"
affects:
  - 15-05-PLAN  # juno_weekly_sweeper.py orchestrator (imports both constants)
  - 15-06-PLAN  # worker.py cron registration (no direct imports but downstream)

# Tech tracking
tech-stack:
  added: []  # no new libraries — pure-Python constants
  patterns:
    - "Verbatim anti-tactical FORBID block as a string-equality contract across two prompt constants (Anthropic content-policy compliance per RESEARCH §4)"
    - "Tenant-scoped X recent-search query as a module-level constant in companies/<tenant>/x_queries.py (parallel to companies/juno/feeds.py + serpapi.py)"

key-files:
  created:
    - scheduler/companies/juno/x_queries.py
    - scheduler/tests/companies/test_juno_x_queries.py
  modified:
    - scheduler/companies/juno/prompts.py
    - scheduler/tests/companies/test_juno_prompts.py

key-decisions:
  - "JUNO_SWEEPER_SYSTEM_PROMPT appended below DEFENCE_NEWS_SYSTEM_PROMPT in the same prompts.py file (NOT a new file) — keeps the FORBID string-equality contract grep-discoverable in a single file"
  - "Verbatim FORBID block copied byte-for-byte from prompts.py:21-22 — grep returns 2 across the file, locking the string-equality contract per D-04"
  - "Defence-prime cashtag anti-feature reinforced at two layers: the x_queries.py query string excludes all cashtags, and the JUNO_SWEEPER_SYSTEM_PROMPT negative-space DO-NOT list explicitly cites LMT/RTX/NOC/BA/GD/BAESY"
  - "Tier-2 Canadian additions (@DavePerryCGAI + @Murray_Brewster) included in v1.0 query per RESEARCH §2 recommendation — total 11 handles + 2 hashtags = 261 chars (60% headroom on 512-char Basic-tier cap)"

patterns-established:
  - "String-equality contract for content-policy clauses: when a clause must appear in multiple prompts for compliance reasons, copy verbatim bytes and assert via a single grep-checkable test that the literal substring is in every required prompt"
  - "Per-tenant X recent-search query constants live in scheduler/companies/<tenant>/x_queries.py, separate from prompt constants in prompts.py — mirrors the existing feeds.py/serpapi.py separation"

requirements-completed: [JSWEEP-02, JSWEEP-04]

# Metrics
duration: 4min
completed: 2026-05-21
---

# Phase 15 Plan 02: Juno Sweeper Sonnet Prompt + X Query Constants Summary

**`JUNO_SWEEPER_SYSTEM_PROMPT` (2534 chars, Janes/CSIS voice + verbatim FORBID + 3-angles + neutral-on-conflict) and `JUNO_SWEEPER_X_QUERY` (261 chars, 11 corrected handles + 2 hashtags) landed as importable constants for Plan 15-05's sweeper orchestrator, with the D-04 string-equality FORBID contract grep-verified to appear in BOTH prompts.**

## Performance

- **Duration:** ~4 min
- **Started:** 2026-05-21T00:38:58Z
- **Completed:** 2026-05-21T00:43:00Z
- **Tasks:** 2 (both TDD)
- **Files modified:** 4 (2 created, 2 modified)

## Accomplishments

- **JUNO_SWEEPER_SYSTEM_PROMPT (NEW, 2534 chars)** appended below the existing `DEFENCE_NEWS_SYSTEM_PROMPT` in `scheduler/companies/juno/prompts.py`. Carries Janes/CSIS desk voice anchor, verbatim FORBID anti-tactical clause (byte-identical bytes from Phase 10), neutral-on-conflict bias (inverts Seva's gold-bull-thesis), refusal-prone-framing avoidance preface, "exactly 3 content angles" task framing with X-signal/news-signal contract, grounding + anti-hallucination rule, output structure block with 3× `### Angle N:` markers, and negative-space DO-NOT list explicitly citing LMT/RTX/NOC/BA/GD/BAESY tickers (PROJECT.md anti-feature).
- **D-04 string-equality contract honored** — `grep -c "FORBID — anti-tactical framing clause" scheduler/companies/juno/prompts.py` returns **2** (once in DEFENCE_NEWS_SYSTEM_PROMPT, once in JUNO_SWEEPER_SYSTEM_PROMPT). Test `test_sweeper_prompt_contains_anti_tactical_clause_verbatim` asserts the same literal `ANTI_TACTICAL_CLAUSE_VERBATIM` string is a substring of both constants.
- **JUNO_SWEEPER_X_QUERY (NEW, 261 chars)** exported from new file `scheduler/companies/juno/x_queries.py`. Encodes the post-research corrected D-02 handle set: 3 think-tanks (@RUSI_org, @CSIS, @IISS_org) + 4 defence press with corrected spellings (@defense_news, @BreakingDefense, @DefenseScoop, @JanesINTEL) + 4 Canadian incl. 2 Tier-2 additions (@CDAInstitute, @CanadianForces, @DavePerryCGAI, @Murray_Brewster) + 2 hashtags (#defence, #NATO) + `-is:retweet lang:en`. Length 261 chars = 51% of the X API Basic-tier 512-char cap (40% headroom even if all 4 reserve tunability candidates are added).
- **8 new prompt tests + 8 new x-query tests** = 16 net-new tests; full prompts file 21/21 GREEN (13 existing + 8 new), full x_queries file 8/8 GREEN.
- **D-10 zero-regression preserved** — `git status --porcelain` empty for `scheduler/agents/weekly_sweeper.py`, `scheduler/agents/x_ingest.py`, `scheduler/companies/juno/feeds.py`, `scheduler/companies/juno/serpapi.py`, `scheduler/companies/juno/__init__.py`. Existing 13 Phase 10 prompt tests pass byte-identically.

## Verbatim FORBID Block Bytes (string-equality contract per D-04)

Both `DEFENCE_NEWS_SYSTEM_PROMPT` (existing, Phase 10) and `JUNO_SWEEPER_SYSTEM_PROMPT` (new, Phase 15) contain this exact substring (~471 chars including the leading "FORBID" header):

```
FORBID — anti-tactical framing clause:
You produce market/industry commentary on the defence sector. You do NOT produce operational, tactical, targeting, force posture, order of battle (OOB), capability gap, or troop movement analysis. If a source story crosses into operational territory, summarize the market/industry implications only and explicitly note the operational details were excluded.
```

The literal `ANTI_TACTICAL_CLAUSE_VERBATIM` defined in `scheduler/tests/companies/test_juno_prompts.py` is asserted (`in`) to be a substring of BOTH prompts. Anthropic content-policy compliance per RESEARCH §4 Anthropic-Pentagon dispute analysis.

## Final X Query (D-01 + D-02 corrected, 261 chars)

```
(from:RUSI_org OR from:CSIS OR from:IISS_org OR from:defense_news OR
 from:BreakingDefense OR from:DefenseScoop OR from:JanesINTEL OR
 from:CDAInstitute OR from:CanadianForces OR from:DavePerryCGAI OR
 from:Murray_Brewster OR #defence OR #NATO) -is:retweet lang:en
```

Corrections vs CONTEXT.md original D-02 (4 of 9 handles would have returned 0 hits as spelled):

- `@DefenseNews` → `defense_news` (snake_case official handle)
- `@CDA_CDAI` → `CDAInstitute` (correct CDA Institute handle)
- `@canadaforces` → `CanadianForces` (correct CAF handle)
- `@JanesIntel` → `JanesINTEL` (case-variant official form)
- ADDED Tier-2 Canadian: `@DavePerryCGAI` (CGAI President) + `@Murray_Brewster` (CBC senior defence reporter) per RESEARCH §2

Defence-prime cashtags (`$LMT`, `$RTX`, `$LDOS`, `$BAESY`, `$GD`, `$NOC`, `$BA`) explicitly EXCLUDED per PROJECT.md anti-feature on equity/financial signals.

## Test Count Delta

| File | Before | After | Delta |
|------|--------|-------|-------|
| `scheduler/tests/companies/test_juno_prompts.py` | 13 tests (7 def + 7-keyword parametrize collapsed) | 21 tests | **+8** |
| `scheduler/tests/companies/test_juno_x_queries.py` | (did not exist) | 8 tests | **+8** |
| Full scheduler suite | baseline | **339 passed, 1 skipped** | well above 323+ target |

## Task Commits

Both tasks executed via TDD (RED → GREEN, no refactor needed):

1. **Task 1 RED: Add 8 failing tests for JUNO_SWEEPER_SYSTEM_PROMPT** — `4743477` (test)
2. **Task 1 GREEN: Add JUNO_SWEEPER_SYSTEM_PROMPT to companies/juno/prompts.py** — `3c2a2ee` (feat)
3. **Task 2 RED: Add 8 failing tests for JUNO_SWEEPER_X_QUERY** — `2a9b0b4` (test)
4. **Task 2 GREEN: Add JUNO_SWEEPER_X_QUERY in companies/juno/x_queries.py** — `faae9f8` (feat)

## Files Created/Modified

- **CREATED** `scheduler/companies/juno/x_queries.py` (40 lines) — exports `JUNO_SWEEPER_X_QUERY` constant with full rationale docstring covering RESEARCH §1/§2/§3 corrections + cashtag-exclusion rationale + tunability path.
- **CREATED** `scheduler/tests/companies/test_juno_x_queries.py` (113 lines) — 8 invariant tests for the query constant.
- **MODIFIED** `scheduler/companies/juno/prompts.py` (+47 lines) — appended `JUNO_SWEEPER_SYSTEM_PROMPT` constant below the unchanged `DEFENCE_NEWS_SYSTEM_PROMPT` (Phase 10 prompt untouched per D-10).
- **MODIFIED** `scheduler/tests/companies/test_juno_prompts.py` (+150 lines) — appended `ANTI_TACTICAL_CLAUSE_VERBATIM` literal + 8 new `test_sweeper_prompt_*` tests below the existing 7 Phase 10 tests (existing tests byte-identically untouched per D-10).

## Decisions Made

- **Single-file co-location of both prompts** — Both `DEFENCE_NEWS_SYSTEM_PROMPT` and `JUNO_SWEEPER_SYSTEM_PROMPT` live in `scheduler/companies/juno/prompts.py`. Keeps the FORBID string-equality contract grep-discoverable from one file (`grep -c "FORBID — anti-tactical framing clause" scheduler/companies/juno/prompts.py` returns 2). PLAN spec preferred this over splitting prompts across files.
- **Tier-2 Canadians added in v1.0** — `@DavePerryCGAI` + `@Murray_Brewster` included immediately rather than held for tunability iteration. Net length still 261 chars (well under cap); these are the highest-signal individual Canadian defence voices per RESEARCH §2.
- **Cashtag anti-feature reinforced at two layers** — both at the data layer (x_queries.py contains no `$TICKER` operators) and at the synthesis layer (JUNO_SWEEPER_SYSTEM_PROMPT negative-space DO-NOT list explicitly cites LMT/RTX/NOC/BA/GD/BAESY). Defence-in-depth on the PROJECT.md anti-feature.
- **Docstring cashtag enumeration rewritten** — initial x_queries.py docstring listed `$LMT, $RTX, $LDOS, $BAESY, $GD` literally, which tripped a coarse grep gate intended to catch cashtag operators in the QUERY. Rewrote the docstring to spell out "Lockheed Martin, RTX/Raytheon, Leidos, BAE Systems, General Dynamics, Northrop Grumman, Boeing" while keeping the anti-feature documented. Functional intent unchanged; passes both the grep gate AND the `test_query_excludes_defence_prime_cashtags` semantic test.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] x_queries.py docstring tripped coarse cashtag-grep acceptance check**
- **Found during:** Task 2 acceptance verification
- **Issue:** PLAN acceptance criterion `grep -cE "\\\$LMT|\\\$RTX|\\\$LDOS|\\\$BAESY|\\\$GD" scheduler/companies/juno/x_queries.py` must return 0 (intent: no cashtag in the QUERY). Initial docstring narrative listed the excluded cashtags using their literal `$TICKER` form (`"$LMT, $RTX, $LDOS, $BAESY, $GD, etc."`) as anti-feature documentation, which caused the coarse grep to return 1.
- **Fix:** Rewrote the docstring opening to spell the names out ("Lockheed Martin, RTX/Raytheon, Leidos, BAE Systems, General Dynamics, Northrop Grumman, Boeing") instead of using literal cashtag operator syntax. The anti-feature is still documented; the QUERY string itself is unchanged and the semantic test `test_query_excludes_defence_prime_cashtags` continues to pass.
- **Files modified:** `scheduler/companies/juno/x_queries.py` (docstring only; constant unchanged)
- **Verification:** `grep -cE "\\\$LMT|\\\$RTX|\\\$LDOS|\\\$BAESY|\\\$GD" scheduler/companies/juno/x_queries.py` returns 0; 8/8 x_query tests still GREEN.
- **Committed in:** `faae9f8` (Task 2 GREEN commit — bundled, not a separate commit since it was fixed before the GREEN commit landed)

**2. [Rule 2 - Missing Critical] Added `JUNO_SWEEPER_X_QUERY` reference in docstring**
- **Found during:** Task 2 acceptance verification
- **Issue:** PLAN acceptance criterion `grep -c "JUNO_SWEEPER_X_QUERY" scheduler/companies/juno/x_queries.py` must return ≥ 2 (intent: constant assignment + at least one docstring/comment reference for discoverability). Initial docstring did not name the exported constant, so the grep returned 1.
- **Fix:** Added "Exports `JUNO_SWEEPER_X_QUERY`:" to the docstring opening sentence, making the exported symbol grep-discoverable.
- **Files modified:** `scheduler/companies/juno/x_queries.py` (docstring only)
- **Verification:** `grep -c "JUNO_SWEEPER_X_QUERY" scheduler/companies/juno/x_queries.py` returns 2.
- **Committed in:** `faae9f8` (bundled in Task 2 GREEN commit before landing)

---

**Total deviations:** 2 auto-fixed (1 docstring-vs-grep coarseness fix, 1 missing-docstring-reference fix). Both fixed during acceptance verification BEFORE the Task 2 GREEN commit landed — no separate "fix" commit required.

**Impact on plan:** Both auto-fixes were docstring-only adjustments to satisfy coarse grep acceptance criteria. The functional code (the query constant, the test invariants) was unchanged. No scope creep. The PLAN's semantic tests were the source of truth; the grep gates were coarse proxies that the docstring needed to align with.

## Issues Encountered

None during planned work. The full scheduler suite at 339 passed (1 skipped, 4 unrelated `RuntimeWarning` on `daily_summary_prune.py` AsyncMock — pre-existing, NOT introduced by this plan) confirms zero regression.

## Self-Check: PASSED

Verified at completion:
- All 5 expected files exist on disk (`scheduler/companies/juno/prompts.py`, `scheduler/companies/juno/x_queries.py`, `scheduler/tests/companies/test_juno_prompts.py`, `scheduler/tests/companies/test_juno_x_queries.py`, `.planning/phases/15-juno-weekly-viral-sweeper/15-02-SUMMARY.md`).
- All 4 task commits exist in `git log --oneline --all`: `4743477`, `3c2a2ee`, `2a9b0b4`, `faae9f8`.
- Full scheduler test suite: 339 passed, 1 skipped, 0 failed (well above 323+ target).
- CI grep gates: `scripts/verify-anthropic-resolver.sh` PASS + `scripts/verify-tenant-isolation.sh` PASS.
- D-10 zero-regression: `git status --porcelain` empty for protected Seva-side files.

## User Setup Required

None - no external service configuration required. Both constants are pure-Python literals; Plan 15-05's orchestrator will be the consumer.

## Next Phase Readiness

- Plan 15-05 can now `from companies.juno.prompts import JUNO_SWEEPER_SYSTEM_PROMPT` and `from companies.juno.x_queries import JUNO_SWEEPER_X_QUERY` without any further constant work.
- The string-equality FORBID contract is locked in tests; Plan 15-05 reviewers can grep for `FORBID — anti-tactical framing clause` and expect exactly 2 matches in `scheduler/companies/juno/prompts.py`.
- Wave 2 (Plan 15-05 + 15-06) is unblocked from this plan's deliverables; orthogonal Wave 1 plans (15-01 substrate, 15-03 frontend, 15-04 backend isolation) executing in parallel do not depend on these constants.
- No blockers or concerns. Plan boundary respected (zero changes to Seva-side files, zero changes to `weekly_sweeper.py`, zero changes to `x_ingest.py`).

---
*Phase: 15-juno-weekly-viral-sweeper*
*Completed: 2026-05-21*
