'use strict';
/**
 * AreaChart component — handles chart types "area" and "stacked_area".
 *
 * For "stacked_area": two Area components with stackId="1", using value and value2 dataKeys.
 * Fill: #1E3A5F (primary, 0.7 opacity) and #4A7FA5 (secondary, 0.5 opacity).
 */
const React = require('react');
const {
  AreaChart: RechartsAreaChart,
  Area,
  XAxis,
  YAxis,
  CartesianGrid,
} = require('recharts');

// NOTE: Recharts' <Legend> renders outside the main chart <svg> (sibling <div>). Our non-greedy
// SVG extractor in render-chart.js stops at the chart's </svg>, so the Recharts legend is dropped.
// We render an inline SVG legend below for stacked_area charts — stays inside the captured <svg>.

/**
 * AreaChart component.
 * @param {Object} props - ChartSpec fields (type, title, subtitle, data, unit, width, height, source, series_labels)
 */
function AreaChart(props) {
  const {
    type = 'area',
    width = 1200,
    height = 675,
    title = '',
    subtitle = null,
    source = null,
    data = [],
    unit = '',
    series_labels = null,
  } = props;

  const isStacked = type === 'stacked_area';
  const MARGIN = { top: 80, right: 40, bottom: 60, left: 70 };
  const label1 = (series_labels && series_labels[0]) || 'Series 1';
  const label2 = (series_labels && series_labels[1]) || 'Series 2';

  return React.createElement(
    RechartsAreaChart,
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
    // Primary area
    React.createElement(Area, {
      type: 'monotone',
      dataKey: 'value',
      name: label1,
      stroke: '#1E3A5F',
      fill: '#1E3A5F',
      fillOpacity: 0.7,
      stackId: isStacked ? '1' : undefined,
      dot: false,
      activeDot: false,
    }),
    // Secondary area (stacked_area only)
    isStacked && React.createElement(Area, {
      type: 'monotone',
      dataKey: 'value2',
      name: label2,
      stroke: '#4A7FA5',
      fill: '#4A7FA5',
      fillOpacity: 0.5,
      stackId: '1',
      dot: false,
      activeDot: false,
    }),
    // Inline SVG legend (stacked_area only) — rendered inside the chart <svg>, top-right
    isStacked && React.createElement('rect', {
      x: width - 260, y: 34, width: 14, height: 14, fill: '#1E3A5F', fillOpacity: 0.7, rx: 2,
    }),
    isStacked && React.createElement('text', {
      x: width - 242, y: 45,
      fontFamily: 'Inter, sans-serif',
      fontSize: 12,
      fontWeight: '500',
      fill: '#0C1B32',
    }, label1),
    isStacked && React.createElement('rect', {
      x: width - 140, y: 34, width: 14, height: 14, fill: '#4A7FA5', fillOpacity: 0.5, rx: 2,
    }),
    isStacked && React.createElement('text', {
      x: width - 122, y: 45,
      fontFamily: 'Inter, sans-serif',
      fontSize: 12,
      fontWeight: '500',
      fill: '#0C1B32',
    }, label2)
  );
}

module.exports = AreaChart;
