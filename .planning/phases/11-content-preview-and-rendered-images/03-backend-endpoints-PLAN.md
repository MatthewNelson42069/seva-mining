---
phase: 11-content-preview-and-rendered-images
plan: 03
type: execute
wave: 1
depends_on: [11-01]
files_modified:
  - backend/app/routers/content_bundles.py
  - backend/app/main.py
  - backend/tests/routers/test_content_bundles.py
  - backend/tests/conftest.py
autonomous: true
requirements: [CREV-02, CREV-06, CREV-09]

must_haves:
  truths:
    - "GET /content-bundles/{id} returns 200 with full bundle payload including rendered_images for authenticated operator"
    - "GET /content-bundles/{id} returns 401 without JWT"
    - "GET /content-bundles/{id} returns 404 for missing bundle"
    - "POST /content-bundles/{id}/rerender returns 202 Accepted with {bundle_id, render_job_id, enqueued_at}"
    - "POST /content-bundles/{id}/rerender clears bundle.rendered_images to [] before enqueueing"
    - "POST /content-bundles/{id}/rerender returns 404 for missing bundle"
    - "The rerender endpoint invokes render_bundle_job via asyncio.create_task so the HTTP response returns immediately (<100ms) even if the render takes 2+ minutes"
    - "Both routes are registered in backend/app/main.py under the shared JWT dependency"
  artifacts:
    - path: "backend/app/routers/content_bundles.py"
      provides: "GET detail + POST rerender endpoints"
      min_lines: 60
      exports: ["router"]
  key_links:
    - from: "backend/app/routers/content_bundles.py"
      to: "backend/app/models/content_bundle.ContentBundle"
      via: "SQLAlchemy select"
      pattern: "select(ContentBundle)"
    - from: "backend/app/routers/content_bundles.py"
      to: "scheduler.agents.image_render_agent.render_bundle_job"
      via: "sys.path shim or shared-code copy — see Task 1 action"
      pattern: "render_bundle_job"
    - from: "backend/app/main.py"
      to: "backend/app/routers/content_bundles.router"
      via: "app.include_router"
      pattern: "content_bundles_router"
---

<objective>
Land the two backend endpoints that power Plan 05's frontend hook and Plan 06's modal: `GET /content-bundles/{id}` (full detail) and `POST /content-bundles/{id}/rerender` (enqueue fresh render). Both are JWT-protected.

The rerender endpoint fires `render_bundle_job` via `asyncio.create_task` in the backend's own event loop per RESEARCH.md Pitfall 1 / Finding 3 (backend and scheduler are separate Railway services — cross-process scheduler access is not possible, so the render function must be importable and invokable from both contexts).

Purpose: CREV-02 + CREV-06 need the GET endpoint so the modal can fetch full draft_content. CREV-09 needs the POST endpoint to back the "Regenerate images" button.

Output: One new router file, two new routes wired into main.py, a working import path to `render_bundle_job` from the backend, and a passing backend test suite.
</objective>

<execution_context>
@$HOME/.claude/get-shit-done/workflows/execute-plan.md
@$HOME/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/PROJECT.md
@.planning/ROADMAP.md
@.planning/phases/11-content-preview-and-rendered-images/11-CONTEXT.md
@.planning/phases/11-content-preview-and-rendered-images/11-RESEARCH.md
@.planning/phases/11-content-preview-and-rendered-images/11-01-SUMMARY.md
@CLAUDE.md

<interfaces>
<!-- backend/app/schemas/content_bundle.py (after Plan 01) -->
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


class RerenderResponse(BaseModel):
    bundle_id: UUID
    render_job_id: str
    enqueued_at: str    # ISO-8601
```

<!-- Existing dependencies pattern (backend/app/routers/content.py for reference) -->
```python
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db
from app.auth import get_current_user  # JWT dependency

router = APIRouter(prefix="/content", tags=["content"],
                   dependencies=[Depends(get_current_user)])
