---
phase: 260420-mfy
plan: 01
type: execute
wave: 1
depends_on: []
files_modified:
  # Backend code to delete (full files)
  - scheduler/chart_renderer/                  # entire directory
  - scheduler/agents/chart_renderer_client.py  # delete
  - scheduler/agents/image_render_agent.py     # delete
  - scheduler/models/chart_spec.py             # delete
  - backend/app/models/chart_spec.py           # delete
  - scheduler/tests/test_chart_renderer_client.py  # delete
  - scheduler/tests/test_chart_spec.py         # delete
  - scheduler/tests/test_image_render_agent.py # delete
  - scheduler/tests/agents/test_image_render.py # delete
  - scheduler/tests/agents/test_image_render_prompts.py # delete
  # Backend code to edit
  - scheduler/Dockerfile
  - scheduler/worker.py
  - scheduler/agents/content_agent.py
  - scheduler/agents/brand_preamble.py         # NEW
  - scheduler/tests/test_content_agent.py
  - backend/app/routers/content_bundles.py
  - backend/app/schemas/content_bundle.py
  - backend/tests/routers/test_content_bundles.py
  # Frontend
  - frontend/src/api/types.ts
  - frontend/src/components/content/InfographicPreview.tsx
  - frontend/src/components/content/InfographicPreview.test.tsx
  - frontend/src/components/content/QuotePreview.tsx
  - frontend/src/components/content/RenderedImagesGallery.tsx  # delete
  - frontend/src/components/approval/ContentSummaryCard.tsx
  - frontend/src/components/approval/ContentDetailModal.tsx
  - frontend/src/components/approval/__tests__/ContentDetailModal.test.tsx
autonomous: true
requirements: [MFY-01, MFY-02, MFY-03, MFY-04, MFY-05]

must_haves:
  truths:
    - "Content agent infographic bundle writes draft_content with three text fields: suggested_headline, data_facts, image_prompt (no `charts` array)."
    - "Content agent quote bundle writes draft_content with three text fields: suggested_headline, data_facts, image_prompt (no Imagen-shaped fields driving renders)."
    - "Every generated image_prompt begins with the BRAND_PREAMBLE string (DRY, module-level constant) and contains all six Seva brand hex codes verbatim: #F0ECE4, #0C1B32, #1E3A5F, #4A7FA5, #5A6B7A, #D4AF37, #D8D2C8, DM Serif Display, Inter, 1200x675, SEVA MINING wordmark."
    - "Scheduler Docker image builds pure-Python (no node, no npm, no chart_renderer COPY, no font download) and no COPY path re-introduces the `scheduler/` prefix bug (quick-t78 `bbc6e6a`)."
    - "Backend rerender endpoint `POST /content-bundles/{id}/rerender` is removed (route no longer registered); clients hitting it get 404."
    - "Dashboard infographic and quote cards (both ContentSummaryCard inline render AND ContentDetailModal) show three copy-buttoned text blocks (Suggested Headline / Key Facts / Image Prompt) — no <img>, no Dialog enlarge, no fetch+blob download, no Regenerate images button."
    - "Legacy pre-mfy bundles (draft_content missing image_prompt) render a minimal \"Legacy format — regenerate this bundle\" placeholder instead of crashing the card."
    - "Grep sweep across scheduler/, backend/, frontend/src/ (excluding .planning/ and .claude/worktrees/) returns zero matches for chart_renderer, ChartRendererClient, ChartSpec, BundleCharts, imagen, render_bundle_job, _enqueue_render_job_if_eligible, rendered_images (in production code — tests may mention the column name for DB compatibility assertions)."
    - "Full test suites pass: `cd scheduler && uv run pytest tests/ -x`, `cd backend && uv run pytest tests/ -x`, `cd frontend && npm run test -- --run`, and `cd frontend && npm run build` all green."
  artifacts:
    - path: "scheduler/agents/brand_preamble.py"
      provides: "Module-level BRAND_PREAMBLE string constant — the full Seva Mining visual spec that seeds every image_prompt."
      exports: ["BRAND_PREAMBLE"]
      contains: "F0ECE4"
      min_lines: 20
    - path: "scheduler/agents/content_agent.py"
      provides: "Infographic and quote prompts rewritten to emit {suggested_headline, data_facts, image_prompt}; _enqueue_render_job_if_eligible removed; BundleCharts validation removed."
    - path: "scheduler/Dockerfile"
      provides: "Pure-Python Dockerfile — no Node base image, no npm, no font download. Root Directory assumes scheduler/ (relative COPY paths, no scheduler/ prefix)."
    - path: "scheduler/worker.py"
      provides: "No chart_renderer_client imports, no get_chart_renderer_client().start()/stop() in main(), no imports from scheduler/agents/chart_renderer_client.py or agents/image_render_agent.py."
    - path: "backend/app/routers/content_bundles.py"
      provides: "Only GET /content-bundles/{id} remains — rerender endpoint and importlib shim removed."
    - path: "frontend/src/components/content/InfographicPreview.tsx"
      provides: "Three copy-buttoned text blocks (Headline, Key Facts, Image Prompt). No images, no downloads, no dialogs."
    - path: "frontend/src/components/content/QuotePreview.tsx"
      provides: "Three copy-buttoned text blocks (Headline, Key Facts, Image Prompt). No images, no downloads, no dialogs."
    - path: "frontend/src/components/approval/ContentSummaryCard.tsx"
      provides: "No InlineImagesGallery for infographic/quote — card is pure text + action buttons. `useContentBundle`, `handleDownload`, `Dialog`, `Download` icon, `RenderedImage` type usage removed."
    - path: "frontend/src/components/approval/ContentDetailModal.tsx"
      provides: "No RenderedImagesGallery mount. Still renders per-format preview."
  key_links:
    - from: "scheduler/agents/content_agent.py"
      to: "scheduler/agents/brand_preamble.py"
      via: "from agents.brand_preamble import BRAND_PREAMBLE"
      pattern: "from agents\\.brand_preamble import BRAND_PREAMBLE"
    - from: "scheduler/agents/content_agent.py infographic+quote prompts"
      to: "draft_content {suggested_headline, data_facts, image_prompt}"
      via: "Sonnet system+user prompt for infographic & quote branches instructs it to emit these three fields; the agent constructs image_prompt as `BRAND_PREAMBLE + type-specific direction` (infographic vs quote gets different visual direction blocks)"
      pattern: "image_prompt.*BRAND_PREAMBLE"
    - from: "frontend infographic/quote preview components"
      to: "three separate copy buttons wired to navigator.clipboard.writeText"
      via: "Inline Button + toast.success pattern mirroring ThreadPreview.tsx (no shared CopyButton component exists; do not add one)"
      pattern: "navigator\\.clipboard\\.writeText"
    - from: "scheduler/Dockerfile"
      to: "Railway scheduler service Root Directory = scheduler/"
      via: "All COPY paths relative to scheduler/ (e.g. `COPY worker.py .` NOT `COPY scheduler/worker.py .`) — per quick-t78 `bbc6e6a` postmortem"
      pattern: "^COPY (?!scheduler/)"
