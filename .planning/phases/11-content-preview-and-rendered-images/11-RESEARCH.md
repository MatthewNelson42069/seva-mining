# Phase 11: Content Preview and Rendered Images — Research

**Researched:** 2026-04-16
**Domain:** Cloudflare R2, Google Gemini image generation (Imagen 4 / Nano Banana), APScheduler one-off jobs, FastAPI async endpoints, TanStack Query polling, React format-aware modal rendering
**Confidence:** HIGH

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- **D-01:** AI image generation via Nano Banana / Gemini image API. No template-based rendering.
- **D-02:** Each infographic bundle produces 4 images: `twitter_visual`, `instagram_slide_1`, `instagram_slide_2`, `instagram_slide_3`.
- **D-03:** Each quote bundle produces 2 images: `twitter_visual`, `instagram_slide_1`.
- **D-04:** No rendering for thread, long_form, breaking_news, video_clip — text-only.
- **D-05:** Prompts enforce brand palette (`#F0ECE4` cream, `#0C1B32` navy, `#D4AF37` gold). Brand colors are locked; exact prompt text is Claude's discretion.
- **D-06:** Images stored in Cloudflare R2 (S3-compatible, free egress, public URLs, ~$0.015/GB-mo). Env vars: `R2_ACCOUNT_ID`, `R2_ACCESS_KEY_ID`, `R2_SECRET_ACCESS_KEY`, `R2_BUCKET`, `R2_PUBLIC_BASE_URL`.
- **D-07:** R2 object key: `content-bundles/{bundle_id}/{role}-{timestamp}.png`. Timestamp suffix keeps old renders.
- **D-08:** `rendered_images` JSONB column on `content_bundles` — array of `{ "role": "...", "url": "...", "generated_at": "ISO-8601" }`. Nullable.
- **D-09:** Image rendering is background job, independent of Content Agent cron. Agent commits and returns in <5s.
- **D-10:** APScheduler one-off DateTrigger job fired immediately after bundle commit. Reuses existing scheduler worker. No Redis/Celery.
- **D-11:** Compliance checker runs before rendering — do not render a bundle that failed compliance.
- **D-12:** TanStack Query refetchInterval polls every 5s until images land (or 5-minute ceiling).
- **D-13:** Structured brief renders immediately regardless of image state.
- **D-14:** Bundles older than 10 minutes with no rendered images stop polling; brief-only display.
- **D-15:** Single "Regenerate images" button — one click = one retry. Posts to `POST /content-bundles/{id}/rerender`. Modal returns to skeleton + poll state.
- **D-16:** Regen works on any bundle including old ones. Old R2 objects kept; `rendered_images` overwritten.
- **D-17:** Regen button disabled while render is in-flight (determined by polling state).
- **D-18:** Exponential backoff retry: 3 attempts (~2s / ~8s / ~30s). On permanent failure, log to `agent_runs`. Silent-fail from operator POV.
- **D-19:** Agent cron and bundle persistence never blocked by render failures.
- **D-20:** Forward-only. No backfill migration script.
- **D-21:** `GET /content-bundles/{id}` returns `ContentBundleDetailResponse`. JWT-protected.
- **D-22:** `POST /content-bundles/{id}/rerender` returns `202 Accepted` with `{ "bundle_id", "render_job_id", "enqueued_at" }`.
- **D-23:** `ContentDetailModal` becomes format-aware dispatcher. Format detection from `bundle.content_type`.
- **D-24:** Fallback: if bundle fetch fails or `content_type` unknown, render flat `DraftAlternative.text` (existing behavior).

### Claude's Discretion
- Exact prompt text to Nano Banana / Gemini (subject to D-05 brand-color constraint).
- Card styling/spacing inside new format renderers (brand palette + shadcn primitives).
- Whether to expose a small in-modal "render status" indicator.
- Whether render job persists itself into `agent_runs` with `agent_name='image_render'` or just logs.
- Pydantic schema naming (`ContentBundleDetailResponse` is a suggestion).

### Deferred Ideas (OUT OF SCOPE)
- Per-slide regeneration
- Backfill migration script
- Template-based rendering fallback (PIL/canvas)
- Multi-variant generation (2-3 variants per slide)
- Image editing inside the dashboard
- WhatsApp alert on render failure
- Rendering for thread / long_form / breaking_news / video_clip
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| CREV-02 | Full draft displayed with format choice and rationale | D-21 endpoint + D-23 modal rewrite; format-aware renderer findings |
| CREV-04 | Infographic preview when applicable | InfographicPreview reuse + D-02 image rendering findings |
| NEW-01 | GET /content-bundles/{id} endpoint (full bundle detail) | Backend router pattern research, new ContentBundleDetailResponse schema |
| NEW-02 | Background render job fires after bundle commit | APScheduler DateTrigger one-off pattern, google-genai async, R2 upload |
| NEW-03 | rendered_images JSONB column via Alembic migration | Existing migration pattern 0001-0005, both model files |
| NEW-04 | Frontend polls for rendered images until they land | TanStack Query refetchInterval with condition pattern |
| NEW-05 | POST /content-bundles/{id}/rerender endpoint | 202 Accepted pattern, scheduler job enqueue from HTTP context |
| NEW-06 | ContentDetailModal format-aware rewrite | Component architecture findings, InfographicPreview props |
| NEW-07 | engagement_snapshot.content_bundle_id surfaced to frontend | Critical gap: DraftItemResponse schema must include engagement_snapshot |
</phase_requirements>

---

## Summary