```

<!-- render_bundle_job signature (Plan 02) -->
```python
# scheduler/agents/image_render_agent.py
async def render_bundle_job(bundle_id: str) -> None: ...
```
</interfaces>
</context>

<tasks>

<task type="auto" tdd="true">
  <name>Task 1: content_bundles router — GET /content-bundles/{id} + shared render import path</name>
  <files>
    backend/app/routers/content_bundles.py,
    backend/app/main.py,
    backend/tests/routers/test_content_bundles.py,
    backend/tests/conftest.py
  </files>
  <read_first>
    /Users/matthewnelson/seva-mining/backend/app/routers/content.py,
    /Users/matthewnelson/seva-mining/backend/app/main.py,
    /Users/matthewnelson/seva-mining/backend/app/auth.py,
    /Users/matthewnelson/seva-mining/backend/tests/conftest.py,
    /Users/matthewnelson/seva-mining/backend/tests/test_crud_endpoints.py,
    /Users/matthewnelson/seva-mining/scheduler/agents/image_render_agent.py,
    /Users/matthewnelson/seva-mining/.planning/phases/11-content-preview-and-rendered-images/11-RESEARCH.md (§Pitfall 1, §Finding 3)
  </read_first>
  <behavior>
    - Test 1 (test_get_content_bundle_returns_full_bundle): Given a seeded ContentBundle (content_type="infographic", compliance_passed=True, rendered_images=[{"role":"twitter_visual","url":"https://r2.example/x.png","generated_at":"2026-04-16T00:00:00+00:00"}]), authed_client.get(f"/content-bundles/{bundle.id}") returns 200 and body includes story_headline, draft_content, rendered_images with len==1.
    - Test 2 (test_get_content_bundle_requires_auth): unauthenticated client.get returns 401.
    - Test 3 (test_get_content_bundle_returns_404_for_missing): authed_client.get(f"/content-bundles/{random_uuid}") returns 404.
    - Test 4 (test_get_content_bundle_rendered_images_null_returns_null): Given a seeded bundle with rendered_images=None, the response includes "rendered_images": null (or empty list per serializer behavior — either is acceptable, but the field MUST be present and MUST NOT be missing from the JSON).

    Shared-code import path decision (planner choice — RESEARCH.md §Open Question 1):
    - The `scheduler/` directory is a sibling of `backend/` at repo root. The render_bundle_job function lives at `scheduler/agents/image_render_agent.py`. To import from the backend, this plan adds a minimal sys.path shim at the TOP of backend/app/routers/content_bundles.py:
        import sys
        import os
        _REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
        _SCHEDULER_PATH = os.path.join(_REPO_ROOT, "scheduler")
        if _SCHEDULER_PATH not in sys.path:
            sys.path.insert(0, _SCHEDULER_PATH)
    - This is a LOCAL import hack acceptable for this one use case. An alternative (shared package) would be a larger refactor and out of scope. Downstream Plan 07 checkpoint should verify this works in Railway deploy (both services share the same repo, so the /app/scheduler path exists).
  </behavior>
  <action>
    Create backend/app/routers/content_bundles.py:

      import sys
      import os
      import asyncio
      from datetime import datetime, timezone
      from uuid import UUID, uuid4

      from fastapi import APIRouter, Depends, HTTPException
      from sqlalchemy import select
      from sqlalchemy.ext.asyncio import AsyncSession

      from app.database import get_db
      from app.auth import get_current_user
      from app.models.content_bundle import ContentBundle
      from app.schemas.content_bundle import ContentBundleDetailResponse, RerenderResponse

      # Allow the backend to import scheduler/agents/image_render_agent.py.
      # Both services share the same repo in Railway — the scheduler/ path is
      # always a sibling of backend/.
      _REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
      _SCHEDULER_PATH = os.path.join(_REPO_ROOT, "scheduler")
      if _SCHEDULER_PATH not in sys.path:
          sys.path.insert(0, _SCHEDULER_PATH)

      router = APIRouter(
          prefix="/content-bundles",
          tags=["content-bundles"],
          dependencies=[Depends(get_current_user)],
      )


      @router.get("/{bundle_id}", response_model=ContentBundleDetailResponse)
      async def get_content_bundle(
          bundle_id: UUID,
          db: AsyncSession = Depends(get_db),
      ) -> ContentBundleDetailResponse:
          """Return full ContentBundle detail for the dashboard modal (CREV-02 / CREV-06)."""
          result = await db.execute(select(ContentBundle).where(ContentBundle.id == bundle_id))
          bundle = result.scalar_one_or_none()
          if bundle is None:
              raise HTTPException(status_code=404, detail="Content bundle not found")
          return ContentBundleDetailResponse.model_validate(bundle)

      # rerender endpoint added in Task 2 to keep Task 1 green-first

    In backend/app/main.py, add import and registration:
      from app.routers.content_bundles import router as content_bundles_router
      app.include_router(content_bundles_router)
      (Register AFTER the other routers, matching the existing pattern.)

    In backend/tests/conftest.py, extend (do not overwrite) with fixtures:
      - seeded_bundle: creates ContentBundle via SQLAlchemy (content_type="infographic", story_headline="Test", draft_content={"format":"infographic"}, compliance_passed=True, rendered_images=None). Yields the committed bundle.
      - seeded_bundle_with_images: same but rendered_images=[{"role":"twitter_visual","url":"https://r2.example/x.png","generated_at":"2026-04-16T00:00:00+00:00"}]
      (READ conftest.py first to see the existing authed_client / client fixtures; reuse them.)

    Remove the module-level pytest.skip from backend/tests/routers/test_content_bundles.py. Fill in Tests 1-4 using the conftest fixtures. Keep Tests 5 and 6 (rerender) as pytest.skip("deferred to Plan 11-03 Task 2", ...) at the individual test level so Task 2 can remove them.
  </action>
  <verify>
    <automated>cd /Users/matthewnelson/seva-mining/backend && uv run pytest tests/routers/test_content_bundles.py -v -k "not rerender"</automated>
  </verify>
  <acceptance_criteria>
    - File /Users/matthewnelson/seva-mining/backend/app/routers/content_bundles.py exists
    - `grep -c "/content-bundles" /Users/matthewnelson/seva-mining/backend/app/routers/content_bundles.py` returns ≥ 1
    - `grep -c "get_current_user" /Users/matthewnelson/seva-mining/backend/app/routers/content_bundles.py` returns 1
    - `grep -c "content_bundles_router" /Users/matthewnelson/seva-mining/backend/app/main.py` returns ≥ 2 (import + include)
    - `grep -c "seeded_bundle" /Users/matthewnelson/seva-mining/backend/tests/conftest.py` returns ≥ 2
    - pytest reports tests 1-4 PASSED (rerender tests skipped at item level)
  </acceptance_criteria>
  <done>
    GET endpoint works, is JWT-protected, returns 404 on miss and 200 with full detail on hit. Router is registered in main.py. Conftest fixtures support both Task 2 and the rerender tests.
  </done>
</task>

<task type="auto" tdd="true">
  <name>Task 2: POST /content-bundles/{id}/rerender endpoint with asyncio.create_task</name>
  <files>
    backend/app/routers/content_bundles.py,
    backend/tests/routers/test_content_bundles.py
  </files>
  <read_first>
    /Users/matthewnelson/seva-mining/backend/app/routers/content_bundles.py (post-Task 1),
    /Users/matthewnelson/seva-mining/backend/tests/routers/test_content_bundles.py (post-Task 1),
    /Users/matthewnelson/seva-mining/scheduler/agents/image_render_agent.py,
    /Users/matthewnelson/seva-mining/.planning/phases/11-content-preview-and-rendered-images/11-CONTEXT.md (§decisions D-15, D-16, D-17)
  </read_first>
  <behavior>
    - Test 5 (test_rerender_returns_202): authed_client.post(f"/content-bundles/{bundle.id}/rerender") returns 202 and body = {"bundle_id": str(bundle.id), "render_job_id": <str>, "enqueued_at": <iso-string>}.
    - Test 6 (test_rerender_clears_existing_images): Given seeded_bundle_with_images (rendered_images has 1 entry), after POST, a subsequent GET returns rendered_images == [] (or a fresh list populated by the mocked render — we assert the DB was cleared BEFORE the task fired by awaiting the response and reading DB).
    - Test 7 (test_rerender_404_on_missing_bundle): authed_client.post(f"/content-bundles/{random_uuid}/rerender") returns 404.
    - Test 8 (test_rerender_requires_auth): unauthenticated client.post returns 401.
    - Test 9 (test_rerender_enqueues_render_bundle_job): Mock `render_bundle_job` via monkeypatch. After POST, assert the mock was called with bundle_id as a string (via asyncio.create_task so test must allow the event loop to tick once — use `await asyncio.sleep(0)` after the HTTP call).
  </behavior>
  <action>
    Extend backend/app/routers/content_bundles.py — append the rerender endpoint after get_content_bundle:

      @router.post("/{bundle_id}/rerender", status_code=202, response_model=RerenderResponse)
      async def rerender_content_bundle(
          bundle_id: UUID,
          db: AsyncSession = Depends(get_db),
      ) -> RerenderResponse:
          """Clear existing rendered_images and enqueue a fresh render (CREV-09).

          Returns 202 immediately; the render runs async in the backend event loop via
          asyncio.create_task. Frontend polls GET /content-bundles/{id} until new URLs appear.
          """
          result = await db.execute(select(ContentBundle).where(ContentBundle.id == bundle_id))
          bundle = result.scalar_one_or_none()
          if bundle is None:
              raise HTTPException(status_code=404, detail="Content bundle not found")
          # Clear so frontend polling state re-engages (D-15/D-16)
          bundle.rendered_images = []
          await db.commit()
          # Fire-and-forget render. Must import here so the sys.path shim at module top has already run.
          from agents.image_render_agent import render_bundle_job  # type: ignore
          asyncio.create_task(render_bundle_job(str(bundle_id)))
          job_id = f"rerender_{bundle_id}_{uuid4().hex[:8]}"
          return RerenderResponse(
              bundle_id=bundle_id,
              render_job_id=job_id,
              enqueued_at=datetime.now(timezone.utc).isoformat(),
          )

    In backend/tests/routers/test_content_bundles.py:
      - Remove the individual pytest.skip markers on the rerender tests from Task 1
      - Implement Tests 5-9 above
      - For Test 9, monkeypatch `app.routers.content_bundles.render_bundle_job` (the imported-at-runtime name — use `import app.routers.content_bundles as cb_module; cb_module.render_bundle_job = fake` is NOT enough because the import is inside the function. Instead, monkeypatch `agents.image_render_agent.render_bundle_job` before the test client posts)
      - Use an AsyncMock that records the call and returns an awaitable None
      - After the POST, `await asyncio.sleep(0.01)` to let create_task run, then assert mock.call_args[0][0] == str(bundle.id)
  </action>
  <verify>
    <automated>cd /Users/matthewnelson/seva-mining/backend && uv run pytest tests/routers/test_content_bundles.py -v</automated>
  </verify>
  <acceptance_criteria>
    - `grep -c "rerender_content_bundle\|POST.*rerender\|rerender\"" /Users/matthewnelson/seva-mining/backend/app/routers/content_bundles.py` returns ≥ 2
    - `grep -c "asyncio.create_task" /Users/matthewnelson/seva-mining/backend/app/routers/content_bundles.py` returns 1
    - `grep -c "rendered_images = \[\]" /Users/matthewnelson/seva-mining/backend/app/routers/content_bundles.py` returns 1
    - `grep -c "pytest.skip\|test.skip" /Users/matthewnelson/seva-mining/backend/tests/routers/test_content_bundles.py` returns 0
    - pytest reports all 9 tests PASSED in test_content_bundles.py
    - Full backend suite: `cd backend && uv run pytest` — no regressions
  </acceptance_criteria>
  <done>
    Rerender endpoint returns 202 in under 100ms, clears rendered_images, enqueues render_bundle_job. All 9 tests pass. Backend full suite still green.
  </done>
</task>

</tasks>

<verification>
- `cd backend && uv run pytest` — full suite green
- Manual request test (local dev): `curl -H "Authorization: Bearer $JWT" http://localhost:8000/content-bundles/$BUNDLE_ID` returns 200 JSON with rendered_images field
- `curl -X POST -H "Authorization: Bearer $JWT" http://localhost:8000/content-bundles/$BUNDLE_ID/rerender` returns 202
</verification>

<success_criteria>
- GET /content-bundles/{id} serves full ContentBundleDetailResponse shape
- POST /content-bundles/{id}/rerender returns 202 and fires render_bundle_job
- Both routes JWT-protected (shared dependency)
- sys.path shim allows backend to import scheduler/agents/image_render_agent.py
- All 9 tests in test_content_bundles.py pass
</success_criteria>

<output>
Create `.planning/phases/11-content-preview-and-rendered-images/11-03-SUMMARY.md` noting:
- Final shape of the two endpoint responses
- Whether the sys.path shim worked at runtime (test it by starting uvicorn locally)
- Any edge cases discovered (e.g. if the SQLAlchemy UUID PK comparison needed str() conversion)
- Known caveat for Plan 07 checkpoint: the shim must also work on Railway — verify paths in the deployed container
</output>
