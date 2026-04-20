'use strict';
/**
 * Timeline component — handles chart type "timeline".
 * Pure SVG — NO Recharts, NO foreignObject.
 *
 * a16z editorial style (theme.js): Playfair Display serif title, cream bg,
 * horizontal navy axis with arrow, alternating above/below event labels,
 * gold highlight for breakthrough events.
 */
const React = require('react');
const theme = require('../theme.js');

const AXIS_COLOR = theme.COLORS.TEXT_PRIMARY;
const TICK_DEFAULT = theme.COLORS.TEXT_SECONDARY;
const TICK_HIGHLIGHT = theme.COLORS.ACCENT_GOLD;
const LABEL_DEFAULT = theme.COLORS.TEXT_PRIMARY;
const LABEL_HIGHLIGHT = theme.COLORS.ACCENT_GOLD;
const DATE_COLOR = theme.COLORS.TEXT_SECONDARY;

/**
 * Timeline component.
 * @param {Object} props - ChartSpec fields (title, subtitle, events, width, height, source)
 */
function Timeline(props) {
  const {
    width = 1200,
    height = 675,
    title = '',
    subtitle = null,
    source = null,
    events = [],
  } = props;

  if (!events || events.length === 0) {
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
      }, 'No events provided')
    );
  }

  // Layout
  const TITLE_H = subtitle ? theme.LAYOUT.HEADER : 80;
  const PAD_X = 80;
  const axisY = TITLE_H + (height - TITLE_H - theme.LAYOUT.FOOTER) / 2;
  const TICK_H = 14;
  const axisLineX1 = PAD_X;
  const axisLineX2 = width - PAD_X;
  const axisW = axisLineX2 - axisLineX1;

  // Evenly space events along the axis
  const n = events.length;
  const step = n > 1 ? axisW / (n - 1) : 0;
  const startX = n > 1 ? axisLineX1 : width / 2;

  const eventElements = events.map((event, i) => {
    const x = n > 1 ? axisLineX1 + i * step : startX;
    const isHighlight = event.highlight === true;
    const tickColor = isHighlight ? TICK_HIGHLIGHT : TICK_DEFAULT;
    const labelColor = isHighlight ? LABEL_HIGHLIGHT : LABEL_DEFAULT;

    // Alternate: even index → label above, odd index → label below
    const above = i % 2 === 0;
    const labelY = above ? axisY - TICK_H - 8 : axisY + TICK_H + 8;
    const dateLabelY = above ? axisY + TICK_H + 16 : axisY - TICK_H - 16;

    return React.createElement('g', { key: `event-${i}` },
      React.createElement('line', {
        x1: x, y1: axisY - TICK_H,
        x2: x, y2: axisY + TICK_H,
        stroke: tickColor,
        strokeWidth: isHighlight ? 3 : 2,
      }),
      React.createElement('text', {
        x, y: labelY,
        textAnchor: 'middle',
        dominantBaseline: above ? 'auto' : 'hanging',
        fontFamily: theme.FONTS.BODY,
        fontSize: 13,
        fontWeight: isHighlight ? '700' : '500',
        fill: labelColor,
      }, event.label || ''),
      React.createElement('text', {
        x, y: dateLabelY,
        textAnchor: 'middle',
        dominantBaseline: above ? 'hanging' : 'auto',
        fontFamily: theme.FONTS.BODY,
        fontSize: 11,
        fontWeight: '400',
        fill: DATE_COLOR,
      }, event.date || '')
    );
  });

  return React.createElement(
    'svg',
    { width, height, xmlns: 'http://www.w3.org/2000/svg' },
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
    // Horizontal axis
    React.createElement('line', {
      x1: axisLineX1, y1: axisY,
      x2: axisLineX2, y2: axisY,
      stroke: AXIS_COLOR,
      strokeWidth: 2,
    }),
    // Arrow at the end of the axis
    React.createElement('polygon', {
      points: `${axisLineX2},${axisY - 5} ${axisLineX2 + 10},${axisY} ${axisLineX2},${axisY + 5}`,
      fill: AXIS_COLOR,
    }),
    // Events
    ...eventElements,
    // Source (bottom-left)
    source && React.createElement('text', {
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

module.exports = Timeline;
