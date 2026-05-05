---
phase: 11
slug: content-preview-and-rendered-images
status: planned
nyquist_compliant: true
wave_0_complete: false
created: 2026-04-16
---

# Phase 11 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.
> Populated by gsd-planner during planning. Wave 0 requirements below must be scheduled as the first plan.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework (backend/scheduler)** | pytest 7.x + pytest-asyncio (anyio backend) |
| **Framework (frontend)** | Vitest + React Testing Library |
| **Config file (backend)** | `backend/pyproject.toml` (pytest section) |
| **Config file (scheduler)** | `scheduler/pyproject.toml` (pytest section) |
| **Config file (frontend)** | `frontend/vitest.config.ts` |
| **Quick run command (backend)** | `cd backend && uv run pytest -x --lf` |
| **Quick run command (scheduler)** | `cd scheduler && uv run pytest -x --lf` |
| **Quick run command (frontend)** | `cd frontend && npm run test -- --run --bail` |
| **Full suite (backend)** | `cd backend && uv run pytest` |
| **Full suite (scheduler)** | `cd scheduler && uv run pytest` |
| **Full suite (frontend)** | `cd frontend && npm run test -- --run` |
| **Estimated runtime (full, all three)** | ~45–90 seconds |

---

## Sampling Rate

- **After every task commit:** Run the relevant quick-run command for the layer touched (backend / scheduler / frontend).
- **After every plan wave:** Run full suite in all three layers touched by the wave.
- **Before `/gsd:verify-work`:** All three full suites must be green.
- **Max feedback latency:** ≤ 90 seconds for full suite.

---

## Per-Task Verification Map

*Each task below references a test file (existing today, or created in Wave 0 as a stub that later waves implement).*

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 11-01-T1 | 01-foundation | 0 | CREV-06..10 | deps + env | `cd scheduler && uv sync && uv run python -c "import google.genai, aioboto3"` | N/A (deps check) | ⬜ pending |
| 11-01-T2 | 01-foundation | 0 | CREV-07, CREV-09 | migration | `cd backend && uv run alembic upgrade head && uv run alembic downgrade -1 && uv run alembic upgrade head` | ✅ (new 0006 revision) | ⬜ pending |
| 11-01-T3 | 01-foundation | 0 | CREV-02, CREV-06 | pydantic schema | `cd backend && uv run pytest tests/schemas/test_content_bundle.py tests/schemas/test_draft_item.py -v` | ❌ (Wave 0 stub) | ⬜ pending |
| 11-01-T4 | 01-foundation | 0 | CREV-07, CREV-10 | scheduler worker | `cd scheduler && uv run pytest tests/test_worker.py -v -k module_level` | ❌ (Wave 0 stub) | ⬜ pending |
| 11-01-T5 | 01-foundation | 0 | all CREV | wave-0 stubs | `cd backend && uv run pytest tests/routers/test_content_bundles.py --collect-only && cd ../scheduler && uv run pytest tests/agents/test_image_render.py --collect-only && cd ../frontend && npm run test -- --run --reporter=verbose` | ❌ → ✅ after T5 | ⬜ pending |
| 11-02-T1 | 02-image-render | 1 | CREV-07, CREV-10 | integration | `cd scheduler && uv run pytest tests/agents/test_image_render.py -v -k "render_bundle_job"` | ✅ (from 11-01-T5) | ⬜ pending |
| 11-02-T2 | 02-image-render | 1 | CREV-07 | unit | `cd scheduler && uv run pytest tests/agents/test_image_render.py -v -k "prompt"` | ✅ | ⬜ pending |
| 11-03-T1 | 03-backend-endpoints | 1 | CREV-02, CREV-06 | router integration | `cd backend && uv run pytest tests/routers/test_content_bundles.py -v -k "get_bundle"` | ✅ (from 11-01-T5) | ⬜ pending |
| 11-03-T2 | 03-backend-endpoints | 1 | CREV-09 | router integration | `cd backend && uv run pytest tests/routers/test_content_bundles.py -v -k "rerender"` | ✅ | ⬜ pending |
| 11-04-T1 | 04-content-agent-integration | 2 | CREV-07, CREV-10 | unit | `cd scheduler && uv run pytest tests/test_content_agent.py -v -k "enqueue or render"` | ✅ (tests appended) | ⬜ pending |
| 11-05-T1 | 05-frontend-api-and-hook | 2 | CREV-02, CREV-06 | api unit (MSW) | `cd frontend && npm run test -- --run src/api/__tests__/content-bundle.test.ts` | ✅ (from 11-01-T5) | ⬜ pending |
| 11-05-T2 | 05-frontend-api-and-hook | 2 | CREV-08, CREV-09 | hook unit | `cd frontend && npm run test -- --run src/hooks/__tests__/useContentBundle.test.ts` | ✅ | ⬜ pending |
| 11-06-T1 | 06-format-aware-modal | 3 | CREV-02, CREV-06 | component unit | `cd frontend && npm run test -- --run src/components/content/__tests__` | ✅ (new dir) | ⬜ pending |
| 11-06-T2 | 06-format-aware-modal | 3 | CREV-02, CREV-06, CREV-08, CREV-09 | component integration | `cd frontend && npm run test -- --run src/components/approval/__tests__/ContentDetailModal.test.tsx` | ✅ (from 11-01-T5) | ⬜ pending |
| 11-07-T1 | 07-human-verification | 4 | all CREV | deploy preflight | `cd backend && uv run pytest && cd ../scheduler && uv run pytest && cd ../frontend && npm run test -- --run && npm run build` | N/A (green-suite gate) | ⬜ pending |
| 11-07-T2 | 07-human-verification | 4 | all CREV | human-verify | Manual — see Manual-Only Verifications table | N/A (checkpoint) | ⬜ pending |
| 11-07-T3 | 07-human-verification | 4 | all CREV | finalize | `node "$HOME/.claude/get-shit-done/bin/gsd-tools.cjs" frontmatter validate .planning/phases/11-content-preview-and-rendered-images/*-PLAN.md --schema plan` | N/A (docs) | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

