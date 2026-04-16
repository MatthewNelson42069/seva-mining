---
phase: 11-content-preview-and-rendered-images
plan: 06
type: execute
wave: 3
depends_on: [11-05]
files_modified:
  - frontend/src/components/approval/ContentDetailModal.tsx
  - frontend/src/components/content/InfographicPreview.tsx
  - frontend/src/components/content/ThreadPreview.tsx
  - frontend/src/components/content/LongFormPreview.tsx
  - frontend/src/components/content/BreakingNewsPreview.tsx
  - frontend/src/components/content/QuotePreview.tsx
  - frontend/src/components/content/VideoClipPreview.tsx
  - frontend/src/components/content/RenderedImagesGallery.tsx
  - frontend/src/components/approval/__tests__/ContentDetailModal.test.tsx
autonomous: true
requirements: [CREV-02, CREV-06, CREV-08, CREV-09]

must_haves:
  truths:
    - "ContentDetailModal fetches the bundle via useContentBundle(item.engagement_snapshot.content_bundle_id)"
    - "When bundle.content_type is one of infographic / thread / long_form / breaking_news / quote / video_clip, the matching *Preview component renders the structured brief"
    - "When bundle fetch fails OR bundle.content_type is unknown, modal falls back to the flat DraftAlternative.text list (existing behavior) per D-24"
    - "Rendered images gallery shows 4 skeleton placeholders with 'rendering…' label when rendered_images is empty AND bundle is <10 min old AND content_type is infographic or quote"
    - "Rendered images gallery shows the actual images once rendered_images has entries, grouped by role (Twitter visual first, then Instagram slides in order)"
    - "Image slots are hidden gracefully (no rendering UI) when rendered_images is empty AND bundle is >10 min old (D-14)"
    - "Regenerate images button calls useRerenderContentBundle and is disabled while rendering is in-flight (D-17)"
    - "The structured brief renders immediately regardless of image state (D-13)"
  artifacts:
    - path: "frontend/src/components/approval/ContentDetailModal.tsx"
      provides: "Format-aware dispatcher modal"
      contains: "useContentBundle"
    - path: "frontend/src/components/content/RenderedImagesGallery.tsx"
      provides: "Image gallery with skeleton/poll UX and regen button"
      exports: ["RenderedImagesGallery"]
    - path: "frontend/src/components/content/ThreadPreview.tsx"
      provides: "Thread format renderer"
      exports: ["ThreadPreview"]
    - path: "frontend/src/components/content/LongFormPreview.tsx"
      provides: "long_form renderer"
      exports: ["LongFormPreview"]
    - path: "frontend/src/components/content/BreakingNewsPreview.tsx"
      provides: "breaking_news renderer"
      exports: ["BreakingNewsPreview"]
    - path: "frontend/src/components/content/QuotePreview.tsx"
      provides: "quote renderer"
      exports: ["QuotePreview"]
    - path: "frontend/src/components/content/VideoClipPreview.tsx"
      provides: "video_clip renderer"
      exports: ["VideoClipPreview"]
  key_links:
    - from: "ContentDetailModal"
      to: "useContentBundle"
      via: "hook import"
      pattern: "useContentBundle"
    - from: "ContentDetailModal"
      to: "InfographicPreview | ThreadPreview | LongFormPreview | BreakingNewsPreview | QuotePreview | VideoClipPreview"
      via: "switch on bundle.content_type"
      pattern: "case 'infographic'"
    - from: "RenderedImagesGallery"
      to: "useRerenderContentBundle"
      via: "button onClick mutation"
      pattern: "useRerenderContentBundle"
---

<objective>
Rewrite `ContentDetailModal` as a format-aware dispatcher. Add the five new preview components (thread, long_form, breaking_news, quote, video_clip) plus a RenderedImagesGallery. The existing InfographicPreview is extended (via optional `images` prop) rather than replaced.

Purpose: Delivers CREV-02 (full brief), CREV-06 (format-aware rendering for all 6 types), CREV-08 (skeleton+poll UX), CREV-09 (regen button integration).

