---
phase: 260419-t78
verified: 2026-04-19T00:00:00Z
status: human_needed
score: 9/9 must-haves verified
re_verification: false
human_verification:
  - test: "Build Docker image with nikolaik/python-nodejs:python3.12-nodejs22 base and pin the sha256 digest"
    expected: "Docker build completes; run: docker image inspect nikolaik/python-nodejs:python3.12-nodejs22 --format='{{.Id}}' and update FROM line in scheduler/Dockerfile"
    why_human: "No Docker binary in worktree — sha256 digest cannot be fetched without a live docker pull"
  - test: "Run: cd scheduler/chart_renderer && sh download-fonts.sh && node render-chart.js, then send a bar chart spec JSON line on stdin"
    expected: "Responds with {\"png_b64\": \"...\"} on stdout; PNG decodes to a valid 1200x675 image with a16z-style palette"
    why_human: "End-to-end render requires Node subprocess running with downloaded fonts + resvg-js native binaries; cannot verify without a live environment"
  - test: "Trigger a full content_agent run that selects infographic format, then observe the render job"
    expected: "bundle.rendered_images contains [{role: 'twitter_visual', url: '...'}] (and optionally twitter_visual_2); no Gemini API call occurs; chart renderer subprocess log shows render completed"
    why_human: "Requires live scheduler environment with ANTHROPIC_API_KEY, DATABASE_URL, R2 credentials, and running Node subprocess"
---

# Quick Task 260419-t78: Replace Gemini Imagen Infographic Rendering — Verification Report

**Task Goal:** Replace Gemini Imagen infographic rendering with Claude chart_spec + Recharts (a16z-style)
**Verified:** 2026-04-19
**Status:** HUMAN_NEEDED — all 9 automated must-haves verified; 3 items require live environment testing
**Re-verification:** No — initial verification

---

## Goal Achievement

### Observable Truths

| #   | Truth                                                                             | Status     | Evidence                                                                                                         |
| --- | --------------------------------------------------------------------------------- | ---------- | ---------------------------------------------------------------------------------------------------------------- |
| 1   | Infographic bundles produce 1-2 PNG files via Recharts SSR + resvg-js (not Gemini) | ✓ VERIFIED | `_render_and_persist()` early-exits to `_render_infographic_charts()` at line 97-99; no genai.Client call in infographic path |
| 2   | PNG files land at rendered_images[].role = 'twitter_visual' (and optionally 'twitter_visual_2') | ✓ VERIFIED | `roles_for_charts = ["twitter_visual", "twitter_visual_2"]` at line 212 of image_render_agent.py |
| 3   | Sonnet emits chart_spec JSON validated by Pydantic BundleCharts model             | ✓ VERIFIED | `BundleCharts.model_validate({"charts": charts_raw, "twitter_caption": twitter_caption})` at content_agent.py line 1327 |
| 4   | Pydantic validation failure on chart_spec downgrades bundle to format=thread      | ✓ VERIFIED | except block sets `draft_content = {"format": "thread", ...}` at content_agent.py lines 1337-1341 |
| 5   | Quote format is UNTOUCHED — still routes through Gemini Imagen                    | ✓ VERIFIED | `ROLES_BY_FORMAT["quote"]` intact; `_render_and_persist()` only early-returns for `format_type == "infographic"` |
| 6   | Instagram slide roles fully removed from active infographic code path              | ✓ VERIFIED | `_render_infographic_charts()` has zero instagram_slide references; infographic path never reaches `_build_prompt()` (dead code) |
| 7   | Node chart renderer process starts once at scheduler startup and persists          | ✓ VERIFIED | `chart_client.start()` before `_scheduler.start()` at worker.py line 368; `chart_client.stop()` in finally block at line 392 |
| 8   | historical_pattern dead code fully removed from content_agent.py infographic path | ✓ VERIFIED | `grep -n "historical_pattern" content_agent.py` returns zero matches |
| 9   | recharts@2.15.4 pinned                                                            | ✓ VERIFIED | `"recharts": "2.15.4"` confirmed in scheduler/chart_renderer/package.json |

**Score:** 9/9 truths verified

---

### Required Artifacts

