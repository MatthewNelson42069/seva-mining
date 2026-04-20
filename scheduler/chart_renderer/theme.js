'use strict';
/**
 * Shared visual theme — a16z editorial style for Seva Mining infographics.
 *
 * Design signatures (matched against a16z.news reference charts, Apr 2026):
 *   - Cream background (#F0ECE4), warm editorial feel
 *   - Serif display TITLE (Playfair Display Bold) — large, left-aligned
 *   - Sans-serif body (Inter Bold/Regular) for subtitles, axes, values, sources
 *   - Uniform solid dark-teal bars (no per-bar gradient or alternation)
 *   - Subtle solid gridlines (no dashes) so data stays the focus
 *   - Value labels drawn AT the bar tip (Bar.LabelList position=top|right)
 *   - Source attribution bottom-LEFT; "SEVA MINING" wordmark bottom-RIGHT
 *     (mirrors the a16z reference: "Source: …" left / "A16Z" wordmark right)
 *   - Gold (#D4AF37) is reserved for hero stats and highlight callouts —
 *     never decorative
 *
 * Fonts are loaded in render-chart.js from ./fonts/ via `fontFiles` paths —
 * resvg-js resolves fontFamily strings by TTF `name` table family:
 *   'Inter'             → Inter-Regular / Inter-Bold
 *   'DM Serif Display'  → DMSerifDisplay-Regular
 *
 * Font choice: DM Serif Display (Google Fonts, SIL OFL) is a high-contrast
 * display serif designed for editorial headlines — heavy enough at one weight
 * that we don't need a separate Bold. Playfair Display was evaluated but
 * Google only ships it as a variable-wght TTF which resvg-js 2.6.x does not
 * resolve reliably via the wght axis.
 *
 * If the serif fails to load (download error, etc.), titles fall back to
 * Inter Bold — the chart still reads as Seva-branded, just without the
 * editorial serif character.
 */
module.exports = {
  COLORS: {
    BG: '#F0ECE4',             // Warm cream background
    TEXT_PRIMARY: '#0C1B32',   // Deep navy — titles, primary labels
    TEXT_SECONDARY: '#5A6B7A', // Muted blue-gray — subtitles, axis, source
    BAR_PRIMARY: '#1E3A5F',    // Dark teal-navy — uniform across bars
    BAR_SECONDARY: '#4A7FA5',  // Lighter teal — second series (multi_line, stacked_area)
    GRID: '#D8D2C8',           // Very subtle warm gray — solid gridlines
    DIVIDER: '#E2DDD6',        // Slightly darker than grid — axis lines, table separators
    ACCENT_GOLD: '#D4AF37',    // Gold — hero stats and highlight callouts only
  },
  FONTS: {
    TITLE: 'DM Serif Display', // Serif display — resvg-js resolves from DMSerifDisplay-Regular.ttf
    BODY: 'Inter',             // Sans — resvg-js resolves from Inter-Regular/Bold.ttf
  },
  SIZES: {
    TITLE: 36,        // Display title (was 22 — a16z titles are visibly larger than body)
    SUBTITLE: 15,     // Subtitle / kicker (was 13)
    AXIS_TICK: 12,    // Axis tick labels
    VALUE_LABEL: 13,  // Value label at bar tip
    LEGEND: 12,       // Inline SVG legend
    SOURCE: 10,       // Source attribution, brand wordmark
    STAT_BIG: 72,     // stat_callouts hero value
    STAT_LABEL: 14,   // stat_callouts caption
    TABLE_HEADER: 13,
    TABLE_CELL: 13,
  },
  LAYOUT: {
    // Space reserved above chart for title + subtitle (used as Recharts MARGIN.top)
    HEADER: 110,
    // Space reserved below chart for source + brand wordmark (used as Recharts MARGIN.bottom)
    FOOTER: 70,
    // Left/right padding for pure-SVG components (StatCallouts, ComparisonTable, Timeline)
    PAD_X: 40,
    // Title/subtitle/source absolute positioning (from top-left of canvas)
    TITLE_Y: 58,
    SUBTITLE_Y: 88,
    FOOTER_Y_OFFSET: 14, // distance from bottom of canvas for source + wordmark
  },
  BRAND: 'SEVA MINING',
};
