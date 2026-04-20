'use strict';
/**
 * render-chart.js — Long-running stdin/stdout chart renderer for Seva Mining.
 *
 * Protocol:
 *   Input  (stdin):  one JSON line per request, matching ChartSpec schema
 *   Output (stdout): one JSON line per response
 *     - success: { "png_b64": "<base64-encoded PNG>" }
 *     - failure: { "error": "<message>" }
 *
 * Fonts: Inter-Regular.ttf and Inter-Bold.ttf must exist at ./fonts/ before start.
 * The download-fonts.sh script fetches them at Docker build time.
 *
 * IMPORTANT: use process.stdout.write (NOT console.log) for protocol reliability.
 * console.log adds no extra buffering but using write makes the newline delimiter explicit.
 */

const readline = require('readline');
const fs = require('fs');
const path = require('path');
const React = require('react');
const ReactDOMServer = require('react-dom/server');
const { Resvg } = require('@resvg/resvg-js');

// Load chart components
// Note: .jsx extension is required because Node's CJS loader does not auto-resolve .jsx
const BarChart = require('./components/BarChart.jsx');
const HorizontalBarChart = require('./components/HorizontalBarChart.jsx');
const LineChart = require('./components/LineChart.jsx');
const AreaChart = require('./components/AreaChart.jsx');
const StatCallouts = require('./components/StatCallouts.jsx');
const ComparisonTable = require('./components/ComparisonTable.jsx');
const Timeline = require('./components/Timeline.jsx');

// ---------------------------------------------------------------------------
// Font loading — resolve paths at startup, reuse across all renders
// ---------------------------------------------------------------------------
// Inter: body/labels/axes. DM Serif Display: editorial titles (theme.js).
//
// We pass absolute PATHS (not buffers) to resvg via `fontFiles`. Testing
// showed that resvg-js 2.6.x's `fontBuffers` path does not register multi-
// family fonts by their `name`-table family correctly — a 2-font array of
// Inter + DM Serif Display caused DM Serif lookups to silently fall back
// to Inter. The `fontFiles` loader goes through fontdb's load_font_file
// which parses the family name correctly.
//
// Missing-font failures are non-fatal — resvg falls back within the registered
// set, and if everything fails text renders as empty boxes but geometry is
// still produced. Warn so Railway logs surface the regression.

const fontFileNames = [
  'Inter-Regular.ttf',
  'Inter-Bold.ttf',
  'DMSerifDisplay-Regular.ttf',
];
const fontFilePaths = [];

for (const name of fontFileNames) {
  const p = path.join(__dirname, 'fonts', name);
  try {
    fs.accessSync(p, fs.constants.R_OK);
    fontFilePaths.push(p);
  } catch (err) {
    process.stderr.write(`[render-chart] WARNING: Could not access ${name}: ${err.message}\n`);
  }
}

if (fontFilePaths.length === 0) {
  process.stderr.write('[render-chart] WARNING: No fonts loaded — text will use system fonts.\n');
}

// ---------------------------------------------------------------------------
// Chart type dispatch
// ---------------------------------------------------------------------------

/**
 * Select the correct component for a given chart spec type.
 * Returns null if type is unrecognized (caller handles error response).
 */
function getComponent(type) {
  switch (type) {
    case 'bar':               return BarChart;
    case 'horizontal_bar':    return HorizontalBarChart;
    case 'line':              return LineChart;
    case 'multi_line':        return LineChart;   // LineChart handles both via props
    case 'area':              return AreaChart;
    case 'stacked_area':      return AreaChart;   // AreaChart handles both via props
    case 'stat_callouts':     return StatCallouts;
    case 'comparison_table':  return ComparisonTable;
    case 'timeline':          return Timeline;
    default:                  return null;
  }
}

// ---------------------------------------------------------------------------
// Render a single ChartSpec to PNG bytes
// ---------------------------------------------------------------------------

/**
 * Render a chart spec to a PNG Buffer.
 *
 * @param {Object} spec - ChartSpec JSON object
 * @returns {Buffer} PNG image bytes
 */
function renderChart(spec) {
  const Component = getComponent(spec.type);
  if (!Component) {
    throw new Error(`Unknown chart type: ${spec.type}`);
  }

  const width = spec.width || 1200;
  const height = spec.height || 675;

  // renderToStaticMarkup requires explicit width/height — NEVER use ResponsiveContainer.
  // Recharts v2.x SSR works with fixed dimensions; v3.x SSR is broken (issue #5997).
  const markup = ReactDOMServer.renderToStaticMarkup(
    React.createElement(Component, { ...spec, width, height })
  );

  // Recharts v2 wraps the SVG in a <div class="recharts-wrapper">...<svg>...</svg></div>.
  // resvg-js requires a standalone SVG root, so strip the wrapper if present.
  // Pure-SVG components (StatCallouts, ComparisonTable, Timeline) return <svg> directly —
  // for those the regex match just returns the original markup, unchanged.
  //
  // Use non-greedy matching: Recharts' <Legend> component emits its own nested <svg>
  // elements inside a sibling <div class="recharts-legend-wrapper">. A greedy regex would
  // swallow past the chart's </svg> and include the legend div, producing invalid markup.
  // Recharts charts don't nest <svg> inside <svg>, so the first </svg> always closes the chart.
  const svgMatch = markup.match(/<svg[\s\S]*?<\/svg>/);
  let svgString = svgMatch ? svgMatch[0] : markup;

  // resvg-js requires the SVG namespace attribute on the root <svg> to parse successfully.
  // Recharts v2 SSR omits xmlns; pure-SVG components set it explicitly.
  // Inject it only when absent (idempotent for the pure-SVG path).
  if (!/\bxmlns\s*=/.test(svgString.slice(0, 200))) {
    svgString = svgString.replace(/^<svg\b/, '<svg xmlns="http://www.w3.org/2000/svg"');
  }

  const resvgOpts = {
    fitTo: { mode: 'width', value: width },
  };

  // Only attach font config if at least one font loaded successfully
  if (fontFilePaths.length > 0) {
    resvgOpts.font = {
      fontFiles: fontFilePaths,
      loadSystemFonts: false,
    };
  }

  const resvg = new Resvg(svgString, resvgOpts);
  return resvg.render().asPng();
}

// ---------------------------------------------------------------------------
// stdin/stdout event loop
// ---------------------------------------------------------------------------

const rl = readline.createInterface({ input: process.stdin });

rl.on('line', (line) => {
  const trimmed = line.trim();
  if (!trimmed) return;

  let spec;
  try {
    spec = JSON.parse(trimmed);
  } catch (err) {
    process.stdout.write(JSON.stringify({ error: `JSON parse error: ${err.message}` }) + '\n');
    return;
  }

  try {
    const pngBuffer = renderChart(spec);
    const pngB64 = pngBuffer.toString('base64');
    process.stdout.write(JSON.stringify({ png_b64: pngB64 }) + '\n');
  } catch (err) {
    process.stdout.write(JSON.stringify({ error: err.message }) + '\n');
  }
});

rl.on('close', () => {
  // stdin closed — Node process exits naturally
  process.exit(0);
});

process.stderr.write('[render-chart] Chart renderer started. Waiting for input...\n');
