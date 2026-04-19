---
phase: 11-content-preview-and-rendered-images
verified: 2026-04-19T23:00:00Z
status: passed
score: 6/6 success criteria verified
re_verification: false
---

# Phase 11: Content Preview and Rendered Images — Verification Report

**Phase Goal:** Operator clicks any Content queue card and sees the full structured brief for every content format plus AI-rendered image previews for infographic and quote formats; no more "just a headline" modals

**Verified:** 2026-04-19T23:00:00Z
**Status:** PASSED
**Re-verification:** No — initial verification

---

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | `GET /content-bundles/{id}` returns full bundle for authenticated operator | PASS | `backend/app/routers/content_bundles.py` lines 101-111; JWT via `dependencies=[Depends(get_current_user)]` on APIRouter (line 97); 404 on missing bundle |
| 2 | ContentDetailModal fetches via `engagement_snapshot.content_bundle_id`; format-aware preview; fallback on failure | PASS | `ContentDetailModal.tsx` line 37 extracts `content_bundle_id`; switch dispatch lines 131-148; `FlatTextFallback` at lines 151-162 covers `!bundleId`, `isError`, and unknown `content_type` |
| 3 | Background job generates AI-rendered images (infographic 4, quote 2) and uploads to R2 | PASS | `image_render_agent.py` ROLES_BY_FORMAT lines 40-51; `_generate_with_retry` uses Imagen 4 (line 166); `_upload_to_r2` uses aioboto3 (lines 200-222) |
| 4 | `rendered_images` JSONB column on ContentBundle via Alembic migration; modal displays inline | PASS | Migration `0006_add_rendered_images.py` lines 17-21; both model files confirmed at line 22; `RenderedImagesGallery.tsx` renders images in grid (lines 80-101) |
| 5 | Background render independent from Content Agent cron; modal polls for updates | PASS | `_enqueue_render_job_if_eligible` in `content_agent.py` lines 117-158 uses APScheduler `DateTrigger` (fire-and-forget, no `await`); `useContentBundle.ts` `refetchInterval` polls every 5s until images land or 10-min ceiling (lines 13-22) |
| 6 | Render failures logged per-image; do not crash agent run; modal gracefully hides slots when URLs absent | PASS | `_generate_with_retry` logs ERROR after 3 attempts (lines 193-196); `render_bundle_job` outer try/except (lines 67-76) never raises; `_enqueue_render_job_if_eligible` bare `except Exception` (line 152) swallows scheduler failures; `RenderedImagesGallery` returns null for non-visual formats (line 38), hides skeletons when `ageMinutes >= 10` (line 42) |

**Score:** 6/6 truths verified

---

## Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `backend/alembic/versions/0006_add_rendered_images.py` | Alembic migration adding `rendered_images` JSONB | VERIFIED | Lines 17-25; `down_revision = "0005"`, `revision = "0006"` |
| `backend/app/models/content_bundle.py` | `rendered_images` JSONB column | VERIFIED | Line 22: `rendered_images = Column(JSONB, nullable=True)` |
| `scheduler/models/content_bundle.py` | `rendered_images` JSONB column (mirror) | VERIFIED | Line 22: identical column definition |
| `backend/app/routers/content_bundles.py` | GET + POST/rerender endpoints with JWT | VERIFIED | 146 lines; both endpoints present; JWT at router level |
| `backend/app/main.py` | `content_bundles_router` registered | VERIFIED | Lines 14, 57: imported and registered |
| `backend/app/schemas/content_bundle.py` | `ContentBundleDetailResponse`, `RenderedImage`, `RerenderResponse` | VERIFIED | Lines 23-50 |
| `scheduler/agents/image_render_agent.py` | `render_bundle_job`, `ROLES_BY_FORMAT`, brand palette, retry | VERIFIED | 317 lines; all structures present |
| `scheduler/agents/content_agent.py` | `_enqueue_render_job_if_eligible` + 3 call sites | VERIFIED | Lines 109-158 (helper), 1447, 1561, 1624 (call sites) |
| `scheduler/worker.py` | Module-level `_scheduler` + `get_scheduler()` accessor | VERIFIED | Lines 36-47 |
| `frontend/src/hooks/useContentBundle.ts` | `useContentBundle` + `useRerenderContentBundle` | VERIFIED | 35 lines; 5s poll interval, 10-min ceiling |
| `frontend/src/api/content.ts` | `getContentBundle()` + `rerenderContentBundle()` | VERIFIED | Lines 12-24 |
| `frontend/src/api/types.ts` | `ContentBundleDetailResponse`, `RenderedImage`, `RerenderResponse` | VERIFIED | Lines 53-79 |
| `frontend/src/components/approval/ContentDetailModal.tsx` | Format-aware dispatcher with fallback | VERIFIED | 163 lines; switch on `content_type`; FlatTextFallback |
| `frontend/src/components/content/RenderedImagesGallery.tsx` | Skeleton+poll UX; regen button; graceful fallback | VERIFIED | 107 lines; skeleton, polling, empty-state logic |
| `frontend/src/components/content/InfographicPreview.tsx` | Extended with optional `images` prop | VERIFIED | Lines 18-19: `images?: RenderedImage[] | null`; renders at lines 71-80 |
| `frontend/src/components/content/ThreadPreview.tsx` | Thread format renderer | VERIFIED | Created (69 lines) |
| `frontend/src/components/content/LongFormPreview.tsx` | Long-form renderer | VERIFIED | Created (44 lines) |
| `frontend/src/components/content/BreakingNewsPreview.tsx` | Breaking news renderer | VERIFIED | Created (64 lines) |
| `frontend/src/components/content/QuotePreview.tsx` | Quote renderer | VERIFIED | Created (89 lines) |
| `frontend/src/components/content/VideoClipPreview.tsx` | Video clip renderer | VERIFIED | Created (79 lines) |

