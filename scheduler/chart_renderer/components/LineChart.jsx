'use strict';
/**
 * LineChart component — handles chart types "line" and "multi_line".
 *
 * a16z editorial style (theme.js): Playfair Display serif title, cream bg,
 * thick dark-teal primary line, lighter secondary line for multi_line,
 * subtle horizontal-only gridlines, inline SVG legend top-right.
 *
 * NOTE: Recharts' <Legend> component renders to a sibling <div> outside the
 * main chart <svg>. Our SVG extractor in render-chart.js stops at the chart's
 * </svg>, so the Recharts legend would be dropped. We render an inline SVG
 * legend for multi_line instead — stays inside the captured <svg>.
 */
const React = require('react');
const {
  LineChart: RechartsLineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
} = require('recharts');
const theme = require('../theme.js');

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
  const MARGIN = { top: theme.LAYOUT.HEADER, right: 40, bottom: theme.LAYOUT.FOOTER, left: 70 };
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
    // Subtitle
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
    // Grid — horizontal lines only, subtle solid
    React.createElement(CartesianGrid, {
      stroke: theme.COLORS.GRID,
      vertical: false,
      strokeDasharray: '0',
    }),
    // X axis
    React.createElement(XAxis, {
      dataKey: 'label',
      tick: { fill: theme.COLORS.TEXT_SECONDARY, fontSize: theme.SIZES.AXIS_TICK, fontFamily: theme.FONTS.BODY },
      axisLine: { stroke: theme.COLORS.DIVIDER },
      tickLine: false,
    }),
    // Y axis
    React.createElement(YAxis, {
      tick: { fill: theme.COLORS.TEXT_SECONDARY, fontSize: theme.SIZES.AXIS_TICK, fontFamily: theme.FONTS.BODY },
      axisLine: false,
      tickLine: false,
      unit: unit,
    }),
    // Primary line
    React.createElement(Line, {
      type: 'monotone',
      dataKey: 'value',
      name: label1,
      stroke: theme.COLORS.BAR_PRIMARY,
      strokeWidth: 2.5,
      dot: false,
      activeDot: false,
    }),
    // Secondary line (multi_line only)
    isMultiLine && React.createElement(Line, {
      type: 'monotone',
      dataKey: 'value2',
      name: label2,
      stroke: theme.COLORS.BAR_SECONDARY,
      strokeWidth: 2.5,
      dot: false,
      activeDot: false,
      strokeDasharray: '5 3',
    }),
    // Inline SVG legend (multi_line only) — kept inside chart <svg> so our non-greedy
    // extractor captures it. Positioned below the subtitle, left-aligned under the title.
    isMultiLine && React.createElement('rect', {
      x: theme.LAYOUT.PAD_X, y: theme.LAYOUT.HEADER - 18, width: 14, height: 14,
      fill: theme.COLORS.BAR_PRIMARY, rx: 2,
    }),
    isMultiLine && React.createElement('text', {
      x: theme.LAYOUT.PAD_X + 22, y: theme.LAYOUT.HEADER - 7,
      fontFamily: theme.FONTS.BODY,
      fontSize: theme.SIZES.LEGEND,
      fontWeight: '600',
      fill: theme.COLORS.TEXT_PRIMARY,
    }, label1),
    isMultiLine && React.createElement('rect', {
      x: theme.LAYOUT.PAD_X + 140, y: theme.LAYOUT.HEADER - 18, width: 14, height: 14,
      fill: theme.COLORS.BAR_SECONDARY, rx: 2,
    }),
    isMultiLine && React.createElement('text', {
      x: theme.LAYOUT.PAD_X + 162, y: theme.LAYOUT.HEADER - 7,
      fontFamily: theme.FONTS.BODY,
      fontSize: theme.SIZES.LEGEND,
      fontWeight: '600',
      fill: theme.COLORS.TEXT_PRIMARY,
    }, label2)
  );
}

module.exports = LineChart;
