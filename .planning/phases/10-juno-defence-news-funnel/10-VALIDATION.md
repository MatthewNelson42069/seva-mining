---
phase: 10
slug: juno-defence-news-funnel
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-05-19
---

# Phase 10 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.
> Derived from `10-RESEARCH.md` §Validation Architecture.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Scheduler framework** | pytest 9.x + pytest-asyncio 1.3.x (`scheduler/pyproject.toml` `[tool.pytest.ini_options]`) |
| **Scheduler quick run** | `cd scheduler && uv run pytest tests/agents/test_juno_relevance.py tests/agents/test_juno_refusal_detector.py tests/agents/test_juno_health_check.py -x` |
| **Scheduler full suite** | `cd scheduler && uv run pytest -x` |
| **Backend framework** | pytest 9.x (existing) |
| **Backend full suite** | `cd backend && uv run pytest -x` |
| **Frontend framework** | Vitest 4.1.2 |
| **Frontend quick run** | `cd frontend && npm test -- --run src/components/summary/__tests__/SummaryCard.test.tsx` |
| **Frontend full suite** | `cd frontend && npm test -- --run` |
| **Phase-0 RSS gate** | `bash scripts/verify-juno-rss.sh` outputs `feed_url\|bozo\|entries_count\|verdict` lines |
| **Estimated runtime (scheduler full)** | ~5 seconds (269 + ~12 new Juno tests) |
| **Estimated runtime (frontend full)** | ~6 seconds (165 + ~2 new SummaryCard tenant tests) |

---

## Sampling Rate

- **After every task commit:** `cd scheduler && uv run pytest tests/agents/test_juno_*.py -x` (~3 seconds)
- **After every plan wave:**
  - W0: `bash scripts/verify-juno-rss.sh` + scheduler full + frontend full
  - W1: scheduler full (Juno classifier + populated config files)
  - W2: scheduler full (real synthesis + refusal-detector + health-check)
  - W3: manual voice UAT + frontend full
  - W4: scheduler full + backend full + frontend full + integration smoke (live cron fire)
- **Before `/gsd:verify-work`:**
  - All 3 full suites green
  - `phase-10-feed-verification.md` artifact present with all 15 endpoints accounted for
  - `voice_calibration_uat.md` shows `APPROVED` by operator
  - Manual walk-through: `/juno/` Tab 1 shows live 3-section card; `/juno/calendar` + `/juno/viral` show empty states unchanged from Phase 9
- **Max feedback latency:** ~10 seconds (scheduler + frontend pytest/vitest)

---

## Per-Task Verification Map

