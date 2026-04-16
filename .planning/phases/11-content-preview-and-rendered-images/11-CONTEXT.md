---
phase: 11
slug: content-preview-and-rendered-images
created: 2026-04-16
discuss_complete: true
---

# Phase 11: Content Preview and Rendered Images — Context

**Gathered:** 2026-04-16
**Status:** Ready for planning

<domain>
## Phase Boundary

Upgrade the Content queue detail modal so clicking a content draft shows the **full structured brief** for every content format (infographic, thread, long_form, breaking_news, quote, video_clip) and displays **AI-rendered image previews** alongside the brief for visual formats (infographic, quote).

**In scope:**
- New `GET /content-bundles/{id}` endpoint returning the full `ContentBundle` row (draft_content, deep_research, story_headline, rendered_images, sources).
- Frontend hook `useContentBundle(id)` fetching the bundle via `item.engagement_snapshot.content_bundle_id`.
- Rewrite of `ContentDetailModal` to render format-aware previews (reusing the existing but orphaned `InfographicPreview` component) + rendered image gallery.
- Background image render service: takes a finalized infographic or quote bundle, generates images via Nano Banana / Gemini, uploads to Cloudflare R2, persists URLs on the bundle.
- Alembic migration adding `rendered_images` JSONB column on `content_bundles`.
- Content Agent integration: after persisting an infographic or quote bundle, enqueue a render job (non-blocking).
- `POST /content-bundles/{id}/rerender` endpoint backing the modal "Regenerate images" button.

**Out of scope (explicit):**
- Template-based image rendering (PIL/canvas) — rejected in discuss phase in favor of AI.
- Rendering for thread, long_form, breaking_news, video_clip formats — these stay text-only.
- Backfill of existing ContentBundles — forward-only.
- Auto-posting, image editing inside the dashboard, multi-variant rendering.

</domain>

<decisions>
## Implementation Decisions

### Image generation
- **D-01:** AI image generation via **Nano Banana / Gemini** image API (matches what was used for live mockups). No template-based rendering.
- **D-02:** Each infographic bundle produces **4 images**: `twitter_visual`, `instagram_slide_1`, `instagram_slide_2`, `instagram_slide_3`.
- **D-03:** Each quote bundle produces **2 images**: `twitter_visual`, `instagram_slide_1`.
- **D-04:** No rendering for thread, long_form, breaking_news, video_clip — these remain text-only in the modal.
- **D-05:** Prompts to the image API must enforce the brand palette (`#F0ECE4` cream, `#0C1B32` navy, `#D4AF37` gold) and pass the slide-level `headline` / `key_stat` / `visual_structure` spec from `draft_content`. Prompt structure is planner/researcher discretion; brand colors are locked.

### Storage
- **D-06:** Images stored in **Cloudflare R2** (S3-compatible, free egress, public URLs, ~$0.015/GB-mo). Add R2 credentials (`R2_ACCOUNT_ID`, `R2_ACCESS_KEY_ID`, `R2_SECRET_ACCESS_KEY`, `R2_BUCKET`, `R2_PUBLIC_BASE_URL`) to env config.
- **D-07:** R2 object key convention: `content-bundles/{bundle_id}/{role}-{timestamp}.png`. Timestamp suffix lets regen archive old renders rather than overwrite (cheap object storage; avoids CDN cache invalidation pain).
- **D-08:** Persistence shape on `content_bundles.rendered_images` (new JSONB column) — array of objects: `[{ "role": "twitter_visual" | "instagram_slide_1" | ..., "url": "https://...", "generated_at": "ISO-8601" }]`. Nullable; empty array or null means "no images yet."

### Latency & scheduling
- **D-09:** Image rendering runs as a **background job, independent of the Content Agent cron**. Agent commits the bundle and returns in <5s. Render completes asynchronously, typically within ~2 minutes.
- **D-10:** Job mechanism: enqueue into APScheduler as a one-off `DateTrigger` job fired immediately after bundle commit (reuses existing scheduler worker — no new infra like Redis/Celery). Each bundle's render is its own job so failures don't cascade.
- **D-11:** Compliance checker still runs before rendering — do not render a bundle that failed compliance.

