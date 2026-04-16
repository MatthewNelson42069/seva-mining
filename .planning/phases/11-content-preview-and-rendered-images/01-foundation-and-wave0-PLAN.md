---
phase: 11-content-preview-and-rendered-images
plan: 01
type: execute
wave: 0
depends_on: []
files_modified:
  - scheduler/pyproject.toml
  - backend/pyproject.toml
  - scheduler/config.py
  - backend/app/config.py
  - scheduler/models/content_bundle.py
  - backend/app/models/content_bundle.py
  - backend/alembic/versions/0006_add_rendered_images.py
  - backend/app/schemas/draft_item.py
  - backend/app/schemas/content_bundle.py
  - scheduler/worker.py
  - .planning/REQUIREMENTS.md
  - scheduler/tests/agents/test_image_render.py
  - scheduler/tests/conftest.py
  - backend/tests/routers/test_content_bundles.py
  - backend/tests/routers/__init__.py
  - backend/tests/test_queue_schema.py
  - frontend/src/api/__tests__/content-bundle.test.ts
  - frontend/src/hooks/__tests__/useContentBundle.test.ts
  - frontend/src/components/approval/__tests__/ContentDetailModal.test.tsx
  - frontend/src/mocks/handlers.ts
  - frontend/src/api/types.ts
autonomous: true
requirements: [CREV-02, CREV-06, CREV-07, CREV-08, CREV-09, CREV-10]

must_haves:
  truths:
    - "Backend and scheduler both import aioboto3 and google-genai without error"
    - "GEMINI_API_KEY, R2_ACCOUNT_ID, R2_ACCESS_KEY_ID, R2_SECRET_ACCESS_KEY, R2_BUCKET, R2_PUBLIC_BASE_URL are all readable from Settings in both services"
    - "ContentBundle model (both scheduler and backend copies) exposes a rendered_images column mapped to PostgreSQL JSONB"
    - "alembic upgrade head applies 0006_add_rendered_images and alembic downgrade -1 reverses it cleanly"
    - "DraftItemResponse Pydantic schema and DraftItemResponse TypeScript type both include engagement_snapshot"
    - "REQUIREMENTS.md CREV section lists CREV-06, CREV-07, CREV-08, CREV-09, CREV-10 mapped to Phase 11"
    - "scheduler.worker exposes a module-level _scheduler variable and a get_scheduler() accessor callable from agent code"
    - "All Wave 0 test files exist and are collected by pytest/vitest (even if individual tests are skipped or failing — tests must be IN the file)"
  artifacts:
    - path: "scheduler/tests/agents/test_image_render.py"
      provides: "Render agent test stubs (mocked imagen + mocked R2)"
      contains: "test_render_bundle_infographic_produces_four_images"
    - path: "backend/tests/routers/test_content_bundles.py"
      provides: "Content bundle endpoint test stubs"
      contains: "test_get_content_bundle_returns_full_bundle"
    - path: "backend/alembic/versions/0006_add_rendered_images.py"
      provides: "Alembic migration for rendered_images JSONB column"
      contains: "rendered_images"
    - path: "scheduler/models/content_bundle.py"
      provides: "Scheduler ContentBundle ORM model with rendered_images"
      contains: "rendered_images"
    - path: "backend/app/models/content_bundle.py"
      provides: "Backend ContentBundle ORM model with rendered_images"
      contains: "rendered_images"
    - path: "backend/app/schemas/draft_item.py"
      provides: "DraftItemResponse with engagement_snapshot field"
      contains: "engagement_snapshot"
  key_links:
    - from: "scheduler/agents/content_agent.py (future)"
      to: "scheduler.worker.get_scheduler()"
      via: "module-level accessor"
      pattern: "get_scheduler"
    - from: "frontend/src/components/approval/ContentDetailModal.tsx (future)"
      to: "item.engagement_snapshot.content_bundle_id"
      via: "queue API response schema"
      pattern: "engagement_snapshot"
---

<objective>
Land the complete foundation for Phase 11 in one atomic wave: dependency adds, env-var settings, Alembic migration, model updates, schema additions (engagement_snapshot + ContentBundleDetailResponse + RerenderResponse + RenderedImage), worker scheduler promotion, REQUIREMENTS.md update, and ALL Wave 0 test stubs.

Purpose: Every downstream plan (02, 03, 04, 05, 06) depends on at least one thing in this list. Landing them together in Wave 0 prevents every subsequent plan from carrying its own dependency toil.