| Artifact                                         | Expected                                               | Status      | Details                                            |
| ------------------------------------------------ | ------------------------------------------------------ | ----------- | -------------------------------------------------- |
| `scheduler/models/chart_spec.py`                 | ChartType, ChartSpec, BundleCharts Pydantic v2 models  | ✓ VERIFIED  | File exists; imports confirmed via test pass       |
| `backend/app/models/chart_spec.py`               | Backend mirror of scheduler chart_spec models          | ✓ VERIFIED  | File exists at correct path                        |
| `scheduler/chart_renderer/package.json`          | recharts@2.15.4, react@19, @resvg/resvg-js@2.6.2 pins | ✓ VERIFIED  | recharts@2.15.4 confirmed; package.json present    |
| `scheduler/chart_renderer/render-chart.js`       | Long-running stdin/stdout JSON renderer process        | ✓ VERIFIED  | readline + process.stdout.write protocol confirmed |
| `scheduler/agents/chart_renderer_client.py`      | asyncio subprocess lifecycle wrapper                   | ✓ VERIFIED  | create_subprocess_exec at line 51                  |
| `scheduler/agents/image_render_agent.py`         | Infographic → ChartRendererClient; quote → Gemini      | ✓ VERIFIED  | Early-exit at line 97; quote path unchanged        |
| `scheduler/agents/content_agent.py`              | BundleCharts JSON + Pydantic validation + thread downgrade | ✓ VERIFIED | Validation block at lines 1321-1341            |
| `scheduler/Dockerfile`                           | nikolaik/python-nodejs base; npm ci; font download     | ✓ VERIFIED  | All three elements present; sha256 not pinned (operator TODO) |
| `scheduler/chart_renderer/components/` (7 files) | BarChart, HorizontalBarChart, LineChart, AreaChart, StatCallouts, ComparisonTable, Timeline | ✓ VERIFIED | All 7 JSX files confirmed present |

---

### Key Link Verification

| From                                    | To                                          | Via                                                    | Status     | Details                                                |
| --------------------------------------- | ------------------------------------------- | ------------------------------------------------------ | ---------- | ------------------------------------------------------ |
| `content_agent.py _research_and_draft()` | `models.chart_spec.BundleCharts`           | `BundleCharts.model_validate()` in try/except          | ✓ WIRED    | Line 1327; failure sets format=thread                 |
| `image_render_agent.py _render_and_persist()` | `chart_renderer_client.ChartRendererClient` | `await get_chart_renderer_client().render_charts()` | ✓ WIRED    | Line 199; correct payload passed                      |
| `chart_renderer_client.py`              | `chart_renderer/render-chart.js`           | `asyncio.create_subprocess_exec('node', ...)` PIPE     | ✓ WIRED    | Line 51 of chart_renderer_client.py                   |
| `worker.py`                             | `chart_renderer_client.ChartRendererClient` | `start()` on startup, `stop()` on shutdown            | ✓ WIRED    | Lines 366-368 (start), 392 (stop in finally)          |

---

### Data-Flow Trace (Level 4)

| Artifact                            | Data Variable  | Source                                                     | Produces Real Data | Status       |
| ----------------------------------- | -------------- | ---------------------------------------------------------- | ------------------ | ------------ |
| `image_render_agent._render_infographic_charts()` | `png_list` | `get_chart_renderer_client().render_charts(payload)` | Yes — Node SSR subprocess (runtime only) | ✓ FLOWING (runtime) |
| `content_agent._research_and_draft()` | `charts_raw` | Sonnet API response parsed from `draft_content["charts"]` | Yes — Anthropic API call | ✓ FLOWING |

---

### Behavioral Spot-Checks