Phase 11 has six discrete technical domains that must be integrated into the existing codebase without disrupting live agents. The critical path runs: (1) Alembic migration adding `rendered_images` column — both model files, (2) backend detail endpoint, (3) render service using google-genai async + aioboto3 for R2, (4) APScheduler one-off job integration into worker, (5) frontend `useContentBundle` hook with polling, (6) ContentDetailModal rewrite.

The most important research finding is that **`engagement_snapshot` is not in `DraftItemResponse`** — neither in the backend Pydantic schema nor the frontend TypeScript type. The content bundle ID that lives in `draft_item.engagement_snapshot["content_bundle_id"]` is invisible to the frontend today. Adding it is the prerequisite for everything else in this phase. This must be Wave 0 work.

The second key finding is that the image generation API name "Nano Banana" refers to Gemini's native multimodal image generation (using `response_modalities=["IMAGE"]` in `generate_content`), distinct from Imagen 4 (which uses `generate_images`). Both are available from the same `google-genai` SDK. **Imagen 4 is recommended** ($0.02–$0.04/image, higher quality, deterministic sizing) over the Gemini flash image model (token-based pricing, less predictable). For 4 images/bundle at $0.04 each = $0.16/bundle. R2 upload uses `aioboto3` (the async boto3 wrapper) since the project is async-first throughout.

**Primary recommendation:** Use `google-genai` SDK with `client.aio.models.generate_images(model="imagen-4.0-generate-001")` for image generation; use `aioboto3` for async R2 uploads; enqueue render jobs via `scheduler.add_job(..., 'date', run_date=datetime.utcnow())` from inside the ContentAgent after bundle commit.

---

## Standard Stack

### Core (new dependencies this phase)

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| google-genai | 1.73.1 | Gemini / Imagen image generation | Official Google Gen AI Python SDK; supports both Imagen 4 (`generate_images`) and Nano Banana native generation (`generate_content` with IMAGE modality); `client.aio` provides async interface |
| google-genai[aiohttp] | same | Async HTTP transport for google-genai | Required extra for async operations (`pip install google-genai[aiohttp]`) |
| aioboto3 | 15.5.0 | Async S3/R2 uploads | boto3 wrapper with aiobotocore backend; fully async via `async with session.client("s3") as s3`; supports all S3-compatible operations including R2 |

### Existing Stack (confirmed compatible)

| Library | Version | Purpose | Phase 11 Use |
|---------|---------|---------|--------------|
| APScheduler | 3.11.2 | Job scheduling | One-off `DateTrigger` jobs for render pipeline |
| httpx | 0.27.x | Async HTTP | Already in project; google-genai uses its own transport |
| SQLAlchemy | 2.0 async | ORM | `rendered_images` JSONB column, async session in render job |
| TanStack Query | 5.x | Frontend state | `refetchInterval` + `enabled` for polling |
| anthropic | 0.86.0 | Compliance check | Already wired; runs before render (D-11) |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Imagen 4 (`generate_images`) | Nano Banana (`generate_content` with IMAGE modality) | Nano Banana uses token-based pricing (~$0.045-$0.067/image) vs Imagen 4 flat $0.02-$0.04; Imagen 4 has deterministic image sizes; both return bytes not URLs |
| aioboto3 | boto3 via `asyncio.to_thread` | `asyncio.to_thread` is acceptable for low-frequency uploads but aioboto3 is idiomatic for the async stack; aioboto3 adds a dep but avoids sync blocking |
| APScheduler DateTrigger | `asyncio.create_task` | `create_task` is simpler but runs in the same coroutine scope; DateTrigger runs through the scheduler's job store and logs like other jobs; better observability |

**Installation:**
```bash
# In scheduler/pyproject.toml dependencies:
uv add google-genai[aiohttp] aioboto3
```

**Version verification (run at implementation time):**
```bash
uv run pip show google-genai aioboto3
```

---

## Architecture Patterns

### Recommended Project Structure (new files)

```
scheduler/
├── agents/
│   ├── content_agent.py         # MODIFY: add render job enqueue after bundle commit
│   └── image_render_agent.py    # NEW: ImageRenderAgent with render_bundle() coroutine
├── models/
│   └── content_bundle.py        # MODIFY: add rendered_images JSONB column
├── worker.py                     # MODIFY: expose scheduler reference for job registration
backend/
├── app/
│   ├── models/
│   │   └── content_bundle.py    # MODIFY: mirror rendered_images column
│   ├── schemas/
│   │   ├── content_bundle.py    # MODIFY: add ContentBundleDetailResponse
│   │   └── draft_item.py        # MODIFY: add engagement_snapshot to DraftItemResponse
│   └── routers/
│       └── content_bundles.py   # NEW: GET /content-bundles/{id} + POST /content-bundles/{id}/rerender
└── alembic/versions/
    └── 0006_add_rendered_images.py  # NEW: Alembic migration
frontend/src/
├── api/
│   ├── types.ts                 # MODIFY: add ContentBundleDetailResponse, RenderedImage, engagement_snapshot
│   └── content.ts               # MODIFY: add getContentBundle(id), rerenderContentBundle(id)
├── hooks/
│   └── useContentBundle.ts      # NEW: TanStack Query hook with refetchInterval
├── components/
│   ├── approval/
│   │   ├── ContentDetailModal.tsx       # REWRITE: format-aware dispatcher
│   │   └── ContentSummaryCard.tsx       # MODIFY: pass content_bundle_id to modal
│   └── content/
│       ├── InfographicPreview.tsx        # MODIFY: extend for rendered images
│       ├── ThreadPreview.tsx             # NEW: thread format renderer
│       ├── LongFormPreview.tsx           # NEW: long_form renderer
│       ├── BreakingNewsPreview.tsx       # NEW: breaking_news renderer
│       ├── QuotePreview.tsx              # NEW: quote renderer
│       └── VideoClipPreview.tsx          # NEW: video_clip renderer
```