Output: Operator clicks a Content queue card and sees: format badge, structured brief per format, source info, rationale, rendered images gallery (for infographic/quote), regen button, graceful fallback on errors.
</objective>

<execution_context>
@$HOME/.claude/get-shit-done/workflows/execute-plan.md
@$HOME/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/PROJECT.md
@.planning/phases/11-content-preview-and-rendered-images/11-CONTEXT.md
@.planning/phases/11-content-preview-and-rendered-images/11-RESEARCH.md
@.planning/phases/11-content-preview-and-rendered-images/11-05-SUMMARY.md
@.planning/phases/08-dashboard-views-and-digest/08-CONTEXT.md

<interfaces>
<!-- hooks from Plan 05 -->
```typescript
import { useContentBundle, useRerenderContentBundle } from '@/hooks/useContentBundle'
```

<!-- Existing InfographicPreview signature (must be EXTENDED, not broken) -->
```typescript
// Current: takes { draft: InfographicDraft }
// Extended: takes { draft: InfographicDraft, images?: RenderedImage[] | null }
// The existing ContentPage usage passes no images — backwards compatible.
```

<!-- draft_content shapes (from Phase 07 output — read existing InfographicPreview for reference on the infographic shape) -->
```json
// thread
{ "format": "thread", "tweets": ["...", "..."], "long_form_post": "..." }

// long_form
{ "format": "long_form", "post_text": "..." }

// breaking_news
{ "format": "breaking_news", "tweet": "...", "infographic_brief": {...optional...} }

// quote
{ "format": "quote", "twitter_post": "...", "instagram_post": "...", "attributed_to": "...", "source_url": "..." }

// video_clip
{ "format": "video_clip", "twitter_caption": "...", "instagram_caption": "...", "video_url": "..." }
```

<!-- RenderedImage shape -->
```typescript
interface RenderedImage {
  role: 'twitter_visual' | 'instagram_slide_1' | 'instagram_slide_2' | 'instagram_slide_3'
  url: string
  generated_at: string
}
```
</interfaces>
</context>

<tasks>