---

<objective>
Rip out on-platform infographic + quote rendering (Node chart_renderer, Gemini Imagen quote renderer, ChartRendererClient, ChartSpec/BundleCharts, rerender endpoint, frontend image UI) and replace with three new text fields per bundle: `suggested_headline`, `data_facts`, `image_prompt`. Operator copies the image_prompt into claude.ai artifacts to produce the final visual. Scheduler Dockerfile returns to pure-Python.

Purpose: Quick-t78 (Recharts SSR) and Phase-11 (Gemini Imagen) both proved too brittle, too slow, and too expensive for a solo operator. Pivoting to "let claude.ai cowork handle the pixels" — we stay in our lane (drafting text + structured data), claude.ai handles rendering.

Output: Pure-text three-field dashboard cards for infographic+quote, a lean pure-Python scheduler image, a smaller and simpler codebase.
</objective>

<execution_context>
@$HOME/.claude/get-shit-done/workflows/execute-plan.md
@$HOME/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@CLAUDE.md
@.planning/STATE.md

<!-- Anchor files (do not need to load in full — executor reads on demand). Key code paths: -->
<!-- scheduler/agents/content_agent.py — infographic prompt lines ~1194, ~1227-1265; quote prompt ~1267-1268 and _draft_quote_post ~1078-1147; _enqueue_render_job_if_eligible ~116-157 and its 3 call sites lines 1709, 1831, 1894. -->
<!-- scheduler/agents/chart_renderer_client.py — full file delete. -->
<!-- scheduler/agents/image_render_agent.py — full file delete. -->
<!-- scheduler/models/chart_spec.py + backend/app/models/chart_spec.py — full file delete. -->
<!-- scheduler/Dockerfile — rewrite per §4. -->
<!-- scheduler/worker.py — lines 21, 366-376, 390-394 (chart_client start/stop). -->
<!-- backend/app/routers/content_bundles.py — lines 33-42 (sys.path shim), 44-87 (_get_render_bundle_job), 114-145 (rerender endpoint) all removed. -->
<!-- frontend/src/components/approval/ContentSummaryCard.tsx — remove lines 13 (Dialog import), 14 (useContentBundle), 15 (RenderedImage), 21-23 (ROLE_LABELS), 60-67 (bundle fetch + renderedImages), 114-133 (handleDownload), 195-202 (InlineImagesGallery mount), 243-294 (InlineImagesGallery component). -->
<!-- frontend/src/components/approval/ContentDetailModal.tsx — remove RenderedImagesGallery import and mount (lines 16, 93-98). -->
<!-- frontend/src/components/content/RenderedImagesGallery.tsx — full file delete. -->

<interfaces>
<!-- New content_agent emission shape for infographic AND quote (both content_types share these 3 new fields on top of type-specific legacy text fields that still ride along for backwards-compat: twitter_caption for infographic, twitter_post for quote): -->

```python
# draft_content shape after this plan (infographic):
{
  "format": "infographic",
  "twitter_caption": "1-3 sentence senior analyst caption (unchanged — this is the tweet)",
  "suggested_headline": "short editorial title, <=60 chars",   # NEW
  "data_facts": ["fact 1", "fact 2", "..."],                    # NEW, 1-5 items
  "image_prompt": "BRAND_PREAMBLE + infographic-specific direction string",  # NEW
}

# draft_content shape after this plan (quote):
{
  "format": "quote",
  "speaker": "Full Name",
  "speaker_title": "title/credentials",
  "quote_text": "\"the exact quote\"",
  "source_url": "...",
  "twitter_post": "tweet text (unchanged)",
  "suggested_headline": "short editorial title, <=60 chars",   # NEW
  "data_facts": ["fact 1", ...],                                # NEW, 1-5 items
  "image_prompt": "BRAND_PREAMBLE + quote-specific direction string",  # NEW
}
```

```typescript
// Frontend type additions (frontend/src/api/types.ts — DraftItemResponse.alternatives[0].text unchanged;
// the three new fields live in ContentBundleDetailResponse.draft_content which is typed `unknown`.
// Previews should type-narrow locally, consistent with existing QuotePreview pattern):
interface InfographicDraft {
  format: 'infographic'
  twitter_caption?: string
  suggested_headline?: string
  data_facts?: string[]
  image_prompt?: string
}

interface QuoteDraft {
  format: 'quote'
  speaker?: string
  attributed_to?: string
  twitter_post?: string
  suggested_headline?: string
  data_facts?: string[]
  image_prompt?: string
}
```