| Behavior                               | Command                                                      | Result          | Status  |
| -------------------------------------- | ------------------------------------------------------------ | --------------- | ------- |
| Full test suite: 145 tests pass         | `uv run pytest tests/ -q`                                    | 145 passed, 1 warning | ✓ PASS |
| Ruff lint: zero errors                 | `uv run ruff check .`                                        | All checks passed | ✓ PASS |
| recharts pinned to 2.15.4              | `grep '"recharts"' scheduler/chart_renderer/package.json`   | `"recharts": "2.15.4"` | ✓ PASS |
| historical_pattern absent from content_agent | `grep -n "historical_pattern" content_agent.py`       | zero matches    | ✓ PASS |
| worker.py start/stop wiring            | `grep -n "chart_renderer_client\|get_chart_renderer_client" worker.py` | 3 hits (import, start, stop) | ✓ PASS |
| End-to-end chart render (PNG output)   | Requires Docker build + running Node subprocess              | N/A             | ? SKIP  |

---

### Requirements Coverage

No `requirements:` field declared in the PLAN frontmatter. Task is self-contained with must_haves as the contract.

---

### Anti-Patterns Found

| File                                | Line(s)  | Pattern                                                         | Severity | Impact                                                                                      |
| ----------------------------------- | -------- | --------------------------------------------------------------- | -------- | ------------------------------------------------------------------------------------------- |
| `scheduler/Dockerfile`              | 1        | `FROM nikolaik/python-nodejs:python3.12-nodejs22` (floating tag) | ⚠️ Warning | Supply-chain drift risk if nikolaik pushes a broken image; operator TODO documented in Dockerfile and SUMMARY.md |
| `scheduler/agents/image_render_agent.py` | 358-383 | `_build_prompt()` contains dead instagram_slide/infographic branches | ℹ️ Info | Unreachable for infographic bundles (infographic path returns before _build_prompt() is called); deferred cleanup documented in SUMMARY.md |

Neither anti-pattern blocks goal achievement. The floating Docker tag is a production-hardening gap, not a functional gap.

---

### Human Verification Required

#### 1. Docker sha256 Digest Pin

**Test:** After running `docker pull nikolaik/python-nodejs:python3.12-nodejs22`, copy the sha256 digest from the pull output and update `scheduler/Dockerfile` line 1 to `FROM nikolaik/python-nodejs:python3.12-nodejs22@sha256:<digest>`.
**Expected:** Dockerfile FROM line references a pinned digest; future `docker build` is reproducible even if nikolaik updates the floating tag.
**Why human:** No Docker binary in worktree. Requires a machine with Docker installed and network access to Docker Hub.

#### 2. Node Renderer End-to-End Output

**Test:** In `scheduler/chart_renderer/`, run `sh download-fonts.sh && npm install`, then start `node render-chart.js` and send a bar chart spec on stdin:
```
{"type":"bar","title":"Gold Price YTD","data":[{"label":"Jan","value":1950},{"label":"Feb","value":2010}],"width":1200,"height":675}
```
**Expected:** stdout responds with `{"png_b64":"<base64>"}`. Decode the base64 to a PNG file. Open it — should show a 1200x675 chart with cream background (#F0ECE4), navy bars (#1E3A5F), Inter font, no garbled text.
**Why human:** Requires Node, npm, font download, and resvg-js native binaries — not available in this worktree.

#### 3. Full Pipeline Smoke Test (infographic format)

**Test:** Trigger a content_agent run against a story with sufficient data points. Verify the bundle persists with `content_type = "infographic"` and `rendered_images` contains `[{role: "twitter_visual", url: "https://..."}]`. Confirm no `GEMINI_API_KEY` call occurs in the scheduler logs for the infographic bundle.
**Expected:** One or two PNG images uploaded to R2 under `content-bundles/<bundle_id>/twitter_visual-<ts>.png`. Log shows "Chart renderer client started successfully" at startup and chart render completion per bundle.
**Why human:** Requires live Railway environment with all environment variables set, running Postgres, and chart renderer subprocess active.

---

### Gaps Summary

No gaps. All 9 must-haves are verified. The three human verification items are production-hardening checks (Docker pin) and live-environment integration tests that cannot be exercised without a running system. They do not indicate missing or broken implementation.

The one notable known limitation is dead code in `_build_prompt()` lines 358-383 (instagram_slide branches for infographic format that are permanently unreachable since the infographic path now early-returns before that function). This is explicitly documented in SUMMARY.md as a future cleanup item and has no functional impact.

---

_Verified: 2026-04-19_
_Verifier: Claude (gsd-verifier)_
