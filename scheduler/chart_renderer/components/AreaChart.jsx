'use strict';
/**
 * AreaChart component — handles chart types "area" and "stacked_area".
 *
 * a16z editorial style (theme.js): Playfair Display serif title, cream bg,
 * dark-teal primary area (0.7 opacity), lighter teal stacked second series
 * (0.5 opacity), subtle horizontal-only gridlines.
 *
 * NOTE: Recharts' <Legend> renders outside the main chart <svg> — dropped by
 * our non-greedy SVG extractor. We render an inline SVG legend for
 * stacked_area inside the chart <svg> instead.
 */
const React = require('react');
const {
  AreaChart: RechartsAreaChart,
  Area,
  XAxis,
  YAxis,
  CartesianGrid,
} = require('recharts');
const theme = require('../theme.js');

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
  const MARGIN = { top: theme.LAYOUT.HEADER, right: 40, bottom: theme.LAYOUT.FOOTER, left: 70 };
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
    // Primary area
    React.createElement(Area, {
      type: 'monotone',
      dataKey: 'value',
      name: label1,
      stroke: theme.COLORS.BAR_PRIMARY,
      fill: theme.COLORS.BAR_PRIMARY,
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
      stroke: theme.COLORS.BAR_SECONDARY,
      fill: theme.COLORS.BAR_SECONDARY,
      fillOpacity: 0.5,
      stackId: '1',
      dot: false,
      activeDot: false,
    }),
    // Inline SVG legend (stacked_area only) — kept inside chart <svg>
    isStacked && React.createElement('rect', {
      x: theme.LAYOUT.PAD_X, y: theme.LAYOUT.HEADER - 18, width: 14, height: 14,
      fill: theme.COLORS.BAR_PRIMARY, fillOpacity: 0.7, rx: 2,
    }),
    isStacked && React.createElement('text', {
      x: theme.LAYOUT.PAD_X + 22, y: theme.LAYOUT.HEADER - 7,
      fontFamily: theme.FONTS.BODY,
      fontSize: theme.SIZES.LEGEND,
      fontWeight: '600',
      fill: theme.COLORS.TEXT_PRIMARY,
    }, label1),
    isStacked && React.createElement('rect', {
      x: theme.LAYOUT.PAD_X + 140, y: theme.LAYOUT.HEADER - 18, width: 14, height: 14,
      fill: theme.COLORS.BAR_SECONDARY, fillOpacity: 0.5, rx: 2,
    }),
    isStacked && React.createElement('text', {
      x: theme.LAYOUT.PAD_X + 162, y: theme.LAYOUT.HEADER - 7,
      fontFamily: theme.FONTS.BODY,
      fontSize: theme.SIZES.LEGEND,
      fontWeight: '600',
      fill: theme.COLORS.TEXT_PRIMARY,
    }, label2)
  );
}

module.exports = AreaChart;
