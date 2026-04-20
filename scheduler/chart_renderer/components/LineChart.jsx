'use strict';
/**
 * LineChart component — handles chart types "line" and "multi_line".
 *
 * For "multi_line": renders two Line components using data[].value and data[].value2.
 * Pass spec.type === "multi_line" via props to enable the second series.
 * series_labels[0] and series_labels[1] set legend labels for the two lines.
 */
const React = require('react');
const {
  LineChart: RechartsLineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
} = require('recharts');

// NOTE: Recharts' <Legend> component renders to a sibling <div class="recharts-legend-wrapper">
// outside the main chart <svg>. Our SVG extractor (non-greedy match in render-chart.js) stops at
// the chart's </svg>, so the Recharts legend would be dropped. We render an inline SVG legend
// below for multi_line charts instead — stays inside the captured <svg>.

/**
 * LineChart component.
 * @param {Object} props - ChartSpec fields (type, title, subtitle, data, unit, width, height, source, series_labels)
 */
function LineChart(props) {
  const {
    type = 'line',
    width = 1200,
    height = 675,
    title = '',
    subtitle = null,
    source = null,
    data = [],
    unit = '',
    series_labels = null,
  } = props;

  const isMultiLine = type === 'multi_line';
  const MARGIN = { top: 80, right: 40, bottom: 60, left: 70 };
  const label1 = (series_labels && series_labels[0]) || 'Series 1';
  const label2 = (series_labels && series_labels[1]) || 'Series 2';

  return React.createElement(
    RechartsLineChart,
    {
      width,
      height,
      data,
      margin: MARGIN,
    },
    // Background
    React.createElement('rect', {
      width,
      height,
      fill: '#F0ECE4',
      x: 0,
      y: 0,
    }),
    // Title
    React.createElement('text', {
      x: MARGIN.left,
      y: 38,
      fontFamily: 'Inter, sans-serif',
      fontSize: 22,
      fontWeight: '700',
      fill: '#0C1B32',
      dominantBaseline: 'middle',
    }, title),
    // Subtitle
    subtitle && React.createElement('text', {
      x: MARGIN.left,
      y: 62,
      fontFamily: 'Inter, sans-serif',
      fontSize: 13,
      fontWeight: '400',
      fill: '#5A6B7A',
      dominantBaseline: 'middle',
    }, subtitle),
    // Source
    source && React.createElement('text', {
      x: width - 10,
      y: height - 8,
      fontFamily: 'Inter, sans-serif',
      fontSize: 10,
      fontWeight: '400',
      fill: '#5A6B7A',
      textAnchor: 'end',
    }, `Source: ${source}`),
    // Grid
    React.createElement(CartesianGrid, {
      strokeDasharray: '3 3',
      stroke: '#E2DDD6',
      vertical: false,
    }),
    // X axis
    React.createElement(XAxis, {
      dataKey: 'label',
      tick: { fill: '#5A6B7A', fontSize: 11, fontFamily: 'Inter, sans-serif' },
      axisLine: { stroke: '#E2DDD6' },
      tickLine: false,
    }),
    // Y axis
    React.createElement(YAxis, {
      tick: { fill: '#5A6B7A', fontSize: 11, fontFamily: 'Inter, sans-serif' },
      axisLine: false,
      tickLine: false,
      unit: unit,
    }),
    // Primary line
    React.createElement(Line, {
      type: 'monotone',
      dataKey: 'value',
      name: label1,
      stroke: '#1E3A5F',
      strokeWidth: 2,
      dot: false,
      activeDot: false,
    }),
    // Secondary line (multi_line only)
    isMultiLine && React.createElement(Line, {
      type: 'monotone',
      dataKey: 'value2',
      name: label2,
      stroke: '#4A7FA5',
      strokeWidth: 2,
      dot: false,
      activeDot: false,
      strokeDasharray: '5 3',
    }),
    // Inline SVG legend (multi_line only) — rendered inside the chart <svg>, top-right
    isMultiLine && React.createElement('rect', {
      x: width - 260, y: 34, width: 14, height: 14, fill: '#1E3A5F', rx: 2,
    }),
    isMultiLine && React.createElement('text', {
      x: width - 242, y: 45,
      fontFamily: 'Inter, sans-serif',
      fontSize: 12,
      fontWeight: '500',
      fill: '#0C1B32',
    }, label1),
    isMultiLine && React.createElement('rect', {
      x: width - 140, y: 34, width: 14, height: 14, fill: '#4A7FA5', rx: 2,
    }),
    isMultiLine && React.createElement('text', {
      x: width - 122, y: 45,
      fontFamily: 'Inter, sans-serif',
      fontSize: 12,
      fontWeight: '500',
      fill: '#0C1B32',
    }, label2)
  );
}

module.exports = LineChart;