---

## Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `content_agent.py` `_enqueue_render_job_if_eligible` | `image_render_agent.render_bundle_job` | Late import inside helper + APScheduler DateTrigger | WIRED | `content_agent.py` line 140: `from agents.image_render_agent import render_bundle_job`; line 144: passed as `scheduler.add_job(render_bundle_job, ...)` |
| `content_bundles.py` POST rerender endpoint | `image_render_agent.render_bundle_job` | `importlib.util.spec_from_file_location` shim + `asyncio.create_task` | WIRED | Lines 44-87 (shim + helper); line 138: `asyncio.create_task(render_fn(str(bundle_id)))`. Verified in Plan 07 smoke check as `seva_image_render_agent.render_bundle_job` (real, not no-op) |
| `ContentDetailModal.tsx` | `useContentBundle` hook | `bundleId` extracted from `engagement_snapshot.content_bundle_id` | WIRED | Line 37: extracts `content_bundle_id`; line 41: `useContentBundle(bundleId ?? null)` |
| `useContentBundle.ts` | `GET /content-bundles/{id}` | TanStack Query `queryFn` → `getContentBundle()` → `apiFetch` | WIRED | `useContentBundle.ts` line 11; `content.ts` lines 12-16 |
| `useRerenderContentBundle` | `POST /content-bundles/{id}/rerender` | `useMutation` → `rerenderContentBundle()` → `apiFetch` | WIRED | `useContentBundle.ts` lines 27-34; `content.ts` lines 18-24 |
| `DraftItem.engagement_snapshot` | `content_bundle_id` populated | `build_draft_item()` in `content_agent.py` | WIRED | `content_agent.py` line 539: `engagement_snapshot={"content_bundle_id": str(content_bundle.id)}`; backend schema line 37: `engagement_snapshot: Optional[Any] = None` exposed to frontend |
| `render_bundle_job` | Neon DB `content_bundles.rendered_images` | `async_sessionmaker(engine)` → `session.commit()` | WIRED | `image_render_agent.py` lines 65-66, 142-143 |
| `render_bundle_job` | Cloudflare R2 | `aioboto3.Session().client('s3', region_name='auto')` | WIRED | Lines 207-222 in `image_render_agent.py` |

---

## Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
|----------|---------------|--------|-------------------|--------|
| `ContentDetailModal.tsx` | `bundle` | `useContentBundle(bundleId)` → GET `/content-bundles/{id}` → DB query via SQLAlchemy | Yes — `select(ContentBundle).where(ContentBundle.id == bundle_id)` in router, returns full ORM object | FLOWING |
| `RenderedImagesGallery.tsx` | `renderedImages` | `bundle.rendered_images` from the same GET response; populated by `render_bundle_job` writing to DB | Yes — `render_bundle_job` writes real R2 URLs to `bundle.rendered_images` via session.commit | FLOWING |
| `useContentBundle.ts` polling | `rendered_images.length` | TanStack Query refetches every 5s until images.length > 0 | Yes — stops when real URLs arrive; stops at 10-min ceiling if not | FLOWING |