### Modal pending-state UX
- **D-12:** On modal open, fetch full bundle via `useContentBundle`. If `rendered_images` is absent/empty AND the bundle's format is infographic or quote AND the bundle was created within the last ~10 minutes, show **skeleton placeholders + "rendering…" label** at the image slots and poll the endpoint every **5 seconds** until images land (or a 5-minute ceiling is hit). TanStack Query `refetchInterval` is the mechanism.
- **D-13:** The structured brief (headline, key_stats, captions, etc.) renders immediately regardless of image state. Operator never has to wait to read the brief.
- **D-14:** For bundles older than 10 minutes with no rendered images, stop polling and hide image slots gracefully (brief-only display) — assume render already failed. Operator can hit the regen button to retry.

### Regeneration
- **D-15:** Modal includes a single **"Regenerate images"** button (not per-slide). One click = one retry attempt. Button posts to `POST /content-bundles/{id}/rerender`, which enqueues a fresh render job. Modal returns to skeleton + poll state until new URLs arrive.
- **D-16:** Regen works on **any** content bundle (including old ones) — this is the only backfill mechanism (lazy, operator-triggered). Old R2 objects are kept; `rendered_images` is overwritten with the new set.
- **D-17:** Button is disabled while a render is in-flight (determined by the polling state) to prevent duplicate jobs.

### Failure handling
- **D-18:** Render job implements **exponential backoff retry: 3 attempts** (initial + 2 retries, ~2s / ~8s / ~30s delays). On permanent failure, log the error to `agent_runs` (or an equivalent run log) with the bundle_id and exception detail. **Silent-fail** from the operator's POV — no WhatsApp alert, no modal error banner. Image slots just never populate.
- **D-19:** The agent cron and bundle persistence are **never blocked** by render failures. A failed render does not mark the bundle as failed, does not prevent the operator from approving it.

### Backfill
- **D-20:** **Forward-only.** New bundles (post-Phase-11 ship) render automatically. Existing bundles get renders only if the operator clicks "Regenerate images" while viewing them — no migration script, no mass API spend.

### Endpoint shape
- **D-21:** `GET /content-bundles/{id}` returns the full `ContentBundle` as `ContentBundleDetailResponse` (new Pydantic schema — superset of the thin existing `ContentBundleResponse`). Includes `draft_content` (JSONB, unknown-typed on frontend but format-aware rendering handles the shape), `deep_research`, `rendered_images`, `story_headline`, `story_url`, `source_name`, `content_type`, `score`, `quality_score`, `compliance_passed`, `created_at`. JWT-protected like all other endpoints.
- **D-22:** `POST /content-bundles/{id}/rerender` returns `202 Accepted` with `{ "bundle_id", "render_job_id", "enqueued_at" }`. No synchronous response content — frontend relies on polling to pick up the new images.

### Frontend format rendering
- **D-23:** `ContentDetailModal` becomes a format-aware dispatcher. Format detection comes from `bundle.content_type` (already persisted). Renderers per format:
  - `infographic` → `InfographicPreview` (existing, needs minor props work) side-by-side Twitter + Instagram (IG in a 3-card carousel layout)
  - `thread` → Tweet-list component + "long_form_post" as a final card
  - `long_form` → Single long-post card
  - `breaking_news` → Tweet card + optional infographic_brief preview when present
  - `quote` → Twitter post card + Instagram post card side-by-side
  - `video_clip` → Twitter caption card + Instagram caption card + external video link
- **D-24:** Fallback: if bundle fetch fails or `content_type` is unknown, render the flat `DraftAlternative.text` (existing behavior) so the modal never breaks.