| Req ID | Behavior | Test Type | Automated Command | File Exists |
|--------|----------|-----------|-------------------|-------------|
| DEF-01 | Tier-1 RSS feeds populated + bozo/entries health-check | unit + integration | `cd scheduler && uv run pytest tests/agents/test_juno_health_check.py -x` | ❌ W0 |
| DEF-01 | Phase-0 endpoint verification script outputs all 15 endpoints | smoke (W0 only) | `bash scripts/verify-juno-rss.sh` | ❌ W0 |
| DEF-02 | SerpAPI `JUNO_SERPAPI_QUERIES` return parseable hits | unit (mocked serpapi.Client) | `cd scheduler && uv run pytest tests/agents/test_juno_daily_summary.py::test_serpapi_canadian_procurement -x` | ❌ W0 (extend stub) |
| DEF-03 | `DEFENCE_NEWS_SYSTEM_PROMPT` contains anti-tactical clause + voice anchor + section structure | unit (string match against prompts.py) | `cd scheduler && uv run pytest tests/companies/test_juno_prompts.py -x` | ❌ W0 |
| DEF-04 | Defence News section ingestion + dedup + 3-7 bullet output | unit (mocked Sonnet) | `cd scheduler && uv run pytest tests/agents/test_juno_daily_summary.py::test_defence_news_section -x` | ❌ W0 (extend stub) |
| DEF-04 | bozo flag + recent-history < 30% threshold flag feeds | unit | `cd scheduler && uv run pytest tests/agents/test_juno_health_check.py::test_health_check_thresholds -x` | ❌ W0 |
| DEF-05 | Canadian Procurement section via SerpAPI + editorial RSS | unit (mocked serpapi + feedparser) | `cd scheduler && uv run pytest tests/agents/test_juno_daily_summary.py::test_canadian_procurement_section -x` | ❌ W0 (extend stub) |
| DEF-06 | Haiku classifier returns DefenceRelevance with correct category + confidence ≥ 0.7 filter | unit (mocked AsyncAnthropic + golden inputs) | `cd scheduler && uv run pytest tests/agents/test_juno_relevance.py -x` | ❌ W0 |
| DEF-06 | confidence < 0.7 items excluded from synthesis | unit | `cd scheduler && uv run pytest tests/agents/test_juno_relevance.py::test_survives_threshold -x` | ❌ W0 |
| DEF-07 | 7 substring patterns detect refusal in first 500 chars | unit | `cd scheduler && uv run pytest tests/agents/test_juno_refusal_detector.py::test_is_refusal_patterns -x` | ❌ W0 |
| DEF-07 | Retry-once with framing nudge on first refusal | integration (mocked AsyncAnthropic) | `cd scheduler && uv run pytest tests/agents/test_juno_refusal_detector.py::test_retry_with_nudge -x` | ❌ W0 |
| DEF-07 | Second refusal → `status='partial'` + section-unavailable copy | integration | `cd scheduler && uv run pytest tests/agents/test_juno_refusal_detector.py::test_second_refusal_fallback -x` | ❌ W0 |
| DEF-08 | SummaryCard renders Juno section titles via `companySectionConfig` | unit (Vitest) | `cd frontend && npm test -- --run src/components/summary/__tests__/SummaryCard.test.tsx` | ⚠ Extend existing |
| DEF-09 | Tab 2/Tab 3 empty-state for Juno (Phase 9 shipped — verify regression-free) | smoke | manual (operator visits `/juno/calendar`, `/juno/viral`, sees empty-state intact) | manual |
| DEF-10 | Voice UAT — operator-approved sample summary | manual-only | manual sign-off in `voice_calibration_uat.md`; cron stays disabled until APPROVED | manual |

*Status legend: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky — populated by executor.*

---

## Wave 0 Requirements

All test files for Phase 10 are NEW (or extensions of existing). Wave 0 must create them in RED state (module-level `pytest.skip(allow_module_level=True)` or `it.skip()` — mirror Phase 8 + Phase 9 pattern). Consumer waves turn them GREEN as production code lands.

- [ ] `scripts/verify-juno-rss.sh` — Phase-0 endpoint verification (D-13/D-14). Verifies all 15 endpoints (12 Tier-1 + war.gov + nato.int + canada.ca defence). Outputs `feed_url|bozo|entries_count|verdict` lines parseable into `phase-10-feed-verification.md`.
- [ ] `scheduler/tests/agents/test_juno_relevance.py` — Haiku classifier unit tests with golden inputs:
  - 1 defence-direct story (e.g., Lockheed F-35 contract win) → expect `is_relevant=true, category='spending policy', confidence >= 0.8`
  - 1 active-conflict story (Ukraine front-line update) → expect `is_relevant=true, category='active conflict', confidence >= 0.8`
  - 1 sanctions story (semiconductor export control) → expect `is_relevant=true, category='sanctions/export controls', confidence >= 0.8`
  - 1 consumer-tech reject (new iPhone announcement) → expect `is_relevant=false, confidence >= 0.8`
  - 1 borderline (drone hobbyist regulation) → expect `confidence ~ 0.5-0.7`
  - 1 below-threshold (sports event with defence sponsor) → expect filtered out at 0.7 threshold
