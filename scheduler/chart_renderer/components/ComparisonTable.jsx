'use strict';
/**
 * ComparisonTable component — handles chart type "comparison_table".
 * Pure SVG — NO Recharts, NO foreignObject.
 *
 * Renders a 2-3 column comparison table with:
 * - Header row: dark navy (#0C1B32) background, white text
 * - Alternating data rows: #F0ECE4 / #E8E3D9
 * - Left column: left-aligned. Data columns: center-aligned.
 */
const React = require('react');

const HEADER_BG = '#0C1B32';
const ROW_BG_1 = '#F0ECE4';
const ROW_BG_2 = '#E8E3D9';
const HEADER_TEXT = '#FFFFFF';
const BODY_TEXT = '#0C1B32';
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

  // Layout constants
  const PAD_X = 60;
  const TITLE_H = subtitle ? 90 : 65;
  const tableW = width - PAD_X * 2;

  // Column widths
  const labelColW = hasCol3 ? tableW * 0.35 : tableW * 0.4;
  const dataColW = hasCol3
    ? (tableW - labelColW) / 2
    : (tableW - labelColW);
  const col3W = hasCol3 ? (tableW - labelColW) / 2 : 0;

  // Row heights
  const headerH = 44;
  const rowH = 42;
  const totalRows = rows.length;
  const tableH = headerH + totalRows * rowH;

  // Center the table vertically in remaining space
  const tableY = TITLE_H + Math.max(0, (height - TITLE_H - 40 - tableH) / 2);

  // Column X positions
  const col0X = PAD_X;                          // Label column start
  const col1X = PAD_X + labelColW;              // Data col 1 start
  const col2X = hasCol3 ? col1X + dataColW : 0; // Data col 2 start

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
      // Label (left-aligned)
      React.createElement('text', {
        key: `row-label-${i}`,
        x: col0X + 12,
        y: textY,
        dominantBaseline: 'middle',
        fontFamily: 'Inter, sans-serif',
        fontSize: 13,
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
        fontFamily: 'Inter, sans-serif',
        fontSize: 13,
        fontWeight: '400',
        fill: BODY_TEXT,
      }, row.col1 || ''),
    ];

    if (hasCol3) {
      elements.push(
        React.createElement('text', {
          key: `row-col2-${i}`,
          x: col2X + col3W / 2,
          y: textY,
          textAnchor: 'middle',
          dominantBaseline: 'middle',
          fontFamily: 'Inter, sans-serif',
          fontSize: 13,
          fontWeight: '400',
          fill: BODY_TEXT,
        }, row.col2 || ''),
        React.createElement('text', {
          key: `row-col3-${i}`,
          x: col2X + dataColW + col3W / 2,
          y: textY,
          textAnchor: 'middle',
          dominantBaseline: 'middle',
          fontFamily: 'Inter, sans-serif',
          fontSize: 13,
          fontWeight: '400',
          fill: BODY_TEXT,
        }, row.col3 || '')
      );
    } else {
      elements.push(
        React.createElement('text', {
          key: `row-col2-${i}`,
          x: col1X + dataColW / 2,
          y: textY,
          textAnchor: 'middle',
          dominantBaseline: 'middle',
          fontFamily: 'Inter, sans-serif',
          fontSize: 13,
          fontWeight: '400',
          fill: BODY_TEXT,
        }, row.col2 || '')
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
    // "Metric" label header
    React.createElement('text', {
      key: 'hdr-label',
      x: col0X + 12,
      y: headerTextY,
      dominantBaseline: 'middle',
      fontFamily: 'Inter, sans-serif',
      fontSize: 13,
      fontWeight: '700',
      fill: HEADER_TEXT,
    }, 'Metric'),
    // Col1 header
    React.createElement('text', {
      key: 'hdr-col1',
      x: col1X + dataColW / 2,
      y: headerTextY,
      textAnchor: 'middle',
      dominantBaseline: 'middle',
      fontFamily: 'Inter, sans-serif',
      fontSize: 13,
      fontWeight: '700',
      fill: HEADER_TEXT,
    }, col1_header || 'A'),
  ];

  if (hasCol3) {
    headerElements.push(
      React.createElement('text', {
        key: 'hdr-col2',
        x: col2X + col3W / 2,
        y: headerTextY,
        textAnchor: 'middle',
        dominantBaseline: 'middle',
        fontFamily: 'Inter, sans-serif',
        fontSize: 13,
        fontWeight: '700',
        fill: HEADER_TEXT,
      }, col2_header || 'B'),
      React.createElement('text', {
        key: 'hdr-col3',
        x: col2X + dataColW + col3W / 2,
        y: headerTextY,
        textAnchor: 'middle',
        dominantBaseline: 'middle',
        fontFamily: 'Inter, sans-serif',
        fontSize: 13,
        fontWeight: '700',
        fill: HEADER_TEXT,
      }, col3_header || 'C')
    );
  } else {
    headerElements.push(
      React.createElement('text', {
        key: 'hdr-col2',
        x: col1X + dataColW / 2,
        y: headerTextY,
        textAnchor: 'middle',
        dominantBaseline: 'middle',
        fontFamily: 'Inter, sans-serif',
        fontSize: 13,
        fontWeight: '700',
        fill: HEADER_TEXT,
      }, col2_header || 'B')
    );
  }

  return React.createElement(
    'svg',
    { width, height, xmlns: 'http://www.w3.org/2000/svg' },
    // Background
    React.createElement('rect', { width, height, fill: '#F0ECE4' }),
    // Title
    React.createElement('text', {
      x: PAD_X,
      y: 42,
      fontFamily: 'Inter, sans-serif',
      fontSize: 22,
      fontWeight: '700',
      fill: '#0C1B32',
      dominantBaseline: 'middle',
    }, title),
    // Subtitle
    subtitle && React.createElement('text', {
      x: PAD_X,
      y: 68,
      fontFamily: 'Inter, sans-serif',
      fontSize: 13,
      fontWeight: '400',
      fill: '#5A6B7A',
      dominantBaseline: 'middle',
    }, subtitle),
    // Header
    React.createElement('g', { key: 'header' }, ...headerElements),
    // Data rows
    ...tableRows,
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

module.exports = ComparisonTable;
