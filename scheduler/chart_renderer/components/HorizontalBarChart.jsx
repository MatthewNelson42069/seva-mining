'use strict';
/**
 * HorizontalBarChart component — handles chart type "horizontal_bar".
 *
 * Matches the a16z "Where do LLMs find answers?" reference: solid uniform
 * dark-teal bars, category labels left-aligned, value labels at the bar tip
 * (right), subtle vertical-only gridlines, cream background.
 *
 * Use when category labels are long (domain names, company names) — vertical
 * bars would truncate or rotate those labels ugly.
 */
const React = require('react');
const {
  BarChart: RechartsBarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  LabelList,
} = require('recharts');
const theme = require('../theme.js');

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

  const MARGIN = {
    top: theme.LAYOUT.HEADER,
    right: 110, // room for value labels at bar tip
    bottom: theme.LAYOUT.FOOTER,
    left: 180,  // wider than vertical-bar variant for long category labels
  };

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
      width, height, fill: theme.COLORS.BG, x: 0, y: 0,
    }),
    // Display title (serif)
    React.createElement('text', {
      x: theme.LAYOUT.PAD_X,
      y: theme.LAYOUT.TITLE_Y,
      fontFamily: theme.FONTS.TITLE,
      fontSize: theme.SIZES.TITLE,
      fontWeight: '700',
      fill: theme.COLORS.TEXT_PRIMARY,
    }, title),
    // Subtitle (sans)
    subtitle && React.createElement('text', {
      x: theme.LAYOUT.PAD_X,
      y: theme.LAYOUT.SUBTITLE_Y,
      fontFamily: theme.FONTS.BODY,
      fontSize: theme.SIZES.SUBTITLE,
      fontWeight: '400',
      fill: theme.COLORS.TEXT_SECONDARY,
    }, subtitle),
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
    }, theme.BRAND),
    // Grid — vertical lines only for horizontal bars
    React.createElement(CartesianGrid, {
      stroke: theme.COLORS.GRID,
      horizontal: false,
      strokeDasharray: '0',
    }),
    // Y axis (categories) — pushed left, bold navy labels
    React.createElement(YAxis, {
      type: 'category',
      dataKey: 'label',
      width: 160,
      tick: { fill: theme.COLORS.TEXT_PRIMARY, fontSize: theme.SIZES.AXIS_TICK + 1, fontFamily: theme.FONTS.BODY, fontWeight: 600 },
      axisLine: false,
      tickLine: false,
    }),
    // X axis (values) at bottom
    React.createElement(XAxis, {
      type: 'number',
      tick: { fill: theme.COLORS.TEXT_SECONDARY, fontSize: theme.SIZES.AXIS_TICK, fontFamily: theme.FONTS.BODY },
      axisLine: { stroke: theme.COLORS.DIVIDER },
      tickLine: false,
      unit: unit,
    }),
    // Bar with value labels at end
    React.createElement(
      Bar,
      { dataKey: 'value', fill: theme.COLORS.BAR_PRIMARY, radius: [0, 2, 2, 0] },
      React.createElement(LabelList, {
        dataKey: 'value',
        position: 'right',
        fill: theme.COLORS.TEXT_PRIMARY,
        fontSize: theme.SIZES.VALUE_LABEL,
        fontWeight: 600,
        fontFamily: theme.FONTS.BODY,
        formatter: unit ? (v) => `${v}${unit}` : undefined,
      })
    )
  );
}

module.exports = HorizontalBarChart;