### Claude's Discretion
- Exact prompt text sent to Nano Banana / Gemini (subject to D-05 brand-color constraint and slide spec from draft_content).
- Card styling/spacing inside new format renderers, as long as the brand palette and shadcn primitives are respected.
- Whether to expose a small in-modal "render status" indicator (e.g., "last rendered 2m ago") — planner may include if trivial, skip if it bloats the modal.
- Whether the render job persists itself into `agent_runs` with a new `agent_name` (e.g., `image_render`) or just logs to app logs — planner call.
- Pydantic schema naming (`ContentBundleDetailResponse` is a suggestion).

</decisions>

<specifics>
## Specific Ideas

- Reference bundle for end-to-end verification: `c0ae9cd9-0fc2-47e4-80d5-f354976107b8` — "African central banks gold accumulation" infographic. Full `draft_content` with `instagram_brief` (headline, 3-slide carousel spec, caption) and `key_stats` array. After Phase 11 ships this bundle should render 4 images when the operator hits regen.
- User saw live Nano Banana mockups of that same bundle (3 Instagram slides — cream headline, two-column comparison, navy "0.02" punchline) and said "looks pretty good, some edits needed later." Text fidelity is acceptable; brand-color accuracy and carousel layout fidelity are the priorities. This sets the quality bar.
- Brand palette (non-negotiable): `#F0ECE4` cream background, `#0C1B32` navy text, `#D4AF37` gold accents. Headlines in navy on cream; punchline slides can invert (navy bg, gold number).

</specifics>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Prior phase context (decisions that carry forward)
- `.planning/phases/07-content-agent/07-CONTEXT.md` — Content Agent pipeline, ContentBundle schema, format decisions (infographic `current_data` vs `historical_pattern` mode, quote/video_clip dual-platform shape)
- `.planning/phases/08-dashboard-views-and-digest/08-CONTEXT.md` — Dashboard conventions, ContentPage / ContentDetailModal origin, existing Infographic preview decision ("stat cards layout"), shadcn Dialog usage
- `.planning/phases/03-react-approval-dashboard/03-CONTEXT.md` — TanStack Query + Zustand split, ApprovalCard conventions

### Project-level
- `CLAUDE.md` — Stack constraints (FastAPI 0.135, SQLAlchemy 2.0 async, APScheduler 3.11.2 single-process, React 19 + Tailwind v4, anthropic 0.86.0). Brand palette source.
- `.planning/PROJECT.md` — Core value: every piece of content must be genuinely valuable.
- `.planning/REQUIREMENTS.md` — v1 requirements, especially CREV-* (content review) requirements this phase expands.
- `.planning/ROADMAP.md` §Phase 11 — phase goal + success criteria + scope decisions locked

### Source files researcher should read (already identified)
- `scheduler/agents/content_agent.py` — ContentAgent pipeline; `build_draft_item()` at line 380 flattens structured draft_content; infographic handling lines 426–436; `_research_and_draft()` at line 936. Integration point for render enqueue is after bundle commit.
- `scheduler/models/content_bundle.py` (and `backend/app/models/content_bundle.py` mirror) — add `rendered_images` column via Alembic migration.
- `scheduler/worker.py` — APScheduler setup; `with_advisory_lock()` helper. New one-off render jobs register here (or via a helper).
- `backend/app/routers/` — location for new `content_bundles.py` router.
- `backend/app/schemas/` — new `ContentBundleDetailResponse`.
- `frontend/src/components/approval/ContentDetailModal.tsx` — rewrite target.
- `frontend/src/components/content/InfographicPreview.tsx` — orphaned reusable component; wire back in.
- `frontend/src/components/approval/ContentSummaryCard.tsx` — card that opens the modal; may need to pass content_bundle_id to modal prop instead of extracting from engagement_snapshot inside modal.
- `frontend/src/api/types.ts` — add `ContentBundleDetailResponse` and `RenderedImage` types; extend existing `ContentBundleResponse`.
- `frontend/src/api/content.ts` (or nearest API module) — add `getContentBundle(id)` and `rerenderContentBundle(id)` calls.

