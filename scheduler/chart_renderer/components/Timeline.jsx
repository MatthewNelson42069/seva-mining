'use strict';
/**
 * Timeline component — handles chart type "timeline".
 * Pure SVG — NO Recharts, NO foreignObject.
 *
 * Renders a horizontal axis with evenly-spaced tick marks and event labels.
 * Alternates labels above/below the axis for dense timelines.
 * Highlighted events (event.highlight=true) use gold tick and label.
 */
const React = require('react');

const AXIS_COLOR = '#0C1B32';
const TICK_DEFAULT = '#5A6B7A';
const TICK_HIGHLIGHT = '#D4AF37';
const LABEL_DEFAULT = '#0C1B32';
const LABEL_HIGHLIGHT = '#D4AF37';
const DATE_COLOR = '#5A6B7A';

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
      React.createElement('rect', { width, height, fill: '#F0ECE4' }),
      React.createElement('text', {
        x: width / 2,
        y: height / 2,
        textAnchor: 'middle',
        fontFamily: 'Inter, sans-serif',
        fontSize: 18,
        fill: '#5A6B7A',
      }, 'No events provided')
    );
  }

  // Layout
  const TITLE_H = subtitle ? 90 : 65;
  const PAD_X = 80;
  const axisY = height * 0.55;  // Horizontal axis at 55% down
  const TICK_H = 14;            // Tick mark height
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
    const labelY = above
      ? axisY - TICK_H - 8    // above axis
      : axisY + TICK_H + 8;  // below axis
    const dateLabelY = above
      ? axisY + TICK_H + 16  // date below tick
      : axisY - TICK_H - 16; // date above tick

    return React.createElement('g', { key: `event-${i}` },
      // Tick mark
      React.createElement('line', {
        x1: x,
        y1: axisY - TICK_H,
        x2: x,
        y2: axisY + TICK_H,
        stroke: tickColor,
        strokeWidth: isHighlight ? 3 : 2,
      }),
      // Event label (above or below)
      React.createElement('text', {
        x,
        y: labelY,
        textAnchor: 'middle',
        dominantBaseline: above ? 'auto' : 'hanging',
        fontFamily: 'Inter, sans-serif',
        fontSize: 12,
        fontWeight: isHighlight ? '700' : '400',
        fill: labelColor,
      }, event.label || ''),
      // Date label (opposite side from event label)
      React.createElement('text', {
        x,
        y: dateLabelY,
        textAnchor: 'middle',
        dominantBaseline: above ? 'hanging' : 'auto',
        fontFamily: 'Inter, sans-serif',
        fontSize: 10,
        fontWeight: '400',
        fill: DATE_COLOR,
      }, event.date || '')
    );
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
    // Horizontal axis line
    React.createElement('line', {
      x1: axisLineX1,
      y1: axisY,
      x2: axisLineX2,
      y2: axisY,
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
    // Source
    source && React.createElement('text', {
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

module.exports = Timeline;