Output: Green-but-skipped test suites, a new Alembic revision applied to local/staging DB, updated Settings classes in both services, a promoted scheduler reference, and 5 new CREV requirements in REQUIREMENTS.md.
</objective>

<execution_context>
@$HOME/.claude/get-shit-done/workflows/execute-plan.md
@$HOME/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/PROJECT.md
@.planning/ROADMAP.md
@.planning/STATE.md
@.planning/REQUIREMENTS.md
@.planning/phases/11-content-preview-and-rendered-images/11-CONTEXT.md
@.planning/phases/11-content-preview-and-rendered-images/11-RESEARCH.md
@.planning/phases/11-content-preview-and-rendered-images/11-VALIDATION.md
@CLAUDE.md

<interfaces>
<!-- Current ContentBundleResponse (backend/app/schemas/content_bundle.py) — add ContentBundleDetailResponse as superset -->
```python
class ContentBundleResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    story_headline: str
    story_url: Optional[str] = None
    source_name: Optional[str] = None
    content_type: Optional[str] = None
    score: Optional[float] = None
    quality_score: Optional[float] = None
    no_story_flag: bool
    deep_research: Optional[Any] = None
    draft_content: Optional[Any] = None
    compliance_passed: Optional[bool] = None
    created_at: datetime
```

<!-- Current DraftItemResponse (backend/app/schemas/draft_item.py) — add engagement_snapshot -->
```python
class DraftItemResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    platform: str
    status: DraftStatusEnum
    source_url: Optional[str] = None
    source_text: Optional[str] = None
    source_account: Optional[str] = None
    follower_count: Optional[float] = None
    score: Optional[float] = None
    quality_score: Optional[float] = None
    alternatives: list = []
    rationale: Optional[str] = None
    urgency: Optional[str] = None
    related_id: Optional[UUID] = None
    rejection_reason: Optional[str] = None
    edit_delta: Optional[str] = None
    expires_at: Optional[datetime] = None
    decided_at: Optional[datetime] = None
    created_at: datetime
    updated_at: Optional[datetime] = None
    # Phase 11 ADDITION: engagement_snapshot: Optional[Any] = None
```

<!-- Current scheduler/worker.py — scheduler is local to main(). Promote to module level. -->
```python
# ADD at module top:
_scheduler: "AsyncIOScheduler | None" = None

def get_scheduler() -> "AsyncIOScheduler":
    if _scheduler is None:
        raise RuntimeError("Scheduler not started")
    return _scheduler

# In main(): replace `scheduler = await build_scheduler(engine)` with:
#     global _scheduler
#     _scheduler = await build_scheduler(engine)
#     _scheduler.start()
# (rename existing `scheduler` local usages)
```
</interfaces>
</context>

<tasks>