### External docs (to read during research)
- Cloudflare R2 Python SDK / boto3-compatible docs — for upload client code
- Nano Banana / Gemini image generation API docs — current rate limits, image size constraints, prompt structure
- APScheduler `DateTrigger` for one-off job scheduling

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `InfographicPreview` (`frontend/src/components/content/InfographicPreview.tsx`) — orphaned 66-line preview component already aligned with the brief's shape. Primary reuse target.
- `Dialog` from shadcn — ContentDetailModal already uses it; keep the modal shell, swap the body.
- `useApprove(platform)` / `useReject(platform)` hooks — still used by the modal's action buttons.
- `ContentSummaryCard` — upstream card that opens modal; already parses `engagement_snapshot.content_bundle_id`, passes item through.
- `EmptyState` — for the "bundle fetch failed" fallback.
- TanStack Query — `refetchInterval` + `enabled` flags give the skeleton+poll pattern for free.
- APScheduler worker already running in Railway — reuse for render jobs, no new service needed.
- Existing `agent_runs` table — can log render attempts/failures without new schema.

### Established Patterns
- All backend routes JWT-protected via shared dependency — new content-bundles routes follow suit.
- All schema changes via Alembic async migrations (never `Base.metadata.create_all()`).
- Scheduler and backend each have their own SQLAlchemy model copy — both must be updated when adding the `rendered_images` column.
- Env config via pydantic-settings `Settings` class — R2 credentials land there.
- Async-first: use `httpx.AsyncClient`, `anthropic.AsyncAnthropic`, `AsyncSession`. No sync I/O inside jobs.

### Integration Points
- Render enqueue: after `ContentAgent` commits a bundle whose `content_type in {"infographic", "quote"}` AND `compliance_passed is True`.
- Render job scheduling: APScheduler `DateTrigger(run_date=datetime.utcnow())` — fires immediately, runs in the same worker process.
- Modal → bundle: `item.engagement_snapshot.content_bundle_id` (already populated). If not present, modal falls back to plain-text rendering.
- Frontend polling: TanStack Query `{ refetchInterval: (data) => data?.rendered_images?.length ? false : 5000 }` — stops polling once images arrive.

</code_context>

<deferred>
## Deferred Ideas

Captured here so they're not lost, but explicitly **out of scope** for Phase 11:

- **Per-slide regeneration** — separate buttons for "regenerate slide 2 only" etc. Nice-to-have if operator frequently has one bad slide, but adds UI complexity and backend per-slot plumbing. Revisit if the per-bundle regen button proves too blunt.
- **Backfill migration** — render images for every existing infographic/quote bundle in one go. Not doing it per D-20; if the operator wants historical coverage, the regen button covers it lazily. Could become Phase 11.1 if the manual approach is painful.
- **Template-based rendering fallback** — an offline PIL/canvas renderer for bundles where AI fails repeatedly. User explicitly chose AI-only for v1.0.1. Revisit only if AI render failure rate proves unacceptable in production.
- **Multi-variant generation** — ask Nano Banana for 2–3 variations per slide and let the operator pick. Useful editorially but 2–3x the cost and longer latency. Out of scope.
- **Image editing inside the dashboard** — text tweaks, color adjustments, crop. Out of scope; operator edits the brief and regens if an image is wrong.
- **WhatsApp alert on render failure** — user chose silent-fail per D-18. Could be toggled on later via config if render failures become common.
- **Rendering for thread / long_form / breaking_news / video_clip** — text-first formats. If breaking_news sometimes includes an `infographic_brief` sub-spec and operators want that rendered too, could be a Phase 11.1 ticket.

</deferred>

---

*Phase: 11-content-preview-and-rendered-images*
*Context gathered: 2026-04-16*