---

## Behavioral Spot-Checks

Step 7b: SKIPPED for in-process logic — requires live Imagen API key and R2 credentials to invoke the actual render pipeline. Human verification (Plan 07) covered this with the 5 manual staging checks including live render confirmation. Smoke tests run at pre-checkpoint showed `alembic current` = `0006 (head)` and `_get_render_bundle_job()` returning real function (not no-op stub).

---

## Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|------------|-------------|--------|----------|
| CREV-06 | 11-01 (declared), 11-03/11-06 (implemented) | Format-aware structured brief rendering in modal | SATISFIED | ContentDetailModal switch dispatch; 6 format renderer components |
| CREV-07 | 11-02 (implemented), 11-04 (wired) | AI-rendered images for infographic (4) and quote (2) stored in R2 | SATISFIED | `image_render_agent.py` ROLES_BY_FORMAT + R2 upload |
| CREV-08 | 11-05/11-06 (implemented) | Images appear in modal with skeleton+poll UX; graceful failure fallback | SATISFIED | `RenderedImagesGallery.tsx` skeleton logic; poll ceiling; null/empty guard |
| CREV-09 | 11-03/11-06 (implemented) | Operator can trigger fresh render via "Regenerate images" button | SATISFIED | `RenderedImagesGallery.tsx` Regen button → `useRerenderContentBundle` mutation → POST `/content-bundles/{id}/rerender` |
| CREV-10 | 11-02/11-04 (implemented) | Render job independent from Content Agent cron; failures do not block bundle persistence | SATISFIED | `_enqueue_render_job_if_eligible` fire-and-forget with bare except; `render_bundle_job` never raises |

All 5 CREV requirements (CREV-06..CREV-10) marked `[x] Complete` in `.planning/REQUIREMENTS.md` traceability table (lines 284-288).

---

## Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| `content_agent.py` | 1561 | `_enqueue_render_job_if_eligible(vc_bundle)` called for `video_clip` bundles that are immediately no-op'd inside the helper (video_clip not in `_RENDER_FORMATS`) | Info | Zero functional impact; documented intentional decision in Plan 04 SUMMARY: "wiring the site means future format additions automatically flow through without touching three separate locations" |
| `content_bundles.py` | 44-87 | `_get_render_bundle_job()` re-loads the module on every POST rerender call (not cached) | Info | Performance: each regen request re-executes `importlib.util.spec_from_file_location`. Not a correctness issue; rerender is operator-triggered (rare). Acceptable trade-off for monkeypatching support in tests. |
| `image_render_agent.py` | 107 | `genai.Client()` instantiated inside `_render_and_persist` on every job invocation | Info | Client is lightweight to construct. No state leak across jobs since each job gets a fresh session. Acceptable for a one-off background job. |

No blockers. No stubs. No hardcoded empty data flowing to user-visible rendering paths.

---

## Integration Gap Analysis

### Gap 1 (Resolved): backend → scheduler cross-process import

**Issue identified in Plan 03:** `scheduler/agents/__init__.py` eagerly imports `TwitterAgent` which requires `tweepy` — not installed in the backend venv. The `_get_render_bundle_job()` helper in `content_bundles.py` originally fell back to a no-op stub.

**Resolution in Plan 07 (commit f31f04c):** Replaced the standard package import with `importlib.util.spec_from_file_location("seva_image_render_agent", module_path)`. This loads `image_render_agent.py` directly, bypassing `scheduler/agents/__init__.py` entirely and avoiding the `tweepy` dependency chain.

**Verified:** Plan 07 smoke check confirmed `_get_render_bundle_job()` resolves to `seva_image_render_agent.render_bundle_job` (real function, not no-op) in the Railway staging environment.