### Pattern 1: APScheduler One-Off DateTrigger from Async Context

**What:** After bundle commit in `content_agent.py`, enqueue an immediate one-off render job into the already-running scheduler. The scheduler instance must be accessible from the agent code.

**When to use:** Any time an agent needs to fire a background task from inside an async job function without blocking the agent's run.

**Key constraint:** The scheduler instance in `worker.py` is currently local to `main()`. It must be promoted to a module-level variable so agents can reference it.

```python
# scheduler/worker.py — promote scheduler to module level
_scheduler: AsyncIOScheduler | None = None

async def main() -> None:
    global _scheduler
    ...
    _scheduler = await build_scheduler(engine)
    _scheduler.start()
    ...

def get_scheduler() -> AsyncIOScheduler:
    if _scheduler is None:
        raise RuntimeError("Scheduler not started")
    return _scheduler
```

```python
# scheduler/agents/content_agent.py — enqueue render job after bundle commit
from worker import get_scheduler  # late import inside _run_pipeline to avoid circular

if compliance_ok and draft_content.get("format") in {"infographic", "quote"}:
    from datetime import datetime, timezone
    from apscheduler.triggers.date import DateTrigger
    scheduler = get_scheduler()
    scheduler.add_job(
        render_bundle_job,          # module-level async function in image_render_agent
        trigger=DateTrigger(run_date=datetime.now(timezone.utc)),
        args=[str(bundle.id)],
        id=f"render_{bundle.id}",
        name=f"Image render — bundle {bundle.id}",
        replace_existing=True,      # if regen button fires again before first completes
    )
```

**Important:** `add_job` is synchronous and safe to call from inside an async function. DateTrigger with `run_date=datetime.now(timezone.utc)` fires immediately on the next scheduler loop tick.

**Source:** APScheduler 3.x docs — https://apscheduler.readthedocs.io/en/3.x/modules/triggers/date.html

### Pattern 2: Async R2 Upload with aioboto3

**What:** Upload PNG bytes returned from google-genai to Cloudflare R2 using the async S3-compatible client. R2 public bucket + `R2_PUBLIC_BASE_URL` env var produces the final public URL.

```python
# Source: aioboto3 docs + Cloudflare R2 boto3 docs
import aioboto3
from config import get_settings

async def upload_image_to_r2(image_bytes: bytes, object_key: str) -> str:
    """Upload image bytes to R2, return public URL."""
    settings = get_settings()
    session = aioboto3.Session()
    async with session.client(
        "s3",
        endpoint_url=f"https://{settings.r2_account_id}.r2.cloudflarestorage.com",
        aws_access_key_id=settings.r2_access_key_id,
        aws_secret_access_key=settings.r2_secret_access_key,
        region_name="auto",  # required by boto3 SDK but ignored by R2
    ) as s3:
        await s3.put_object(
            Bucket=settings.r2_bucket,
            Key=object_key,
            Body=image_bytes,
            ContentType="image/png",
        )
    # Public URL = base URL + object key (no signing needed for public bucket)
    return f"{settings.r2_public_base_url.rstrip('/')}/{object_key}"
```

**R2 public bucket note:** Enabling "public access" on the R2 bucket in the Cloudflare dashboard makes ALL objects accessible via `{public_base_url}/{key}` without any signature. No ACL parameter needed in `put_object` — R2 doesn't use ACLs. `R2_PUBLIC_BASE_URL` is either the r2.dev subdomain Cloudflare assigns or a custom domain.

**Source:** https://developers.cloudflare.com/r2/examples/aws/boto3/ + https://developers.cloudflare.com/r2/buckets/public-buckets/

### Pattern 3: Async Imagen 4 Image Generation

**What:** Use `google-genai` SDK with Imagen 4 model. The async interface is `client.aio.models.generate_images()`. Response contains image bytes (not URLs).

```python
# Source: https://ai.google.dev/gemini-api/docs/imagen
import google.genai as genai
from google.genai import types

async def generate_image(prompt: str, aspect_ratio: str = "1:1") -> bytes:
    """Generate a single image. Returns PNG bytes."""
    client = genai.Client()  # reads GEMINI_API_KEY from env
    response = await client.aio.models.generate_images(
        model="imagen-4.0-generate-001",
        prompt=prompt,
        config=types.GenerateImageConfig(
            number_of_images=1,
            aspect_ratio=aspect_ratio,  # "1:1", "16:9", "9:16", "3:4", "4:3"
            output_mime_type="image/png",
        ),
    )
    return response.generated_images[0].image.image_bytes
```

**Aspect ratios for this phase:**
- `twitter_visual`: `"16:9"` (landscape, ~1600x900 equivalent)
- `instagram_slide_*`: `"1:1"` (square, 1K default)

**Response format:** `response.generated_images[0].image.image_bytes` — raw bytes, not a URL or base64 string. You write these bytes directly to R2.

**Authentication:** Set `GEMINI_API_KEY` environment variable. The `genai.Client()` constructor reads it automatically.

**Source:** https://ai.google.dev/gemini-api/docs/imagen

### Pattern 4: Alembic Migration for JSONB Column

**What:** Hand-written migration (not autogenerate). The existing migrations (0001-0005) are all hand-written. The new migration adds `rendered_images` JSONB nullable column.

