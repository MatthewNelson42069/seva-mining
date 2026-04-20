'use strict';
/**
 * HorizontalBarChart component — handles chart type "horizontal_bar".
 *
 * Identical to BarChart but with layout="horizontal" and swapped XAxis/YAxis types.
 * Use for long category labels where vertical bars would cause label overlap.
 */
const React = require('react');
const {
  BarChart: RechartsBarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
} = require('recharts');

/**
 * HorizontalBarChart component.
 * @param {Object} props - ChartSpec fields (title, subtitle, data, unit, width, height, source)
 */
function HorizontalBarChart(props) {
  const {
    width = 1200,
    height = 675,
    title = '',
    subtitle = null,
    source = null,
    data = [],
    unit = '',
  } = props;

  const MARGIN = { top: 80, right: 60, bottom: 40, left: 160 };

  return React.createElement(
    RechartsBarChart,
    {
      width,
      height,
      data,
      layout: 'vertical',
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
    // Grid — vertical lines only (horizontal bar chart shows horizontal bars)
    React.createElement(CartesianGrid, {
      strokeDasharray: '3 3',
      stroke: '#E2DDD6',
      horizontal: false,
    }),
    // Y axis (categories) for horizontal layout
    React.createElement(YAxis, {
      type: 'category',
      dataKey: 'label',
      width: 140,
      tick: { fill: '#5A6B7A', fontSize: 11, fontFamily: 'Inter, sans-serif' },
      axisLine: { stroke: '#E2DDD6' },
      tickLine: false,
    }),
    // X axis (values) for horizontal layout
    React.createElement(XAxis, {
      type: 'number',
      tick: { fill: '#5A6B7A', fontSize: 11, fontFamily: 'Inter, sans-serif' },
      axisLine: false,
      tickLine: false,
      unit: unit,
    }),
    // Bar
    React.createElement(Bar, {
      dataKey: 'value',
      fill: '#1E3A5F',
      radius: [0, 2, 2, 0],
    })
  );
}

module.exports = HorizontalBarChart;
