'use strict';
/**
 * BarChart component — handles chart type "bar" (vertical bar chart).
 *
 * a16z editorial style (theme.js): Playfair Display serif title, cream bg,
 * uniform dark-teal bars with value labels at the bar tip, subtle solid
 * gridlines, source bottom-left, brand wordmark bottom-right.
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
  LabelList,
} = require('recharts');
const theme = require('../theme.js');

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

  const MARGIN = { top: theme.LAYOUT.HEADER, right: 40, bottom: theme.LAYOUT.FOOTER, left: 70 };

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
    // Grid (horizontal only for vertical bars; subtle solid lines)
    React.createElement(CartesianGrid, {
      stroke: theme.COLORS.GRID,
      vertical: false,
      strokeDasharray: '0',
    }),
    // X axis (categories)
    React.createElement(XAxis, {
      dataKey: 'label',
      tick: { fill: theme.COLORS.TEXT_SECONDARY, fontSize: theme.SIZES.AXIS_TICK, fontFamily: theme.FONTS.BODY },
      axisLine: { stroke: theme.COLORS.DIVIDER },
      tickLine: false,
    }),
    // Y axis (values)
    React.createElement(YAxis, {
      tick: { fill: theme.COLORS.TEXT_SECONDARY, fontSize: theme.SIZES.AXIS_TICK, fontFamily: theme.FONTS.BODY },
      axisLine: false,
      tickLine: false,
      unit: unit,
    }),
    // Bar + value labels at top of each bar
    React.createElement(
      Bar,
      { dataKey: 'value', fill: theme.COLORS.BAR_PRIMARY, radius: [2, 2, 0, 0] },
      React.createElement(LabelList, {
        dataKey: 'value',
        position: 'top',
        fill: theme.COLORS.TEXT_PRIMARY,
        fontSize: theme.SIZES.VALUE_LABEL,
        fontWeight: 600,
        fontFamily: theme.FONTS.BODY,
        formatter: unit ? (v) => `${v}${unit}` : undefined,
      })
    )
  );
}

module.exports = BarChart;