- [ ] `scheduler/tests/agents/test_juno_refusal_detector.py` — 7 substring patterns + retry-once with framing nudge + second-refusal fallback
  - `test_is_refusal_patterns`: each pattern triggers detection
  - `test_retry_with_nudge`: first refusal triggers retry with appended framing nudge
  - `test_second_refusal_fallback`: second refusal → `status='partial'` + section-unavailable copy + `agent_runs.notes` logs `{"refusal_detected": true, "section": "<name>"}`
- [ ] `scheduler/tests/agents/test_juno_health_check.py` — bozo + recent-history threshold tests
  - `test_bozo_flag`: `feedparser.parse` returning `bozo=1` triggers flag
  - `test_empty_entries_flag`: `entries=[]` triggers flag
  - `test_history_threshold`: today's count < 30% of 7-day avg from `agent_runs.notes.feed_entry_counts` triggers flag
  - `test_three_flags_partial`: 3+ feed flags → `status='partial'` on row
- [ ] `scheduler/tests/agents/test_juno_daily_summary.py` — EXTEND existing Phase 9 stub. Cover real synthesis path with mocked Sonnet + serpapi + feedparser. Integration test for live-DB row write.
- [ ] `scheduler/tests/companies/test_juno_prompts.py` (NEW directory) — string-match assertions on `DEFENCE_NEWS_SYSTEM_PROMPT`:
  - Contains "market/industry commentary" substring
  - Contains anti-tactical refusal-trigger words ("force posture", "OOB", "troop movement", "capability gap", "targeting") in the FORBID section
  - Contains 3 section markers (Defence News / Canadian Procurement / World Events)
- [ ] `frontend/src/components/summary/__tests__/SummaryCard.test.tsx` — EXTEND for per-tenant section-field rendering test:
  - Renders `/seva/` SummaryCard → expect "Gold News" title
  - Renders `/juno/` SummaryCard → expect "Defence News" title
- [ ] `frontend/src/config/companySectionConfig.ts` — NEW config map (production code + types; tested via SummaryCard.test.tsx)

**Framework install:** none needed — pytest, pytest-asyncio, Vitest all present.

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Voice UAT — operator-approved sample summary | DEF-10 | Voice quality is qualitative; no automated metric captures "Janes/CSIS desk energy" | Run Sonnet against 5-10 hand-curated stories (see `voice_calibration_uat_corpus.md` planner deliverable); operator reads + approves on 7 pass bars (qualitative voice, anti-tactical clause compliance, source attribution, bullet counts, zero refusals, borderline classification correctness, dual-use exclusion); sign off in `voice_calibration_uat.md`. Cron stays DISABLED until APPROVED. |
| Tab 2/Tab 3 empty-state regression | DEF-09 | Verify Phase 9 deliverables didn't break under Phase 10 changes | Operator visits `/juno/calendar` and `/juno/viral`; confirms empty-state copy ("Coming in v3.1...") still renders; no console errors |
| Populated Juno SummaryCard at 1440×900 | DEF-04, DEF-05, DEF-06, DEF-08 | Real-time rendering of synthesized markdown not testable via jsdom | After cron enable + first production fire: operator opens `/juno/` at 1440×900; sees 3 sections (Defence News, Canadian Procurement, World Events) with 3-7 bullets each in Janes/CSIS voice; no console errors; X-handle pills render correctly if any @handles in the markdown |

---

## Validation Sign-Off

- [ ] All `auto` tasks have `<automated>` verify commands
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all NEW Phase 10 test files (8 items above)
- [ ] No watch-mode flags (`--watch` forbidden)
- [ ] Feedback latency < 15s (pytest + vitest combined)
- [ ] `voice_calibration_uat.md` artifact present at phase close with `APPROVED`
- [ ] `phase-10-feed-verification.md` artifact present at phase close
- [ ] `nyquist_compliant: true` set in frontmatter at plan close

**Approval:** pending
