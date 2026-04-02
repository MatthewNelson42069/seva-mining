---
phase: 7
slug: content-agent
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-04-02
---

# Phase 7 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 8.0+ with pytest-asyncio 0.23+, asyncio_mode=auto |
| **Config file** | `scheduler/pyproject.toml` [tool.pytest.ini_options] — already configured |
| **Quick run command** | `cd scheduler && uv run pytest tests/test_content_agent.py -x -q` |
| **Full suite command** | `cd scheduler && uv run pytest tests/ -q` |
| **Estimated runtime** | ~10 seconds |

---

## Sampling Rate

- **After every task commit:** Run `cd scheduler && uv run pytest tests/test_content_agent.py -x -q`
- **After every plan wave:** Run `cd scheduler && uv run pytest tests/ -q`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** ~10 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 7-01-01 | 01 | 0 | CONT-01..17 | unit stubs | `pytest tests/test_content_agent.py -x -q` | ❌ W0 | ⬜ pending |
| 7-02-01 | 02 | 1 | CONT-02 | unit | `pytest tests/test_content_agent.py::test_rss_feed_parsing -x` | ❌ W0 | ⬜ pending |
| 7-02-02 | 02 | 1 | CONT-03 | unit | `pytest tests/test_content_agent.py::test_serpapi_parsing -x` | ❌ W0 | ⬜ pending |
| 7-02-03 | 02 | 1 | CONT-04 | unit | `pytest tests/test_content_agent.py::test_url_deduplication -x` | ❌ W0 | ⬜ pending |
| 7-02-04 | 02 | 1 | CONT-04 | unit | `pytest tests/test_content_agent.py::test_headline_deduplication -x` | ❌ W0 | ⬜ pending |
| 7-02-05 | 02 | 1 | CONT-05 | unit | `pytest tests/test_content_agent.py::test_recency_score -x` | ❌ W0 | ⬜ pending |
| 7-02-06 | 02 | 1 | CONT-05 | unit | `pytest tests/test_content_agent.py::test_credibility_score -x` | ❌ W0 | ⬜ pending |
| 7-02-07 | 02 | 1 | CONT-05 | unit | `pytest tests/test_content_agent.py::test_final_score_formula -x` | ❌ W0 | ⬜ pending |
| 7-02-08 | 02 | 1 | CONT-06 | unit | `pytest tests/test_content_agent.py::test_select_top_story -x` | ❌ W0 | ⬜ pending |
| 7-03-01 | 03 | 2 | CONT-07 | unit | `pytest tests/test_content_agent.py::test_no_story_flag -x` | ❌ W0 | ⬜ pending |
| 7-03-02 | 03 | 2 | CONT-08 | unit | `pytest tests/test_content_agent.py::test_article_fetch_fallback -x` | ❌ W0 | ⬜ pending |
| 7-03-03 | 03 | 2 | CONT-10 | unit | `pytest tests/test_content_agent.py::test_thread_draft_structure -x` | ❌ W0 | ⬜ pending |
| 7-04-01 | 04 | 2 | CONT-14/15 | unit | `pytest tests/test_content_agent.py::test_compliance_fail_seva_mining -x` | ❌ W0 | ⬜ pending |
| 7-04-02 | 04 | 2 | CONT-16 | unit | `pytest tests/test_content_agent.py::test_compliance_failsafe -x` | ❌ W0 | ⬜ pending |
| 7-04-03 | 04 | 2 | CONT-17 | unit | `pytest tests/test_content_agent.py::test_draft_item_fields -x` | ❌ W0 | ⬜ pending |
| 7-04-04 | 04 | 2 | CONT-17 | unit | `pytest tests/test_content_agent.py::test_content_bundle_link -x` | ❌ W0 | ⬜ pending |
| 7-05-01 | 05 | 3 | CONT-01 | unit | `pytest tests/test_content_agent.py::test_scheduler_wiring -x` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `scheduler/tests/test_content_agent.py` — 15 test stubs covering CONT-01 through CONT-17. Must be created before any implementation task. Use `pytest.skip()` BEFORE lazy imports (same pattern as `test_instagram_agent.py`).
- [ ] `scheduler/models/content_bundle.py` — scheduler mirror of `backend/app/models/content_bundle.py`, using `from models.base import Base`
- [ ] `scheduler/seed_content_data.py` — seeds 4 `content_*` config keys (mirrors `seed_instagram_data.py`)
- [ ] New deps added to `scheduler/pyproject.toml`: `uv add "feedparser>=6.0" "beautifulsoup4>=4.12" "serpapi>=1.0" "httpx>=0.27"` (run `uv sync --all-extras` to preserve dev deps)

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Agent actually runs at 6am daily and ingests RSS + SerpAPI | CONT-01 | Requires live SERPAPI_API_KEY + real RSS feeds | After deploy: confirm `agent_runs` record created for `content_agent` at 6am; check `notes` field has story counts |
| SerpAPI quota doesn't 429 after first 10 days | CONT-03 | Requires verifying SerpAPI plan tier | Pre-deploy: confirm account is on Developer plan (5,000/mo). Basic plan (100/mo) overruns in ~10 days |
| World Gold Council feed returns results | CONT-02 | Feed may require auth; can't verify without live HTTP | Post-deploy Wave 1: test `feedparser.parse("https://www.gold.org/goldhub/news/feed")` returns >0 entries |
| ContentBundle visible in dashboard | CONT-17 | Phase 8 renders it | Phase 8 verification: confirm `content_bundles` table has record with `no_story_flag=False` and `compliance_passed=True` |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 15s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
