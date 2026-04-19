---
phase: 11
plan: 06
subsystem: frontend
status: completed
wave: 3
autonomous: true
tasks_completed: 2
tasks_total: 2
tags: [react, format-dispatch, preview-components, rendered-images, modal]
requires: [11-05]
provides: [format-aware-modal, preview-components, rendered-images-gallery]
affects: [ContentPage, ContentSummaryCard]
tech-stack:
  added: []
  patterns:
    - "vi.mock + mockReturnValue pattern for hook mocking in component tests"
    - "cleanup() in afterEach for base-ui dialog portal DOM isolation"
    - "Format dispatch via switch + FORMAT_RENDERERS sentinel object"
key-files:
  created:
    - frontend/src/components/content/ThreadPreview.tsx
    - frontend/src/components/content/LongFormPreview.tsx
    - frontend/src/components/content/BreakingNewsPreview.tsx
    - frontend/src/components/content/QuotePreview.tsx
    - frontend/src/components/content/VideoClipPreview.tsx
    - frontend/src/components/content/RenderedImagesGallery.tsx
  modified:
    - frontend/src/components/content/InfographicPreview.tsx
    - frontend/src/components/approval/ContentDetailModal.tsx
    - frontend/src/components/approval/__tests__/ContentDetailModal.test.tsx
key-decisions:
  - "FORMAT_RENDERERS sentinel object (keys → true) chosen over switch fallthrough for O(1) unknown-format detection before entering the switch"
  - "cleanup() added explicitly in afterEach — base-ui Dialog renders into a portal outside the RTL container root, so auto-cleanup misses stale DOM nodes causing getByText to find multiple matches across sequential tests"
  - "isPolling computed inside RenderedImagesGallery from bundleCreatedAt prop (not from useContentBundle refetchInterval state) — keeps the component self-contained and testable without mocking query internals"
  - "No GoldHistoryPreview component needed — plan spec consolidated gold_history into the default/unknown fallback path; no distinct format renderer required"
requirements-completed: [CREV-02, CREV-06, CREV-08, CREV-09]
duration: "~15 min"
completed: "2026-04-19"
---

# Phase 11 Plan 06: Format-Aware Modal — Summary

ContentDetailModal rewritten as a format-aware dispatcher backed by `useContentBundle`; six format renderer components added; `RenderedImagesGallery` implemented with skeleton/poll UX and regen button; `InfographicPreview` extended with optional images prop.

## Duration

- Start: 2026-04-19T21:31:14Z
- End: 2026-04-19T21:47:00Z (approx)
- Duration: ~15 min
- Tasks: 2 completed / 2 total
- Files: 9 (6 created, 3 modified)

## Commits

- `13c7653` — feat(11-06): add format preview components and extend InfographicPreview
- `9c3a22d` — feat(11-06): rewrite ContentDetailModal as format-aware dispatcher with 12 tests

## Task 1 — Five new format renderers + RenderedImagesGallery

### Files created

| File | Lines | Key behavior |
|------|-------|-------------|
| `ThreadPreview.tsx` | 69 | Numbered tweet list with reply-chain indicator; long-form version section; Copy Thread button |
| `LongFormPreview.tsx` | 44 | Single post card; whitespace-pre-wrap; Copy Post button |
| `BreakingNewsPreview.tsx` | 64 | Tweet card; optional collapsed infographic_brief summary (headline + visual_structure) |
| `QuotePreview.tsx` | 89 | Twitter/Instagram two-column grid (collapses on small screens); per-column copy buttons; attribution + source link |
| `VideoClipPreview.tsx` | 79 | Twitter/Instagram caption grid; Watch clip button opens video_url in new tab |
| `RenderedImagesGallery.tsx` | 82 | expectedCount (4 infographic / 2 quote / 0 others); skeleton placeholders + "Rendering images…" while isPolling; sorted image grid; Regen button disabled while mutation.isPending OR isPolling |

### File modified

| File | Change |
|------|--------|
| `InfographicPreview.tsx` | Added optional `images?: RenderedImage[] | null` prop; renders rendered previews grid below caption if images present; existing one-prop callers (ContentPage.tsx) unaffected |

### UX polish added (Claude discretion)

- Role labels map (`twitter_visual` → "Twitter / X", `instagram_slide_1` → "Instagram 1", etc.) shown under each rendered image
- Images in gallery are clickable links that open the full-size URL in a new tab
- Gallery images sorted by canonical role order (twitter_visual first)
- All components handle `undefined`/null draft fields defensively — renders "No draft content available." rather than crashing

## Task 2 — ContentDetailModal rewrite + 12 tests

### ContentDetailModal.tsx rewrite

