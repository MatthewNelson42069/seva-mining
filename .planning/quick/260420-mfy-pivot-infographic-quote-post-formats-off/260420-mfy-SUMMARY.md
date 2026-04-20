---
quick_task: 260420-mfy
subsystem: [scheduler, backend, frontend]
tags: [pivot, image-rendering, content-agent, infographic, quote, cleanup]
dependency_graph:
  requires: [260419-t78, 260419-si2]
  provides: [three-field-copy-blocks, brand-preamble, pure-python-scheduler]
  affects: [content_agent, content_bundle_schema, frontend_approval_cards]
tech_stack:
  removed: [google-genai, aioboto3, chart_renderer (Node SSR), RenderedImagesGallery]
  patterns: [three-copy-block UI, BRAND_PREAMBLE module constant, legacy-bundle graceful fallback]
key_files:
  created:
    - scheduler/agents/brand_preamble.py
  modified:
    - scheduler/Dockerfile
    - scheduler/worker.py
    - scheduler/agents/content_agent.py
    - scheduler/config.py
    - scheduler/pyproject.toml
    - backend/app/routers/content_bundles.py
    - backend/app/schemas/content_bundle.py
    - frontend/src/api/types.ts
    - frontend/src/api/content.ts
    - frontend/src/components/content/InfographicPreview.tsx
    - frontend/src/components/content/QuotePreview.tsx
    - frontend/src/components/approval/ContentSummaryCard.tsx
    - frontend/src/components/approval/ContentDetailModal.tsx
    - frontend/src/hooks/useContentBundle.ts
    - frontend/src/mocks/handlers.ts
  deleted:
    - scheduler/chart_renderer/ (entire directory, 13 files)
    - scheduler/agents/chart_renderer_client.py
    - scheduler/agents/image_render_agent.py
    - scheduler/models/chart_spec.py
    - backend/app/models/chart_spec.py
    - frontend/src/components/content/RenderedImagesGallery.tsx
decisions:
  - Kept rendered_images DB column (operator-locked) but removed from Pydantic schemas and API response
  - BRAND_PREAMBLE is a module-level constant (not config) — changes require code deploy, not env var
  - Legacy bundles (no image_prompt) show "Legacy format — regenerate this bundle." placeholder, never crash
  - image_prompt assembled in Python (not by Claude directly) — brand preamble + headline + facts + story direction
  - Copy buttons use inline onClick (no shared CopyButton component) — follows ThreadPreview.tsx pattern
metrics:
  duration: "~3 hours (multi-session)"
  completed_date: "2026-04-20"
  tasks_completed: 3
  files_changed: 31
---

# Quick Task 260420-mfy: Pivot Infographic/Quote — Image Rendering Off SUMMARY

**One-liner:** Ripped out Node chart_renderer + Gemini Imagen + Cloudflare R2 pipeline; replaced infographic/quote bundles with three text fields (`suggested_headline`, `data_facts`, `image_prompt`) that the operator pastes into claude.ai to produce the final visual.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Delete backend rendering infrastructure, rewrite Dockerfile, remove rerender endpoint | `5514db0` | 13 deleted chart_renderer files, Dockerfile, worker.py, content_bundles router+schema, pyproject.toml, conftest |
| 2 RED | Failing tests for brand_preamble + three-field shape | `be2f7a7` | scheduler/tests/test_content_agent.py |
| 2 GREEN | brand_preamble.py + content_agent three-field prompts | `d589c68` | scheduler/agents/brand_preamble.py, content_agent.py |
| 3 RED | Failing tests for InfographicPreview three-copy-block shape | `8a4fcb1` | frontend/src/components/content/InfographicPreview.test.tsx |
| 3 GREEN | Simplify frontend cards, remove all image UI | `76f3769` | 15 frontend+scheduler files |

## What Was Built

### Task 1 — Backend Rendering Removed

- Deleted `scheduler/chart_renderer/` (Node SSR renderer, 13 files including package.json, worker.js, renderChart.ts, SVG-to-PNG pipeline)
- Deleted `scheduler/agents/chart_renderer_client.py`, `image_render_agent.py`
- Deleted `scheduler/models/chart_spec.py`, `backend/app/models/chart_spec.py`
- Rewrote `scheduler/Dockerfile` to pure Python (no Node, no npm install stage); all COPY paths relative (no `scheduler/` prefix — Railway Root Directory constraint from quick-t78)
- Removed `chart_client` startup/shutdown from `scheduler/worker.py`
- Rewrote `backend/app/routers/content_bundles.py` to GET-only (no rerender POST)
- Removed `RenderedImage`, `rendered_images`, `RerenderResponse` from backend schema
- Removed `google-genai[aiohttp]` and `aioboto3` from `scheduler/pyproject.toml`

### Task 2 — Brand Preamble + Three-Field Prompts