```python
# backend/alembic/versions/0006_add_rendered_images.py
"""Add rendered_images JSONB column to content_bundles

Revision ID: 0006
Revises: 0005
Create Date: 2026-04-16
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None

def upgrade() -> None:
    op.add_column(
        "content_bundles",
        sa.Column("rendered_images", postgresql.JSONB(), nullable=True),
    )

def downgrade() -> None:
    op.drop_column("content_bundles", "rendered_images")
```

**Critical:** Both `scheduler/models/content_bundle.py` AND `backend/app/models/content_bundle.py` must get the new column. The project pattern (from Phase 04 decision) is that scheduler models mirror backend models manually — no shared package.

### Pattern 5: TanStack Query Polling with Condition

**What:** `useContentBundle` hook polls every 5s, stops when images arrive or 10-minute window expires.

```typescript
// Source: TanStack Query v5 docs — refetchInterval with callback
import { useQuery } from '@tanstack/react-query'
import { getContentBundle } from '@/api/content'

const MAX_POLL_MS = 10 * 60 * 1000 // 10 minutes

export function useContentBundle(bundleId: string | null | undefined) {
  return useQuery({
    queryKey: ['content-bundle', bundleId],
    queryFn: () => getContentBundle(bundleId!),
    enabled: !!bundleId,
    refetchInterval: (query) => {
      const data = query.state.data
      if (!data) return false
      // Stop polling if images have landed
      if (data.rendered_images && data.rendered_images.length > 0) return false
      // Stop polling if bundle is older than 10 minutes
      const age = Date.now() - new Date(data.created_at).getTime()
      if (age > MAX_POLL_MS) return false
      // Images not yet landed and bundle is recent — keep polling
      return 5000
    },
  })
}
```

**Important TanStack Query v5 note:** `refetchInterval` accepts a function whose argument is `query: Query` (not `data` directly). The data is at `query.state.data`. This changed in v5.

### Pattern 6: Format-Aware Modal Dispatcher

**What:** ContentDetailModal fetches bundle by ID (from `item.engagement_snapshot?.content_bundle_id`) and dispatches to per-format renderer components.

**Current state of ContentDetailModal:** 128-line component showing flat `DraftAlternative.text`. No bundle fetching. Must be rewritten with format-aware dispatch (D-23) while preserving the approve/reject actions in ContentSummaryCard (those already use separate hooks — `useApprove`, `useReject` — and are not inside ContentDetailModal).

**What's preserved from ContentSummaryCard:** Approve/Reject buttons and their handlers live in ContentSummaryCard, not in ContentDetailModal. The modal is read-only (review only). This architecture is already correct and does not need to change.

**The format dispatch pattern:**
```typescript
// ContentDetailModal.tsx (skeleton)
const bundleId = item.engagement_snapshot?.content_bundle_id
const { data: bundle } = useContentBundle(bundleId)
const format = bundle?.content_type ?? 'unknown'

switch (format) {
  case 'infographic': return <InfographicPreview draft={bundle.draft_content} images={bundle.rendered_images} />
  case 'thread': return <ThreadPreview draft={bundle.draft_content} />
  case 'long_form': return <LongFormPreview draft={bundle.draft_content} />
  case 'breaking_news': return <BreakingNewsPreview draft={bundle.draft_content} />
  case 'quote': return <QuotePreview draft={bundle.draft_content} />
  case 'video_clip': return <VideoClipPreview draft={bundle.draft_content} />
  default: return <FlatTextFallback item={item} />  // D-24
}
```

### Anti-Patterns to Avoid

- **Calling `scheduler.add_job` from a FastAPI route:** The scheduler runs in the scheduler worker process; the API backend is a separate Railway service. `POST /content-bundles/{id}/rerender` cannot directly call `scheduler.add_job`. Instead, the endpoint must trigger the render in the scheduler's context — the simplest approach is a DB-based job queue: the endpoint writes a "pending render" record or flag, and the scheduler polls for it OR the render job is implemented as a standalone async function that the backend can call via an internal HTTP call to the scheduler worker. **Recommended:** Rerender endpoint writes to the `rendered_images` column (clearing it) and then calls the render function directly in the background via `asyncio.create_task` from the backend's own process, since the render logic doesn't need to be in the scheduler worker — it just needs DB access and external API keys. This avoids cross-process coordination entirely.
- **Storing image URLs in `draft_content` JSONB:** The schema decision (D-08) puts `rendered_images` in its own dedicated column, not nested inside `draft_content`. Keep these concerns separate.
- **Using sync boto3 in async context:** Always use `aioboto3` for uploads inside APScheduler async jobs. Using `boto3` directly would require `asyncio.to_thread`, which is acceptable but less clean.
- **Assuming `engagement_snapshot` is in DraftItemResponse:** It is NOT currently in the schema. This is a required addition before the modal can get `content_bundle_id`.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Async S3/R2 uploads | Manual httpx calls to R2 REST API | aioboto3 | S3 API has multipart upload edge cases, signature v4 complexity, error handling |
| Image generation | PIL/canvas template rendering | google-genai Imagen 4 | User explicitly chose AI; template approach rejected in discuss phase |
| Polling state | Custom WebSocket or SSE | TanStack Query refetchInterval | Already in project; 5s HTTP poll is sufficient for ~2min render latency |
| Background jobs | Redis task queue / Celery | APScheduler DateTrigger | CLAUDE.md explicitly prohibits Celery; APScheduler 3.11.2 already running |
| Base64 decode of response | Manual | `response.generated_images[0].image.image_bytes` | google-genai SDK returns bytes directly; no base64 step needed |

