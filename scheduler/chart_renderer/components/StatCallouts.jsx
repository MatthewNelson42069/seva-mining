'use strict';
/**
 * StatCallouts component — handles chart type "stat_callouts".
 * Pure SVG JSX — NO Recharts, NO foreignObject.
 *
 * Renders a grid of 2-4 large-number "hero stats" with label below.
 * Gold accent (#D4AF37) applied to first stat value (the lead stat).
 */
const React = require('react');

/**
 * StatCallouts component.
 * @param {Object} props - ChartSpec fields (title, subtitle, stats, width, height, source)
 */
function StatCallouts(props) {
  const {
    width = 1200,
    height = 675,
    title = '',
    subtitle = null,
    source = null,
    stats = [],
  } = props;

  if (!stats || stats.length === 0) {
    return React.createElement(
      'svg',
      { width, height, xmlns: 'http://www.w3.org/2000/svg' },
      React.createElement('rect', { width, height, fill: '#F0ECE4' }),
      React.createElement('text', {
        x: width / 2,
        y: height / 2,
        textAnchor: 'middle',
        fontFamily: 'Inter, sans-serif',
        fontSize: 18,
        fill: '#5A6B7A',
      }, 'No stats provided')
    );
  }

  // Grid layout: 1-4 stats, max 2 columns
  const cols = stats.length <= 2 ? stats.length : Math.min(stats.length, 2);
  const rows = Math.ceil(stats.length / cols);

  // Reserve space for title at top
  const titleAreaH = subtitle ? 90 : 65;
  const bottomPad = 30;
  const gridAreaH = height - titleAreaH - bottomPad;
  const cellW = width / cols;
  const cellH = gridAreaH / rows;

  const statElements = stats.map((stat, i) => {
    const col = i % cols;
    const row = Math.floor(i / cols);
    const cx = col * cellW + cellW / 2;
    const cy = titleAreaH + row * cellH + cellH / 2;

    // Gold accent on lead stat (index 0) — Seva brand feature
    const valueFill = i === 0 ? '#D4AF37' : '#0C1B32';

    const elements = [
      // Large value
      React.createElement('text', {
        key: `val-${i}`,
        x: cx,
        y: cy - 12,
        textAnchor: 'middle',
        dominantBaseline: 'bottom',
        fontFamily: 'Inter, sans-serif',
        fontSize: 56,
        fontWeight: '700',
        fill: valueFill,
      }, stat.value || ''),
      // Label below
      React.createElement('text', {
        key: `label-${i}`,
        x: cx,
        y: cy + 18,
        textAnchor: 'middle',
        dominantBaseline: 'top',
        fontFamily: 'Inter, sans-serif',
        fontSize: 14,
        fontWeight: '400',
        fill: '#5A6B7A',
      }, stat.label || ''),
    ];

    // Source (small, bottom-right of cell)
    if (stat.source) {
      elements.push(
        React.createElement('text', {
          key: `src-${i}`,
          x: col * cellW + cellW - 10,
          y: titleAreaH + (row + 1) * cellH - 8,
          textAnchor: 'end',
          fontFamily: 'Inter, sans-serif',
          fontSize: 10,
          fontWeight: '400',
          fill: '#5A6B7A',
        }, stat.source)
      );
    }

    // Divider line between cells (vertical, except rightmost column)
    if (col < cols - 1) {
      elements.push(
        React.createElement('line', {
          key: `div-v-${i}`,
          x1: (col + 1) * cellW,
          y1: titleAreaH + 20,
          x2: (col + 1) * cellW,
          y2: height - bottomPad - 10,
          stroke: '#E2DDD6',
          strokeWidth: 1,
        })
      );
    }

    return React.createElement('g', { key: `stat-${i}` }, ...elements);
  });

  return React.createElement(
    'svg',
    { width, height, xmlns: 'http://www.w3.org/2000/svg' },
    // Background
    React.createElement('rect', { width, height, fill: '#F0ECE4' }),
    // Title
    React.createElement('text', {
      x: 40,
      y: 42,
      fontFamily: 'Inter, sans-serif',
      fontSize: 22,
      fontWeight: '700',
      fill: '#0C1B32',
      dominantBaseline: 'middle',
    }, title),
    // Subtitle
    subtitle && React.createElement('text', {
      x: 40,
      y: 68,
      fontFamily: 'Inter, sans-serif',
      fontSize: 13,
      fontWeight: '400',
      fill: '#5A6B7A',
      dominantBaseline: 'middle',
    }, subtitle),
    // Horizontal divider below title
    React.createElement('line', {
      x1: 40,
      y1: titleAreaH - 8,
      x2: width - 40,
      y2: titleAreaH - 8,
      stroke: '#E2DDD6',
      strokeWidth: 1,
    }),
    // Stats grid
    ...statElements,
    // Source (bottom-right of entire chart, if no per-stat sources)
    source && !stats.some(s => s.source) && React.createElement('text', {
      x: width - 10,
      y: height - 8,
      textAnchor: 'end',
      fontFamily: 'Inter, sans-serif',
      fontSize: 10,
      fontWeight: '400',
      fill: '#5A6B7A',
    }, `Source: ${source}`)
  );
}

module.exports = StatCallouts;