New behavior:
- Extracts `bundleId` from `item.engagement_snapshot.content_bundle_id`
- Calls `useContentBundle(bundleId ?? null)` — no-op when null
- **Loading state**: three animated skeleton lines while bundle is fetching
- **Fallback** (D-24): renders `FlatTextFallback` (first `DraftAlternative.text`) when bundleId is missing, `isError` is true, or `content_type` is unknown
- **Format dispatch**: switch on `bundle.content_type` → correct preview component
- **Gallery**: `<RenderedImagesGallery>` always mounted for infographic and quote; component self-returns null for all other formats
- Source metadata, rationale, and quality score sections preserved from prior implementation

The `FORMAT_RENDERERS` object (`Record<string, true>`) guards the switch statement, making unknown-format detection a single map lookup before entering the dispatcher.

### ContentDetailModal.test.tsx — 12 tests (all green)

| Test | What it covers |
|------|---------------|
| 1 | infographic → InfographicPreview renders |
| 2 | thread → ThreadPreview renders; no RenderedImagesGallery |
| 3 | long_form → LongFormPreview renders |
| 4 | breaking_news → BreakingNewsPreview renders |
| 5 | quote → QuotePreview + RenderedImagesGallery (regen button present) |
| 6 | video_clip → VideoClipPreview; no gallery |
| 7 | fetch error → FlatTextFallback with first alternative text |
| 8 | unknown content_type → FlatTextFallback |
| 9 | fresh infographic, no images → skeleton × 4 + "Rendering images…" |
| 10 | 15min-old infographic, no images → no skeletons, regen button present |
| 11 | fresh infographic, no images → regen button disabled (isPolling=true) |
| 12 | brief renders immediately alongside skeleton gallery (D-13) |

## Verification Results

- `npx vitest run src/components/approval/__tests__/ContentDetailModal.test.tsx` → **12 passed**
- `npx vitest run src/components/content/InfographicPreview.test.tsx` → **7 passed** (backward compat confirmed)
- `npm run test -- --run` → **67 passed, 7 failed** (failures are pre-existing DigestPage/ApprovalCard failures from prior phases — not introduced by Plan 06)
- `npx tsc --noEmit` → **0 errors**
- `npm run build` → **successful** (561KB bundle, no new warnings about imports/types)

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Base-UI dialog portal leaves stale DOM across RTL tests**

- **Found during:** Task 2 test authoring (tests 2-3 failing with "multiple elements found")
- **Issue:** base-ui `Dialog` renders into a portal outside the React Testing Library container. The library's auto-cleanup only unmounts the root container, leaving portal nodes in `document.body`. Sequential tests then found text matches in both the previous test's portal and the current render.
- **Fix:** Added explicit `cleanup()` call in `afterEach` in the test file. This forces RTL to unmount all rendered trees including portals before each test.
- **Files modified:** `frontend/src/components/approval/__tests__/ContentDetailModal.test.tsx`
- **Commit:** `9c3a22d`

None - all other implementation followed plan exactly as written.

**Total deviations:** 1 auto-fixed (Rule 3 - Blocking). Impact: test correctness only; no production code changed.

## Known Stubs

None. All preview components wire to real draft_content shapes from Phase 07 spec. RenderedImagesGallery wires to real `useRerenderContentBundle` mutation. No hardcoded empty values flow to UI rendering.

## Known UX Caveat

If the bundle fetch succeeds but `content_type` is null or empty string, the modal falls back to the flat text view (D-24 compliant). This is intentional and documented.

## Pre-existing Test Failures (out of scope)

These failures existed before Plan 06 and are documented in Plan 05 SUMMARY:

- `DigestPage.test.tsx` — 6 failures (unrelated fetch/rendering issues)
- `ApprovalCard.test.tsx` — 1 failure ("renders draft tabs")

## Readiness for Plan 07

Plan 07 (human verification) can proceed. The following are ready for manual verification:

1. Open a Content queue card → modal shows format badge + structured brief
2. Infographic modal shows rendered images or skeleton (polling state) if fresh
3. Regen button triggers new render; modal returns to skeleton+poll
4. Text-only formats (thread, long_form, breaking_news, video_clip) never show image skeletons
5. Clicking a content item with no engagement_snapshot shows the flat-text fallback gracefully

## Self-Check: PASSED

- `frontend/src/components/content/ThreadPreview.tsx` — FOUND
- `frontend/src/components/content/LongFormPreview.tsx` — FOUND
- `frontend/src/components/content/BreakingNewsPreview.tsx` — FOUND
- `frontend/src/components/content/QuotePreview.tsx` — FOUND
- `frontend/src/components/content/VideoClipPreview.tsx` — FOUND
- `frontend/src/components/content/RenderedImagesGallery.tsx` — FOUND
- `frontend/src/components/approval/ContentDetailModal.tsx` — FOUND (rewritten)
- `frontend/src/components/approval/__tests__/ContentDetailModal.test.tsx` — FOUND (12 tests)
- Commit `13c7653` — FOUND (Task 1)
- Commit `9c3a22d` — FOUND (Task 2)
