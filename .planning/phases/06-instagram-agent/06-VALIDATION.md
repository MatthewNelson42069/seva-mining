---
phase: 6
slug: instagram-agent
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-04-02
---

# Phase 6 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 8.0+ with pytest-asyncio 0.23+, asyncio_mode=auto |
| **Config file** | `scheduler/pyproject.toml` [tool.pytest.ini_options] — already configured |
| **Quick run command** | `cd scheduler && uv run pytest tests/test_instagram_agent.py -x -q` |
| **Full suite command** | `cd scheduler && uv run pytest tests/ -q` |
| **Estimated runtime** | ~10 seconds |

---

## Sampling Rate

- **After every task commit:** Run `cd scheduler && uv run pytest tests/test_instagram_agent.py -x -q`
- **After every plan wave:** Run `cd scheduler && uv run pytest tests/ -q`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** ~10 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 6-01-01 | 01 | 0 | INST-01..12 | unit stubs | `pytest tests/test_instagram_agent.py -x -q` | ❌ W0 | ⬜ pending |
| 6-02-01 | 02 | 1 | INST-02 | unit | `pytest tests/test_instagram_agent.py::test_scoring_formula -x` | ❌ W0 | ⬜ pending |
| 6-02-02 | 02 | 1 | INST-02 | unit | `pytest tests/test_instagram_agent.py::test_normalize_followers -x` | ❌ W0 | ⬜ pending |
| 6-02-03 | 02 | 1 | INST-03 | unit | `pytest tests/test_instagram_agent.py::test_engagement_gate -x` | ❌ W0 | ⬜ pending |
| 6-02-04 | 02 | 1 | INST-04 | unit | `pytest tests/test_instagram_agent.py::test_select_top_posts -x` | ❌ W0 | ⬜ pending |
| 6-03-01 | 03 | 1 | INST-05, INST-06 | unit | `pytest tests/test_instagram_agent.py::test_draft_for_post -x` | ❌ W0 | ⬜ pending |
| 6-03-02 | 03 | 1 | INST-06 | unit | `pytest tests/test_instagram_agent.py::test_compliance_blocks_hashtags -x` | ❌ W0 | ⬜ pending |
| 6-03-03 | 03 | 1 | INST-08 | unit | `pytest tests/test_instagram_agent.py::test_compliance_blocks_seva -x` | ❌ W0 | ⬜ pending |
| 6-03-04 | 03 | 1 | INST-08 | unit | `pytest tests/test_instagram_agent.py::test_compliance_fail_safe -x` | ❌ W0 | ⬜ pending |
| 6-04-01 | 04 | 2 | INST-09 | unit | `pytest tests/test_instagram_agent.py::test_retry_logic -x` | ❌ W0 | ⬜ pending |
| 6-04-02 | 04 | 2 | INST-10 | unit | `pytest tests/test_instagram_agent.py::test_health_check_skip_baseline -x` | ❌ W0 | ⬜ pending |
| 6-04-03 | 04 | 2 | INST-10 | unit | `pytest tests/test_instagram_agent.py::test_health_warning_threshold -x` | ❌ W0 | ⬜ pending |
| 6-04-04 | 04 | 2 | INST-11 | unit | `pytest tests/test_instagram_agent.py::test_critical_failure_alert -x` | ❌ W0 | ⬜ pending |
| 6-04-05 | 04 | 2 | INST-11 | unit | `pytest tests/test_instagram_agent.py::test_no_duplicate_alert -x` | ❌ W0 | ⬜ pending |
| 6-05-01 | 05 | 3 | INST-01, INST-12 | unit | `pytest tests/test_instagram_agent.py::test_scheduler_wiring -x` | ❌ W0 | ⬜ pending |
| 6-05-02 | 05 | 3 | INST-12 | unit | `pytest tests/test_instagram_agent.py::test_expiry_12h -x` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `scheduler/tests/test_instagram_agent.py` — 15 test stubs covering INST-01 through INST-12. Must be created before any implementation task.
- [ ] `scheduler/pyproject.toml` — add `"apify-client>=2.5.0"` to dependencies and run `uv sync` to resolve lockfile

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Agent actually scrapes Instagram posts every 4 hours | INST-01 | Requires live Apify API token + active Instagram hashtags | After deployment: confirm agent_runs record created for `instagram_agent` every 4h; check `notes` field has per-hashtag result counts |
| WhatsApp critical failure alert fires | INST-11 | Requires 2 consecutive real runs returning zero results + live Twilio | With live credentials: disable hashtags temporarily, let 2 runs complete, confirm WhatsApp message received |
| Related cards visually linked on dashboard | INST-07 (Senior Agent dedup) | Frontend display is Phase 8 — `related_id` is set in DB | Verify via: `SELECT id, related_id FROM draft_items WHERE platform='instagram' AND related_id IS NOT NULL` |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 15s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