**Key insight:** The image bytes pipeline is: `google-genai → Python bytes → aioboto3 put_object → R2 public URL`. There is no filesystem write, no base64 encode/decode cycle, and no temporary file.

---

## Common Pitfalls

### Pitfall 1: Cross-Process Scheduler Access for Rerender Endpoint

**What goes wrong:** `POST /content-bundles/{id}/rerender` lives in the FastAPI backend (separate Railway service). Calling `scheduler.add_job()` from the backend would reference the wrong process's scheduler.

**Why it happens:** Phase 11 assumes a single scheduler worker process that also handles ad-hoc render jobs. But the HTTP endpoint for rerender is in the backend.

**How to avoid:** Two clean options:
- Option A (simpler): Backend endpoint clears `rendered_images` column to null/empty, then `asyncio.create_task`s a render coroutine directly inside the backend's event loop. The render function (image generation + R2 upload + DB write) doesn't need to be in the scheduler worker — it needs DB access and API keys, both available in the backend.
- Option B: ContentAgent enqueues via the scheduler worker; rerender endpoint writes a flag to DB; scheduler polls the flag and re-fires. More complex, not needed here.

**Recommended:** Option A — the render coroutine lives in a shared module importable by both backend and scheduler. Backend calls it for rerender; scheduler calls it post-bundle-commit.

**Warning signs:** If planning involves an RPC call from backend to scheduler or a message queue for this single use case, stop and use Option A instead.

### Pitfall 2: DraftItemResponse Missing engagement_snapshot

**What goes wrong:** Frontend cannot get `content_bundle_id` because `engagement_snapshot` is not in `DraftItemResponse` Pydantic schema OR TypeScript type.

**Why it happens:** The field was intentionally omitted from the serialized response schema when the content agent was built (it stores internal data). But Phase 11 now needs it.

**How to avoid:** Wave 0 task must:
1. Add `engagement_snapshot: Optional[Any] = None` to `backend/app/schemas/draft_item.py`
2. Add `engagement_snapshot?: Record<string, unknown>` to `DraftItemResponse` in `frontend/src/api/types.ts`

**Warning signs:** If `ContentDetailModal` tries to access `item.engagement_snapshot?.content_bundle_id` and always gets undefined, this is the cause.

### Pitfall 3: Imagen 4 Response Contains Bytes, Not URL

**What goes wrong:** Developer expects a URL from the Imagen API and tries to persist the response URL. No URL is returned.

**Why it happens:** Imagen 4 returns `response.generated_images[0].image.image_bytes` — raw PNG bytes. This is different from DALL-E (which returns URLs).

**How to avoid:** The pipeline must be: bytes → R2 upload → construct public URL from `R2_PUBLIC_BASE_URL + "/" + object_key`. Never try to persist the API response as a URL.

**Warning signs:** Any code that does `str(response)` or looks for `.url` attribute on image response.

### Pitfall 4: R2 ACL vs Public Bucket

**What goes wrong:** Developer adds `ACL='public-read'` to `put_object` call, which R2 silently ignores or raises an error.

**Why it happens:** AWS S3 uses per-object ACLs for public access. R2 does not — public access is bucket-level configuration in the Cloudflare dashboard.

**How to avoid:** Enable public access on the R2 bucket once in the Cloudflare dashboard. Do NOT pass ACL parameter to `put_object`. All objects in a public bucket are accessible via `{public_base_url}/{key}`.

### Pitfall 5: GEMINI_API_KEY vs ANTHROPIC_API_KEY Confusion

**What goes wrong:** The render agent initializes with `anthropic_api_key` or the wrong env var name.

**Why it happens:** The project uses `anthropic` for all current LLM calls. Imagen 4 uses a separate `GEMINI_API_KEY`.

**How to avoid:** Add `gemini_api_key: Optional[str] = None` to both `backend/app/config.py` and `scheduler/config.py` Settings classes. The `genai.Client()` constructor reads `GEMINI_API_KEY` from the environment automatically — no need to pass it explicitly if the env var name matches.

### Pitfall 6: APScheduler Job ID Collision on Rerender

**What goes wrong:** If operator hits regen while a render is already in-flight, `scheduler.add_job` raises `ConflictingIdError`.

**Why it happens:** Jobs registered with the same `id` conflict by default.

**How to avoid:** Use `replace_existing=True` in `scheduler.add_job()` call, OR use a unique id like `f"render_{bundle.id}_{datetime.now().timestamp()}"`. The CONTEXT.md says "disabled while a render is in-flight" (D-17), so the frontend should prevent duplicate calls — but the backend should also be defensive with `replace_existing=True`.

### Pitfall 7: TanStack Query v5 refetchInterval Callback Signature

**What goes wrong:** `refetchInterval: (data) => ...` works in TanStack Query v4 but not v5. In v5, the callback receives a `Query` object.

**Why it happens:** Breaking change in TanStack Query v5.

**How to avoid:** Use `refetchInterval: (query) => { const data = query.state.data; ... }` in v5. The project uses TanStack Query v5.

---

## Code Examples

### Image Render Service (scheduler/agents/image_render_agent.py)