<task type="auto" tdd="false">
  <name>Task 1: Dependencies, env-config, REQUIREMENTS.md additions</name>
  <files>
    scheduler/pyproject.toml,
    backend/pyproject.toml,
    scheduler/config.py,
    backend/app/config.py,
    .planning/REQUIREMENTS.md
  </files>
  <read_first>
    /Users/matthewnelson/seva-mining/scheduler/pyproject.toml,
    /Users/matthewnelson/seva-mining/backend/pyproject.toml,
    /Users/matthewnelson/seva-mining/scheduler/config.py,
    /Users/matthewnelson/seva-mining/backend/app/config.py,
    /Users/matthewnelson/seva-mining/.planning/REQUIREMENTS.md,
    /Users/matthewnelson/seva-mining/.planning/phases/11-content-preview-and-rendered-images/11-RESEARCH.md (§Standard Stack, §Pitfall 5)
  </read_first>
  <action>
    Add two prod dependencies to scheduler/pyproject.toml `[project].dependencies`:
      "google-genai[aiohttp]==1.73.1",
      "aioboto3==15.5.0",

    Add the same two to backend/pyproject.toml `[project].dependencies` (both services need them — scheduler for cron-path render, backend for rerender endpoint path per RESEARCH.md Finding 3).

    Run `cd scheduler && uv sync --all-extras` and `cd backend && uv sync --all-extras` to install.

    In BOTH scheduler/config.py and backend/app/config.py, add these new Optional fields to Settings (after the existing optional fields, matching their patterns exactly):
      gemini_api_key: Optional[str] = None
      r2_account_id: Optional[str] = None
      r2_access_key_id: Optional[str] = None
      r2_secret_access_key: Optional[str] = None
      r2_bucket: Optional[str] = None
      r2_public_base_url: Optional[str] = None

    In .planning/REQUIREMENTS.md:
      1. Under `### Content Review` section (after the existing CREV-05 line), append these five lines:
         - [ ] **CREV-06**: Content detail modal displays full structured brief for all content formats (infographic, thread, long_form, breaking_news, quote, video_clip) with format-aware rendering
         - [ ] **CREV-07**: Infographic and quote ContentBundles automatically generate AI-rendered images (4 and 2 respectively) stored in Cloudflare R2
         - [ ] **CREV-08**: Rendered images appear in the Content detail modal with skeleton+poll UX and graceful fallback on render failure
         - [ ] **CREV-09**: Operator can trigger a fresh image render via a "Regenerate images" button in the modal
         - [ ] **CREV-10**: Image rendering runs as a background job independent of the Content Agent cron; failures do not block bundle persistence or approval
      2. In the `## Traceability` table (after the existing CREV-05 row), append:
         | CREV-06 | Phase 11 | Pending |
         | CREV-07 | Phase 11 | Pending |
         | CREV-08 | Phase 11 | Pending |
         | CREV-09 | Phase 11 | Pending |
         | CREV-10 | Phase 11 | Pending |
      3. Update the Coverage footer: change "v1 requirements: 99 total" to "v1 requirements: 104 total" and "Mapped to phases: 99" to "Mapped to phases: 104"

    HUMAN ACTION REQUIRED (do NOT attempt to automate — surface as a blocker if not yet done; see RESEARCH.md §Open Questions 2 and 3):
      - Provision GEMINI_API_KEY in Railway env for both `seva-mining-backend` and `seva-mining-scheduler` services
      - Create Cloudflare R2 bucket (suggested name: `seva-mining-content`)
      - Enable public access on bucket (dashboard → bucket → Settings → Public access → r2.dev subdomain)
      - Copy bucket credentials into Railway env for both services: R2_ACCOUNT_ID, R2_ACCESS_KEY_ID, R2_SECRET_ACCESS_KEY, R2_BUCKET, R2_PUBLIC_BASE_URL
      - If credentials are not yet provisioned at the time this task executes, write a clear note into the task SUMMARY and continue — the test stubs in later tasks mock everything, so local dev does not need live credentials. Plan 07 will verify live credentials at the human checkpoint.
  </action>
  <verify>
    <automated>cd /Users/matthewnelson/seva-mining/scheduler && uv run python -c "import google.genai; import aioboto3; from config import get_settings; s = get_settings(); print('ok')" && cd /Users/matthewnelson/seva-mining/backend && uv run python -c "import google.genai; import aioboto3; from app.config import get_settings; s = get_settings(); print('ok')"</automated>
  </verify>
  <acceptance_criteria>
    - `grep -c "google-genai\[aiohttp\]==1.73.1" /Users/matthewnelson/seva-mining/scheduler/pyproject.toml` returns 1
    - `grep -c "aioboto3==15.5.0" /Users/matthewnelson/seva-mining/scheduler/pyproject.toml` returns 1
    - `grep -c "google-genai\[aiohttp\]==1.73.1" /Users/matthewnelson/seva-mining/backend/pyproject.toml` returns 1
    - `grep -c "aioboto3==15.5.0" /Users/matthewnelson/seva-mining/backend/pyproject.toml` returns 1
    - `grep -c "gemini_api_key\|r2_account_id\|r2_bucket" /Users/matthewnelson/seva-mining/scheduler/config.py` returns ≥ 3
    - `grep -c "gemini_api_key\|r2_account_id\|r2_bucket" /Users/matthewnelson/seva-mining/backend/app/config.py` returns ≥ 3
    - `grep -c "CREV-06\|CREV-07\|CREV-08\|CREV-09\|CREV-10" /Users/matthewnelson/seva-mining/.planning/REQUIREMENTS.md` returns ≥ 10 (5 IDs × 2 occurrences: section + traceability)
    - The verify command exits 0 in both services
  </acceptance_criteria>
  <done>
    Both services install the two new deps. Both Settings classes expose all six new env vars. REQUIREMENTS.md has five new CREV-* rows with traceability. Human-setup note recorded in task notes if credentials not yet provisioned.
  </done>
</task>