<!-- Existing copy-button pattern (reuse verbatim — do NOT extract a shared component): -->
```tsx
// From ThreadPreview.tsx — replicate this inline for each of the 3 blocks:
<Button size="sm" variant="ghost" onClick={() => {
  navigator.clipboard.writeText(text)
  toast.success('Copied')
}}>Copy</Button>
```
</interfaces>
</context>

<tasks>

<task type="auto">
  <name>Task 1: Rip out backend rendering (deletions + Dockerfile + wiring)</name>
  <files>
    scheduler/chart_renderer/ (directory delete),
    scheduler/agents/chart_renderer_client.py (delete),
    scheduler/agents/image_render_agent.py (delete),
    scheduler/models/chart_spec.py (delete),
    backend/app/models/chart_spec.py (delete),
    scheduler/tests/test_chart_renderer_client.py (delete),
    scheduler/tests/test_chart_spec.py (delete),
    scheduler/tests/test_image_render_agent.py (delete),
    scheduler/tests/agents/test_image_render.py (delete),
    scheduler/tests/agents/test_image_render_prompts.py (delete),
    scheduler/Dockerfile,
    scheduler/worker.py,
    backend/app/routers/content_bundles.py,
    backend/tests/routers/test_content_bundles.py
  </files>
  <action>
**Execution order matters — delete files first, then edit callers, then edit Dockerfile last.**

### 1a. Discover & confirm no unexpected callers
Run Grep for each symbol below across `scheduler/`, `backend/`, `frontend/src/` (exclude `.planning/` and `.claude/`). Record the files that match; expected set is listed in parens. If any OTHER file matches, STOP and add a removal edit for it in this task.

- `chart_renderer` → expect: `scheduler/Dockerfile`, `scheduler/worker.py`, `scheduler/agents/image_render_agent.py` (being deleted), `scheduler/agents/chart_renderer_client.py` (being deleted), test files being deleted, `scheduler/chart_renderer/` (being deleted).
- `ChartRendererClient` → expect: `scheduler/agents/chart_renderer_client.py`, `scheduler/worker.py`, test files.
- `ChartSpec` / `BundleCharts` → expect: `scheduler/models/chart_spec.py`, `backend/app/models/chart_spec.py`, `scheduler/agents/content_agent.py` (lazy import inside `_research_and_draft`), `scheduler/agents/chart_renderer_client.py`, `scheduler/agents/image_render_agent.py`, test files.
- `imagen` / `google.genai` / `genai_types` → expect: `scheduler/agents/image_render_agent.py`, `scheduler/tests/test_image_render_agent.py`.
- `render_bundle_job` → expect: `scheduler/agents/image_render_agent.py`, `scheduler/agents/content_agent.py` (_enqueue_render_job_if_eligible), `backend/app/routers/content_bundles.py`, test files.
- `rendered_images` → expect: `backend/app/models/content_bundle.py` (KEEP — column stays), `backend/app/schemas/content_bundle.py` (REMOVE the `rendered_images` field from `ContentBundleDetailResponse` AND remove the `RenderedImage` class), `backend/tests/routers/test_content_bundles.py` (update assertions below), `scheduler/agents/image_render_agent.py` (being deleted), `frontend/src/api/types.ts` (REMOVE `RenderedImage` interface and `rendered_images` field from `ContentBundleDetailResponse`), `frontend/src/components/approval/ContentSummaryCard.tsx` (Task 3), `frontend/src/components/content/RenderedImagesGallery.tsx` (Task 3), `frontend/src/components/approval/ContentDetailModal.tsx` (Task 3), `frontend/src/components/content/InfographicPreview.tsx` (Task 3).

Scope note: the `rendered_images` JSONB column stays in the DB schema (operator explicitly said do NOT drop the table/column — migration 0006 stays untouched). But nothing in production code writes to it anymore after this plan, and it's not surfaced via the API response schema.

### 1b. Delete files (git rm for tracked, rm -rf for untracked)
```bash
git rm -r scheduler/chart_renderer/
git rm scheduler/agents/chart_renderer_client.py
git rm scheduler/agents/image_render_agent.py
git rm scheduler/models/chart_spec.py
git rm backend/app/models/chart_spec.py
git rm scheduler/tests/test_chart_renderer_client.py
git rm scheduler/tests/test_chart_spec.py
git rm scheduler/tests/test_image_render_agent.py
git rm scheduler/tests/agents/test_image_render.py
git rm scheduler/tests/agents/test_image_render_prompts.py
```
If any `git rm` fails with "did not match any files" the path is untracked — use `rm -rf` / `rm` for those.

### 1c. scheduler/worker.py
- Delete line 21: `from agents.chart_renderer_client import get_chart_renderer_client`.
- Delete lines 365-376 (the `chart_client = get_chart_renderer_client()` block plus try/except around `chart_client.start()`).
- Delete lines 390-394 (the chart_client.stop() try/except in the finally block). Leave `await engine.dispose()` as the finally body.

### 1d. backend/app/routers/content_bundles.py
- Remove the sys.path shim (lines 33-42).
- Remove the entire `_get_render_bundle_job()` helper (lines 44-87).
- Remove the entire `rerender_content_bundle` POST handler (lines 114-145).
- Remove unused imports that were only used by the deleted code: `asyncio`, `os`, `sys`, `uuid4`, `datetime`, `UTC`. Keep `logging`, `UUID`, FastAPI/SQLAlchemy imports, and the remaining schema imports.
- Remove `RerenderResponse` from the schema import since it's now unused.
- Final file should contain only the module docstring (updated to reference only GET), the router definition, and the single GET handler.

### 1e. backend/app/schemas/content_bundle.py
- Delete the `RenderedImage` BaseModel (lines 24-30).
- Delete the `rendered_images: list[RenderedImage] | None = None` field from `ContentBundleDetailResponse` (line 46).
- Delete the `RerenderResponse` BaseModel entirely (lines 50-53).

