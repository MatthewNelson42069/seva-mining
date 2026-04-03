---
phase: 8
slug: dashboard-views-and-digest
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-04-02
---

# Phase 8 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Backend framework** | pytest + pytest-asyncio; asyncio_mode=auto |
| **Backend config** | `[tool.pytest.ini_options]` in `backend/pyproject.toml` |
| **Backend quick run** | `cd backend && uv run pytest tests/test_crud_endpoints.py -x -q` |
| **Backend full suite** | `cd backend && uv run pytest -x -q` |
| **Frontend framework** | Vitest 4.1.2 + Testing Library 16.3.2 + MSW 2.x |
| **Frontend config** | `test` block in `frontend/vite.config.ts` |
| **Frontend quick run** | `cd frontend && npm run test -- --run` |
| **Frontend full suite** | `cd frontend && npm run test -- --run` |
| **Estimated runtime** | ~20 seconds (both suites) |

---

## Sampling Rate

- **After every task commit:** `cd frontend && npm run test -- --run` (for frontend tasks) or `cd backend && uv run pytest tests/test_crud_endpoints.py -x -q` (for backend tasks)
- **After every plan wave:** Run both full suites
- **Before `/gsd:verify-work`:** Both suites must be green
- **Max feedback latency:** ~20 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 8-01-01 | 01 | 0 | ALL | setup | `cd frontend && npm run test -- --run` | ❌ W0 | ⬜ pending |
| 8-01-02 | 01 | 0 | SETT-04 backend | unit | `cd backend && uv run pytest tests/test_crud_endpoints.py -x -q` | ❌ W0 | ⬜ pending |
| 8-02-01 | 02 | 1 | DGST-01 | component | `cd frontend && npm run test -- --run DigestPage` | ❌ W0 | ⬜ pending |
| 8-02-02 | 02 | 1 | DGST-02 | component | `cd frontend && npm run test -- --run DigestPage` | ❌ W0 | ⬜ pending |
| 8-02-03 | 02 | 1 | DGST-03 | component | `cd frontend && npm run test -- --run DigestPage` | ❌ W0 | ⬜ pending |
| 8-03-01 | 03 | 1 | CREV-01 | component | `cd frontend && npm run test -- --run ContentPage` | ❌ W0 | ⬜ pending |
| 8-03-02 | 03 | 1 | CREV-02 | component | `cd frontend && npm run test -- --run ContentPage` | ❌ W0 | ⬜ pending |
| 8-03-03 | 03 | 1 | CREV-03 | component | `cd frontend && npm run test -- --run ContentPage` | ❌ W0 | ⬜ pending |
| 8-03-04 | 03 | 1 | CREV-04 | component | `cd frontend && npm run test -- --run ContentPage` | ❌ W0 | ⬜ pending |
| 8-03-05 | 03 | 1 | CREV-05 | component | `cd frontend && npm run test -- --run ContentPage` | ❌ W0 | ⬜ pending |
| 8-04-01 | 04 | 2 | SETT-01 | component | `cd frontend && npm run test -- --run SettingsPage` | ❌ W0 | ⬜ pending |
| 8-04-02 | 04 | 2 | SETT-02 | component | `cd frontend && npm run test -- --run SettingsPage` | ❌ W0 | ⬜ pending |
| 8-04-03 | 04 | 2 | SETT-03 | component | `cd frontend && npm run test -- --run SettingsPage` | ❌ W0 | ⬜ pending |
| 8-04-04 | 04 | 2 | SETT-04 | component | `cd frontend && npm run test -- --run SettingsPage` | ❌ W0 | ⬜ pending |
| 8-04-05 | 04 | 2 | SETT-05 | component | `cd frontend && npm run test -- --run SettingsPage` | ❌ W0 | ⬜ pending |
| 8-04-06 | 04 | 2 | SETT-06 | component | `cd frontend && npm run test -- --run SettingsPage` | ❌ W0 | ⬜ pending |
| 8-04-07 | 04 | 2 | SETT-07 | component | `cd frontend && npm run test -- --run SettingsPage` | ❌ W0 | ⬜ pending |
| 8-04-08 | 04 | 2 | SETT-08 | component | `cd frontend && npm run test -- --run SettingsPage` | ❌ W0 | ⬜ pending |
| 8-05-01 | 05 | 3 | ALL | integration | `cd frontend && npm run test -- --run && cd backend && uv run pytest -x -q` | ✅ | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

**Frontend (MUST exist before any component implementation):**
- [ ] `frontend/src/mocks/handlers.ts` — extend with all 15 new endpoint handlers (GET /digests/latest, GET /digests/{date}, GET /content/today, GET /queue?platform=content, GET /agent-runs, GET /watchlists, POST /watchlists, PATCH /watchlists/{id}, DELETE /watchlists/{id}, GET /keywords, POST /keywords, PATCH /keywords/{id}, DELETE /keywords/{id}, GET /config, PATCH /config/{key}) — **CRITICAL: must be added before any test, MSW uses `onUnhandledRequest: 'error'`**
- [ ] `frontend/src/pages/DigestPage.test.tsx` — component test stubs covering DGST-01, DGST-02, DGST-03 (use `test.skip()` or `vi.skip()`)
- [ ] `frontend/src/pages/ContentPage.test.tsx` — component test stubs covering CREV-01 through CREV-05
- [ ] `frontend/src/pages/SettingsPage.test.tsx` — component test stubs covering SETT-01 through SETT-08

**Backend (MUST exist before any backend implementation):**
- [ ] `backend/tests/test_crud_endpoints.py` — add `test_list_config`, `test_patch_config_update`, `test_patch_config_create` stubs (the `_TestBase` SQLite infrastructure already exists)

**TypeScript types (MUST be added to types.ts before any API module):**
- [ ] `DailyDigestResponse`, `AgentRunResponse`, `WatchlistCreate`, `WatchlistUpdate`, `WatchlistResponse`, `KeywordCreate`, `KeywordUpdate`, `KeywordResponse`, `ConfigEntry`, `QuotaResponse` — add to `frontend/src/api/types.ts`
- [ ] **CRITICAL:** `KeywordCreate` must use `term: string` (not `keyword: string`) — verified against backend `backend/app/schemas/keyword.py`

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Scoring param changes take effect on next agent run | SETT-04 | Requires live agent run against real DB | Post-deploy: change content_quality_threshold via Settings; confirm next Content Agent run reads new value from DB (check AgentRun.notes) |
| WhatsApp notification timing change | SETT-06 | Requires live Twilio + Senior Agent run | Post-deploy: change whatsapp_daily_digest_time in Settings; confirm Senior Agent sends at updated time |
| Schedule config changes reflected after worker restart | SETT-07 | APScheduler reads config at startup only | Post Phase 9: change schedule via Settings; restart scheduler worker; confirm new cron trigger |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 20s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