<task type="auto" tdd="false">
  <name>Task 2: rendered_images column — model mirror + Alembic migration</name>
  <files>
    scheduler/models/content_bundle.py,
    backend/app/models/content_bundle.py,
    backend/alembic/versions/0006_add_rendered_images.py
  </files>
  <read_first>
    /Users/matthewnelson/seva-mining/scheduler/models/content_bundle.py,
    /Users/matthewnelson/seva-mining/backend/app/models/content_bundle.py,
    /Users/matthewnelson/seva-mining/backend/alembic/versions/0005_rename_format_type_to_content_type.py,
    /Users/matthewnelson/seva-mining/.planning/phases/11-content-preview-and-rendered-images/11-RESEARCH.md (§Pattern 4)
  </read_first>
  <action>
    In scheduler/models/content_bundle.py AND backend/app/models/content_bundle.py:
      Add a new column after `compliance_passed`:
        rendered_images = Column(JSONB, nullable=True)
      (Do not touch anything else in these files. Keep the existing `from sqlalchemy.dialects.postgresql import UUID, JSONB` import — JSONB is already imported in both files.)

    Create backend/alembic/versions/0006_add_rendered_images.py with EXACTLY this content:

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

    Apply the migration locally:
      cd /Users/matthewnelson/seva-mining/backend && uv run alembic upgrade head

    Do NOT apply in staging/production from this task — Railway auto-applies on deploy. Record the new revision id in the task summary.
  </action>
  <verify>
    <automated>cd /Users/matthewnelson/seva-mining/backend && uv run alembic current | grep -q "0006" && uv run alembic downgrade -1 && uv run alembic current | grep -q "0005" && uv run alembic upgrade head && uv run alembic current | grep -q "0006"</automated>
  </verify>
  <acceptance_criteria>
    - `grep -c "rendered_images" /Users/matthewnelson/seva-mining/scheduler/models/content_bundle.py` returns 1
    - `grep -c "rendered_images" /Users/matthewnelson/seva-mining/backend/app/models/content_bundle.py` returns 1
    - File /Users/matthewnelson/seva-mining/backend/alembic/versions/0006_add_rendered_images.py exists
    - `grep -c 'down_revision = "0005"' /Users/matthewnelson/seva-mining/backend/alembic/versions/0006_add_rendered_images.py` returns 1
    - The verify command exits 0 (upgrade, downgrade, upgrade all succeed)
  </acceptance_criteria>
  <done>
    Both ORM models expose rendered_images as a JSONB-mapped column. Alembic migration 0006 upgrades and downgrades cleanly. Neon database has the column after upgrade.
  </done>
</task>

<task type="auto" tdd="false">
  <name>Task 3: Schema additions — engagement_snapshot, ContentBundleDetailResponse, RerenderResponse</name>
  <files>
    backend/app/schemas/draft_item.py,
    backend/app/schemas/content_bundle.py,
    frontend/src/api/types.ts
  </files>
  <read_first>
    /Users/matthewnelson/seva-mining/backend/app/schemas/draft_item.py,
    /Users/matthewnelson/seva-mining/backend/app/schemas/content_bundle.py,
    /Users/matthewnelson/seva-mining/frontend/src/api/types.ts,
    /Users/matthewnelson/seva-mining/.planning/phases/11-content-preview-and-rendered-images/11-RESEARCH.md (§Finding 1, §Pattern 6)
  </read_first>
  <action>
    In backend/app/schemas/draft_item.py:
      In the DraftItemResponse class, after the existing `updated_at: Optional[datetime] = None` line, add:
        engagement_snapshot: Optional[Any] = None
      Add `Any` to the existing `from typing import Optional` import → `from typing import Optional, Any`

    In backend/app/schemas/content_bundle.py (which currently only contains ContentBundleResponse):
      Append two new classes after the existing ContentBundleResponse:

        class RenderedImage(BaseModel):
            model_config = ConfigDict(from_attributes=True)
            role: str           # "twitter_visual" | "instagram_slide_1" | "instagram_slide_2" | "instagram_slide_3"
            url: str
            generated_at: str   # ISO-8601


        class ContentBundleDetailResponse(BaseModel):
            model_config = ConfigDict(from_attributes=True)
            id: UUID
            story_headline: str
            story_url: Optional[str] = None
            source_name: Optional[str] = None
            content_type: Optional[str] = None
            score: Optional[float] = None
            quality_score: Optional[float] = None
            no_story_flag: bool
            deep_research: Optional[Any] = None
            draft_content: Optional[Any] = None
            compliance_passed: Optional[bool] = None
            rendered_images: Optional[list[RenderedImage]] = None
            created_at: datetime


        class RerenderResponse(BaseModel):
            bundle_id: UUID
            render_job_id: str
            enqueued_at: str    # ISO-8601

    In frontend/src/api/types.ts:
      1. Inside the existing DraftItemResponse interface, add a new property before the closing brace:
           engagement_snapshot?: Record<string, unknown>
      2. After the existing ContentBundleResponse interface, append:

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
          rendered_images?: RenderedImage[] | null
          created_at: string
        }

        export interface RerenderResponse {
          bundle_id: string
          render_job_id: string
          enqueued_at: string
        }
  </action>
  <verify>
    <automated>cd /Users/matthewnelson/seva-mining/backend && uv run python -c "from app.schemas.draft_item import DraftItemResponse; from app.schemas.content_bundle import ContentBundleDetailResponse, RerenderResponse, RenderedImage; assert 'engagement_snapshot' in DraftItemResponse.model_fields; assert 'rendered_images' in ContentBundleDetailResponse.model_fields; print('ok')" && cd /Users/matthewnelson/seva-mining/frontend && npx tsc --noEmit</automated>
  </verify>
  <acceptance_criteria>
    - `grep -c "engagement_snapshot" /Users/matthewnelson/seva-mining/backend/app/schemas/draft_item.py` returns 1
    - `grep -c "ContentBundleDetailResponse\|RerenderResponse\|RenderedImage" /Users/matthewnelson/seva-mining/backend/app/schemas/content_bundle.py` returns ≥ 3
    - `grep -c "engagement_snapshot?" /Users/matthewnelson/seva-mining/frontend/src/api/types.ts` returns 1
    - `grep -c "ContentBundleDetailResponse\|RerenderResponse\|RenderedImage" /Users/matthewnelson/seva-mining/frontend/src/api/types.ts` returns ≥ 3
    - `npx tsc --noEmit` in frontend exits 0
    - The backend python import check exits 0
  </acceptance_criteria>
  <done>
    DraftItemResponse (Python + TS) includes engagement_snapshot. ContentBundleDetailResponse, RerenderResponse, RenderedImage exist in both languages with identical shapes. TypeScript compiles clean.
  </done>
