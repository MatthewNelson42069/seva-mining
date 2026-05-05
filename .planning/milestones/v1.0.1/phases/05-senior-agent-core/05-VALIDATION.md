---
phase: 5
slug: senior-agent-core
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-04-02
---

# Phase 5 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 8.0+ with pytest-asyncio 0.23+, asyncio_mode=auto |
| **Config file** | `scheduler/pyproject.toml` [tool.pytest.ini_options] — already configured |
| **Quick run command** | `cd scheduler && uv run pytest tests/test_senior_agent.py -x -q` |
| **Full suite command** | `cd scheduler && uv run pytest tests/ -v` |
| **Estimated runtime** | ~15 seconds |

---

## Sampling Rate

- **After every task commit:** Run `cd scheduler && uv run pytest tests/test_senior_agent.py -x -q`
- **After every plan wave:** Run `cd scheduler && uv run pytest tests/ -v`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** ~15 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 5-01-01 | 01 | 0 | SENR-01..09, WHAT-01..03, WHAT-05 | unit stubs | `pytest tests/test_senior_agent.py -x -q` | ❌ W0 | ⬜ pending |
| 5-02-01 | 02 | 1 | SENR-02 | unit | `pytest tests/test_senior_agent.py::test_jaccard_similarity -x` | ❌ W0 | ⬜ pending |
| 5-02-02 | 02 | 1 | SENR-02 | unit | `pytest tests/test_senior_agent.py::test_extract_fingerprint_tokens -x` | ❌ W0 | ⬜ pending |
| 5-02-03 | 02 | 1 | SENR-02 | unit | `pytest tests/test_senior_agent.py::test_dedup_sets_related_id -x` | ❌ W0 | ⬜ pending |
| 5-02-04 | 02 | 1 | SENR-02 | unit | `pytest tests/test_senior_agent.py::test_dedup_no_match_below_threshold -x` | ❌ W0 | ⬜ pending |
| 5-03-01 | 03 | 1 | SENR-04 | unit | `pytest tests/test_senior_agent.py::test_queue_cap_accepts_below_cap -x` | ❌ W0 | ⬜ pending |
| 5-03-02 | 03 | 1 | SENR-04 | unit | `pytest tests/test_senior_agent.py::test_queue_cap_displaces_lowest -x` | ❌ W0 | ⬜ pending |
| 5-03-03 | 03 | 1 | SENR-04 | unit | `pytest tests/test_senior_agent.py::test_queue_cap_discards_new_item -x` | ❌ W0 | ⬜ pending |
| 5-03-04 | 03 | 1 | SENR-04 | unit | `pytest tests/test_senior_agent.py::test_queue_cap_tiebreak_expires_at -x` | ❌ W0 | ⬜ pending |
| 5-04-01 | 04 | 2 | SENR-05, SENR-09 | unit | `pytest tests/test_senior_agent.py::test_expiry_sweep_marks_expired -x` | ❌ W0 | ⬜ pending |
| 5-04-02 | 04 | 2 | WHAT-03 | unit | `pytest tests/test_senior_agent.py::test_expiry_alert_fires -x` | ❌ W0 | ⬜ pending |
| 5-04-03 | 04 | 2 | WHAT-03 | unit | `pytest tests/test_senior_agent.py::test_expiry_alert_no_double_send -x` | ❌ W0 | ⬜ pending |
| 5-04-04 | 04 | 2 | WHAT-02 | unit | `pytest tests/test_senior_agent.py::test_breaking_news_alert_fires -x` | ❌ W0 | ⬜ pending |
| 5-04-05 | 04 | 2 | WHAT-02 | unit | `pytest tests/test_senior_agent.py::test_breaking_news_alert_no_fire -x` | ❌ W0 | ⬜ pending |
| 5-04-06 | 04 | 2 | WHAT-02 | unit | `pytest tests/test_senior_agent.py::test_engagement_alert_watchlist_early -x` | ❌ W0 | ⬜ pending |
| 5-04-07 | 04 | 2 | WHAT-02 | unit | `pytest tests/test_senior_agent.py::test_engagement_alert_watchlist_viral -x` | ❌ W0 | ⬜ pending |
| 5-04-08 | 04 | 2 | WHAT-02 | unit | `pytest tests/test_senior_agent.py::test_engagement_alert_nonwatchlist_viral -x` | ❌ W0 | ⬜ pending |
| 5-04-09 | 04 | 2 | WHAT-02 | unit | `pytest tests/test_senior_agent.py::test_engagement_alert_no_repeat_viral -x` | ❌ W0 | ⬜ pending |
| 5-05-01 | 05 | 3 | SENR-06, SENR-07, WHAT-01 | unit | `pytest tests/test_senior_agent.py::test_morning_digest_assembly -x` | ❌ W0 | ⬜ pending |
| 5-05-02 | 05 | 3 | WHAT-01 | unit | `pytest tests/test_senior_agent.py::test_morning_digest_whatsapp_send -x` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `scheduler/tests/test_senior_agent.py` — 19 test stubs covering SENR-01..09 and WHAT-01..03, WHAT-05 + engagement alert behaviors. Must be created before any implementation task.
- [ ] `scheduler/models/daily_digest.py` — scheduler mirror of backend DailyDigest model (table already in DB from migration 0001; scheduler model never created)
- [ ] `scheduler/services/__init__.py` — new services directory init file
- [ ] `scheduler/services/whatsapp.py` — WhatsApp service mirror (same SIDs, same asyncio.to_thread pattern as backend)
- [ ] `twilio>=9.0` added to `scheduler/pyproject.toml` dependencies — scheduler is a separate Railway service; Twilio missing from its deps
- [ ] `backend/alembic/versions/0004_add_engagement_alert_columns.py` — adds `engagement_alert_level VARCHAR(20) NULLABLE` and `alerted_expiry_at TIMESTAMPTZ NULLABLE` to `draft_items`

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| WhatsApp morning digest arrives at correct time | WHAT-01 | Requires live Twilio credentials + Meta-approved template + real 8am trigger | After deployment: confirm WhatsApp message received at 8am on day after deploy; check `daily_digests.whatsapp_sent_at` populated |
| WhatsApp engagement alert fires within 30 min of Twitter Agent run | WHAT-02 | Requires live X API + real qualifying post + end-to-end scheduler run | With live credentials: let Twitter Agent run, confirm WhatsApp alert arrives within next expiry sweep cycle |
| Dashboard shows related cards visually linked | SENR-02 | Frontend display wired in Phase 3/8 — `related_id` set in DB but visual linking is frontend code | Verify `related_id` is non-null on deduped items via: `SELECT id, related_id FROM draft_items WHERE related_id IS NOT NULL` |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 15s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