```python
# Source: google-genai docs + aioboto3 docs + project patterns
import asyncio
import logging
from datetime import datetime, timezone
from uuid import UUID

import aioboto3
import google.genai as genai
from google.genai import types
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from models.content_bundle import ContentBundle

logger = logging.getLogger(__name__)

BRAND_COLORS = "#F0ECE4 cream background, #0C1B32 navy text, #D4AF37 gold accents"

async def render_bundle_job(bundle_id: str) -> None:
    """Top-level render job function — registered with APScheduler."""
    from database import engine
    from sqlalchemy.ext.asyncio import async_sessionmaker
    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    for attempt in range(3):
        try:
            async with session_factory() as session:
                await _render_and_persist(session, UUID(bundle_id))
            return
        except Exception as exc:
            if attempt < 2:
                delay = 2 ** (attempt + 1)  # 2s, 8s (then 30s would be attempt 3)
                logger.warning("Render attempt %d failed for %s: %s — retrying in %ds",
                               attempt + 1, bundle_id, exc, delay)
                await asyncio.sleep(delay)
            else:
                logger.error("Render permanently failed for %s: %s", bundle_id, exc, exc_info=True)


async def _render_and_persist(session: AsyncSession, bundle_id: UUID) -> None:
    result = await session.execute(select(ContentBundle).where(ContentBundle.id == bundle_id))
    bundle = result.scalar_one_or_none()
    if not bundle or not bundle.compliance_passed:
        return

    client = genai.Client()  # reads GEMINI_API_KEY from env
    images = []
    roles = _roles_for_format(bundle.content_type)
    for role, aspect_ratio in roles:
        prompt = _build_prompt(role, bundle.draft_content, bundle.story_headline)
        image_bytes = await _generate_with_retry(client, prompt, aspect_ratio)
        if image_bytes:
            timestamp = int(datetime.now(timezone.utc).timestamp())
            key = f"content-bundles/{bundle_id}/{role}-{timestamp}.png"
            url = await _upload_to_r2(image_bytes, key)
            images.append({"role": role, "url": url, "generated_at": datetime.now(timezone.utc).isoformat()})

    bundle.rendered_images = images
    await session.commit()


def _roles_for_format(content_type: str) -> list[tuple[str, str]]:
    if content_type == "infographic":
        return [
            ("twitter_visual", "16:9"),
            ("instagram_slide_1", "1:1"),
            ("instagram_slide_2", "1:1"),
            ("instagram_slide_3", "1:1"),
        ]
    if content_type == "quote":
        return [("twitter_visual", "16:9"), ("instagram_slide_1", "1:1")]
    return []


async def _generate_with_retry(client, prompt: str, aspect_ratio: str) -> bytes | None:
    response = await client.aio.models.generate_images(
        model="imagen-4.0-generate-001",
        prompt=prompt,
        config=types.GenerateImageConfig(
            number_of_images=1,
            aspect_ratio=aspect_ratio,
            output_mime_type="image/png",
        ),
    )
    return response.generated_images[0].image.image_bytes


async def _upload_to_r2(image_bytes: bytes, object_key: str) -> str:
    from config import get_settings
    settings = get_settings()
    session = aioboto3.Session()
    async with session.client(
        "s3",
        endpoint_url=f"https://{settings.r2_account_id}.r2.cloudflarestorage.com",
        aws_access_key_id=settings.r2_access_key_id,
        aws_secret_access_key=settings.r2_secret_access_key,
        region_name="auto",
    ) as s3:
        await s3.put_object(Bucket=settings.r2_bucket, Key=object_key,
                            Body=image_bytes, ContentType="image/png")
    return f"{settings.r2_public_base_url.rstrip('/')}/{object_key}"
```

### New Backend Router (backend/app/routers/content_bundles.py)

```python
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from uuid import UUID
from app.database import get_db
from app.dependencies import get_current_user
from app.models.content_bundle import ContentBundle
from app.schemas.content_bundle import ContentBundleDetailResponse, RerenderResponse

router = APIRouter(
    prefix="/content-bundles",
    tags=["content-bundles"],
    dependencies=[Depends(get_current_user)],
)

@router.get("/{bundle_id}", response_model=ContentBundleDetailResponse)
async def get_content_bundle(bundle_id: UUID, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(ContentBundle).where(ContentBundle.id == bundle_id))
    bundle = result.scalar_one_or_none()
    if not bundle:
        raise HTTPException(status_code=404, detail="Content bundle not found")
    return ContentBundleDetailResponse.model_validate(bundle)


@router.post("/{bundle_id}/rerender", status_code=202, response_model=RerenderResponse)
async def rerender_content_bundle(bundle_id: UUID, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(ContentBundle).where(ContentBundle.id == bundle_id))
    bundle = result.scalar_one_or_none()
    if not bundle:
        raise HTTPException(status_code=404, detail="Content bundle not found")
    # Clear existing images so frontend enters polling state
    bundle.rendered_images = []
    await db.commit()
    # Enqueue render job — asyncio.create_task fires in backend's event loop
    import asyncio
    from agents.image_render_agent import render_bundle_job  # shared module
    asyncio.create_task(render_bundle_job(str(bundle_id)))
    job_id = f"rerender_{bundle_id}_{int(__import__('time').time())}"
    return RerenderResponse(bundle_id=bundle_id, render_job_id=job_id,
                            enqueued_at=__import__('datetime').datetime.utcnow().isoformat())
```

### New Frontend Types