</task>

<task type="auto" tdd="false">
  <name>Task 4: Scheduler worker module-level promotion + get_scheduler accessor</name>
  <files>
    scheduler/worker.py
  </files>
  <read_first>
    /Users/matthewnelson/seva-mining/scheduler/worker.py,
    /Users/matthewnelson/seva-mining/.planning/phases/11-content-preview-and-rendered-images/11-RESEARCH.md (§Pattern 1, §Finding 2)
  </read_first>
  <action>
    Modify scheduler/worker.py to expose the scheduler at module level so agent code can call `scheduler.add_job()` for one-off render jobs (per RESEARCH Pattern 1 and Finding 2).

    1. After the existing `logger = logging.getLogger(__name__)` line (around line 32), add:

        _scheduler: AsyncIOScheduler | None = None


        def get_scheduler() -> AsyncIOScheduler:
            """Return the running module-level scheduler. Raises if not started yet.

            Used by agents (e.g. ContentAgent) to enqueue one-off DateTrigger jobs
            (Phase 11 — Image render).
            """
            if _scheduler is None:
                raise RuntimeError("Scheduler has not been started yet")
            return _scheduler

    2. Inside the existing `async def main()` function (around line 359), replace the current block:
        scheduler = await build_scheduler(engine)
        scheduler.start()
        logger.info("Scheduler worker started. %d jobs registered.", len(scheduler.get_jobs()))

        try:
            # Block forever — scheduler runs in background event loop
            await asyncio.Event().wait()
        except (KeyboardInterrupt, SystemExit):
            logger.info("Scheduler worker shutting down.")
            scheduler.shutdown()

    With:
        global _scheduler
        _scheduler = await build_scheduler(engine)
        _scheduler.start()
        logger.info("Scheduler worker started. %d jobs registered.", len(_scheduler.get_jobs()))

        try:
            # Block forever — scheduler runs in background event loop
            await asyncio.Event().wait()
        except (KeyboardInterrupt, SystemExit):
            logger.info("Scheduler worker shutting down.")
            _scheduler.shutdown()

    Do NOT change any other lines, including JOB_LOCK_IDS, build_scheduler(), _make_job(), with_advisory_lock(), upsert_agent_config(), _validate_env(), or _read_schedule_config.
  </action>
  <verify>
    <automated>cd /Users/matthewnelson/seva-mining/scheduler && uv run python -c "from worker import get_scheduler, _scheduler; assert _scheduler is None; import worker; assert callable(worker.get_scheduler); print('ok')"</automated>
  </verify>
  <acceptance_criteria>
    - `grep -c "_scheduler: AsyncIOScheduler" /Users/matthewnelson/seva-mining/scheduler/worker.py` returns 1
    - `grep -c "def get_scheduler" /Users/matthewnelson/seva-mining/scheduler/worker.py` returns 1
    - `grep -c "global _scheduler" /Users/matthewnelson/seva-mining/scheduler/worker.py` returns 1
    - `grep -c "_scheduler.start()" /Users/matthewnelson/seva-mining/scheduler/worker.py` returns 1
    - `grep -c "_scheduler.shutdown()" /Users/matthewnelson/seva-mining/scheduler/worker.py` returns 1
    - The verify command exits 0
    - `cd /Users/matthewnelson/seva-mining/scheduler && uv run pytest tests/test_worker.py -x` still passes (existing tests)
  </acceptance_criteria>
  <done>
    Scheduler reference is module-level and reachable via get_scheduler(). main() uses the module-level variable. Existing worker tests still pass.
  </done>
