---
phase: 11-content-preview-and-rendered-images
plan: 02
type: execute
wave: 1
depends_on: [11-01]
files_modified:
  - scheduler/agents/image_render_agent.py
  - scheduler/tests/agents/test_image_render.py
  - scheduler/tests/agents/test_image_render_prompts.py
autonomous: true
requirements: [CREV-07, CREV-10]

must_haves:
  truths:
    - "render_bundle_job(bundle_id) is a module-level async function that can be imported by both the scheduler (for post-commit enqueue) and the backend (for rerender endpoint via asyncio.create_task)"
    - "render_bundle_job generates 4 images for infographic bundles and 2 images for quote bundles, each with correct aspect ratio"
    - "render_bundle_job does NOT render if ContentBundle.compliance_passed is False"
    - "render_bundle_job retries transient failures with exponential backoff (3 total attempts, ~2s/8s delays between)"
    - "render_bundle_job logs errors but never raises on permanent failure (silent-fail per D-18)"
    - "Final rendered_images JSONB has the shape [{role, url, generated_at}, ...] matching the RenderedImage Pydantic schema"
    - "R2 upload uses aioboto3 with endpoint_url=f'https://{account_id}.r2.cloudflarestorage.com' and region_name='auto'; no ACL parameter is set (R2 rejects ACLs — public access is bucket-level)"
    - "Prompts embed brand palette string (#F0ECE4 cream, #0C1B32 navy, #D4AF37 gold) per D-05"
  artifacts:
    - path: "scheduler/agents/image_render_agent.py"
      provides: "Shared render orchestrator importable from both backend and scheduler"
      min_lines: 120
      exports: ["render_bundle_job"]
  key_links:
    - from: "scheduler/agents/image_render_agent.render_bundle_job"
      to: "google.genai.Client().aio.models.generate_images"
      via: "Imagen 4 async API"
      pattern: "imagen-4.0-generate-001"
    - from: "scheduler/agents/image_render_agent.render_bundle_job"
      to: "aioboto3.Session().client('s3')"
      via: "async S3-compatible put_object"
      pattern: "put_object"
    - from: "scheduler/agents/image_render_agent.render_bundle_job"
      to: "ContentBundle.rendered_images"
      via: "SQLAlchemy async session commit"
      pattern: "bundle.rendered_images ="
---

<objective>
Build the core image render service as a single shared async function `render_bundle_job(bundle_id: str) -> None`. It reads a ContentBundle from DB, calls Imagen 4 for each required role, uploads bytes to Cloudflare R2, and writes the `rendered_images` JSONB array back to the bundle.

Purpose: This is the engine for CREV-07 and CREV-10. Isolated from the ContentAgent (Plan 04) and the rerender endpoint (Plan 03) so both can invoke it without coupling to each other.

Output: A fully tested (mocked Imagen + mocked R2) async function and unit tests confirming retry behavior, shape correctness, compliance gating, and brand-color prompt injection.
</objective>

<execution_context>
@$HOME/.claude/get-shit-done/workflows/execute-plan.md
@$HOME/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/PROJECT.md
@.planning/ROADMAP.md
@.planning/STATE.md
@.planning/phases/11-content-preview-and-rendered-images/11-CONTEXT.md
@.planning/phases/11-content-preview-and-rendered-images/11-RESEARCH.md
@.planning/phases/11-content-preview-and-rendered-images/11-VALIDATION.md
@.planning/phases/11-content-preview-and-rendered-images/11-01-SUMMARY.md
@CLAUDE.md

<interfaces>
<!-- ContentBundle model — after Plan 01 applied -->
```python
class ContentBundle(Base):
    id = Column(UUID(as_uuid=True), primary_key=True)
    content_type = Column(String(50))         # "infographic" | "quote" | others
    story_headline = Column(Text, nullable=False)
    draft_content = Column(JSONB)
    compliance_passed = Column(Boolean)
    rendered_images = Column(JSONB, nullable=True)  # NEW in Plan 01
```

<!-- draft_content shape for infographic (from Phase 07 content_agent) -->
```json
{
  "format": "infographic",
  "headline": "...",
  "key_stats": [{ "stat": "...", "source": "...", "source_url": "..." }],
  "visual_structure": "...",
  "caption_text": "...",
  "instagram_brief": {
     "headline": "...",
     "carousel_slides": [
        { "slide_number": 1, "headline": "...", "key_stat": "..." },
        { "slide_number": 2, "headline": "...", "key_stat": "..." },
        { "slide_number": 3, "headline": "...", "key_stat": "..." }
     ],
     "caption": "..."
  }
}
```