```typescript
// frontend/src/api/types.ts additions
export interface RenderedImage {
  role: 'twitter_visual' | 'instagram_slide_1' | 'instagram_slide_2' | 'instagram_slide_3'
  url: string
  generated_at: string
}

export interface ContentBundleDetailResponse {
  id: string
  story_headline: string
  story_url?: string
  source_name?: string
  content_type?: string
  score?: number
  quality_score?: number
  no_story_flag: boolean
  deep_research?: unknown
  draft_content?: unknown
  compliance_passed?: boolean
  rendered_images?: RenderedImage[]
  created_at: string
}

// Extend DraftItemResponse — add engagement_snapshot
export interface DraftItemResponse {
  // ... existing fields ...
  engagement_snapshot?: Record<string, unknown>  // ADD THIS
}
```

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| DALL-E (returns URL) | Imagen 4 (returns bytes) | 2024-2025 | Pipeline must upload bytes to R2; cannot store generation URL directly |
| APScheduler v4 (avoided) | APScheduler 3.11.2 stable | CLAUDE.md directive | DateTrigger API is stable in 3.x; v4 has breaking changes |
| Imagen 3 | Imagen 4 (`imagen-4.0-generate-001`) | 2025 | Imagen 3 shut down per official docs; Imagen 4 is current |
| `google-generativeai` (old SDK) | `google-genai` (new unified SDK) | 2024-2025 | New SDK is the official replacement; import is `from google import genai` |
| TanStack Query v4 `refetchInterval: (data) => ...` | TanStack Query v5 `refetchInterval: (query) => query.state.data...` | v5 release | Breaking callback signature change |

**Deprecated/outdated:**
- `google-generativeai` package: replaced by `google-genai` (the new unified SDK). Do NOT install `google-generativeai`.
- Imagen 3 (`imagen-3.0-generate-002`): shut down per official Google docs as of 2025/2026. Use `imagen-4.0-generate-001`.
- R2 ACL parameters in put_object: not supported by R2. Use public bucket dashboard setting instead.

---

## Open Questions

1. **Render job shared module accessibility**
   - What we know: The backend and scheduler are separate Railway services. A shared `image_render_agent.py` module can be imported by the backend only if it shares the same Python path, OR the render code is duplicated/abstracted differently.
   - What's unclear: Is there a `scheduler/` directory import path accessible from the backend? Both services appear to share the same repo root.
   - Recommendation: Planner should check if the backend `app/` package can import from `scheduler/agents/`. If not, create `backend/app/services/image_render.py` as the backend's render entry point (it can share the same logic without circular imports since it only imports from models and config).

2. **GEMINI_API_KEY env var name**
   - What we know: `genai.Client()` reads `GEMINI_API_KEY` automatically from environment.
   - What's unclear: Whether the operator already has a Gemini API key configured, or if this is a new credential to provision.
   - Recommendation: Add `gemini_api_key: Optional[str] = None` to Settings, and log a WARNING at scheduler startup if it's absent (matching the pattern in `_validate_env`).

3. **R2 bucket already provisioned?**
   - What we know: R2 credentials are in the locked decisions (D-06). Operator mentioned having used Nano Banana for mockups.
   - What's unclear: Whether the R2 bucket and public access are already configured in the Cloudflare dashboard.
   - Recommendation: Wave 0 plan should include a manual checkpoint: "Provision R2 bucket and enable public access in Cloudflare dashboard before Wave 1 executes."

---

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| python3 | All backend/scheduler | Yes | 3.12+ | — |
| google-genai | Image generation | Yes (already installed) | 1.73.1 | — |
| aioboto3 | R2 upload | Not yet in project deps | — | boto3 + asyncio.to_thread |
| GEMINI_API_KEY | genai.Client() | Unknown (env var) | — | Phase blocked without it |
| R2_ACCOUNT_ID etc. | R2 upload | Unknown (env vars) | — | Phase blocked without it |
| Cloudflare R2 bucket (public) | Public URLs | Unknown (must be provisioned) | — | Phase blocked |

**Missing dependencies with no fallback (blocking):**
- `GEMINI_API_KEY` env var — must be provisioned before any image generation test
- R2 credentials (`R2_ACCOUNT_ID`, `R2_ACCESS_KEY_ID`, `R2_SECRET_ACCESS_KEY`, `R2_BUCKET`, `R2_PUBLIC_BASE_URL`) — must be provisioned
- R2 bucket with public access enabled in Cloudflare dashboard

**Missing dependencies with fallback:**
- `aioboto3` — not yet in `scheduler/pyproject.toml` or `backend/requirements.txt`; needs to be added in Wave 0 with `uv add aioboto3`

---

## Validation Architecture

nyquist_validation is enabled (config.json: `"nyquist_validation": true`).

### Test Framework

| Property | Value |
|----------|-------|
| Framework (backend) | pytest + pytest-asyncio, asyncio_mode=auto |
| Framework (frontend) | Vitest + jsdom + Testing Library |
| Config (scheduler) | pyproject.toml `[tool.pytest.ini_options]` |
| Config (frontend) | vite.config.ts with `test.globals=true, environment='jsdom'` |
| Quick run (scheduler) | `cd scheduler && uv run pytest tests/test_content_agent.py -x` |
| Quick run (frontend) | `cd frontend && npm run test` |
| Full suite | `cd scheduler && uv run pytest && cd ../frontend && npm run test` |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| NEW-01 | GET /content-bundles/{id} returns 200 with rendered_images | unit | `cd backend && pytest tests/test_content_bundles.py::test_get_bundle -x` | No — Wave 0 |
| NEW-01 | GET /content-bundles/{id} returns 404 for unknown id | unit | same file | No — Wave 0 |
| NEW-02 | render_bundle_job generates images + uploads to R2 | unit (mocked) | `cd scheduler && uv run pytest tests/test_image_render.py -x` | No — Wave 0 |
| NEW-03 | Alembic migration upgrades and downgrades cleanly | manual | `alembic upgrade head && alembic downgrade -1` | No — new migration |
| NEW-04 | useContentBundle polls until rendered_images arrive | unit | `cd frontend && npm run test -- src/hooks/useContentBundle.test.ts` | No — Wave 0 |
| NEW-05 | POST /content-bundles/{id}/rerender returns 202 | unit | `cd backend && pytest tests/test_content_bundles.py::test_rerender -x` | No — Wave 0 |
| NEW-07 | DraftItemResponse includes engagement_snapshot | unit | `cd backend && pytest tests/test_queue_schema.py -x` | No — Wave 0 |
| CREV-02 | ContentDetailModal shows format-specific content | component | `cd frontend && npm run test -- src/components/approval/ContentDetailModal.test.tsx` | No — Wave 0 |