</task>

<task type="auto" tdd="false">
  <name>Task 5: All Wave 0 test stubs + MSW handlers</name>
  <files>
    scheduler/tests/agents/__init__.py,
    scheduler/tests/agents/test_image_render.py,
    scheduler/tests/conftest.py,
    backend/tests/routers/__init__.py,
    backend/tests/routers/test_content_bundles.py,
    backend/tests/test_queue_schema.py,
    frontend/src/api/__tests__/content-bundle.test.ts,
    frontend/src/hooks/__tests__/useContentBundle.test.ts,
    frontend/src/components/approval/__tests__/ContentDetailModal.test.tsx,
    frontend/src/mocks/handlers.ts
  </files>
  <read_first>
    /Users/matthewnelson/seva-mining/scheduler/tests/test_content_agent.py,
    /Users/matthewnelson/seva-mining/backend/tests/test_crud_endpoints.py,
    /Users/matthewnelson/seva-mining/backend/tests/conftest.py,
    /Users/matthewnelson/seva-mining/frontend/src/mocks/handlers.ts,
    /Users/matthewnelson/seva-mining/.planning/phases/11-content-preview-and-rendered-images/11-VALIDATION.md (§Wave 0 Requirements)
  </read_first>
  <action>
    Create the following test stub files. Each stub uses pytest.skip() or test.skip() BEFORE the import of the module-under-test so tests are COLLECTED but SKIPPED during Wave 0 (matching Phase 4/5/6/7 Wave-0 patterns — see STATE.md decisions). Later plans (02-06) remove the skip and fill in real assertions.

    ---

    File: scheduler/tests/agents/__init__.py
    Content: (empty file — single newline)

    ---

    File: scheduler/tests/agents/test_image_render.py
      import pytest

      # Wave 0 stub — skip until image_render_agent module exists (Plan 02)
      pytest.skip("image_render_agent not implemented yet (Plan 11-02)", allow_module_level=True)

      from agents.image_render_agent import render_bundle_job  # noqa: E402


      async def test_render_bundle_infographic_produces_four_images():
          """render_bundle_job on an infographic bundle writes 4 entries to rendered_images."""
          pass


      async def test_render_bundle_quote_produces_two_images():
          """render_bundle_job on a quote bundle writes 2 entries to rendered_images."""
          pass


      async def test_render_bundle_skips_when_compliance_failed():
          """render_bundle_job must not render if bundle.compliance_passed is False (D-11)."""
          pass


      async def test_render_bundle_retries_on_transient_failure():
          """render_bundle_job retries up to 3 times with ~2s/8s/30s backoff (D-18)."""
          pass


      async def test_render_bundle_silent_fail_after_permanent_error():
          """On 3 retries exhausted, render logs error but raises nothing (D-18)."""
          pass


      async def test_upload_to_r2_returns_public_url():
          """_upload_to_r2 returns {R2_PUBLIC_BASE_URL}/{object_key} exactly (no ACL)."""
          pass

    ---

    File: scheduler/tests/conftest.py
      (CREATE if missing, otherwise APPEND the fixtures below. Read existing file first — the file exists in many scheduler test setups, so append rather than overwrite.)

      Append these fixtures at the bottom:

      import pytest
      from unittest.mock import AsyncMock, MagicMock


      @pytest.fixture
      def fake_imagen_client():
          """Mock google.genai.Client returning fixed PNG bytes."""
          client = MagicMock()
          fake_image = MagicMock()
          fake_image.image.image_bytes = b"\x89PNG\r\n\x1a\nFAKE"
          response = MagicMock()
          response.generated_images = [fake_image]
          client.aio.models.generate_images = AsyncMock(return_value=response)
          return client


      @pytest.fixture
      def fake_r2_client():
          """Mock aioboto3 S3 client context manager — records put_object calls."""
          s3 = AsyncMock()
          s3.put_object = AsyncMock(return_value={})
          session = MagicMock()
          session.client.return_value.__aenter__ = AsyncMock(return_value=s3)
          session.client.return_value.__aexit__ = AsyncMock(return_value=None)
          return session, s3

    ---

    File: backend/tests/routers/__init__.py
    Content: (empty)

    ---

    File: backend/tests/routers/test_content_bundles.py
      import pytest

      # Wave 0 stub — skip until content_bundles router exists (Plan 03)
      pytest.skip("content_bundles router not implemented yet (Plan 11-03)", allow_module_level=True)


      async def test_get_content_bundle_returns_full_bundle(authed_client, seeded_bundle):
          """GET /content-bundles/{id} returns 200 with full payload for authenticated operator."""
          pass


      async def test_get_content_bundle_requires_auth(client, seeded_bundle):
          """GET /content-bundles/{id} returns 401 without token."""
          pass


      async def test_get_content_bundle_returns_404_for_missing(authed_client):
          """GET /content-bundles/{random_uuid} returns 404."""
          pass


      async def test_rerender_returns_202(authed_client, seeded_bundle):
          """POST /content-bundles/{id}/rerender returns 202 with {bundle_id, render_job_id, enqueued_at}."""
          pass


      async def test_rerender_clears_existing_images(authed_client, seeded_bundle_with_images):
          """POST /content-bundles/{id}/rerender sets bundle.rendered_images to [] in DB."""
          pass


      async def test_rerender_404_on_missing_bundle(authed_client):
          """POST /content-bundles/{random_uuid}/rerender returns 404."""
          pass

    ---

    File: backend/tests/test_queue_schema.py
      import pytest

      # Wave 0 stub — DraftItemResponse.engagement_snapshot added in this same plan (Task 3)
      # but leaving tests skipped until real assertion fixtures exist in Plan 03.
      pytest.skip("queue schema test deferred to Plan 11-03", allow_module_level=True)


      async def test_queue_response_includes_engagement_snapshot(authed_client):
          """Queue list response items include engagement_snapshot with content_bundle_id for content-agent drafts."""
          pass

    ---

    File: frontend/src/api/__tests__/content-bundle.test.ts
      import { describe, it } from 'vitest'

      // Wave 0 stub — skip until getContentBundle / rerenderContentBundle exist (Plan 05)
      describe.skip('content-bundle api (Plan 11-05)', () => {
        it('getContentBundle fetches GET /content-bundles/:id', () => {})
        it('rerenderContentBundle posts to /content-bundles/:id/rerender', () => {})
      })

    ---

    File: frontend/src/hooks/__tests__/useContentBundle.test.ts
      import { describe, it } from 'vitest'

      // Wave 0 stub — skip until useContentBundle exists (Plan 05)
      describe.skip('useContentBundle (Plan 11-05)', () => {
        it('polls every 5s while rendered_images is empty and bundle is <10min old', () => {})
        it('stops polling once rendered_images has length ≥ 1', () => {})
        it('stops polling after bundle is older than 10 minutes', () => {})
        it('is disabled when bundleId is null/undefined', () => {})
      })

    ---

    File: frontend/src/components/approval/__tests__/ContentDetailModal.test.tsx
      import { describe, it } from 'vitest'

      // Wave 0 stub — skip until ContentDetailModal rewrite lands (Plan 06)
      describe.skip('ContentDetailModal format-aware (Plan 11-06)', () => {
        it('renders InfographicPreview when bundle.content_type === "infographic"', () => {})
        it('renders ThreadPreview when bundle.content_type === "thread"', () => {})
        it('renders LongFormPreview when bundle.content_type === "long_form"', () => {})
        it('renders BreakingNewsPreview when bundle.content_type === "breaking_news"', () => {})
        it('renders QuotePreview when bundle.content_type === "quote"', () => {})
        it('renders VideoClipPreview when bundle.content_type === "video_clip"', () => {})
        it('falls back to flat DraftAlternative.text when bundle fetch fails (D-24)', () => {})
        it('shows skeleton placeholders + "rendering…" when rendered_images empty and bundle <10min old', () => {})
        it('hides image slots gracefully when bundle is >10min old and no rendered_images', () => {})
        it('Regenerate images button is disabled while rendering is in-flight (D-17)', () => {})
      })

    ---

    File: frontend/src/mocks/handlers.ts
      READ the existing file first. Add these two handlers inside the existing `handlers` array (at the bottom of the array, before the closing `]`):

        // Phase 11 — content-bundle detail + rerender (Plan 11-05/06 test coverage)
        http.get('/content-bundles/:id', ({ params }) => {
          return HttpResponse.json({
            id: params.id,
            story_headline: 'Mock headline',
            content_type: 'infographic',
            no_story_flag: false,
            draft_content: {},
            rendered_images: [],
            created_at: new Date().toISOString(),
          })
        }),
        http.post('/content-bundles/:id/rerender', ({ params }) => {
          return HttpResponse.json(
            {
              bundle_id: params.id,
              render_job_id: `rerender_${params.id}_${Date.now()}`,
              enqueued_at: new Date().toISOString(),
            },
            { status: 202 }
          )
        }),

      (Use the same `http`/`HttpResponse` import pattern already present at the top of the file — do not add new imports.)
  </action>
  <verify>
    <automated>cd /Users/matthewnelson/seva-mining/scheduler && uv run pytest tests/agents/test_image_render.py --collect-only -q && cd /Users/matthewnelson/seva-mining/backend && uv run pytest tests/routers/test_content_bundles.py tests/test_queue_schema.py --collect-only -q && cd /Users/matthewnelson/seva-mining/frontend && npx vitest run src/api/__tests__/content-bundle.test.ts src/hooks/__tests__/useContentBundle.test.ts src/components/approval/__tests__/ContentDetailModal.test.tsx --reporter=verbose</automated>
  </verify>
  <acceptance_criteria>
    - `ls /Users/matthewnelson/seva-mining/scheduler/tests/agents/test_image_render.py` exists
    - `ls /Users/matthewnelson/seva-mining/backend/tests/routers/test_content_bundles.py` exists
    - `ls /Users/matthewnelson/seva-mining/frontend/src/api/__tests__/content-bundle.test.ts` exists
    - `ls /Users/matthewnelson/seva-mining/frontend/src/hooks/__tests__/useContentBundle.test.ts` exists
    - `ls /Users/matthewnelson/seva-mining/frontend/src/components/approval/__tests__/ContentDetailModal.test.tsx` exists
    - `grep -c "fake_imagen_client\|fake_r2_client" /Users/matthewnelson/seva-mining/scheduler/tests/conftest.py` returns ≥ 2
    - `grep -c "/content-bundles/:id/rerender" /Users/matthewnelson/seva-mining/frontend/src/mocks/handlers.ts` returns 1
    - pytest --collect-only in scheduler reports 6 tests from test_image_render.py (all SKIPPED at module level — that is the expected Wave 0 state)
    - pytest --collect-only in backend reports 6+1 tests from test_content_bundles.py + test_queue_schema.py
    - npx vitest --run in frontend collects the 3 new test files with all suites skipped (describe.skip)
  </acceptance_criteria>
  <done>
    All Wave 0 test files exist on disk with module-level skip markers. Fixtures added. MSW handlers added. Frontend tsc compiles. All test runners can collect these files without error.
  </done>