### 1f. backend/tests/routers/test_content_bundles.py
- Delete all rerender tests: `test_rerender_returns_202`, `test_rerender_clears_existing_images`, `test_rerender_404_on_missing_bundle`, `test_rerender_requires_auth`, `test_rerender_enqueues_render_bundle_job` (lines ~173 to end of file).
- In `test_get_content_bundle_*` tests, remove assertions about `rendered_images` being in the response payload.
- In `test_get_content_bundle_rendered_images_null_returns_null`, either delete the test or rename + rewrite to verify `rendered_images` is NOT in the response body at all.
- In the `make_content_bundle` test helper, keep the `rendered_images` param + attribute set so DB-layer compatibility is preserved; tests just no longer assert on it via API.

### 1g. scheduler/Dockerfile (rewrite, pure-Python)
Replace entire file with:

```dockerfile
# Pure-Python scheduler image. Railway scheduler service Root Directory = scheduler/,
# so all COPY paths are relative to scheduler/ (NO `scheduler/` prefix — quick-t78 `bbc6e6a` lesson).
FROM python:3.12-slim

WORKDIR /app

RUN pip install --no-cache-dir uv

# Copy dependency spec first (layer caching)
COPY pyproject.toml .
COPY uv.lock* .

# Install production dependencies only
RUN uv sync --no-dev

# Copy scheduler source files
COPY worker.py .
COPY config.py .
COPY database.py .
COPY agents/ ./agents/
COPY models/ ./models/
COPY services/ ./services/
COPY seed_content_data.py .
COPY seed_twitter_data.py .

# No EXPOSE — scheduler worker has no HTTP port

CMD ["/app/.venv/bin/python", "worker.py"]
```

Verify: every COPY uses a path relative to `scheduler/` (e.g. `COPY worker.py .`) and NOT `COPY scheduler/worker.py .`. Any `scheduler/`-prefixed COPY recreates the quick-t78 Root Directory bug.

### 1h. scheduler/pyproject.toml
Check if `google-genai`, `aioboto3`, or any Node-toolchain-related deps appear in `[project.dependencies]`. If they exist AND are only used by the deleted `image_render_agent.py`, remove them and re-run `uv sync --no-dev`. Leave `aioboto3` if any other code imports it (grep first). Do NOT remove `anthropic`, `tweepy`, `feedparser`, `serpapi`, `apscheduler`, `sqlalchemy`, `asyncpg`, `pydantic`.

### 1i. Verify
```bash
cd scheduler && uv run ruff check agents/ worker.py config.py database.py tests/
cd scheduler && uv run pytest tests/ -x
cd ../backend && uv run ruff check app/ tests/
cd backend && uv run pytest tests/ -x
```

All four commands must pass. Any `ImportError` indicates a missed caller — fix and re-run.
  </action>
  <verify>
    <automated>cd /Users/matthewnelson/seva-mining/scheduler && uv run pytest tests/ -x && cd ../backend && uv run pytest tests/ -x && cd .. && ! grep -rn -E "chart_renderer|ChartRendererClient|ChartSpec|BundleCharts|render_bundle_job|_enqueue_render_job|rendered_images|imagen" scheduler/ backend/ frontend/src/ --include='*.py' --include='*.ts' --include='*.tsx' | grep -vE '^(scheduler|backend)/tests/|^scheduler/chart_renderer/|Binary file'</automated>
  </verify>
  <done>
    All 10 target files/directories deleted from disk. scheduler/Dockerfile is pure-Python (no `FROM nikolaik`, no `npm ci`, no `download-fonts.sh`, no `chart_renderer/` COPY). scheduler/worker.py no longer imports chart_renderer_client. backend/app/routers/content_bundles.py exposes only GET (no rerender route). Both pytest suites green. Grep sweep confirms zero production-code references to deleted symbols.
  </done>
</task>

<task type="auto" tdd="true">
  <name>Task 2: Rewrite content agent prompts — brand preamble + three new fields</name>
  <files>
    scheduler/agents/brand_preamble.py (NEW),
    scheduler/agents/content_agent.py,
    scheduler/tests/test_content_agent.py
  </files>
  <behavior>
    - Test A (new): `from agents.brand_preamble import BRAND_PREAMBLE` loads; the string contains all of these substrings verbatim: `#F0ECE4`, `#0C1B32`, `#1E3A5F`, `#4A7FA5`, `#5A6B7A`, `#D4AF37`, `#D8D2C8`, `DM Serif Display`, `Inter`, `SEVA MINING`, `1200x675`, `HTML artifact`.
    - Test B (new): `len(BRAND_PREAMBLE) >= 200` (operator-specified floor — brand spec is dense enough).
    - Test C (new, monkey-patched Anthropic mock returning the new-shape JSON): `ContentAgent._research_and_draft` for an infographic story returns a draft_content dict whose keys include `suggested_headline`, `data_facts`, `image_prompt` AND whose `image_prompt` starts with `BRAND_PREAMBLE` verbatim (prefix match).
    - Test D (new): same as C but for the quote path (`_draft_quote_post`) — returns `suggested_headline`, `data_facts`, `image_prompt`, image_prompt starts with BRAND_PREAMBLE.
    - Test E (new): `suggested_headline` length assertion — when Sonnet emits a >60-char headline, the draft_content STILL includes it (soft hint only, not a Pydantic constraint that rejects the bundle). No downgrade on headline-length alone.
    - Test F (new): `data_facts` is a list with 1-5 items; if Sonnet returns 0 or >5, content_agent clamps it (slice `[:5]` and keep empty list as empty, never raise).
    - Test G (existing): the long-form 400-char floor still works (nothing in this plan touches it).
    - Test H (existing): the compliance check in `_extract_check_text` now reads from `twitter_caption` / `twitter_post` (unchanged) plus the new `suggested_headline` and `data_facts` strings so those fields are ALSO compliance-screened. Add a test case that blocks a bundle whose `data_facts` contains "Seva Mining" or financial-advice phrasing.
  </behavior>
  <action>