**Residual limitation:** If the two Railway services are ever split into separate repositories, this importlib shim will fail (file won't exist at the relative path). An HTTP call between services would be needed. Not a v1.0.1 concern; documented in Plan 07 SUMMARY as a known limitation.

### Gap 2 (Non-issue): `render_bundle_job` function signature alignment

Plan 04 calls `scheduler.add_job(render_bundle_job, args=[str(bundle.id)], ...)`. Plan 02's function signature is `async def render_bundle_job(bundle_id: str) -> None`. These align: APScheduler passes `args` positionally, matching the single `bundle_id: str` parameter. No mismatch.

### Gap 3 (Non-issue): Polling stops on `rendered_images.length > 0`, not `>= expectedCount`

The `useContentBundle` hook stops polling when `rendered_images.length > 0` (any image arrived), not when all expected images (4 or 2) have arrived. This is acceptable per the partial-render contract: a bundle may produce 1-4 images if some roles fail permanently (Plan 02 SUMMARY). The gallery renders whatever URLs are present. If the operator wants more, the Regen button triggers a fresh render attempt.

### Gap 4 (Non-issue): `compliance_passed` gate in enqueue helper is unchecked for quote tweet loop

`_enqueue_render_job_if_eligible` is called at `content_agent.py` line 1624 **outside** the `if compliance_ok:` block for the quote tweet loop — before `compliance_ok` is evaluated at the bundle level. However, the helper itself gates on `bundle.compliance_passed` (line 132), which has already been written to the bundle via `session.flush()` at line 1621. The gate is in the helper, not the call site. Semantically correct; just the call site ordering looks odd.

---

## Planning Artifacts Verification

| Item | Expected | Status |
|------|----------|--------|
| ROADMAP.md Phase 11 checkbox | `[x]` | PASS — line 26: `- [x] **Phase 11: Content Preview and Rendered Images**` |
| ROADMAP.md progress table row | `7/7 \| Complete \| 2026-04-19` | PASS — line 278: `\| 11. Content Preview and Rendered Images \| 7/7 \| Complete   \| 2026-04-19 \|` |
| ROADMAP.md v1.0.1 milestone annotation | ship date present | PASS — line 264: `v1.0.1 — Phase 11 (content preview & rendered images) — shipped 2026-04-19` |
| STATE.md status | `v1.0.1 complete` | PASS — line 4: `status: v1.0.1 complete` |
| STATE.md stopped_at | Completed Phase 11 message | PASS — line 6: `stopped_at: Completed Phase 11 — v1.0.1 milestone shipped` |
| REQUIREMENTS.md CREV-06..10 | All `[x] Complete` | PASS — lines 118-122 all marked `[x]` |
| `alembic current` | `0006 (head)` | PASS — Plan 07 smoke check confirmed; Plan 01 gate also verified |

---

## Human Verification Completed (Plan 07)

The following were confirmed by the operator on staging (documented in Plan 07 SUMMARY):

1. Live Imagen render on a new infographic bundle — 4 images within ~2 min, brand palette correct
2. R2 public URLs serve PNGs (HTTP 200 in incognito)
3. Regenerate button — skeletons appear, new 4 images replace old
4. Silent-fail on invalid GEMINI_API_KEY — brief-only render, no modal error, no WhatsApp alert
5. Quote bundle — 2 images (twitter_visual + instagram_slide_1)

---

## Gaps Summary

No gaps. All 6 success criteria pass. All 5 CREV requirements satisfied. All planning artifacts updated correctly. The one substantive integration gap (backend → scheduler cross-process import) was identified during Plan 03, resolved in Plan 07 (commit f31f04c), and confirmed in the staging smoke check.

---

## Recommended Follow-up Tickets (Non-blocking)

1. **Pre-existing test failures cleanup** — 9 total: `test_today_content_404` (backend), `test_morning_digest_assembly` (scheduler), 6x DigestPage + 1x ApprovalCard "renders draft tabs" (frontend). None introduced by Phase 11; all pre-date it. Candidate for a v1.0.1.1 cleanup task.

2. **Frontend bundle size** — Production build is 561 KB / 166 KB gzipped, exceeding Vite's 500 KB warning. The new format renderer components add ~10 KB. Code-splitting on the approval modal or the content preview components would bring the bundle within threshold. Candidate quick task before v1.0.2.

3. **Backend rerender performance** — `_get_render_bundle_job()` re-executes `importlib.util.spec_from_file_location` on every POST rerender call. Caching the result in a module-level variable (thread-safe under asyncio) would remove the file-load overhead for repeated regen attempts. Low-priority since regen is operator-triggered.

4. **Split-repo contingency** — If Railway services are ever moved to separate repositories, replace the `_get_render_bundle_job()` importlib shim with an HTTP call from the backend to the scheduler service's internal port. Document this risk in the architecture notes for the next engineer.

---

_Verified: 2026-04-19T23:00:00Z_
_Verifier: Claude (gsd-verifier)_
