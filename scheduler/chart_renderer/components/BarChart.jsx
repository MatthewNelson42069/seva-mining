'use strict';
/**
 * BarChart component — handles chart type "bar" (vertical bar chart).
 *
 * Palette (a16z-style with Seva brand):
 *   Background:   #F0ECE4 (Seva cream)
 *   Primary text: #0C1B32 (Seva deep navy)
 *   Bar fill:     #1E3A5F (deeper navy-blue)
 *   Grid lines:   #E2DDD6 (warm light gray)
 *   Axis labels:  #5A6B7A (muted blue-gray)
 *
 * IMPORTANT: Never use ResponsiveContainer — pass explicit width/height props.
 * recharts v2.x SSR requires fixed dimensions (v3.x SSR is broken, issue #5997).
 */
const React = require('react');
const {
  BarChart: RechartsBarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Cell,
} = require('recharts');

/**
 * BarChart component.
 * @param {Object} props - ChartSpec fields (type, title, subtitle, data, unit, width, height, source)
 */
function BarChart(props) {
  const {
    width = 1200,
    height = 675,
    title = '',
    subtitle = null,
    source = null,
    data = [],
    unit = '',
  } = props;

  const MARGIN = { top: 80, right: 40, bottom: 60, left: 70 };

  return React.createElement(
    RechartsBarChart,
    {
      width,
      height,
      data,
      margin: MARGIN,
    },
    // Background rect — rendered inside the SVG wrapper Recharts produces
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
    // Subtitle (optional)
    subtitle && React.createElement('text', {
      x: MARGIN.left,
      y: 62,
      fontFamily: 'Inter, sans-serif',
      fontSize: 13,
      fontWeight: '400',
      fill: '#5A6B7A',
      dominantBaseline: 'middle',
    }, subtitle),
    // Source citation (bottom-right)
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
    // Bar
    React.createElement(
      Bar,
      { dataKey: 'value', fill: '#1E3A5F', radius: [2, 2, 0, 0] },
    )
  );
}

module.exports = BarChart;