### 2a. Create scheduler/agents/brand_preamble.py
Single exported constant. Use this exact content (operator-locked wording — do not improvise):

```python
"""Seva Mining brand preamble for claude.ai artifact prompts.

Concatenated verbatim at the start of every image_prompt emitted by the content agent
for infographic and quote post types. Centralizing the visual spec keeps prompts DRY
and makes brand updates a one-line change.

Target: claude.ai artifacts / cowork. Operator pastes the full image_prompt into claude.ai
and receives a finished HTML artifact they can screenshot for social.
"""

BRAND_PREAMBLE = """You are building a Seva Mining editorial social asset as a single self-contained HTML artifact. The operator will screenshot the rendered artifact for Twitter/X.

BRAND PALETTE (use exactly these hex codes):
- Cream background: #F0ECE4
- Deep navy primary: #0C1B32
- Lighter navy secondary: #1E3A5F
- Teal secondary: #4A7FA5
- Muted blue-gray text: #5A6B7A
- Gold accent: #D4AF37 (reserved for hero stats only — use sparingly)
- Warm gridlines: #D8D2C8 (horizontal-only, subtle)

TYPOGRAPHY:
- Titles: DM Serif Display (or a high-contrast editorial serif like Playfair Display as fallback)
- Body and data labels: Inter (or a clean modern sans-serif)

LAYOUT (a16z editorial):
- Large serif title, sans subtitle beneath
- Horizontal-only gridlines for any charts
- Uniform solid bars, no gradients, value labels at bar tips
- "SEVA MINING" wordmark bottom-right in small caps, muted blue-gray
- Source attribution bottom-left, smaller still
- Generous whitespace, no decorative elements

DIMENSIONS: 1200x675 (16:9, Twitter card friendly).

FORMAT: Produce as a single self-contained HTML artifact I can screenshot. Inline all CSS. No external fonts, images, or scripts — use system serif/sans fallbacks if DM Serif Display / Inter are not available in your runtime.
"""
```

### 2b. scheduler/agents/content_agent.py

**Delete:**
- Lines ~107-157: the entire `_enqueue_render_job_if_eligible` helper (no longer needed — no format writes rendered_images).
- Lines ~113: `_RENDER_FORMATS` constant.
- Lines 1318-1341: the BundleCharts validation + thread-downgrade block inside `_research_and_draft`. There is no more schema validation gate (Sonnet emits text, not chart specs).
- All 3 call sites of `_enqueue_render_job_if_eligible` (lines ~1709, ~1831, ~1894). Do not replace with anything — rendering is gone.

**Import at top of content_agent.py (near other local imports):**
```python
from agents.brand_preamble import BRAND_PREAMBLE
```

**Rewrite the infographic branch of the Sonnet system/user prompt in `_research_and_draft` (around lines 1194, 1227-1265):**

Replace the current infographic instructions (lines 1194, 1227-1265 — chart_spec JSON schema, chart_type guidance, carousel rule, visual style) with:

```
   - "infographic" — for stories with clear comparison, trend, or historical parallel with >=4 stats — better visualized than narrated. Choose this when the data is the story. Produces a tweet caption PLUS three fields (suggested_headline, data_facts, image_prompt) the operator will paste into claude.ai to render the visual.

[... keep the rest of format enumeration and rules unchanged ...]

For "infographic" format, draft_content must have:
{{"format": "infographic",
  "twitter_caption": "1-3 sentences for X in senior analyst voice",
  "suggested_headline": "short editorial title for the artifact, ideally <=60 chars",
  "data_facts": ["1-5 key numbers, percentages, quotes, or data points the image should feature — each <=120 chars"],
  "image_prompt_direction": "2-4 sentences telling claude.ai what kind of visual to build: which chart type (bar / line / stat-callouts / comparison-table / timeline), what the X and Y axes should be, what specific numbers/labels to use, and what the visual hierarchy should be. DO NOT restate the brand palette or layout rules — those are applied automatically. Focus on the STORY-SPECIFIC visual direction."
}}
```

After parsing Sonnet's JSON, construct the final `image_prompt` in Python:
```python
if draft_content.get("format") == "infographic":
    direction = draft_content.pop("image_prompt_direction", "").strip()
    # Clamp data_facts to 1-5 items
    facts = draft_content.get("data_facts") or []
    if not isinstance(facts, list):
        facts = []
    draft_content["data_facts"] = facts[:5]
    # Build final paste-ready prompt
    headline = draft_content.get("suggested_headline", "")
    facts_block = "\n".join(f"- {f}" for f in draft_content["data_facts"])
    draft_content["image_prompt"] = (
        f"{BRAND_PREAMBLE}\n\n"
        f"HEADLINE FOR THIS VISUAL:\n{headline}\n\n"
        f"KEY FACTS TO FEATURE:\n{facts_block}\n\n"
        f"STORY-SPECIFIC DIRECTION:\n{direction}"
    )
```

**Rewrite the quote path in `_draft_quote_post` (around lines 1078-1147):**

Update the Sonnet user_prompt for quote to also request `suggested_headline`, `data_facts`, `image_prompt_direction` alongside the existing `twitter_post` / `instagram_post` fields. Then after parsing, build `image_prompt` the same way as infographic, but with a quote-specific direction-framing (the returned JSON structure is the same three new fields):