</task>

</tasks>

<verification>
Full Wave 0 gate (run before merging any downstream plan):
- `cd backend && uv run pytest -x` (all existing tests still green; new stubs SKIPPED not FAILED)
- `cd scheduler && uv run pytest -x` (all existing tests still green; new stubs SKIPPED)
- `cd frontend && npm run test -- --run` (all existing tests still green; new stubs SKIPPED)
- `cd backend && uv run alembic current` prints "0006"
- `grep -q "CREV-10" .planning/REQUIREMENTS.md` returns 0 (exit code)
</verification>

<success_criteria>
Wave 0 foundation is complete when:
- All new test files exist and are collectable
- Both config files expose all 6 new env vars
- Both pyproject.toml files list google-genai[aiohttp]==1.73.1 and aioboto3==15.5.0
- Both ContentBundle ORM models have rendered_images
- Alembic 0006 is applied and reversible
- DraftItemResponse (Py + TS) has engagement_snapshot
- ContentBundleDetailResponse / RerenderResponse / RenderedImage types exist in Py + TS
- scheduler/worker.py exports get_scheduler() and _scheduler is module-level
- REQUIREMENTS.md has CREV-06..CREV-10 with traceability rows
</success_criteria>

<output>
After completion, create `.planning/phases/11-content-preview-and-rendered-images/11-01-SUMMARY.md` describing:
- Final state of pyproject.toml deps (versions confirmed installed)
- Alembic revision id applied (should be "0006")
- Whether GEMINI_API_KEY / R2 credentials were provisioned by the human yet (if not, flag as blocker for Plan 07 checkpoint)
- Exact shape of ContentBundleDetailResponse and RerenderResponse for downstream plans to reference
</output>
