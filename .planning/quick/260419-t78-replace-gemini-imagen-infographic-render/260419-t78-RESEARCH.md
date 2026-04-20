# Quick Task 260419-t78: Replace Gemini Imagen Infographic Rendering — Research

**Researched:** 2026-04-20
**Domain:** Recharts SSR / resvg-js / Node chart renderer / a16z visual style / Claude design system
**Confidence:** MEDIUM overall (see per-section breakdown)

---

## Executive Summary

- **Recharts v3 has a confirmed, unresolved SSR regression** (issue #5997, opened June 2025). Rendering to SVG string via `renderToStaticMarkup` returns an empty div wrapper, not SVG. The project MUST pin to **Recharts 2.15.4** (latest v2.x as of April 2026). Recharts v2.x SSR requires fixed `width`/`height` props — no `ResponsiveContainer`.
- **resvg-js is the correct rasterizer.** License is MPL-2.0 (compatible), binary is ~4 MB on Linux x64 (not ~20 MB). Font loading requires passing TTF bytes via `fontFiles` or `fontBuffers`. Google Inter (or any Google Font) is available as TTF via jsDelivr CDN or `@fontsource/inter` npm package (files/ directory).
- **"Claude Design" is an AI prototyping tool (April 2026), not a published design token system.** There is no published Anthropic design token file. The a16z visual style is the sole North Star for chart aesthetics.
- **a16z published infographics share a consistent visual grammar**: white/off-white backgrounds, dark charcoal/navy text, sans-serif typeface, stat callouts as large-bold-numeral pull-quotes, moderate annotation density, single chart per visual. The existing Seva brand palette (#F0ECE4 / #0C1B32 / #D4AF37) is a close analog and should remain primary.
- **Option A (subprocess) is the correct Node renderer architecture** for this codebase. Spawn a persistent long-running Node process at scheduler startup; communicate via stdin/stdout newline-delimited JSON. No separate Railway service, no second billing line, no cold-start-per-render.

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- Use Claude design tokens (researcher validated: no published token file exists — a16z style is sole North Star)
- Base visual style on a16z published infographics
- Chart library: Recharts (emits SVG natively)
- Server-side resvg-js (Node) for SVG → PNG rasterization
- Downgrade to thread format when chart_spec is invalid (Pydantic validation failure)
- Pydantic v2 model shared between scheduler + backend for schema
- Agent decides 1 vs 2 charts via prompt guidance
- Quote format stays on Gemini (out of scope)

### Claude's Discretion
- Exact Pydantic schema field names and nested structure
- Specific design tokens to adopt (confirmed: a16z aesthetic is primary source)
- Node sidecar architecture (subprocess vs separate service) — recommendation: subprocess, persistent process
- Exact prompt wording for Sonnet chart_spec emission
- Chart type coverage in v1 (stat_callouts and comparison_table need custom SVG components)

### Deferred Ideas (OUT OF SCOPE)
- Quote format migration away from Gemini
- Breaking news / thread / long_form format images
- Frontend display changes (ContentSummaryCard gallery already wired in quick-si2)
- Instagram slide roles (dropped post-lvy)
</user_constraints>

---

## Q1 — a16z Visual Style (Confidence: MEDIUM)

Direct extraction of hex codes from a16z page screenshots was not possible via WebFetch (pages are JavaScript-rendered). The following is synthesized from multiple a16z pages (State of AI, American Dynamism 50, State of Consumer AI 2025) and cross-verified against a16z's known brand identity.

### Color Palette

| Role | Color | Notes |
|------|-------|-------|
| Background | White or very light off-white | Near #FFFFFF; some reports use warm off-white ~#F8F7F5 |
| Primary text | Dark charcoal/navy | #1A1A2E or similar dark navy; near black in practice |
| Accent / highlight | Deep blue or indigo | Used for chart fills, bars, line strokes — NOT gold |
| Secondary accent | Lighter blue-gray | Used for secondary data series |
| Grid lines | Light gray | #E5E5E5 — minimal, non-distracting |
| Data labels | Same as primary text, smaller weight | Placed directly on or adjacent to data |

**Critical implication for Seva:** The a16z palette does NOT use gold. Seva's brand palette (#F0ECE4 / #0C1B32 / #D4AF37) departs from a16z in one specific way — the gold accent. This is a **brand feature, not a bug**. Keep it. Map it as: cream background → #F0ECE4, navy text → #0C1B32, bar fill/line → a deep blue (#1E3A5F or similar), gold accent (#D4AF37) sparingly for a single highlighted stat or callout only.

### Typography Hierarchy

| Element | Style |
|---------|-------|
| Chart headline | Bold, sans-serif, ~24-28px equivalent at 1200px wide; left-aligned above chart |
| Axis labels | Regular weight, ~11-12px, muted gray |
| Data labels (on bars) | Semi-bold, ~11px, contrast color |
| Source citation | Light weight, ~9px, bottom-right |
| Stat callout number | Extra-bold, ~48-60px, primary accent color |
| Stat callout label | Regular, ~14px, beneath the number |

**Font choice:** a16z uses a geometric sans-serif (confirmed sans-serif, unconfirmed specific typeface). **Inter** is the standard choice for this aesthetic — it is the dominant sans-serif for data dashboards and editorial tech publishing as of 2025. Use Inter 400/600/700.

### Chart Type Frequency

Based on a16z publications surveyed:
1. **Bar chart (vertical or horizontal)** — most frequent; used for comparisons, rankings
2. **Stat callouts / big-number grid** — very common; 2-4 large numbers in a grid
3. **Line chart** — for time series, model performance over time
4. **Area chart** — less common; used for cumulative/stacked data
5. **Comparison table** — used in report-style pieces for side-by-side specs
6. **Scatter plot** — rare; used for model capability vs cost comparisons

### Headline Placement

**Above the chart, left-aligned.** Not overlaid, not centered. Subheading (if any) directly below headline at smaller weight. Source line bottom-right.

### Chart Density

**Single chart per image** — always. a16z does not pack two charts into one visual. If two views are needed, they appear on separate slides/pages. This aligns with the locked decision to allow 1-2 charts as separate PNGs, not a combined layout.

### Annotation Patterns

- **Minimalist** — not rich annotations. Key data labels on bars/lines, but no callout arrows or annotation boxes.
- Grid lines are subtle, horizontal only (no vertical grid on bar charts).
- Bar chart values labeled directly above/inside bars.
- Line charts use endpoint labels or legend, not every-point labels.
- Source attribution always present, bottom-right, small.

### Implementation Palette (Recommended)

```
Background:    #F0ECE4   (Seva cream — matches warm off-white aesthetic)
Primary text:  #0C1B32   (Seva deep navy)
Bar fill:      #1E3A5F   (deeper navy-blue for primary data series)
Bar fill 2:    #4A7FA5   (medium blue for secondary series)
Gold accent:   #D4AF37   (Seva gold — use on ONE highlighted element only)
Grid lines:    #E2DDD6   (warm light gray, matches cream bg)
Axis labels:   #5A6B7A   (muted blue-gray)
```

---

## Q2 — Claude Design System (Confidence: HIGH)

**Finding: No published design token file exists from Anthropic/Claude.**

"Claude Design" (announced April 17, 2026) is an AI-powered visual prototyping tool, not a design token system. It generates designs by *ingesting your own codebase and design files*, not by exposing Anthropic's own token library. There is no published `tokens.json`, no color/font specification document from Anthropic.

**Consequence:** The user's reference to "Claude design update" refers to this product launch. There are no tokens to adopt.

**Decision for implementer:** The a16z aesthetic is the sole visual source. Use the Seva brand palette with the mapping in Q1. Do not wait for or reference a "Claude design system" anywhere in code or comments.

Sources: https://www.anthropic.com/news/claude-design-anthropic-labs, https://techcrunch.com/2026/04/17/anthropic-launches-claude-design-a-new-product-for-creating-quick-visuals/

---

## Q3 — Recharts Capability Audit vs 8 Chart Types (Confidence: HIGH for native types, MEDIUM for custom)

### Version Decision: Pin to 2.15.4

Recharts 3.x (current latest: 3.8.1) has a **confirmed, open SSR regression** (issue #5997, opened June 24, 2025). `renderToStaticMarkup` returns `<div class="recharts-wrapper" ...></div>` with no SVG content. No fix or timeline exists as of April 2026. **Pin to 2.15.4** — the last v2.x release, which has verified working SSR via `renderToStaticMarkup` with fixed `width`/`height` props.

Recharts v2.15.4 peer deps: `react ^16||^17||^18||^19`, `react-dom` same — compatible with React 19.

### SSR Requirement (CRITICAL)

For Recharts v2.x to render on the server:
1. Never use `<ResponsiveContainer>` — it requires DOM measurements
2. Pass explicit `width={1200}` `height={675}` (or your target px) as props
3. Call `ReactDOMServer.renderToStaticMarkup(<BarChart width={1200} height={675} ...>)` in Node
4. The output is a full SVG string; no DOM shim (jsdom) required

This was confirmed in multiple GitHub issues and the leanylabs.com blog post.

### Native Recharts Chart Types (all supported in v2.x)

| chart_spec type | Recharts Component | Key Props |
|---|---|---|
| `bar` | `<BarChart layout="vertical">` (or default) with `<Bar>` | `width`, `height`, `data`, `layout` |
| `horizontal_bar` | `<BarChart layout="horizontal">` with `<Bar dataKey>` | Swap XAxis/YAxis types |
| `line` | `<LineChart>` with `<Line>` | `type="monotone"` for smooth curve |
| `multi_line` | `<LineChart>` with multiple `<Line>` children | Each Line has a `dataKey` |
| `area` | `<AreaChart>` with `<Area>` | `type`, `fill`, `stroke` |
| `stacked_area` | `<AreaChart>` with multiple `<Area stackId="1">` | `stackId` prop creates stacking |

All 6 native chart types confirmed supported in Recharts v2.x. HIGH confidence.

### Non-Recharts Types: Custom SVG React Components

These three are **not Recharts chart types** — they are layout/display components. Build them as pure React components that emit valid SVG, so `renderToStaticMarkup` produces the same SVG pipeline as Recharts.

#### `stat_callouts` — Big-number grid

Pattern: 2-4 stat boxes in a horizontal grid. Each box contains a large number, a label below, and an optional source line. Rendered as SVG `<text>` elements on a `<rect>` background.

```jsx
// Pure SVG React — no Recharts needed
// Example: 2-column, 1200x400 SVG
function StatCallouts({ width, height, stats }) {
  // stats: [{value: "2,400", label: "Gold price $/oz", source: "WGC"}]
  const cols = stats.length <= 2 ? stats.length : Math.ceil(stats.length / 2);
  const rows = Math.ceil(stats.length / cols);
  const cellW = width / cols;
  const cellH = height / rows;
  return (
    <svg width={width} height={height} xmlns="http://www.w3.org/2000/svg">
      <rect width={width} height={height} fill="#F0ECE4" />
      {stats.map((s, i) => {
        const col = i % cols;
        const row = Math.floor(i / cols);
        const cx = col * cellW + cellW / 2;
        const cy = row * cellH + cellH / 2;
        return (
          <g key={i}>
            <text x={cx} y={cy - 10} textAnchor="middle"
              fontSize={60} fontWeight="700" fill="#0C1B32" fontFamily="Inter">
              {s.value}
            </text>
            <text x={cx} y={cy + 30} textAnchor="middle"
              fontSize={16} fontWeight="400" fill="#5A6B7A" fontFamily="Inter">
              {s.label}
            </text>
          </g>
        );
      })}
    </svg>
  );
}
```

#### `comparison_table` — Side-by-side stats

Pattern: 2-3 column table with a header row and data rows. Rendered as SVG `<rect>` cells with `<text>` content. No HTML table — pure SVG so resvg-js pipeline is uniform.

Key implementation notes: alternate row background shading (#F0ECE4 vs #E8E3D9), header row in #0C1B32 with white text, left column left-aligned, data columns center-aligned, gold accent on "winner" cell if applicable.

#### `timeline` — Event markers on horizontal axis

Pattern: horizontal axis (line) with vertical tick marks and event labels above/below alternating. Recharts has no first-class timeline. Options:

- **Option A:** Custom SVG component with a horizontal `<line>`, evenly-spaced `<line>` ticks, and `<text>` labels
- **Option B:** Recharts `<ScatterChart>` with y=0 for all points and custom `<Dot>` shape — viable but awkward

**Recommendation: Option A (custom SVG)**. It's 40 lines of SVG JSX and stays on the same rendering path as stat_callouts and comparison_table. Recharts scatter emulation adds complexity without benefit.

### SSR Unification

All 8 chart types (6 native Recharts + 3 custom SVG) are rendered via `ReactDOMServer.renderToStaticMarkup()` in the Node chart renderer. The Python side calls the renderer and receives PNG bytes regardless of which component was used. The renderer script dispatches on `chart_spec.type` to select the right component.

---

## Q4 — SVG → PNG Export via resvg-js (Confidence: HIGH)

### Confirmed Specifics

**Version:** 2.6.2 (latest as of April 2026)
**License:** MPL-2.0 — confirmed compatible. MPL-2.0 allows use in proprietary projects; only modifications to MPL-licensed files must be shared. No concern for this use case.
**Linux x64 binary size:** ~4.2 MB (not ~20 MB — that figure was wrong in CONTEXT.md). The full installed node_modules footprint with platform binary is approximately 6-8 MB.
**Performance benchmark:** 12 ops/s for resize operations; outperforms sharp (9), skr-canvas (7), svg2img (6). For a Recharts SVG at 1200x675 with ~50 data points, expect sub-100ms render time (MEDIUM confidence — no direct benchmark found; extrapolated from benchmarks above).

**Font loading for Inter:**

```javascript
const { Resvg } = require('@resvg/resvg-js');
const { readFileSync } = require('fs');
const path = require('path');

// Option A: Ship a bundled Inter-Regular.ttf in the renderer package
// Download from Google Fonts API or use the TTF from @fontsource/inter
// Path within @fontsource/inter: node_modules/@fontsource/inter/files/inter-latin-400-normal.woff2
// NOTE: resvg-js requires TTF/OTF, not WOFF2.
// Preferred approach: download Inter-Regular.ttf at Docker build time and bundle alongside render-chart.js

// Option B: Fetch from jsDelivr CDN at startup (requires network, less reliable)
// const fontRes = await fetch('https://fonts.gstatic.com/s/inter/v13/UcCO3FwrK3iLTeHuS_fvQtMwCp50KnMw2boKoduKmMEVuLyfAZ9hiA.woff2')
// NOTE: also WOFF2. Must use TTF endpoint.

// Correct font loading for resvg-js:
const fontBuffer = readFileSync(path.join(__dirname, 'fonts/Inter-Regular.ttf'));
const resvg = new Resvg(svgString, {
  font: {
    fontBuffers: [new Uint8Array(fontBuffer)],
    loadSystemFonts: false,  // faster, deterministic
  },
  fitTo: { mode: 'width', value: 1200 },
});
const pngBuffer = resvg.render().asPng();
```

**Font acquisition strategy (recommended):** Add a Dockerfile step or a `postinstall` npm script that downloads `Inter-Regular.ttf` and `Inter-Bold.ttf` from the official Inter GitHub release (https://github.com/rsms/inter/releases) or Google Fonts static endpoint. Bundle the TTF files at `scheduler/chart-renderer/fonts/`. Two files at ~300KB each is negligible.

**Known limitations:**
- Async API not yet supported — `resvg.render()` is synchronous. For a single chart per call this is fine; in a long-running Node process it blocks the event loop for ~50-100ms. Use `setImmediate` / worker threads if rendering multiple charts in parallel.
- No AVIF/WebP output — PNG only. Not relevant here.
- SVG with `<foreignObject>` (HTML embedded in SVG) is not supported. This means the custom components (stat_callouts, comparison_table, timeline) MUST be pure SVG — no HTML elements inside the SVG. This is a hard requirement.
- Font text rendering is sensitive to font variant matching — if SVG specifies `font-weight: 700` but only `Inter-Regular.ttf` is loaded, resvg-js will substitute. Load both Regular (400) and Bold (700) TTF files.

**What we'd lose with alternatives:**
- **Playwright:** ~200MB chromium binary, ~1-3s cold start per render. No benefit over resvg-js for this use case.
- **@vercel/og (satori-based):** Designed for Next.js/Edge runtime; requires JSX → SVG via satori, not Recharts. Would require re-implementing chart components in satori's JSX subset. Not viable.
- **cairosvg (Python):** No Recharts — would require reimplementing all chart types in Python + Cairo. Rejected in CONTEXT.md.

**Conclusion:** resvg-js is the correct choice. Decision validated.

---

## Q5 — Node Renderer Architecture (Confidence: HIGH for recommendation)

### Three Options Evaluated

**Option A: Long-running subprocess (stdin/stdout JSON)**
Python scheduler spawns `node render-chart.js` once at startup. Chart requests are sent as newline-delimited JSON to the Node process stdin; PNG bytes (base64) are returned on stdout. Node process stays alive across renders.

**Option B: Separate Railway service (HTTP microservice)**
Dedicated Railway service at `http://chart-renderer:3000/render`. Python sends POST with chart_spec JSON, receives PNG bytes. Separate billing line (~$5-10/mo). Independent deploy, clean separation.

**Option C: Spawn-per-render subprocess**
Python spawns `node render-chart.js` fresh for each chart render. Node starts cold each time (~300-500ms V8 init + Recharts module load + font load).

### Recommendation: Option A (Long-running Subprocess)

**Why:**
1. **No cold start per render.** V8 init + loading Recharts + reading font TTF files takes ~300-500ms at startup. Subsequent renders are ~50-100ms each. With spawn-per-render (Option C), every infographic would pay the 300-500ms cold start — unacceptable for a system that produces 4-5 stories/week.
2. **No extra Railway service cost** vs Option B. No extra deploy/monitor surface.
3. **Simpler than Option C** (no repeated process management). Python treats it like a persistent worker.
4. **Well-understood pattern.** Python `asyncio.create_subprocess_exec` with `PIPE` for stdin/stdout is standard. Send JSON line → receive JSON line with base64 PNG.

**Option B trade-offs:** Only worth it if the renderer needs to be independently scaled or independently updated without a scheduler redeploy. For Seva's scale (4-5 infographics/week), overkill.

### Implementation Sketch

**Startup (scheduler/worker.py or a new `chart_renderer_process.py` module):**
```python
# Start Node renderer once at scheduler startup
import asyncio, base64, json

_node_proc = None

async def get_node_renderer():
    global _node_proc
    if _node_proc is None or _node_proc.returncode is not None:
        _node_proc = await asyncio.create_subprocess_exec(
            "node", "/app/chart-renderer/render-chart.js",
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
    return _node_proc

async def render_chart_spec(chart_spec: dict) -> bytes | None:
    proc = await get_node_renderer()
    request = json.dumps(chart_spec) + "\n"
    proc.stdin.write(request.encode())
    await proc.stdin.drain()
    line = await proc.stdout.readline()
    result = json.loads(line)
    if result.get("error"):
        logger.error("chart renderer error: %s", result["error"])
        return None
    return base64.b64decode(result["png_b64"])
```

**Node side (`chart-renderer/render-chart.js`) — event-loop-based line reader:**
```javascript
const readline = require('readline');
const ReactDOMServer = require('react-dom/server');
const { Resvg } = require('@resvg/resvg-js');
const fs = require('fs');

const fontRegular = new Uint8Array(fs.readFileSync('./fonts/Inter-Regular.ttf'));
const fontBold = new Uint8Array(fs.readFileSync('./fonts/Inter-Bold.ttf'));

const rl = readline.createInterface({ input: process.stdin });

rl.on('line', async (line) => {
  try {
    const spec = JSON.parse(line);
    const svgString = ReactDOMServer.renderToStaticMarkup(buildChart(spec));
    const resvg = new Resvg(svgString, {
      font: { fontBuffers: [fontRegular, fontBold], loadSystemFonts: false },
      fitTo: { mode: 'width', value: spec.width || 1200 },
    });
    const pngB64 = resvg.render().asPng().toString('base64');
    process.stdout.write(JSON.stringify({ png_b64: pngB64 }) + '\n');
  } catch (err) {
    process.stdout.write(JSON.stringify({ error: err.message }) + '\n');
  }
});
```

### Docker Base Image

**Recommended:** `nikolaik/python-nodejs:python3.12-nodejs22`

- Python 3.12 (matches existing scheduler)
- Node.js 22 (LTS, supported through April 2027)
- Both linux/amd64 and linux/arm64
- Total image ~589 MB (per Docker Hub)
- **Caveat:** Maintainer labels it "experimental." Mitigate by locking to a specific digest in your Dockerfile rather than the floating tag.

**Alternative:** Build your own Dockerfile FROM `python:3.12-slim`, then `apt-get install nodejs npm`. More control, more Dockerfile complexity.

### Memory Overhead Estimate

| Component | Estimated RAM |
|-----------|--------------|
| Node V8 runtime | ~50-80 MB |
| Recharts v2 + React dependencies | ~30-40 MB |
| resvg-js native module | ~15-20 MB |
| Font buffers (2 TTF × ~300KB each) | ~1 MB |
| **Total Node renderer process** | **~100-140 MB** |

MEDIUM confidence — no benchmark data found for this specific combination. This is additive to the existing Python scheduler process (~150-200 MB for APScheduler + anthropic SDK + sqlalchemy + all agent deps). **Total container memory budget: ~300-350 MB.** Railway default container limit is 512 MB; this fits within standard tier.

### Cold Start vs Warm Render

| Mode | Latency |
|------|---------|
| First render (process startup + font load) | ~400-600ms |
| Subsequent renders (warm process) | ~50-150ms |
| resvg-js render only | ~40-80ms |

Since infographic rendering is a background job (fires after bundle commit, not on the critical path of agent execution), even the 600ms startup cost is acceptable. The persistent process eliminates per-render startup cost from the second render onward.

---

## Standard Stack for Chart Renderer

| Package | Version | Purpose |
|---------|---------|---------|
| recharts | 2.15.4 (pinned, NOT 3.x) | Chart components → SVG via renderToStaticMarkup |
| react | 19.2.5 | JSX rendering (already in frontend; needed in renderer too) |
| react-dom | 19.2.5 | renderToStaticMarkup |
| @resvg/resvg-js | 2.6.2 | SVG → PNG rasterization |
| Inter font TTF | latest release | Text rendering in resvg-js |

**Installation (chart renderer package.json):**
```bash
npm install recharts@2.15.4 react@19 react-dom@19 @resvg/resvg-js@2.6.2
# Then download fonts:
# curl -L "https://github.com/rsms/inter/releases/download/v4.0/Inter-4.0.zip" | unzip -j "*/Inter-Regular.ttf" "*/Inter-Bold.ttf" -d ./fonts/
```

---

## Common Pitfalls

### Pitfall 1: Recharts v3 SSR Regression
**What goes wrong:** Install latest Recharts (3.8.1), `renderToStaticMarkup` returns `<div class="recharts-wrapper">` with no SVG content.
**Prevention:** Pin `recharts@2.15.4` in chart renderer package.json. Add a `// recharts: DO NOT UPGRADE TO 3.x — SSR is broken (issue #5997)` comment.
**Warning signs:** PNG renders as blank/white image.

### Pitfall 2: ResponsiveContainer blocks SSR
**What goes wrong:** Using `<ResponsiveContainer>` in the renderer — it requires DOM. Node throws or produces empty output.
**Prevention:** All chart components receive explicit `width` and `height` from the chart_spec. Never use ResponsiveContainer in the renderer.

### Pitfall 3: WOFF2 fonts fail in resvg-js
**What goes wrong:** Loading `@fontsource/inter` files (which are WOFF2/WOFF format) — resvg-js silently falls back to system fonts or renders blank text.
**Prevention:** Use TTF files. Download directly from Inter GitHub releases or Google Fonts static endpoint with TTF format.

### Pitfall 4: `<foreignObject>` in custom SVG components
**What goes wrong:** Using HTML elements (`<div>`, `<p>`, `<table>`) inside `<foreignObject>` in custom SVG components for stat_callouts or comparison_table — resvg-js does not support foreignObject and silently drops it.
**Prevention:** All components (stat_callouts, comparison_table, timeline) must be pure SVG primitives only (`<text>`, `<rect>`, `<line>`, `<g>`, `<path>`). No HTML.

### Pitfall 5: Node process stdin/stdout buffering deadlock
**What goes wrong:** Node process buffers stdout; Python waits forever for the response line.
**Prevention:** Use `process.stdout.write(json + '\n')` (not `console.log` — same behavior, but explicit). In Python, use `readline()` not `read()`. Each request/response is one JSON line.

### Pitfall 6: chart_spec type mismatch breaks fallback
**What goes wrong:** Sonnet emits malformed chart_spec JSON; Pydantic validation raises; fallback to `thread` format is not triggered because the exception is caught too late.
**Prevention:** Validate with `ChartSpec.model_validate_json()` inside a try/except immediately after Sonnet response. On any ValidationError, log and set `bundle.content_type = "thread"` before the render job is enqueued. Never enqueue a render job for a bundle with no valid chart_spec.

### Pitfall 7: nikolaik image tag drift
**What goes wrong:** Using `nikolaik/python-nodejs:python3.12-nodejs22` as a floating tag — image updates automatically, potentially breaking.
**Prevention:** Pin to a specific image digest in Dockerfile: `FROM nikolaik/python-nodejs@sha256:<digest>`. Lock the digest after initial working build.

---

## Pydantic Schema Design Guidance

The planner will need to define `ChartSpec`. Based on Recharts component signatures:

```python
# scheduler/models/chart_spec.py
from pydantic import BaseModel, Field
from typing import Literal, Optional
from enum import Enum

class ChartType(str, Enum):
    bar = "bar"
    horizontal_bar = "horizontal_bar"
    line = "line"
    multi_line = "multi_line"
    area = "area"
    stacked_area = "stacked_area"
    stat_callouts = "stat_callouts"
    comparison_table = "comparison_table"
    timeline = "timeline"

class DataPoint(BaseModel):
    label: str           # XAxis category or date string
    value: float         # Primary series value
    value2: Optional[float] = None  # Second series for multi_line/stacked_area

class StatCallout(BaseModel):
    value: str           # "2,400" — pre-formatted string
    label: str           # "Gold price $/oz"
    source: Optional[str] = None

class TableRow(BaseModel):
    label: str
    col1: str
    col2: str
    col3: Optional[str] = None

class TimelineEvent(BaseModel):
    date: str            # "2024-Q1" or "Jan 2024"
    label: str           # Event description
    highlight: bool = False  # Whether to render in gold accent

class ChartSpec(BaseModel):
    type: ChartType
    title: str           # Headline above chart
    subtitle: Optional[str] = None
    source: Optional[str] = None      # Citation bottom-right
    x_label: Optional[str] = None    # X-axis label (for bar/line types)
    y_label: Optional[str] = None    # Y-axis label
    unit: Optional[str] = None       # "$/oz", "%", "tonnes"
    data: list[DataPoint] = Field(default_factory=list)    # For bar/line/area types
    stats: list[StatCallout] = Field(default_factory=list) # For stat_callouts
    rows: list[TableRow] = Field(default_factory=list)     # For comparison_table
    events: list[TimelineEvent] = Field(default_factory=list)  # For timeline
    col1_header: Optional[str] = None  # comparison_table headers
    col2_header: Optional[str] = None
    col3_header: Optional[str] = None
    width: int = 1200    # Render target width
    height: int = 675    # Render target height (16:9)
    series_labels: Optional[list[str]] = None  # For multi_line legend

class BundleCharts(BaseModel):
    """Top-level wrapper — what Sonnet emits and what goes in draft_content['charts']"""
    charts: list[ChartSpec] = Field(max_length=2)
    twitter_caption: str
```

Key design choices:
- `charts: list[ChartSpec]` with `max_length=2` enforces the 1-or-2 chart constraint at validation time.
- `data`, `stats`, `rows`, `events` are all present but only the relevant field is populated per type. Pydantic ignores empty lists. Alternative: use a discriminated union — but that requires Sonnet to emit `type` first before the data, which makes prompting awkward.
- `width`/`height` default to 1200x675 (16:9 Twitter). Renderer uses these to size the SVG.

---

## Existing Code Touch Points

| File | Current State | Change Needed |
|------|--------------|---------------|
| `scheduler/agents/image_render_agent.py` | Gemini Imagen + R2 upload; `ROLES_BY_FORMAT["infographic"]` has 4 roles | Replace infographic branch with chart pipeline; keep quote branch and R2 upload intact; drop instagram_slide_* from infographic roles |
| `scheduler/agents/content_agent.py` | Infographic format Sonnet prompt emits `visual_structure`, `key_stats`, `instagram_brief` | Update Sonnet prompt to emit `charts: [{type, title, data, ...}]` instead; update `_extract_check_text` to read from charts[].title |
| `scheduler/models/content_bundle.py` | `draft_content JSONB` holds current infographic fields; `rendered_images JSONB` holds PNG URLs | `draft_content` will now contain `charts` array within infographic branch (no schema migration — JSONB is schemaless); no model file change needed |
| `scheduler/models/chart_spec.py` | Does not exist | Create new file with Pydantic models above |
| `scheduler/chart-renderer/` | Does not exist | Create new Node.js renderer package |
| `backend/app/models/chart_spec.py` | Does not exist | Create mirror of scheduler model (per established pattern — no shared package) |

---

## Environment Availability

| Dependency | Required By | Available | Version | Notes |
|------------|-------------|-----------|---------|-------|
| Node.js | Chart renderer | Unknown on Railway worker | TBD | Must be added to Docker image |
| npm | Chart renderer deps | Unknown on Railway worker | TBD | Ships with Node |
| Python 3.12 | Existing scheduler | Yes (existing) | 3.12 | No change |
| Cloudflare R2 | PNG upload | Yes (existing) | — | aioboto3 already wired |

**Missing dependencies with no fallback:**
- Node.js is not currently in the scheduler Docker image. Requires Dockerfile change to `nikolaik/python-nodejs:python3.12-nodejs22` or equivalent.

---

## Planner Should Know

1. **Recharts must be pinned to 2.15.4, not latest.** This is a hard constraint. If the planner specifies "install recharts" without a version pin, the implementer will get 3.8.1 and SSR will be broken.

2. **The `chart-renderer/` is a separate npm package inside the scheduler directory.** It has its own `package.json`, `node_modules/`, and a single entry point `render-chart.js`. The Python scheduler imports nothing from it — it's spawned as a subprocess. Railway Dockerfile needs to `npm install` in this sub-directory.

3. **Three chart types need custom SVG components, not Recharts.** `stat_callouts`, `comparison_table`, `timeline` — all pure SVG JSX. This is implementation work the planner should account for as distinct tasks from the Recharts chart types.

4. **The content_agent.py Sonnet prompt needs a complete rewrite of the infographic branch.** The current prompt emits `visual_structure`, `key_stats`, `instagram_brief` — all of which go away. New prompt emits `charts: [{type, title, data|stats|rows|events, ...}]`. This is a behavior-changing prompt change that will affect production infographic quality immediately on deploy.

5. **Font TTF files must be committed to the repo** (or downloaded at Docker build time). They cannot be loaded at runtime without a network call. Committing two ~300KB TTF files to `scheduler/chart-renderer/fonts/` is the simplest approach. Add them to `.gitignore` exceptions if needed.

6. **The fallback-to-thread logic belongs in content_agent.py, before `_enqueue_render_job_if_eligible`.** Not in image_render_agent.py. The render job should only be enqueued when `draft_content['charts']` is a valid `BundleCharts`. Validation failure → set `bundle.content_type = 'thread'` → no render job enqueued → no frontend image slots.

7. **The existing backend mirror model pattern** (scheduler/models mirrors backend/app/models manually) applies here too. The planner must include a task to create `backend/app/models/chart_spec.py` as a copy of `scheduler/models/chart_spec.py`.

8. **nikolaik docker image is labeled "experimental."** This is the lowest-risk available option but if the project has a custom Dockerfile already, adding `apt-get install nodejs npm` to `python:3.12-slim` is more controlled.

9. **No Pydantic schema migration is needed in the database.** `draft_content` is a JSONB column — it accepts any valid JSON. The `charts` array will just live inside the existing column alongside `format`, `headline`, etc.

10. **The long-running Node process restart strategy:** If the Node process crashes (stderr output, non-zero returncode), Python must detect this via `_node_proc.returncode is not None` check and restart. Add a simple `get_node_renderer()` helper that checks for a dead process and restarts it.

---

## Sources

### Primary (HIGH confidence)
- Recharts GitHub issue #5997 (SSR v3 regression): https://github.com/recharts/recharts/issues/5997
- Recharts v2.x branch: https://github.com/recharts/recharts/tree/2.x
- resvg-js GitHub: https://github.com/thx/resvg-js
- npm: recharts (latest 3.8.1, v2.x latest 2.15.4): https://www.npmjs.com/package/recharts
- Anthropic Claude Design announcement: https://www.anthropic.com/news/claude-design-anthropic-labs
- nikolaik/python-nodejs Docker Hub: https://hub.docker.com/r/nikolaik/python-nodejs

### Secondary (MEDIUM confidence)
- leanylabs.com Recharts SSR tips (ResponsiveContainer + SSR workaround): https://leanylabs.com/blog/awesome-react-charts-tips/
- Recharts GitHub issue #1806 (renderToStaticMarkup history): https://github.com/recharts/recharts/issues/1806
- resvg-js npm unpackedSize 44489 bytes (package metadata only; binary ~4MB separate): https://www.npmjs.com/package/@resvg/resvg-js
- Satori + resvg-js fontBuffers pattern (OG image generation): https://mfyz.com/generate-beautiful-og-images-astro-satori/
- a16z American Dynamism 50 visual analysis: https://a16z.com/american-dynamism-50-ai/

### Tertiary (LOW confidence)
- a16z State of Consumer AI 2025 (WebFetch — limited visual data): https://a16z.com/state-of-consumer-ai-2025-product-hits-misses-and-whats-next/
- Memory overhead estimates (extrapolated from benchmarks, not measured)

---

## Metadata

**Confidence breakdown:**
- Recharts SSR pinning requirement (v2.15.4): HIGH — confirmed via GitHub issue, multiple sources
- resvg-js font loading + license: HIGH — confirmed via npm + GitHub
- a16z visual style: MEDIUM — WebFetch has limited access to rendered images; description synthesized from multiple page analyses
- Claude design system (no published tokens): HIGH — confirmed via official Anthropic announcement
- Node subprocess architecture: HIGH — well-established pattern; recommendation is grounded
- Memory/performance estimates: MEDIUM — extrapolated, not benchmarked

**Research date:** 2026-04-20
**Valid until:** 2026-07-20 (stable domain; Recharts SSR issue may be resolved before then — check before upgrading)
