# Seva Chart Renderer

Long-running Node.js chart renderer for the Seva Mining infographic pipeline.

Reads ChartSpec JSON from stdin, renders charts via Recharts SSR + resvg-js, returns PNG as base64 JSON on stdout.

## stdin/stdout Protocol

### Input (one JSON line per request)

```json
{
  "type": "bar",
  "title": "Gold Price YTD",
  "subtitle": "Optional sub-headline",
  "source": "World Gold Council",
  "data": [
    {"label": "Jan", "value": 2050.0},
    {"label": "Feb", "value": 2100.0},
    {"label": "Mar", "value": 2180.0}
  ],
  "unit": "$/oz",
  "width": 1200,
  "height": 675
}
```

Full ChartSpec shape — only populate the fields relevant to your chart type:
- `data` — for bar, horizontal_bar, line, multi_line, area, stacked_area
- `stats` — for stat_callouts
- `rows` — for comparison_table
- `events` — for timeline

### Output (one JSON line per response)

**Success:**
```json
{"png_b64": "<base64-encoded PNG bytes>"}
```

**Failure:**
```json
{"error": "error message string"}
```

## Supported Chart Types

| type | Component | Data field |
|------|-----------|------------|
| `bar` | BarChart (Recharts) | `data` |
| `horizontal_bar` | HorizontalBarChart (Recharts) | `data` |
| `line` | LineChart (Recharts) | `data` |
| `multi_line` | LineChart (Recharts) | `data[].value + data[].value2` |
| `area` | AreaChart (Recharts) | `data` |
| `stacked_area` | AreaChart (Recharts) | `data[].value + data[].value2` |
| `stat_callouts` | StatCallouts (pure SVG) | `stats` |
| `comparison_table` | ComparisonTable (pure SVG) | `rows` |
| `timeline` | Timeline (pure SVG) | `events` |

## Font Requirement

Inter-Regular.ttf and Inter-Bold.ttf must exist at `./fonts/` before starting the renderer.

Run `sh download-fonts.sh` to download them (requires internet access). This is done automatically during Docker build.

```
scheduler/chart_renderer/
├── fonts/
│   ├── Inter-Regular.ttf   (NOT committed — download at build time)
│   └── Inter-Bold.ttf      (NOT committed — download at build time)
├── components/
│   ├── AreaChart.jsx
│   ├── BarChart.jsx
│   ├── ComparisonTable.jsx
│   ├── HorizontalBarChart.jsx
│   ├── LineChart.jsx
│   ├── StatCallouts.jsx
│   └── Timeline.jsx
├── download-fonts.sh
├── package.json
├── render-chart.js
└── README.md
```

## Version Pinning

**recharts is pinned to 2.15.4.** Do not upgrade to 3.x — SSR is broken in v3 (GitHub issue #5997).
`renderToStaticMarkup` returns an empty div wrapper in v3.x; v2.x produces correct SVG.

## Visual Style

a16z-inspired, minimal, data-forward. Seva brand palette:
- Background: `#F0ECE4` (Seva cream)
- Primary text: `#0C1B32` (Seva deep navy)
- Bar fill primary: `#1E3A5F` (deeper navy-blue)
- Bar fill secondary: `#4A7FA5` (medium blue)
- Gold accent (one element only): `#D4AF37`
- Grid lines: `#E2DDD6`
- Axis labels: `#5A6B7A`
- Font: Inter (TTF), loaded from `./fonts/`

## Python Integration

The Python `ChartRendererClient` (scheduler/agents/chart_renderer_client.py) manages this process:
- Spawns once at scheduler startup via `asyncio.create_subprocess_exec`
- Sends one JSON line per chart spec to stdin
- Reads one JSON response line from stdout
- Auto-restarts if the process crashes
