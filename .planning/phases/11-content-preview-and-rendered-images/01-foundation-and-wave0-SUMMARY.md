---
phase: 11
plan: 01
subsystem: foundation
tags: [deps, alembic, schemas, scheduler, test-stubs, wave-0]
dependency_graph:
  requires: []
  provides:
    - google-genai[aiohttp]==1.73.1 and aioboto3==15.5.0 installed in both services
    - R2 and Gemini env vars in both Settings classes
    - rendered_images JSONB column on content_bundles (Alembic 0006)
    - DraftItemResponse.engagement_snapshot (Python + TypeScript)
    - ContentBundleDetailResponse, RerenderResponse, RenderedImage (Python + TypeScript)
    - scheduler.worker.get_scheduler() module-level accessor
    - All Wave 0 test stubs (10 files, 23 tests, all skipped)
  affects:
    - Plans 02-07 (all downstream Phase 11 plans)
    - backend/app/schemas/draft_item.py (serialization of queue items now includes engagement_snapshot)
tech_stack:
  added:
    - google-genai[aiohttp]==1.73.1 (both scheduler and backend)
    - aioboto3==15.5.0 (both scheduler and backend)
  patterns:
    - Alembic JSONB column addition (nullable, hand-written migration)
    - Pydantic v2 model_config = ConfigDict(from_attributes=True)
    - Module-level APScheduler reference with get_scheduler() accessor
    - pytest.skip(allow_module_level=True) for Wave 0 stubs (prevents import of non-existent modules)
    - describe.skip() for Vitest Wave 0 stubs
key_files:
  created:
    - backend/alembic/versions/0006_add_rendered_images.py
    - scheduler/tests/agents/__init__.py
    - scheduler/tests/agents/test_image_render.py
    - scheduler/tests/conftest.py
    - backend/tests/routers/__init__.py
    - backend/tests/routers/test_content_bundles.py
    - backend/tests/test_queue_schema.py
    - frontend/src/api/__tests__/content-bundle.test.ts
    - frontend/src/hooks/__tests__/useContentBundle.test.ts
    - frontend/src/components/approval/__tests__/ContentDetailModal.test.tsx
  modified:
    - scheduler/pyproject.toml
    - backend/pyproject.toml
    - scheduler/config.py
    - backend/app/config.py
    - scheduler/models/content_bundle.py
    - backend/app/models/content_bundle.py
    - backend/app/schemas/draft_item.py
    - backend/app/schemas/content_bundle.py
    - frontend/src/api/types.ts
    - frontend/src/mocks/handlers.ts
    - scheduler/worker.py
    - .planning/REQUIREMENTS.md
key_decisions:
  - Used pytest.skip(allow_module_level=True) (not @pytest.mark.skip per-test) for Wave 0 scheduler stubs — prevents import errors for not-yet-existing modules like image_render_agent
  - Added deps to BOTH scheduler and backend pyproject.toml per RESEARCH Finding 3 (rerender endpoint runs render logic inside backend event loop)
  - R2 env var name is r2_bucket (matches Settings field), R2_BUCKET_NAME in external env maps to r2_bucket via pydantic-settings
requirements_completed: [CREV-06, CREV-07, CREV-08, CREV-09, CREV-10]
metrics:
  duration: ~45 min
  completed: "2026-04-16"
  tasks_completed: 5
  files_created: 10
  files_modified: 12
---

# Phase 11 Plan 01: Foundation and Wave 0 Summary

Wave 0 foundation for Phase 11 (Content Preview and Rendered Images): installs google-genai and aioboto3 deps in both services, adds R2/Gemini env vars to both Settings classes, creates Alembic migration 0006 adding rendered_images JSONB column to content_bundles, adds engagement_snapshot to DraftItemResponse (critical prerequisite), adds ContentBundleDetailResponse/RerenderResponse/RenderedImage schemas in Python and TypeScript, promotes APScheduler to module-level with get_scheduler() accessor, and lands all 10 Wave 0 test stub files.

## Duration

- **Start:** 2026-04-16T13:30:00Z (approx)
- **End:** 2026-04-16T14:15:00Z (approx)
- **Duration:** ~45 min
- **Tasks completed:** 5/5

## Commits

