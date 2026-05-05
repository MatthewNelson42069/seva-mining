---
phase: 1
slug: infrastructure-and-foundation
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-03-30
---

# Phase 1 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 8.x |
| **Config file** | backend/pyproject.toml |
| **Quick run command** | `cd backend && uv run pytest tests/ -x -q` |
| **Full suite command** | `cd backend && uv run pytest tests/ -v` |
| **Estimated runtime** | ~5 seconds |

---

## Sampling Rate

- **After every task commit:** Run `cd backend && uv run pytest tests/ -x -q`
- **After every plan wave:** Run `cd backend && uv run pytest tests/ -v`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 10 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| (Populated during planning) | | | | | | | |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `backend/tests/conftest.py` — shared fixtures, test database connection
- [ ] `backend/tests/test_schema.py` — stubs for INFRA-01, INFRA-02
- [ ] `backend/tests/test_health.py` — stubs for INFRA-09
- [ ] pytest + pytest-asyncio installation via uv

*If none: "Existing infrastructure covers all phase requirements."*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Railway deployment succeeds | INFRA-03, INFRA-04 | External platform deployment | Push to Railway, verify both services show "Active" in dashboard |
| Twilio templates submitted to Meta | WHAT-04 | External API + human verification | Verify templates appear in Twilio console with "Pending" or "Approved" status |
| APScheduler DB lock prevents duplicate | INFRA-05 | Requires two concurrent processes | Start two worker processes, verify only one acquires lock |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 10s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