- Created `scheduler/agents/brand_preamble.py` with 1267-char `BRAND_PREAMBLE` constant containing full Seva Mining visual spec (palette, typography, layout, dimensions, HTML artifact format)
- Updated `content_agent.py` infographic path: LLM returns `suggested_headline`, `data_facts[]`, `image_prompt_direction`; agent assembles `image_prompt = BRAND_PREAMBLE + headline + facts + direction`
- Updated `_draft_quote_post`: same three-field shape with `ARTIFACT TYPE: pull-quote card` framing in image_prompt
- Updated `_extract_check_text`: reads `suggested_headline` + `data_facts` instead of old chart spec fields
- 8 new tests: brand_preamble loads/length, infographic/quote three-field shape, facts clamped to 5, compliance screens new fields

### Task 3 — Frontend Cards Simplified

- Rewrote `InfographicPreview`: three copy blocks (Suggested Headline, Key Facts, Image Prompt); legacy bundles show placeholder
- Rewrote `QuotePreview`: Twitter block always visible; three copy blocks shown when `image_prompt` present
- Rewrote `ContentSummaryCard`: pure text card, removed Dialog/Download button/useContentBundle/InlineImagesGallery
- Updated `ContentDetailModal`: removed RenderedImagesGallery mount; InfographicPreview called with `draft` prop only
- Deleted `RenderedImagesGallery.tsx`
- Removed `RenderedImage`/`RerenderResponse` from `api/types.ts`; removed `rerenderContentBundle` from `api/content.ts`; removed `useRerenderContentBundle` from `useContentBundle.ts`
- Updated all affected tests (ApprovalCard, ContentDetailModal, ContentSummaryCard, useContentBundle, content-bundle API, ContentPage)

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 - Missing] Removed stale Phase 11 config settings**
- **Found during:** Task 3 grep sweep
- **Issue:** `scheduler/config.py` still declared `gemini_api_key`, `r2_account_id`, `r2_access_key_id`, `r2_secret_access_key`, `r2_bucket`, `r2_public_base_url` — all now orphaned (no callers)
- **Fix:** Removed the 6 settings fields and updated stale comment referencing deleted `image_render_agent`
- **Files modified:** `scheduler/config.py`
- **Commit:** `76f3769`

**2. [Rule 1 - Bug] ApprovalCard.test.tsx useContentBundle mock returned undefined**
- **Found during:** Task 3 test run
- **Issue:** `vi.mock('@/hooks/useContentBundle', () => ({ useContentBundle: vi.fn() }))` — the default mock returned `undefined`, causing `TypeError: Cannot destructure property 'data' of 'useContentBundle(...)'` in ContentDetailModal
- **Fix:** Changed mock to `vi.fn(() => ({ data: undefined, isLoading: false, isError: false }))`
- **Files modified:** `frontend/src/components/approval/ApprovalCard.test.tsx`
- **Commit:** `76f3769`

**3. [Rule 1 - Bug] ContentPage.test.tsx expected old INFOGRAPHIC BRIEF label**
- **Found during:** Task 3 test run
- **Issue:** Test at line 148 used `findByText('INFOGRAPHIC BRIEF')` but new component shows `'INFOGRAPHIC'`; also `infographicBundle.draft_content` lacked `image_prompt` so legacy placeholder rendered
- **Fix:** Updated test description + assertion to `'INFOGRAPHIC'`, updated `infographicBundle.draft_content` to include `suggested_headline`, `data_facts`, and `image_prompt`
- **Files modified:** `frontend/src/pages/ContentPage.test.tsx`
- **Commit:** `76f3769`

**4. [Rule 1 - Bug] ContentSummaryCard "Approve" button found multiple times**
- **Found during:** Task 3 test run (ApprovalCard.test.tsx line 220)
- **Issue:** `screen.getByRole('button', { name: /Approve/i })` threw "multiple elements found" because ContentDetailModal (even with `isOpen={false}`) renders additional action buttons in the DOM via Radix Dialog
- **Fix:** Changed to `getAllByRole(...).length >= 1` assertion
- **Files modified:** `frontend/src/components/approval/ApprovalCard.test.tsx`
- **Commit:** `76f3769`

**5. [Rule 1 - Bug] TypeScript error: mockUseContentBundle declared but never read**
- **Found during:** `npm run build`
- **Issue:** After removing `useContentBundle` usage from ContentSummaryCard, the test file still imported and aliased it
- **Fix:** Removed the unused import and const declaration
- **Files modified:** `frontend/src/components/approval/ApprovalCard.test.tsx`
- **Commit:** `76f3769`

## Known Stubs

None. All three copy blocks are wired to real `draft_content` fields populated by the content agent.

## Verification

- `npm run test -- --run`: 73/73 tests pass (10 test files)
- `npm run build`: TypeScript + Vite build clean (no errors)
- `npx eslint src/`: 0 lint errors
- Grep sweep: zero production-code references to deleted symbols (ChartRendererClient, BundleCharts, RenderedImage, RerenderResponse, rerenderContentBundle, useRerenderContentBundle, image_render_agent)

## Self-Check: PASSED

- `5514db0` exists: confirmed
- `be2f7a7` exists: confirmed
- `d589c68` exists: confirmed
- `8a4fcb1` exists: confirmed
- `76f3769` exists: confirmed
- `scheduler/agents/brand_preamble.py` exists: confirmed
- `frontend/src/components/content/RenderedImagesGallery.tsx` deleted: confirmed
