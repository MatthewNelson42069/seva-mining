'use strict';
/**
 * StatCallouts component — handles chart type "stat_callouts".
 * Pure SVG JSX — NO Recharts, NO foreignObject.
 *
 * a16z editorial style (theme.js): Playfair Display serif hero numbers and
 * title, Inter labels/sources, cream bg. Lead stat (index 0) gets the gold
 * accent — everything else in deep navy.
 *
 * Grid layout: 1-4 stats, max 2 columns. Subtle dividers between cells only
 * on the interior boundaries (no frame).
 */
const React = require('react');
const theme = require('../theme.js');

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
      React.createElement('rect', { width, height, fill: theme.COLORS.BG }),
      React.createElement('text', {
        x: width / 2,
        y: height / 2,
        textAnchor: 'middle',
        fontFamily: theme.FONTS.BODY,
        fontSize: 18,
        fill: theme.COLORS.TEXT_SECONDARY,
      }, 'No stats provided')
    );
  }

  // Grid layout: 1-4 stats, max 2 columns
  const cols = stats.length <= 2 ? stats.length : Math.min(stats.length, 2);
  const rows = Math.ceil(stats.length / cols);

  // Reserve space for title at top (room for Playfair Display 36 + optional subtitle)
  const titleAreaH = subtitle ? theme.LAYOUT.HEADER : 75;
  const bottomPad = theme.LAYOUT.FOOTER - 30;
  const gridAreaH = height - titleAreaH - bottomPad;
  const cellW = width / cols;
  const cellH = gridAreaH / rows;

  const statElements = stats.map((stat, i) => {
    const col = i % cols;
    const row = Math.floor(i / cols);
    const cx = col * cellW + cellW / 2;
    const cy = titleAreaH + row * cellH + cellH / 2;

    // Gold accent on lead stat (index 0) — Seva brand feature
    const valueFill = i === 0 ? theme.COLORS.ACCENT_GOLD : theme.COLORS.TEXT_PRIMARY;

    const elements = [
      // Hero value — Playfair Display for editorial weight
      React.createElement('text', {
        key: `val-${i}`,
        x: cx,
        y: cy - 8,
        textAnchor: 'middle',
        dominantBaseline: 'alphabetic',
        fontFamily: theme.FONTS.TITLE,
        fontSize: theme.SIZES.STAT_BIG,
        fontWeight: '700',
        fill: valueFill,
      }, stat.value || ''),
      // Caption label below (Inter)
      React.createElement('text', {
        key: `label-${i}`,
        x: cx,
        y: cy + 24,
        textAnchor: 'middle',
        dominantBaseline: 'hanging',
        fontFamily: theme.FONTS.BODY,
        fontSize: theme.SIZES.STAT_LABEL,
        fontWeight: '500',
        fill: theme.COLORS.TEXT_SECONDARY,
      }, stat.label || ''),
    ];

    // Per-stat source (small, below caption)
    if (stat.source) {
      elements.push(
        React.createElement('text', {
          key: `src-${i}`,
          x: cx,
          y: cy + 48,
          textAnchor: 'middle',
          dominantBaseline: 'hanging',
          fontFamily: theme.FONTS.BODY,
          fontSize: theme.SIZES.SOURCE,
          fontWeight: '400',
          fill: theme.COLORS.TEXT_SECONDARY,
        }, stat.source)
      );
    }

    // Vertical divider between columns (no frame on outer edges)
    if (col < cols - 1) {
      elements.push(
        React.createElement('line', {
          key: `div-v-${i}`,
          x1: (col + 1) * cellW,
          y1: titleAreaH + 30,
          x2: (col + 1) * cellW,
          y2: height - bottomPad - 20,
          stroke: theme.COLORS.DIVIDER,
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
    React.createElement('rect', { width, height, fill: theme.COLORS.BG }),
    // Display title (serif)
    React.createElement('text', {
      x: theme.LAYOUT.PAD_X,
      y: theme.LAYOUT.TITLE_Y,
      fontFamily: theme.FONTS.TITLE,
      fontSize: theme.SIZES.TITLE,
      fontWeight: '700',
      fill: theme.COLORS.TEXT_PRIMARY,
    }, title),
    // Subtitle
    subtitle && React.createElement('text', {
      x: theme.LAYOUT.PAD_X,
      y: theme.LAYOUT.SUBTITLE_Y,
      fontFamily: theme.FONTS.BODY,
      fontSize: theme.SIZES.SUBTITLE,
      fontWeight: '400',
      fill: theme.COLORS.TEXT_SECONDARY,
    }, subtitle),
    // Horizontal divider below title
    React.createElement('line', {
      x1: theme.LAYOUT.PAD_X,
      y1: titleAreaH - 14,
      x2: width - theme.LAYOUT.PAD_X,
      y2: titleAreaH - 14,
      stroke: theme.COLORS.DIVIDER,
      strokeWidth: 1,
    }),
    // Stats grid
    ...statElements,
    // Source (bottom-left, only if no per-stat sources)
    source && !stats.some(s => s.source) && React.createElement('text', {
      x: theme.LAYOUT.PAD_X,
      y: height - theme.LAYOUT.FOOTER_Y_OFFSET,
      fontFamily: theme.FONTS.BODY,
      fontSize: theme.SIZES.SOURCE,
      fontWeight: '400',
      fill: theme.COLORS.TEXT_SECONDARY,
    }, `Source: ${source}`),
    // Brand wordmark (bottom-right)
    React.createElement('text', {
      x: width - theme.LAYOUT.PAD_X,
      y: height - theme.LAYOUT.FOOTER_Y_OFFSET,
      textAnchor: 'end',
      fontFamily: theme.FONTS.BODY,
      fontSize: theme.SIZES.SOURCE,
      fontWeight: '700',
      letterSpacing: '0.15em',
      fill: theme.COLORS.TEXT_SECONDARY,
    }, theme.BRAND)
  );
}

module.exports = StatCallouts;