<!-- draft_content shape for quote -->
```json
{
  "format": "quote",
  "twitter_post": "...",
  "instagram_post": "...",
  "attributed_to": "...",
  "source_url": "..."
}
```

<!-- Settings (scheduler/config.py + backend/app/config.py after Plan 01) -->
```python
gemini_api_key: Optional[str]
r2_account_id: Optional[str]
r2_access_key_id: Optional[str]
r2_secret_access_key: Optional[str]
r2_bucket: Optional[str]
r2_public_base_url: Optional[str]
```
</interfaces>
</context>

<tasks>

<task type="auto" tdd="true">
  <name>Task 1: render_bundle_job implementation (compliance gate, roles-for-format, orchestrator)</name>
  <files>
    scheduler/agents/image_render_agent.py,
    scheduler/tests/agents/test_image_render.py
  </files>
  <read_first>
    /Users/matthewnelson/seva-mining/scheduler/agents/content_agent.py,
    /Users/matthewnelson/seva-mining/scheduler/models/content_bundle.py,
    /Users/matthewnelson/seva-mining/scheduler/database.py,
    /Users/matthewnelson/seva-mining/scheduler/tests/agents/test_image_render.py,
    /Users/matthewnelson/seva-mining/.planning/phases/11-content-preview-and-rendered-images/11-RESEARCH.md (§Pattern 2, §Pattern 3, §Code Examples)
  </read_first>
  <behavior>
    - Test 1 (test_render_bundle_infographic_produces_four_images): Given a ContentBundle with content_type="infographic" and compliance_passed=True, after await render_bundle_job(str(bundle.id)), the bundle's rendered_images column has exactly 4 entries with roles ["twitter_visual", "instagram_slide_1", "instagram_slide_2", "instagram_slide_3"] and each has a url starting with R2_PUBLIC_BASE_URL.
    - Test 2 (test_render_bundle_quote_produces_two_images): Given a ContentBundle with content_type="quote" and compliance_passed=True, rendered_images has exactly 2 entries with roles ["twitter_visual", "instagram_slide_1"].
    - Test 3 (test_render_bundle_skips_when_compliance_failed): Given compliance_passed=False, render_bundle_job returns without calling the Imagen client and bundle.rendered_images remains None.
    - Test 4 (test_render_bundle_skips_unsupported_format): Given content_type="thread", render_bundle_job returns without calling Imagen and rendered_images remains None.
    - Test 5 (test_render_bundle_retries_on_transient_failure): When generate_images raises Exception on attempt 1+2 and succeeds on attempt 3, one successful upload completes and rendered_images has len==1 (or len equal to number of roles, per role independence — spec below).
    - Test 6 (test_render_bundle_silent_fail_after_permanent_error): When generate_images raises on all 3 attempts for all roles, render_bundle_job returns None (no raise), rendered_images stays None (or [] — spec), and logger.error was called with exc_info.
    - Test 7 (test_upload_to_r2_returns_public_url): _upload_to_r2(b"bytes", "key") returns f"{R2_PUBLIC_BASE_URL.rstrip('/')}/key" and the aioboto3 put_object mock was called with Bucket=settings.r2_bucket, Key="key", Body=b"bytes", ContentType="image/png", and NO 'ACL' kwarg.

    Open retry semantics decision (planner choice — document in implementation):
    - Retry is PER-ROLE (not per-bundle): each role gets up to 3 attempts; a role that permanently fails produces no entry in rendered_images. A single bundle can therefore end up with partial renders (e.g. 3/4 images) — acceptable per D-18 silent-fail.
    - On any role success, the entry is appended. On all-roles-failed, rendered_images is set to an empty list [] (not left None) so the frontend polling stops (D-14 check uses 10-min ceiling, but empty list matches "no render" → modal shows brief-only).
  </behavior>
  <action>
    Remove the top-level `pytest.skip("image_render_agent not implemented yet (Plan 11-02)", allow_module_level=True)` line from scheduler/tests/agents/test_image_render.py.

    Create scheduler/agents/image_render_agent.py. Structure (roughly — exact code is implementer's discretion, as long as behavior matches the tests):

      import asyncio
      import logging
      from datetime import datetime, timezone
      from uuid import UUID
      from typing import Any

      import aioboto3
      import google.genai as genai
      from google.genai import types as genai_types
      from sqlalchemy import select
      from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

      from database import engine
      from models.content_bundle import ContentBundle
      from config import get_settings

      logger = logging.getLogger(__name__)

      # Per D-05 — brand palette locked; exact prompt wording is discretion but must embed these colors verbatim.
      BRAND_PALETTE = "Brand palette (MUST use): #F0ECE4 warm cream background, #0C1B32 deep navy text, #D4AF37 gold accents."

      ROLES_BY_FORMAT: dict[str, list[tuple[str, str]]] = {
          "infographic": [
              ("twitter_visual", "16:9"),
              ("instagram_slide_1", "1:1"),
              ("instagram_slide_2", "1:1"),
              ("instagram_slide_3", "1:1"),
          ],
          "quote": [
              ("twitter_visual", "16:9"),
              ("instagram_slide_1", "1:1"),
          ],
      }


      async def render_bundle_job(bundle_id: str) -> None:
          """Background job: generate images for an infographic/quote bundle and persist URLs to rendered_images.

          Silent-fail per D-18: never raises. Logs at WARNING on retry, ERROR on permanent failure.
          """
          session_factory = async_sessionmaker(engine, expire_on_commit=False)
          async with session_factory() as session:
              try:
                  await _render_and_persist(session, UUID(bundle_id))
              except Exception as exc:  # defensive outer guard — NEVER let this job raise
                  logger.error("Render job unexpected failure for %s: %s", bundle_id, exc, exc_info=True)


      async def _render_and_persist(session: AsyncSession, bundle_id: UUID) -> None:
          result = await session.execute(select(ContentBundle).where(ContentBundle.id == bundle_id))
          bundle = result.scalar_one_or_none()
          if bundle is None:
              logger.warning("render: bundle %s not found", bundle_id)
              return
          if not bundle.compliance_passed:
              logger.info("render: bundle %s skipped (compliance_passed=False)", bundle_id)
              return
          roles = ROLES_BY_FORMAT.get((bundle.content_type or "").lower())
          if not roles:
              logger.info("render: bundle %s format=%s has no render roles", bundle_id, bundle.content_type)
              return

          client = genai.Client()  # reads GEMINI_API_KEY from env
          rendered: list[dict[str, Any]] = []
          for role, aspect_ratio in roles:
              prompt = _build_prompt(role, bundle.draft_content or {}, bundle.story_headline)
              image_bytes = await _generate_with_retry(client, prompt, aspect_ratio, role, str(bundle_id))
              if image_bytes is None:
                  continue  # per-role permanent failure — skip but keep going
              timestamp = int(datetime.now(timezone.utc).timestamp())
              object_key = f"content-bundles/{bundle_id}/{role}-{timestamp}.png"
              try:
                  url = await _upload_to_r2(image_bytes, object_key)
              except Exception as exc:
                  logger.error("render: R2 upload failed for bundle %s role %s: %s", bundle_id, role, exc, exc_info=True)
                  continue
              rendered.append({
                  "role": role,
                  "url": url,
                  "generated_at": datetime.now(timezone.utc).isoformat(),
              })

          # Always write SOMETHING: either the rendered list (possibly partial) or an empty list.
          # Empty list tells frontend polling "no images landed — stop polling" (D-14 works on age;
          # empty-but-present list also works via the refetchInterval check in Plan 05).
          bundle.rendered_images = rendered
          await session.commit()
          logger.info("render: bundle %s produced %d/%d images", bundle_id, len(rendered), len(roles))


      async def _generate_with_retry(client, prompt: str, aspect_ratio: str, role: str, bundle_id: str) -> bytes | None:
          """Imagen 4 call with exponential backoff (3 attempts, ~2s/~8s delays per D-18)."""
          for attempt in range(3):
              try:
                  response = await client.aio.models.generate_images(
                      model="imagen-4.0-generate-001",
                      prompt=prompt,
                      config=genai_types.GenerateImageConfig(
                          number_of_images=1,
                          aspect_ratio=aspect_ratio,
                          output_mime_type="image/png",
                      ),
                  )
                  return response.generated_images[0].image.image_bytes
              except Exception as exc:
                  if attempt < 2:
                      delay = 2 ** (attempt + 1)  # 2s, 4s (actually per D-18 "~2s/~8s/~30s" guidance — 2/8 here)
                      if attempt == 1:
                          delay = 8
                      logger.warning(
                          "render: bundle %s role %s attempt %d failed: %s — retrying in %ds",
                          bundle_id, role, attempt + 1, exc, delay,
                      )
                      await asyncio.sleep(delay)
                  else:
                      logger.error(
                          "render: bundle %s role %s permanently failed after 3 attempts: %s",
                          bundle_id, role, exc, exc_info=True,
                      )
          return None


      async def _upload_to_r2(image_bytes: bytes, object_key: str) -> str:
          settings = get_settings()
          session = aioboto3.Session()
          async with session.client(
              "s3",
              endpoint_url=f"https://{settings.r2_account_id}.r2.cloudflarestorage.com",
              aws_access_key_id=settings.r2_access_key_id,
              aws_secret_access_key=settings.r2_secret_access_key,
              region_name="auto",
          ) as s3:
              await s3.put_object(
                  Bucket=settings.r2_bucket,
                  Key=object_key,
                  Body=image_bytes,
                  ContentType="image/png",
              )
          return f"{(settings.r2_public_base_url or '').rstrip('/')}/{object_key}"


      def _build_prompt(role: str, draft_content: dict, story_headline: str) -> str:
          """Return the Imagen prompt for a given role. Prompt wording is discretion; brand palette is locked (D-05)."""
          # Implementer: build a compact prompt referencing draft_content slide spec, story_headline, and BRAND_PALETTE.
          # Must include the literal hex codes "#F0ECE4", "#0C1B32", "#D4AF37" in the prompt string.
          raise NotImplementedError("See docstring — implementer writes prompt; see test_render_prompts.py for shape requirements.")

    Now REPLACE the scheduler/tests/agents/test_image_render.py stubs with real tests matching behaviors 1–7 above. Use the `fake_imagen_client` and `fake_r2_client` fixtures from scheduler/tests/conftest.py. Patch genai.Client and aioboto3.Session at the module level using monkeypatch.

    Ensure tests mock settings so r2_public_base_url returns e.g. "https://pub.r2.dev/seva-test".

    For the retry test (Test 5), make the mock raise on the first two calls and return bytes on the third call — assert len(rendered_images)==1 and logger.warning was called twice.

    For the compliance gate test (Test 3), assert fake_imagen_client.aio.models.generate_images was NOT called (call_count == 0).

    Make these tests run as async via pytest-asyncio (asyncio_mode=auto is already set in scheduler/pyproject.toml).
  </action>
  <verify>
    <automated>cd /Users/matthewnelson/seva-mining/scheduler && uv run pytest tests/agents/test_image_render.py -v</automated>
  </verify>
  <acceptance_criteria>
    - File /Users/matthewnelson/seva-mining/scheduler/agents/image_render_agent.py exists
    - `grep -c "async def render_bundle_job" /Users/matthewnelson/seva-mining/scheduler/agents/image_render_agent.py` returns 1
    - `grep -c "imagen-4.0-generate-001" /Users/matthewnelson/seva-mining/scheduler/agents/image_render_agent.py` returns 1
    - `grep -c "region_name=\"auto\"" /Users/matthewnelson/seva-mining/scheduler/agents/image_render_agent.py` returns 1
    - `grep -c "ACL" /Users/matthewnelson/seva-mining/scheduler/agents/image_render_agent.py` returns 0 (R2 rejects ACLs — Pitfall 4)
    - `grep -c "compliance_passed" /Users/matthewnelson/seva-mining/scheduler/agents/image_render_agent.py` returns ≥ 1
    - `grep -c "pytest.skip" /Users/matthewnelson/seva-mining/scheduler/tests/agents/test_image_render.py` returns 0 (skip marker removed)
    - pytest run reports 6 PASSED (or 6 PASSED + 1 XFAIL if prompt test split — see Task 2)
  </acceptance_criteria>
  <done>
    render_bundle_job is implemented with correct compliance gating, per-role retry, R2 upload, and DB write. All 6 behavioral tests pass. _build_prompt is deliberately left as NotImplementedError for Task 2 to fill.
  </done>
</task>

<task type="auto" tdd="true">
  <name>Task 2: Prompt builder with brand palette enforcement</name>
  <files>
    scheduler/agents/image_render_agent.py,
    scheduler/tests/agents/test_image_render_prompts.py
  </files>
  <read_first>
    /Users/matthewnelson/seva-mining/scheduler/agents/image_render_agent.py (current state after Task 1),
    /Users/matthewnelson/seva-mining/.planning/phases/11-content-preview-and-rendered-images/11-CONTEXT.md (§decisions D-05, §specifics)
  </read_first>
  <behavior>
    - Test 1 (test_prompt_infographic_twitter_visual_contains_brand_hex): _build_prompt("twitter_visual", infographic_draft, headline) returns a string containing all three hex codes: "#F0ECE4", "#0C1B32", "#D4AF37".
    - Test 2 (test_prompt_infographic_slide_1_references_slide_headline): _build_prompt("instagram_slide_1", draft_with_carousel_slides, headline) returns a string containing the slide 1 headline text.
    - Test 3 (test_prompt_infographic_slide_2_references_slide_headline): Same for slide 2.
    - Test 4 (test_prompt_infographic_slide_3_references_slide_headline): Same for slide 3.
    - Test 5 (test_prompt_quote_twitter_visual_contains_attributed_to): _build_prompt("twitter_visual", quote_draft, headline) contains draft_content["attributed_to"] value.
    - Test 6 (test_prompt_quote_instagram_slide_1_contains_quote_text): Contains the twitter_post or instagram_post string.
    - Test 7 (test_prompt_missing_slide_falls_back_to_headline): _build_prompt("instagram_slide_3", draft_without_slide_3, headline) does not crash; falls back to story_headline.
    - Test 8 (test_prompt_never_raises_on_malformed_draft_content): _build_prompt("twitter_visual", {}, "Story") returns a valid non-empty string.
  </behavior>
  <action>
    Replace the NotImplementedError stub in image_render_agent._build_prompt with a real implementation. The prompt must:
      1. Include BRAND_PALETTE constant (which contains all three hex codes verbatim)
      2. Include role-specific visual direction:
         - twitter_visual / infographic → "horizontal 16:9 hero graphic ... headline in navy on cream"
         - instagram_slide_N / infographic → pull draft_content["instagram_brief"]["carousel_slides"][N-1] if present; use its headline and key_stat; wrap with brand palette directive
         - twitter_visual / quote → quote pull-card with attribution
         - instagram_slide_1 / quote → square quote card
      3. Include a structural prefix "Design a [aspect] social media image" so Imagen gets a clear framing instruction
      4. Never raise on missing keys — use .get() chains with sensible fallbacks to story_headline

    Create scheduler/tests/agents/test_image_render_prompts.py with the 8 tests above. Tests import _build_prompt directly and assert substring presence — they do NOT call Imagen.

    Keep this test file separate from test_image_render.py so the mocked-Imagen orchestrator tests stay focused.
  </action>
  <verify>
    <automated>cd /Users/matthewnelson/seva-mining/scheduler && uv run pytest tests/agents/test_image_render_prompts.py -v</automated>
  </verify>
  <acceptance_criteria>
    - `grep -c "NotImplementedError" /Users/matthewnelson/seva-mining/scheduler/agents/image_render_agent.py` returns 0
    - `grep -c "#F0ECE4\|#0C1B32\|#D4AF37" /Users/matthewnelson/seva-mining/scheduler/agents/image_render_agent.py` returns ≥ 3
    - File /Users/matthewnelson/seva-mining/scheduler/tests/agents/test_image_render_prompts.py exists
    - pytest reports 8 PASSED from test_image_render_prompts.py
    - pytest --collect-only on scheduler still passes
  </acceptance_criteria>
  <done>
    _build_prompt produces non-empty strings with all brand hex codes and role-appropriate content. 8 prompt tests pass. The full test_image_render.py suite still passes (no regressions).
  </done>
</task>

</tasks>

<verification>
- `cd scheduler && uv run pytest tests/agents/ -v` — ≥ 14 PASSED (6 orchestrator + 8 prompt)
- `cd scheduler && uv run pytest` — full suite green, no regressions
- Manual code read: image_render_agent.py follows async patterns, uses aioboto3 (not sync boto3), and never imports `requests`
</verification>

<success_criteria>
- render_bundle_job is importable from both `from agents.image_render_agent import render_bundle_job` (scheduler context) and via the same path when scheduler/ is on the Python path from backend (Plan 03 will verify import from backend side)
- Compliance gate works: compliance_passed=False → no API calls
- Retry logic is per-role with 3 attempts and exponential backoff
- Silent-fail guarantee: no exception ever propagates out of render_bundle_job
- Brand palette is enforced in every prompt
</success_criteria>

<output>
Create `.planning/phases/11-content-preview-and-rendered-images/11-02-SUMMARY.md` noting:
- Final render_bundle_job signature
- Exact retry semantics (per-role, backoff delays)
- Whether partial-success path (e.g. 3/4 images) was tested and which path the code takes (writes partial list → frontend stops polling)
- Any API quirks discovered while running against the mocked Imagen client that downstream plans should know about
</output>