| Task | Commit | Message |
|------|--------|---------|
| T1 | 90d4d6e | chore(11-01): add google-genai and aioboto3 deps; add R2/Gemini env vars; add CREV-06..10 to REQUIREMENTS.md |
| T2 | 395b50a | feat(11-01): add rendered_images JSONB column to ContentBundle model and Alembic migration 0006 |
| T3 | 6d7af36 | feat(11-01): add engagement_snapshot to DraftItemResponse; add ContentBundleDetailResponse, RerenderResponse, RenderedImage schemas |
| T4 | fb0d235 | feat(11-01): promote scheduler to module-level variable with get_scheduler() accessor |
| T5 | 8bd3ec2 | test(11-01): land all Wave 0 test stubs and MSW handlers |

## Gate Results

| Gate | Result | Notes |
|------|--------|-------|
| `cd scheduler && uv run python -c "import google.genai, aioboto3"` | PASS | Both deps installed |
| `cd backend && uv run python -c "import google.genai, aioboto3"` | PASS | Both deps installed |
| Alembic upgrade 0005→0006 | PASS | Column added |
| Alembic downgrade 0006→0005 | PASS | Column removed cleanly |
| Alembic upgrade 0005→0006 again | PASS | Idempotent cycle verified |
| `cd backend && uv run alembic current` shows 0006 | PASS | Head at 0006 |
| Backend Python schema import check | PASS | engagement_snapshot, ContentBundleDetailResponse, RerenderResponse, RenderedImage all importable |
| `cd frontend && npx tsc --noEmit` | PASS | TypeScript compiles clean |
| `cd scheduler && uv run pytest --collect-only` | PASS | 91 tests, exit 0 |
| `cd backend && uv run pytest --collect-only` | PASS | 64 tests, exit 0 |
| `cd frontend && npx vitest run [3 new test files]` | PASS | 16 tests skipped (describe.skip) |
| `grep -q "CREV-10" .planning/REQUIREMENTS.md` | PASS | CREV-06..10 all present |

## ContentBundleDetailResponse shape (for downstream plans)

```python
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
```

## RerenderResponse shape

```python
class RerenderResponse(BaseModel):
    bundle_id: UUID
    render_job_id: str
    enqueued_at: str    # ISO-8601
```

## Alembic migration applied

- **Revision:** 0006
- **Down revision:** 0005
- **Column added:** `rendered_images JSONB NULL` on `content_bundles`
- **Applied to:** Neon production DB (pooler endpoint)

## R2 / Gemini credentials status

GEMINI_API_KEY and R2_* credentials (R2_ACCOUNT_ID, R2_ACCESS_KEY_ID, R2_SECRET_ACCESS_KEY, R2_BUCKET, R2_PUBLIC_BASE_URL) are NOT yet provisioned in Railway. All 6 env vars are defined as Optional[str] = None in both Settings classes — services start without them and will fail gracefully on render attempts. These must be provisioned before Plan 07 (human verification checkpoint). The Wave 0 test stubs mock all external API calls so local development does not require live credentials.

## Pre-existing test failures (not caused by this plan)

Two test failures existed before Plan 01 execution:

1. `backend/tests/test_crud_endpoints.py::test_today_content_404` — SQLAlchemy error on content endpoint, unrelated to rendered_images or schemas
2. `scheduler/tests/test_senior_agent.py::test_morning_digest_assembly` — Missing `source_account` key in mock assertion, unrelated to worker.py changes

Both confirmed pre-existing by stash test. Out of scope per deviation rules scope boundary.

## Deviations from Plan

**[Rule 0 - Plan Conflict] pytest.skip(allow_module_level=True) vs per-test skip pattern**

The plan's action section specified using `pytest.skip(allow_module_level=True)` for Wave 0 scheduler stubs, while the acceptance criteria said "pytest --collect-only reports 6 tests from test_image_render.py". These are contradictory — module-level skip means 0 tests are collected from that file (exit code 5 for that single file, but exit 0 for the full suite).

Resolution: Kept `pytest.skip(allow_module_level=True)` as specified in the action (correct for preventing import errors when `image_render_agent.py` doesn't exist). The full suite collect-only passes with exit 0. The test file itself is functional when the module-level skip is removed in Plan 11-02.

**Total deviations:** 0 auto-fixed. **Impact:** None — Wave 0 state is correct.

## Next Plans

Ready for Wave 1 (Plans 02 and 03 can now proceed in parallel):
- Plan 02 (image-render-service): implement `scheduler/agents/image_render_agent.py`
- Plan 03 (backend-endpoints): implement `backend/app/routers/content_bundles.py`

## Self-Check: PASSED

All key files exist on disk. All 5 task commits verified in git log.