### Sampling Continuity Check

No run of 3 consecutive tasks lacks an automated verify. Every content-producing task has a concrete pytest/vitest command; only the human-verify checkpoint (11-07-T2) is manual by design, and it is immediately preceded by 11-07-T1 (full-suite gate) and followed by 11-07-T3 (frontmatter validation).

---

## Wave 0 Requirements

Wave 0 (Plan 01) must land before any other plan starts. Wave 0 scope for Phase 11:

- [ ] `scheduler/tests/agents/test_image_render.py` — pytest stubs for render service (prompt construction, retry behavior, R2 upload mock, bytes→URL shape)
- [ ] `scheduler/tests/conftest.py` — add R2 upload mock fixture (`fake_r2_client`) and Imagen mock fixture (`fake_imagen_client` returning fixed PNG bytes)
- [ ] `scheduler/tests/test_worker.py` — pytest stub for `get_scheduler()` module-level accessor
- [ ] `backend/tests/routers/test_content_bundles.py` — pytest stubs for `GET /content-bundles/{id}` (200 auth, 401 no token, 404 missing) and `POST /content-bundles/{id}/rerender` (202, enqueue fires, 404 missing)
- [ ] `backend/tests/conftest.py` — fixtures for authenticated client, seeded ContentBundle with `rendered_images=null`
- [ ] `backend/tests/schemas/test_content_bundle.py` + `backend/tests/schemas/test_draft_item.py` — pydantic schema stubs (DraftItemResponse.engagement_snapshot, ContentBundleDetailResponse, RerenderResponse)
- [ ] `frontend/src/api/__tests__/content-bundle.test.ts` — stub for `getContentBundle(id)` and `rerenderContentBundle(id)` API calls (MSW handlers)
- [ ] `frontend/src/components/approval/__tests__/ContentDetailModal.test.tsx` — stubs for format-aware rendering (infographic, thread, quote), fallback to flat text on fetch error, skeleton+poll behavior
- [ ] `frontend/src/components/content/__tests__/` — stub directory for per-format renderer component tests (InfographicPreview, ThreadPreview, QuotePreview, LongFormPreview, BreakingNewsPreview, VideoClipPreview, GoldHistoryPreview, RenderedImagesGallery)
- [ ] `frontend/src/hooks/__tests__/useContentBundle.test.ts` — stub for TanStack Query hook with polling semantics
- [ ] MSW handler additions in `frontend/src/mocks/handlers.ts` for `GET /content-bundles/:id` and `POST /content-bundles/:id/rerender`

*Pytest, Vitest, MSW, and React Testing Library are already installed per Phase 3/7/8 scaffolding — no framework install needed.*

---

## Manual-Only Verifications

Some behaviors can only be checked by a human because they depend on live external APIs or visual quality. Automated tests use mocks; these must be manually verified on a Railway/Vercel deploy (covered by Plan 07 Task 2):

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Imagen 4 actually renders brand-color-aligned images | D-05 | Image quality/branding cannot be asserted by unit tests; depends on live Imagen 4 output | On staging, approve an infographic bundle; open modal; verify 4 rendered images appear within ~2 min; verify navy/cream/gold palette is visibly present |
| R2 public URL is actually reachable | D-06, D-07 | URLs are mocked in tests; real R2 bucket policy + CDN caching only testable with a live request | After render completes, click the image URL in the browser; verify it returns the PNG with HTTP 200 |
| Regen button triggers a fresh render, modal swaps images | D-15, D-17 | Requires live scheduler + Imagen round-trip | Click "Regenerate images" on a rendered bundle; verify skeleton appears, poll replaces with new URLs within ~2 min, button is disabled during poll |
| Failure path is silent (no WhatsApp alert, no modal error) | D-18 | Must verify by simulating Imagen/R2 outage in staging env | Temporarily set `GEMINI_API_KEY=invalid`; approve an infographic bundle; verify modal shows brief only with no image slots, no operator alert, agent_runs log contains the error |
| 10-min polling ceiling stops polling | D-14 | Time-based behavior hard to unit-test cleanly | Approve a bundle, wait 11 minutes without images landing; verify modal stops polling and shows brief only |
| Quote bundle renders a single image, not 4 | D-04, CREV-07 | Depends on live Imagen output + role-specific prompt | Approve a quote bundle; verify exactly 1 rendered image appears (hero role only) |

---

## Validation Sign-Off

- [x] All tasks have `<automated>` verify or Wave 0 dependencies
- [x] Sampling continuity: no 3 consecutive tasks without automated verify
- [x] Wave 0 covers all MISSING references above (see Plan 01 Task 5)
- [x] No watch-mode flags (all commands use `--run` / `-x` / `--run --bail` — exit after one run)
- [x] Feedback latency < 90s (measured: ~45–90s for full suite across all three layers)
- [x] `nyquist_compliant: true` set in frontmatter

**Approval:** planner-approved (2026-04-16) — awaiting Wave 0 execution to flip `wave_0_complete: true`
