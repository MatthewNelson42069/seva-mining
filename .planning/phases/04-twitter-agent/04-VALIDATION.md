---
phase: 4
slug: twitter-agent
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-04-01
---

# Phase 4 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest + pytest-asyncio 0.23, asyncio_mode=auto |
| **Config file** | `scheduler/pyproject.toml` [tool.pytest.ini_options] — already configured |
| **Quick run command** | `cd scheduler && uv run pytest tests/test_twitter_agent.py -x -q` |
| **Full suite command** | `cd scheduler && uv run pytest tests/ -v` |
| **Estimated runtime** | ~15 seconds |

---

## Sampling Rate

- **After every task commit:** Run `cd scheduler && uv run pytest tests/test_twitter_agent.py -x -q`
- **After every plan wave:** Run `cd scheduler && uv run pytest tests/ -v`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** ~15 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 4-01-01 | 01 | 0 | TWIT-01..14 | unit stubs | `pytest tests/test_twitter_agent.py -x -q` | ❌ W0 | ⬜ pending |
| 4-02-01 | 02 | 1 | TWIT-01 | unit | `pytest tests/test_twitter_agent.py::test_scheduler_wiring -x` | ❌ W0 | ⬜ pending |
| 4-02-02 | 02 | 1 | TWIT-02, TWIT-03 | unit | `pytest tests/test_twitter_agent.py::test_scoring_formula -x` | ❌ W0 | ⬜ pending |
| 4-02-03 | 02 | 1 | TWIT-04 | unit | `pytest tests/test_twitter_agent.py::test_engagement_gate -x` | ❌ W0 | ⬜ pending |
| 4-02-04 | 02 | 1 | TWIT-05 | unit | `pytest tests/test_twitter_agent.py::test_recency_decay -x` | ❌ W0 | ⬜ pending |
| 4-02-05 | 02 | 1 | TWIT-06 | unit | `pytest tests/test_twitter_agent.py::test_top_n_selection -x` | ❌ W0 | ⬜ pending |
| 4-03-01 | 03 | 2 | TWIT-07, TWIT-08 | unit (mock) | `pytest tests/test_twitter_agent.py::test_draft_types -x` | ❌ W0 | ⬜ pending |
| 4-03-02 | 03 | 2 | TWIT-09, TWIT-10 | unit (mock) | `pytest tests/test_twitter_agent.py::test_compliance_separate_call -x` | ❌ W0 | ⬜ pending |
| 4-03-03 | 03 | 2 | TWIT-14 | unit (mock) | `pytest tests/test_twitter_agent.py::test_rationale_populated -x` | ❌ W0 | ⬜ pending |
| 4-04-01 | 04 | 3 | TWIT-11, TWIT-12, TWIT-13 | unit | `pytest tests/test_twitter_agent.py::test_quota_counter_increments -x` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `scheduler/tests/test_twitter_agent.py` — stub file covering TWIT-01 through TWIT-14 (all tests, mock tweepy + mock anthropic + mock DB). Must be created before any implementation task.
- [ ] Alembic migration for `config` key-value table — required for quota counter tests against real DB
- [ ] Alembic migration for `watchlists.platform_user_id` column — required for watchlist lookup optimization
- [ ] `tweepy` added to `scheduler/pyproject.toml` dependencies — required for imports to work in tests
- [ ] `anthropic` added to `scheduler/pyproject.toml` dependencies — required for imports to work in tests

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Gold topic filter Claude fallback correctly classifies borderline tweets | TWIT-01 | Requires real Claude API call + real tweet content to verify classification accuracy | Run agent once with live credentials; check agent_runs.notes for borderline classification log entries |
| Dashboard quota display shows correct count | TWIT-13 | Frontend display wired in Phase 8 Settings page — not built in Phase 4 | Verify quota counter increments in DB: `SELECT value FROM config WHERE key = 'twitter_quota_month_YYYY_MM'` |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 15s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
