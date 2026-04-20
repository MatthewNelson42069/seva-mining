'use strict';
/**
 * ComparisonTable component — handles chart type "comparison_table".
 * Pure SVG — NO Recharts, NO foreignObject.
 *
 * a16z editorial style (theme.js): Playfair Display serif title, dark navy
 * header row, alternating cream/warm-beige data rows, left-aligned label
 * column, center-aligned data columns.
 */
const React = require('react');
const theme = require('../theme.js');

const HEADER_BG = theme.COLORS.TEXT_PRIMARY;
const ROW_BG_1 = theme.COLORS.BG;
const ROW_BG_2 = '#E8E3D9';
const HEADER_TEXT = '#FFFFFF';
const BODY_TEXT = theme.COLORS.TEXT_PRIMARY;
const LABEL_TEXT = '#1E3A5F';

/**
 * ComparisonTable component.
 * @param {Object} props - ChartSpec fields (title, subtitle, rows, col1_header, col2_header, col3_header, width, height, source)
 */
function ComparisonTable(props) {
  const {
    width = 1200,
    height = 675,
    title = '',
    subtitle = null,
    source = null,
    rows = [],
    col1_header = 'A',
    col2_header = 'B',
    col3_header = null,
  } = props;

  const hasCol3 = col3_header !== null && col3_header !== undefined;

  const PAD_X = theme.LAYOUT.PAD_X + 20; // slight inset from canvas edge
  const TITLE_H = subtitle ? theme.LAYOUT.HEADER : 80;
  const tableW = width - PAD_X * 2;

  // Column widths — wider label column, evenly-split data columns
  const labelColW = hasCol3 ? tableW * 0.35 : tableW * 0.4;
  const dataColsN = hasCol3 ? 3 : 2;
  const dataColW = (tableW - labelColW) / dataColsN;

  // Row heights
  const headerH = 48;
  const rowH = 44;
  const totalRows = rows.length;
  const tableH = headerH + totalRows * rowH;

  // Center the table vertically in remaining space
  const tableY = TITLE_H + Math.max(0, (height - TITLE_H - 60 - tableH) / 2);

  // Column X positions
  const col0X = PAD_X;
  const col1X = PAD_X + labelColW;
  const col2X = col1X + dataColW;
  const col3X = col2X + dataColW;

  const tableRows = rows.map((row, i) => {
    const rowY = tableY + headerH + i * rowH;
    const bg = i % 2 === 0 ? ROW_BG_1 : ROW_BG_2;
    const textY = rowY + rowH / 2;

    const elements = [
      React.createElement('rect', {
        key: `row-bg-${i}`,
        x: PAD_X,
        y: rowY,
        width: tableW,
        height: rowH,
        fill: bg,
      }),
      // Label (left-aligned, bold)
      React.createElement('text', {
        key: `row-label-${i}`,
        x: col0X + 14,
        y: textY,
        dominantBaseline: 'middle',
        fontFamily: theme.FONTS.BODY,
        fontSize: theme.SIZES.TABLE_CELL,
        fontWeight: '600',
        fill: LABEL_TEXT,
      }, row.label || ''),
      // Col1 (center-aligned)
      React.createElement('text', {
        key: `row-col1-${i}`,
        x: col1X + dataColW / 2,
        y: textY,
        textAnchor: 'middle',
        dominantBaseline: 'middle',
        fontFamily: theme.FONTS.BODY,
        fontSize: theme.SIZES.TABLE_CELL,
        fontWeight: '400',
        fill: BODY_TEXT,
      }, row.col1 || ''),
    ];

    // Col2 (always present — schema guarantees row.col2)
    elements.push(
      React.createElement('text', {
        key: `row-col2-${i}`,
        x: col2X + dataColW / 2,
        y: textY,
        textAnchor: 'middle',
        dominantBaseline: 'middle',
        fontFamily: theme.FONTS.BODY,
        fontSize: theme.SIZES.TABLE_CELL,
        fontWeight: '400',
        fill: BODY_TEXT,
      }, row.col2 || '')
    );
    if (hasCol3) {
      elements.push(
        React.createElement('text', {
          key: `row-col3-${i}`,
          x: col3X + dataColW / 2,
          y: textY,
          textAnchor: 'middle',
          dominantBaseline: 'middle',
          fontFamily: theme.FONTS.BODY,
          fontSize: theme.SIZES.TABLE_CELL,
          fontWeight: '400',
          fill: BODY_TEXT,
        }, row.col3 || '')
      );
    }

    return React.createElement('g', { key: `row-${i}` }, ...elements);
  });

  // Header cells
  const headerTextY = tableY + headerH / 2;
  const headerElements = [
    React.createElement('rect', {
      key: 'hdr-bg',
      x: PAD_X,
      y: tableY,
      width: tableW,
      height: headerH,
      fill: HEADER_BG,
      rx: 3,
    }),
    React.createElement('text', {
      key: 'hdr-label',
      x: col0X + 14,
      y: headerTextY,
      dominantBaseline: 'middle',
      fontFamily: theme.FONTS.BODY,
      fontSize: theme.SIZES.TABLE_HEADER,
      fontWeight: '700',
      fill: HEADER_TEXT,
    }, 'Metric'),
    React.createElement('text', {
      key: 'hdr-col1',
      x: col1X + dataColW / 2,
      y: headerTextY,
      textAnchor: 'middle',
      dominantBaseline: 'middle',
      fontFamily: theme.FONTS.BODY,
      fontSize: theme.SIZES.TABLE_HEADER,
      fontWeight: '700',
      fill: HEADER_TEXT,
    }, col1_header || 'A'),
  ];

  headerElements.push(
    React.createElement('text', {
      key: 'hdr-col2',
      x: col2X + dataColW / 2,
      y: headerTextY,
      textAnchor: 'middle',
      dominantBaseline: 'middle',
      fontFamily: theme.FONTS.BODY,
      fontSize: theme.SIZES.TABLE_HEADER,
      fontWeight: '700',
      fill: HEADER_TEXT,
    }, col2_header || 'B')
  );
  if (hasCol3) {
    headerElements.push(
      React.createElement('text', {
        key: 'hdr-col3',
        x: col3X + dataColW / 2,
        y: headerTextY,
        textAnchor: 'middle',
        dominantBaseline: 'middle',
        fontFamily: theme.FONTS.BODY,
        fontSize: theme.SIZES.TABLE_HEADER,
        fontWeight: '700',
        fill: HEADER_TEXT,
      }, col3_header || 'C')
    );
  }

  return React.createElement(
    'svg',
    { width, height, xmlns: 'http://www.w3.org/2000/svg' },
    // Background
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
    // Header
    React.createElement('g', { key: 'header' }, ...headerElements),
    // Data rows
    ...tableRows,
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

module.exports = ComparisonTable;