<task type="auto" tdd="true">
  <name>Task 1: Five new format renderers + RenderedImagesGallery</name>
  <files>
    frontend/src/components/content/ThreadPreview.tsx,
    frontend/src/components/content/LongFormPreview.tsx,
    frontend/src/components/content/BreakingNewsPreview.tsx,
    frontend/src/components/content/QuotePreview.tsx,
    frontend/src/components/content/VideoClipPreview.tsx,
    frontend/src/components/content/RenderedImagesGallery.tsx,
    frontend/src/components/content/InfographicPreview.tsx
  </files>
  <read_first>
    /Users/matthewnelson/seva-mining/frontend/src/components/content/InfographicPreview.tsx,
    /Users/matthewnelson/seva-mining/frontend/src/components/ui/badge.tsx,
    /Users/matthewnelson/seva-mining/frontend/src/components/ui/button.tsx,
    /Users/matthewnelson/seva-mining/frontend/src/hooks/useContentBundle.ts,
    /Users/matthewnelson/seva-mining/frontend/src/api/types.ts
  </read_first>
  <behavior>
    Each preview component takes `{ draft: unknown }` and renders safely even if draft fields are missing. All use shadcn primitives (Badge, Button) + Tailwind classes. Brand palette is for rendered IMAGE prompts only — preview components use the existing ContentPage styling (matching InfographicPreview's pattern: `border rounded-lg p-4 space-y-3`).

    - ThreadPreview: Given draft.tweets as string[], renders each tweet as a numbered card; renders draft.long_form_post below with a label "Long-form version".
    - LongFormPreview: Renders draft.post_text in a single card, preserves newlines (whitespace-pre-wrap).
    - BreakingNewsPreview: Renders draft.tweet prominently in a card; if draft.infographic_brief is present, renders a collapsed summary (headline + visual_structure) below.
    - QuotePreview: Renders draft.twitter_post and draft.instagram_post side-by-side (two-column grid collapses to stacked on small screens); shows "— {attributed_to}" attribution and a source_url link.
    - VideoClipPreview: Renders draft.twitter_caption + draft.instagram_caption side-by-side; shows a "Watch clip" button linking to draft.video_url in new tab.
    - RenderedImagesGallery: Takes { bundleId, contentType, renderedImages, bundleCreatedAt }. Computes:
        * expectedCount = contentType === 'infographic' ? 4 : contentType === 'quote' ? 2 : 0
        * ageMinutes = (Date.now() - new Date(bundleCreatedAt).getTime()) / 60000
        * isPolling = renderedImages?.length === 0 && ageMinutes < 10 && expectedCount > 0
        * If expectedCount === 0 → render nothing (null)
        * If renderedImages.length > 0 → render <img> tags grouped by role; Twitter 16:9 first, Instagram slides in a horizontal row
        * If isPolling → render `expectedCount` skeleton rectangles + label "Rendering images…"
        * Otherwise (age > 10min with no images) → render nothing
        * Always render the "Regenerate images" button when expectedCount > 0; disable while mutation.isPending OR isPolling.
    - InfographicPreview EXTENSION: add optional second prop `images?: RenderedImage[] | null`. When images is provided and non-empty, render the rendered images section above (or below — implementer choice) the existing brief. The existing signature (one-prop caller) remains supported.

    Each component should handle `undefined` or malformed draft fields by rendering an empty-state placeholder ("No draft content available") rather than crashing.

    No tests in this task — Task 2 tests the modal which in turn renders these components.
  </action>
  <action>
    Create five new TSX files for the format renderers, one file for RenderedImagesGallery (importing `useRerenderContentBundle` from Plan 05), and extend InfographicPreview.

    For brevity, each format component follows the InfographicPreview pattern:
      1. Top wrapper: `<div className="space-y-3 border rounded-lg p-4">`
      2. Header row: format label badge + optional "Copy" button for the primary text
      3. Body: format-specific content
      4. No interaction beyond copy — approve/reject is still handled by ContentSummaryCard outside the modal

    Ensure all components export a named function (e.g. `export function ThreadPreview({ draft }) { ... }`).

    For RenderedImagesGallery:
      - Use `useRerenderContentBundle(bundleId)` for the regen mutation
      - Render skeletons using an inline component (e.g. `<div className="aspect-square bg-muted/40 rounded animate-pulse" />`)
      - Use a simple grid: `grid grid-cols-1 md:grid-cols-4 gap-3` for the image gallery
      - Button: `<Button variant="outline" onClick={() => mutation.mutate()} disabled={mutation.isPending || isPolling}>{mutation.isPending ? 'Queuing…' : 'Regenerate images'}</Button>`

    Extend InfographicPreview to accept the optional `images` prop and render a subsection:
      {images && images.length > 0 && (
        <div className="space-y-2">
          <p className="text-xs font-medium text-muted-foreground uppercase tracking-wide">Rendered previews</p>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-2">
            {images.map((img) => (
              <img key={img.role} src={img.url} alt={img.role} className="w-full rounded border" loading="lazy" />
            ))}
          </div>
        </div>
      )}

    Keep the existing ContentPage.tsx call site working (it passes only `draft`; new `images` is optional).
  </action>
  <verify>
    <automated>cd /Users/matthewnelson/seva-mining/frontend && npx tsc --noEmit && npx vitest run src/components/content/ --reporter=verbose --passWithNoTests</automated>
  </verify>
  <acceptance_criteria>
    - All six new/modified files exist in frontend/src/components/content/
    - `grep -l "export function ThreadPreview\|export function LongFormPreview\|export function BreakingNewsPreview\|export function QuotePreview\|export function VideoClipPreview\|export function RenderedImagesGallery" /Users/matthewnelson/seva-mining/frontend/src/components/content/*.tsx | wc -l` returns 6
    - `grep -c "images?:" /Users/matthewnelson/seva-mining/frontend/src/components/content/InfographicPreview.tsx` returns ≥ 1 (new optional prop)
    - `grep -c "useRerenderContentBundle" /Users/matthewnelson/seva-mining/frontend/src/components/content/RenderedImagesGallery.tsx` returns 1
    - `grep -c "animate-pulse\|Rendering" /Users/matthewnelson/seva-mining/frontend/src/components/content/RenderedImagesGallery.tsx` returns ≥ 1
    - tsc --noEmit exits 0
    - Existing ContentPage tests still pass (InfographicPreview backward compat)
  </acceptance_criteria>
  <done>
    All 5 new format renderers exist, RenderedImagesGallery implements skeleton/image/button logic, InfographicPreview supports optional images prop without breaking existing callers. TypeScript compiles clean.
  </done>
</task>

<task type="auto" tdd="true">
  <name>Task 2: ContentDetailModal rewrite with format dispatch + gallery wiring</name>
  <files>
    frontend/src/components/approval/ContentDetailModal.tsx,
    frontend/src/components/approval/__tests__/ContentDetailModal.test.tsx
  </files>
  <read_first>
    /Users/matthewnelson/seva-mining/frontend/src/components/approval/ContentDetailModal.tsx,
    /Users/matthewnelson/seva-mining/frontend/src/components/approval/ContentSummaryCard.tsx,
    /Users/matthewnelson/seva-mining/frontend/src/components/approval/__tests__/ContentDetailModal.test.tsx,
    /Users/matthewnelson/seva-mining/frontend/src/hooks/useContentBundle.ts,
    /Users/matthewnelson/seva-mining/frontend/src/components/content/InfographicPreview.tsx,
    /Users/matthewnelson/seva-mining/frontend/src/components/content/ThreadPreview.tsx,
    /Users/matthewnelson/seva-mining/frontend/src/components/content/LongFormPreview.tsx,
    /Users/matthewnelson/seva-mining/frontend/src/components/content/BreakingNewsPreview.tsx,
    /Users/matthewnelson/seva-mining/frontend/src/components/content/QuotePreview.tsx,
    /Users/matthewnelson/seva-mining/frontend/src/components/content/VideoClipPreview.tsx,
    /Users/matthewnelson/seva-mining/frontend/src/components/content/RenderedImagesGallery.tsx
  </read_first>
  <behavior>
    - Test 1 (renders InfographicPreview for content_type="infographic"): Given a mock bundle with content_type="infographic" and draft_content with a valid infographic shape, the modal renders InfographicPreview and RenderedImagesGallery.
    - Test 2 (renders ThreadPreview): content_type="thread" → ThreadPreview renders; RenderedImagesGallery renders NOTHING (expectedCount=0).
    - Test 3 (renders LongFormPreview): content_type="long_form" → LongFormPreview renders.
    - Test 4 (renders BreakingNewsPreview): content_type="breaking_news" → BreakingNewsPreview renders.
    - Test 5 (renders QuotePreview): content_type="quote" → QuotePreview renders AND RenderedImagesGallery renders (expectedCount=2).
    - Test 6 (renders VideoClipPreview): content_type="video_clip" → VideoClipPreview renders; no gallery.
    - Test 7 (falls back to flat text on bundle fetch error): When useContentBundle returns isError=true OR bundleId is undefined (no engagement_snapshot.content_bundle_id), the modal renders the existing flat DraftAlternative.text list (D-24 fallback).
    - Test 8 (falls back to flat text on unknown content_type): content_type="unknown_format" → flat text fallback.
    - Test 9 (shows skeleton+"rendering…" for fresh infographic with no images): Mock bundle with created_at="now", content_type="infographic", rendered_images=[] → gallery renders 4 skeleton elements and text "Rendering images…".
    - Test 10 (hides gallery after 10 minutes for bundle with no images): created_at="15 min ago", rendered_images=[] → gallery renders no skeletons and no images (just the regen button).
    - Test 11 (Regenerate button disabled while polling): rendered_images=[], fresh bundle → regen button has disabled attribute while isPolling is true.
    - Test 12 (renders structured brief immediately even if images still loading — D-13): Modal body shows the InfographicPreview brief content AND the skeleton gallery at the same time.
  </behavior>
  <action>
    REWRITE frontend/src/components/approval/ContentDetailModal.tsx from scratch. Keep the existing Dialog wrapper + modal shell; replace the body rendering logic.

      import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from '@/components/ui/dialog'
      import type { DraftItemResponse, DraftAlternative } from '@/api/types'
      import { useContentBundle } from '@/hooks/useContentBundle'
      import { InfographicPreview } from '@/components/content/InfographicPreview'
      import { ThreadPreview } from '@/components/content/ThreadPreview'
      import { LongFormPreview } from '@/components/content/LongFormPreview'
      import { BreakingNewsPreview } from '@/components/content/BreakingNewsPreview'
      import { QuotePreview } from '@/components/content/QuotePreview'
      import { VideoClipPreview } from '@/components/content/VideoClipPreview'
      import { RenderedImagesGallery } from '@/components/content/RenderedImagesGallery'

      interface ContentDetailModalProps {
        item: DraftItemResponse
        isOpen: boolean
        onClose: () => void
      }

      export function ContentDetailModal({ item, isOpen, onClose }: ContentDetailModalProps) {
        // Pull content_bundle_id from engagement_snapshot (populated by Plan 01 schema change)
        const bundleId =
          (item.engagement_snapshot as Record<string, unknown> | undefined)?.content_bundle_id as
            | string
            | undefined

        const { data: bundle, isError } = useContentBundle(bundleId ?? null)

        const headline = bundle?.story_headline ?? item.source_text?.split('\n')[0] ?? 'Content Review'

        // Fallback path: no bundle id, fetch failed, or unknown format → flat text (D-24)
        const contentType = bundle?.content_type ?? ''
        const showFallback = !bundleId || isError || !FORMAT_RENDERERS[contentType]

        return (
          <Dialog open={isOpen} onOpenChange={(open) => { if (!open) onClose() }}>
            <DialogContent className="sm:max-w-3xl max-h-[85vh] overflow-y-auto">
              <DialogHeader>
                <DialogTitle className="text-base leading-snug pr-8">{headline}</DialogTitle>
              </DialogHeader>

              <div className="space-y-4">
                {/* Source metadata — unchanged */}
                {(item.source_account || item.source_url) && (
                  <div className="text-xs text-muted-foreground space-y-0.5">
                    {item.source_account && <p>Source: {item.source_account}</p>}
                    {item.source_url && (
                      <a href={item.source_url} target="_blank" rel="noopener noreferrer" className="underline hover:text-foreground">
                        View original
                      </a>
                    )}
                  </div>
                )}

                {/* Brief renders immediately (D-13) */}
                {showFallback ? (
                  <FlatTextFallback item={item} />
                ) : (
                  <>
                    {renderForFormat(contentType, bundle)}
                    {/* Gallery mounts for infographic/quote; RenderedImagesGallery self-renders null otherwise */}
                    {bundle && (
                      <RenderedImagesGallery
                        bundleId={bundle.id}
                        contentType={bundle.content_type ?? ''}
                        renderedImages={bundle.rendered_images ?? []}
                        bundleCreatedAt={bundle.created_at}
                      />
                    )}
                  </>
                )}

                {/* Rationale + score — unchanged */}
                {item.rationale && (
                  <div className="space-y-1.5">
                    <p className="text-xs font-medium text-muted-foreground uppercase tracking-wide">Why this format?</p>
                    <p className="text-sm leading-relaxed text-muted-foreground">{item.rationale}</p>
                  </div>
                )}
                {item.score != null && (
                  <div className="flex items-center gap-2">
                    <span className="text-xs text-muted-foreground">Quality score:</span>
                    <span className="text-sm font-medium">{item.score.toFixed(1)}/10</span>
                  </div>
                )}
              </div>

              <DialogFooter showCloseButton />
            </DialogContent>
          </Dialog>
        )
      }

      // Dispatcher map — keys must match content_type values from Phase 07
      const FORMAT_RENDERERS: Record<string, true> = {
        infographic: true,
        thread: true,
        long_form: true,
        breaking_news: true,
        quote: true,
        video_clip: true,
      }

      function renderForFormat(contentType: string, bundle: NonNullable<ReturnType<typeof useContentBundle>['data']>) {
        const draft = bundle.draft_content as any
        switch (contentType) {
          case 'infographic':
            return <InfographicPreview draft={draft} images={bundle.rendered_images} />
          case 'thread':
            return <ThreadPreview draft={draft} />
          case 'long_form':
            return <LongFormPreview draft={draft} />
          case 'breaking_news':
            return <BreakingNewsPreview draft={draft} />
          case 'quote':
            return <QuotePreview draft={draft} />
          case 'video_clip':
            return <VideoClipPreview draft={draft} />
          default:
            return null
        }
      }

      function FlatTextFallback({ item }: { item: DraftItemResponse }) {
        // Preserve the pre-Phase-11 behavior: render draft alternatives as plain text
        const alt: DraftAlternative | undefined = item.alternatives[0]
        if (!alt) return <p className="text-sm text-muted-foreground">No draft content available.</p>
        return (
          <div className="bg-background border border-border rounded-lg p-4">
            <p className="text-sm leading-relaxed whitespace-pre-wrap">{alt.text}</p>
          </div>
        )
      }

    Replace the describe.skip in ContentDetailModal.test.tsx with the 12 tests above. Use `QueryClientProvider` wrapper for all tests. Mock `useContentBundle` via `vi.mock('@/hooks/useContentBundle', ...)` to return the appropriate shape per test. For Test 11 (regen button disabled) render the gallery and assert `screen.getByRole('button', { name: /Regenerate/i }).toHaveAttribute('disabled')` during polling state.

    Ensure fixtures cover realistic draft_content shapes for each format.
  </action>
  <verify>
    <automated>cd /Users/matthewnelson/seva-mining/frontend && npx vitest run src/components/approval/__tests__/ContentDetailModal.test.tsx && npx tsc --noEmit</automated>
  </verify>
  <acceptance_criteria>
    - `grep -c "useContentBundle" /Users/matthewnelson/seva-mining/frontend/src/components/approval/ContentDetailModal.tsx` returns ≥ 1
    - `grep -c "FORMAT_RENDERERS\|case 'infographic'\|case 'thread'\|case 'long_form'\|case 'breaking_news'\|case 'quote'\|case 'video_clip'" /Users/matthewnelson/seva-mining/frontend/src/components/approval/ContentDetailModal.tsx` returns ≥ 6
    - `grep -c "FlatTextFallback\|showFallback" /Users/matthewnelson/seva-mining/frontend/src/components/approval/ContentDetailModal.tsx` returns ≥ 2
    - `grep -c "RenderedImagesGallery" /Users/matthewnelson/seva-mining/frontend/src/components/approval/ContentDetailModal.tsx` returns 1
    - `grep -c "describe.skip" /Users/matthewnelson/seva-mining/frontend/src/components/approval/__tests__/ContentDetailModal.test.tsx` returns 0
    - vitest reports 12 PASSED
    - tsc --noEmit exits 0
  </acceptance_criteria>
  <done>
    ContentDetailModal dispatches to the correct format renderer, falls back gracefully for unknown types and fetch errors, renders the gallery for infographic/quote, and never breaks on missing engagement_snapshot. All 12 tests pass.
  </done>
</task>

</tasks>

<verification>
- `cd frontend && npm run test -- --run` — full suite green
- `cd frontend && npx tsc --noEmit` — no type errors
- Manual sanity: `npm run dev` → log in → open a Content queue card → verify the new modal renders
</verification>

<success_criteria>
- All 6 content_type values render the correct preview
- Unknown content_type and fetch errors fall back to flat text (D-24)
- Gallery renders only for infographic (4 slots) and quote (2 slots)
- Skeleton UX shows while polling; graceful hide after 10min; regen button works
- Existing ContentPage.tsx + InfographicPreview call site still works (no regression)
</success_criteria>

<output>
Create `.planning/phases/11-content-preview-and-rendered-images/11-06-SUMMARY.md` noting:
- Files created and line counts
- Any minor UI polish added at Claude's discretion (e.g. hover states, loading spinners)
- Known UX caveat: if the bundle fetch succeeds but content_type is null/empty → treated as unknown → fallback rendered
- Readiness for Plan 07 human verification checkpoint
</output>