### Sampling Rate

- **Per task commit:** `cd scheduler && uv run pytest tests/test_image_render.py -x` (render agent) OR `cd frontend && npm run test` (frontend)
- **Per wave merge:** Full suite for both scheduler and frontend
- **Phase gate:** All tests green before `/gsd:verify-work`

### Wave 0 Gaps

- [ ] `scheduler/tests/test_image_render.py` — covers NEW-02 (mocked google-genai + mocked aioboto3)
- [ ] `backend/tests/test_content_bundles.py` — covers NEW-01, NEW-05
- [ ] `frontend/src/hooks/useContentBundle.test.ts` — covers NEW-04
- [ ] `frontend/src/components/approval/ContentDetailModal.test.tsx` — covers CREV-02, D-24 fallback
- [ ] `frontend/src/mocks/handlers.ts` — add MSW handler for `GET /content-bundles/:id` and `POST /content-bundles/:id/rerender`

---

## Critical Pre-Implementation Findings

These findings are not in the CONTEXT.md and must be addressed by the planner:

### Finding 1: engagement_snapshot NOT in DraftItemResponse schema

The `engagement_snapshot` JSONB column exists on the `draft_item` DB model and is populated by `build_draft_item()` in content_agent.py with `{"content_bundle_id": str(bundle.id)}`. However, `DraftItemResponse` in `backend/app/schemas/draft_item.py` does NOT include `engagement_snapshot`. This means the frontend cannot currently access `content_bundle_id` from the queue API response.

**Required changes:**
1. `backend/app/schemas/draft_item.py`: Add `engagement_snapshot: Optional[Any] = None`
2. `frontend/src/api/types.ts`: Add `engagement_snapshot?: Record<string, unknown>` to `DraftItemResponse`

This is a prerequisite for `useContentBundle` to work at all.

### Finding 2: Scheduler Reference for ContentAgent Enqueue

`worker.py` creates the scheduler as a local variable inside `main()`. The `ContentAgent` runs inside the scheduler's job, so it could enqueue new jobs via `scheduler.add_job()` — but only if the scheduler instance is accessible. Currently there is no module-level reference.

**Required change:** Promote scheduler to a module-level variable in `worker.py` with a `get_scheduler()` accessor function.

### Finding 3: Rerender Endpoint Cannot Call scheduler.add_job Directly

The backend (`backend/`) and scheduler (`scheduler/`) are separate Railway services. The rerender endpoint cannot access the scheduler's job queue. Simplest solution: implement `render_bundle_job` as a standalone async function that both the scheduler worker AND the backend can invoke. The backend calls it via `asyncio.create_task(render_bundle_job(str(bundle_id)))`.

### Finding 4: Both Config Files Need R2 and Gemini Keys

Both `backend/app/config.py` and `scheduler/config.py` have `Settings` classes that must be updated with the new env vars. The render function will be called from both contexts.

---

## Sources

### Primary (HIGH confidence)
- Official Cloudflare R2 boto3 docs — https://developers.cloudflare.com/r2/examples/aws/boto3/
- Official Cloudflare R2 public buckets docs — https://developers.cloudflare.com/r2/buckets/public-buckets/
- Official Google Imagen API docs — https://ai.google.dev/gemini-api/docs/imagen
- Official Google Gemini image generation (Nano Banana) docs — https://ai.google.dev/gemini-api/docs/image-generation
- google-genai PyPI page — version 1.73.1, confirmed 2026-04-14 — https://pypi.org/project/google-genai/
- aioboto3 PyPI page — version 15.5.0, confirmed 2026 — https://pypi.org/project/aioboto3/

### Secondary (MEDIUM confidence)
- APScheduler 3.x DateTrigger docs — https://apscheduler.readthedocs.io/en/3.x/modules/triggers/date.html (403 during fetch; content inferred from WebSearch + project knowledge)
- google-genai async pattern — `client.aio.models.generate_images` confirmed by inspecting installed package `dir()` output: `generate_images` confirmed in `client.aio.models`
- aioboto3 put_object pattern — https://aioboto3.readthedocs.io/en/latest/usage.html (403 during fetch; confirmed via multiple secondary sources)

### Tertiary (LOW confidence)
- Imagen 4 pricing ($0.02-$0.04/image) — from Google AI pricing page; pricing can change
- Imagen 4 model name `imagen-4.0-generate-001` — confirmed by official Imagen docs; confirm at implementation time as model names can change

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — google-genai 1.73.1 confirmed on PyPI; aioboto3 15.5.0 confirmed; APScheduler 3.11.2 locked by project
- Architecture: HIGH — existing codebase read in full; patterns confirmed against live source files
- Pitfalls: HIGH — critical findings (engagement_snapshot gap, cross-process scheduler issue) discovered from direct code inspection
- Image generation: MEDIUM — Imagen 4 model name and pricing from official docs but pricing can change; async API confirmed by `dir()` inspection

**Research date:** 2026-04-16
**Valid until:** 2026-05-16 (google-genai model names change frequently — re-verify at implementation)