```python
# After json.loads(raw) returns the parsed quote JSON:
direction = parsed.pop("image_prompt_direction", "").strip()
facts = parsed.get("data_facts") or []
if not isinstance(facts, list):
    facts = []
parsed["data_facts"] = facts[:5]
headline = parsed.get("suggested_headline", "")
facts_block = "\n".join(f"- {f}" for f in parsed["data_facts"])
parsed["image_prompt"] = (
    f"{BRAND_PREAMBLE}\n\n"
    f"ARTIFACT TYPE: pull-quote card (NOT a chart — center the quote itself as the hero element).\n\n"
    f"HEADLINE FOR THIS VISUAL:\n{headline}\n\n"
    f"KEY FACTS TO FEATURE:\n{facts_block}\n\n"
    f"STORY-SPECIFIC DIRECTION:\n{direction}"
)
```

Remove the old quote user_prompt's Instagram-shaped guidance (no more `instagram_post` Imagen-oriented design system block — operator confirmed Instagram is out of scope).

**Update `_extract_check_text` (around line 742-776) — infographic + quote branches:**
- Infographic: `parts.append(draft_content.get("suggested_headline", ""))` and `parts.extend(draft_content.get("data_facts", []))` in addition to the existing `twitter_caption` extraction. DROP the `for chart in draft_content.get("charts", [])` block — no more charts.
- Quote: add `parts.append(draft_content.get("suggested_headline", ""))` and `parts.extend(draft_content.get("data_facts", []))` to existing extraction.
- Do NOT compliance-check `image_prompt` (it's entirely brand preamble + derived from headline/facts, and would match "financial" words as false positives).

### 2c. scheduler/tests/test_content_agent.py
Update existing tests and add new ones per the `<behavior>` block above. Drop any test that asserts on `draft_content["charts"]` or BundleCharts validation. Add tests A-H above. Tests must run without hitting the real Anthropic API — use `monkeypatch.setattr` on `ContentAgent.anthropic.messages.create` to return a stub `response` object whose `content[0].text` is a pre-baked JSON string matching the new shape.

### 2d. Verify
```bash
cd scheduler && uv run ruff check agents/ tests/
cd scheduler && uv run pytest tests/test_content_agent.py -x
cd scheduler && uv run pytest tests/ -x
```
  </action>
  <verify>
    <automated>cd /Users/matthewnelson/seva-mining/scheduler && uv run pytest tests/test_content_agent.py -x && uv run python -c "from agents.brand_preamble import BRAND_PREAMBLE; required = ['#F0ECE4', '#0C1B32', '#1E3A5F', '#4A7FA5', '#5A6B7A', '#D4AF37', '#D8D2C8', 'DM Serif Display', 'Inter', 'SEVA MINING', '1200x675', 'HTML artifact']; missing = [s for s in required if s not in BRAND_PREAMBLE]; assert not missing, f'BRAND_PREAMBLE missing substrings: {missing}'; assert len(BRAND_PREAMBLE) >= 200, 'BRAND_PREAMBLE too short'"</automated>
  </verify>
  <done>
    brand_preamble.py exists with BRAND_PREAMBLE containing all 12 required substrings and >=200 chars. Content agent infographic + quote paths emit `{suggested_headline, data_facts, image_prompt}`; image_prompt starts with BRAND_PREAMBLE. _enqueue_render_job_if_eligible and _RENDER_FORMATS deleted. BundleCharts validation deleted. All content_agent tests pass. Full scheduler pytest suite green.
  </done>
</task>

<task type="auto" tdd="true">
  <name>Task 3: Simplify frontend cards — three copy blocks, remove image UI</name>
  <files>
    frontend/src/components/content/RenderedImagesGallery.tsx (delete),
    frontend/src/components/content/InfographicPreview.tsx,
    frontend/src/components/content/InfographicPreview.test.tsx,
    frontend/src/components/content/QuotePreview.tsx,
    frontend/src/components/approval/ContentSummaryCard.tsx,
    frontend/src/components/approval/ContentDetailModal.tsx,
    frontend/src/components/approval/__tests__/ContentDetailModal.test.tsx,
    frontend/src/api/types.ts
  </files>
  <behavior>
    - Test A (InfographicPreview.test.tsx): when `draft = {format:'infographic', suggested_headline:'H', data_facts:['f1','f2'], image_prompt:'BRAND_PREAMBLE ...'}` the component renders three labeled sections (text "Suggested Headline", "Key Facts", "Image Prompt") and three Copy buttons. Clicking each Copy button calls `navigator.clipboard.writeText` with the corresponding string (the facts button writes a joined string with each fact on its own line prefixed with "- ").
    - Test B (InfographicPreview.test.tsx): when `draft = {format:'infographic'}` (legacy shape, no image_prompt), the component renders ONLY "Legacy format — regenerate this bundle" and NO copy buttons. No crash, no console errors.
    - Test C (ContentDetailModal.test.tsx — update existing): the modal no longer renders `RenderedImagesGallery` (remove any query for it in existing tests). No `rendered_images` field is fetched or displayed.
    - Test D (new in InfographicPreview.test.tsx OR ContentDetailModal.test.tsx): no `<img>` tag is rendered anywhere for infographic or quote bundles.
  </behavior>
  <action>
### 3a. Delete frontend/src/components/content/RenderedImagesGallery.tsx

### 3b. frontend/src/api/types.ts
- Remove the `RenderedImage` interface.
- Remove `rendered_images?: RenderedImage[] | null` from `ContentBundleDetailResponse`.
- Remove `RerenderResponse` interface (endpoint is gone).

### 3c. frontend/src/components/content/InfographicPreview.tsx
Complete rewrite. Replace the whole file with a three-block copy-buttoned layout. Shape:

```tsx
import { Button } from '@/components/ui/button'
import { toast } from 'sonner'

interface InfographicDraft {
  format: 'infographic'
  twitter_caption?: string
  suggested_headline?: string
  data_facts?: string[]
  image_prompt?: string
}

export function InfographicPreview({ draft }: { draft: unknown }) {
  const d = (draft ?? {}) as InfographicDraft
  const headline = typeof d.suggested_headline === 'string' ? d.suggested_headline : ''
  const facts = Array.isArray(d.data_facts) ? d.data_facts.filter((f): f is string => typeof f === 'string') : []
  const imagePrompt = typeof d.image_prompt === 'string' ? d.image_prompt : ''
  const factsClipboard = facts.map(f => `- ${f}`).join('\n')

  // Legacy bundles pre-date this plan — show a minimal placeholder, never crash.
  if (!imagePrompt) {
    return (
      <div className="space-y-3 border rounded-lg p-4">
        <p className="text-sm text-muted-foreground">Legacy format — regenerate this bundle.</p>
      </div>
    )
  }

  return (
    <div className="space-y-3 border rounded-lg p-4">
      <span className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
        INFOGRAPHIC
      </span>

      {/* Block 1: Suggested Headline */}
      <div className="space-y-1.5">
        <div className="flex items-center justify-between">
          <p className="text-xs font-medium text-muted-foreground uppercase tracking-wide">Suggested Headline</p>
          <Button size="sm" variant="ghost" onClick={() => { navigator.clipboard.writeText(headline); toast.success('Headline copied') }}>
            Copy
          </Button>
        </div>
        <div className="bg-muted/40 rounded-lg p-3">
          <p className="text-sm leading-relaxed whitespace-pre-wrap">{headline}</p>
        </div>
      </div>

      {/* Block 2: Key Facts */}
      <div className="space-y-1.5">
        <div className="flex items-center justify-between">
          <p className="text-xs font-medium text-muted-foreground uppercase tracking-wide">Key Facts</p>
          <Button size="sm" variant="ghost" onClick={() => { navigator.clipboard.writeText(factsClipboard); toast.success('Facts copied') }}>
            Copy
          </Button>
        </div>
        <div className="bg-muted/40 rounded-lg p-3">
          <ul className="text-sm leading-relaxed space-y-1">
            {facts.map((f, i) => <li key={i}>- {f}</li>)}
          </ul>
        </div>
      </div>

      {/* Block 3: Image Prompt (claude.ai artifact) */}
      <div className="space-y-1.5">
        <div className="flex items-center justify-between">
          <p className="text-xs font-medium text-muted-foreground uppercase tracking-wide">Image Prompt (paste into claude.ai)</p>
          <Button size="sm" variant="ghost" onClick={() => { navigator.clipboard.writeText(imagePrompt); toast.success('Prompt copied') }}>
            Copy
          </Button>
        </div>
        <div className="bg-muted/40 rounded-lg p-3 max-h-64 overflow-y-auto">
          <pre className="text-xs leading-relaxed whitespace-pre-wrap font-mono">{imagePrompt}</pre>
        </div>
      </div>
    </div>
  )
}
```

### 3d. frontend/src/components/content/QuotePreview.tsx
Complete rewrite. Keep the existing twitter_post Copy block (unchanged behavior for the tweet itself), then add the same three new blocks AFTER it. Use the same legacy-placeholder gating: if `image_prompt` is missing, show ONLY the existing tweet block (if tweet exists) — do not crash. Structure:

- Header: `QUOTE` label + optional attribution inline.
- Block: Twitter / X tweet (existing Copy button — unchanged).
- Block: Suggested Headline + Copy (only if image_prompt present).
- Block: Key Facts + Copy (only if image_prompt present).
- Block: Image Prompt + Copy (only if image_prompt present).
- Footer: attribution + source link (unchanged).

Use the same inline Button + navigator.clipboard.writeText + toast.success pattern as above.

### 3e. frontend/src/components/content/InfographicPreview.test.tsx
Rewrite to cover behaviors A-D. Use `@testing-library/react` render + fireEvent. Stub `navigator.clipboard` and `toast` appropriately (existing tests already do this — follow the same pattern as ThreadPreview tests if present, or QuotePreview).

### 3f. frontend/src/components/approval/ContentSummaryCard.tsx
Remove all image/download UI:
- Remove imports: `Dialog, DialogContent, DialogTrigger` from `@/components/ui/dialog`, `Download` from `lucide-react`, `useContentBundle` from `@/hooks/useContentBundle`, `RenderedImage` from `@/api/types`.
- Remove `ROLE_LABELS` constant.
- Remove `bundleId` extraction from engagement_snapshot (lines 61-64).
- Remove `useContentBundle(bundleId)` call and `renderedImages` state (lines 65-66).
- Remove the `handleDownload` method (lines 114-133).
- Remove the `<InlineImagesGallery>` mount (lines 195-202).
- Remove the entire `InlineImagesGallery` component definition at the bottom of the file (lines 243-294).

The card becomes pure text (headline + format badge + source + score + approve/reject actions). Nothing else changes.

### 3g. frontend/src/components/approval/ContentDetailModal.tsx
- Remove the `RenderedImagesGallery` import (line 16).
- Remove the `<RenderedImagesGallery ... />` element that mounts after `renderForFormat(...)` (lines 93-98).
- Remove the now-unused local `bundle.rendered_images` / `bundle.created_at` access in that section (the modal still uses `bundle` for the content-type switch).
- In `renderForFormat` (around line 134), update the `case 'infographic'` to pass ONLY `draft` (no more `images` prop): `return <InfographicPreview draft={draft as Parameters<typeof InfographicPreview>[0]['draft']} />`.

### 3h. frontend/src/components/approval/__tests__/ContentDetailModal.test.tsx
Update any test that queries for `rendered_images`, `Rendered images` text, rerender button, `RenderedImagesGallery`, Dialog trigger for image preview, or `img` elements in infographic/quote renderings. Remove those assertions and replace with assertions that the three new text blocks (Suggested Headline / Key Facts / Image Prompt) render correctly when bundle.draft_content has the new shape.

### 3i. Verify
```bash
cd frontend && npm run test -- --run
cd frontend && npm run build
cd frontend && npx eslint src/
```

All three must pass. Any TypeScript error from a removed type import = fix before moving on.
  </action>
  <verify>
    <automated>cd /Users/matthewnelson/seva-mining/frontend && npm run test -- --run && npm run build && npx eslint src/</automated>
  </verify>
  <done>
    RenderedImagesGallery.tsx deleted. InfographicPreview and QuotePreview render three copy-buttoned text blocks when image_prompt present; render "Legacy format — regenerate" placeholder when absent. ContentSummaryCard is text-only (no img, no Dialog, no download, no useContentBundle). ContentDetailModal no longer mounts RenderedImagesGallery. All frontend tests green, build green, no ESLint errors. RenderedImage and RerenderResponse removed from frontend/src/api/types.ts.
  </done>
</task>

</tasks>

<verification>
Full-system validation after all three tasks complete:

```bash
# Backend (both services)
cd /Users/matthewnelson/seva-mining/scheduler && uv run ruff check . && uv run pytest tests/ -x
cd /Users/matthewnelson/seva-mining/backend && uv run ruff check . && uv run pytest tests/ -x

# Frontend
cd /Users/matthewnelson/seva-mining/frontend && npm run test -- --run && npm run build

# Dockerfile builds (local smoke — skip if no Docker on machine, Railway will build anyway)
cd /Users/matthewnelson/seva-mining/scheduler && docker build . --tag seva-scheduler-mfy-check

# Grep sweep — must return ZERO matches in production code
cd /Users/matthewnelson/seva-mining && \
  ! grep -rn -E "chart_renderer|ChartRendererClient|ChartSpec|BundleCharts|render_bundle_job|_enqueue_render_job_if_eligible" \
    scheduler/agents scheduler/models scheduler/worker.py scheduler/Dockerfile \
    backend/app frontend/src \
    --include='*.py' --include='*.ts' --include='*.tsx' --include='Dockerfile'

# Smoke: BRAND_PREAMBLE loads and has all required substrings
cd /Users/matthewnelson/seva-mining/scheduler && uv run python -c "
from agents.brand_preamble import BRAND_PREAMBLE
required = ['#F0ECE4', '#0C1B32', '#1E3A5F', '#4A7FA5', '#5A6B7A', '#D4AF37', '#D8D2C8',
            'DM Serif Display', 'Inter', 'SEVA MINING', '1200x675', 'HTML artifact']
missing = [s for s in required if s not in BRAND_PREAMBLE]
assert not missing, f'BRAND_PREAMBLE missing: {missing}'
assert len(BRAND_PREAMBLE) >= 200
print('BRAND_PREAMBLE OK:', len(BRAND_PREAMBLE), 'chars')
"
```

Post-deploy (Railway rebuild, manual ops check — record results in SUMMARY.md):
- Scheduler image size is smaller than the pre-rip image (report both sizes in the SUMMARY)
- Railway scheduler deploy SHA matches the merge commit
- Next content_agent run produces an infographic or quote bundle — inspect `draft_content` in the DB and confirm it contains `suggested_headline`, `data_facts`, `image_prompt` and the image_prompt starts with "You are building a Seva Mining editorial social asset"
- Open the dashboard content queue — a new infographic/quote card shows three copy buttons and NO images
- Click each Copy button — clipboard contains the expected content
- One old (pre-mfy) infographic/quote bundle still in the queue shows the "Legacy format — regenerate" placeholder instead of crashing
- `POST /content-bundles/{id}/rerender` returns 404 (route removed)
</verification>

<success_criteria>
- All 10 target files/directories deleted from disk and from git index (chart_renderer/, chart_renderer_client.py, image_render_agent.py, chart_spec.py x2, 5 test files).
- `scheduler/agents/brand_preamble.py` created with BRAND_PREAMBLE matching all 12 required substrings and >=200 chars.
- content_agent.py infographic AND quote paths emit `{suggested_headline, data_facts, image_prompt}`. `image_prompt` always starts with BRAND_PREAMBLE.
- `_enqueue_render_job_if_eligible`, `_RENDER_FORMATS`, and all 3 call sites deleted from content_agent.py.
- `scheduler/Dockerfile` is pure-Python (python:3.12-slim base, no Node, no npm, no font download, no `scheduler/`-prefixed COPY paths).
- `scheduler/worker.py` has no chart_renderer_client import or start/stop calls.
- `backend/app/routers/content_bundles.py` exposes ONLY GET. POST /rerender route removed. `RerenderResponse` and `RenderedImage` schemas removed.
- Frontend: `InfographicPreview.tsx` and `QuotePreview.tsx` render three copy-buttoned text blocks (Suggested Headline / Key Facts / Image Prompt); legacy bundles show the placeholder; no `<img>` tags rendered for these formats; ContentSummaryCard has no InlineImagesGallery; ContentDetailModal does not mount RenderedImagesGallery; RenderedImagesGallery.tsx deleted; RenderedImage and RerenderResponse removed from types.ts.
- `cd scheduler && uv run pytest tests/ -x` passes.
- `cd backend && uv run pytest tests/ -x` passes.
- `cd frontend && npm run test -- --run` passes.
- `cd frontend && npm run build` passes.
- `ruff check scheduler/ backend/` zero lint issues.
- `npx eslint src/` zero lint issues.
- Grep sweep confirms zero production-code references to deleted symbols.
</success_criteria>

<output>
After completion, create `.planning/quick/260420-mfy-pivot-infographic-quote-post-formats-off/260420-mfy-SUMMARY.md` with:
- Line-count delta (files deleted, lines removed, files added, lines added)
- Scheduler image size before vs after (if Docker build was run)
- Each of the three tasks' verify command output (tail)
- Any caller discovered during Task 1a grep sweep that was not in the expected list, and what was done about it
- Railway deploy SHA + post-deploy DB spot-check: one fresh bundle's draft_content dumped as JSON to confirm the new three-field shape shipped end-to-end
</output>
