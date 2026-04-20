"""
ChartSpec — Pydantic v2 schema for structured chart specifications.

Used by:
- content_agent.py: validates Sonnet's chart_spec JSON for infographic bundles
- image_render_agent.py: passes validated BundleCharts to ChartRendererClient
- chart_renderer_client.py: serializes ChartSpec to Node chart renderer stdin

Design decisions:
- ChartType is str,Enum so JSON serializes to the string value (not .value wrapper)
- BundleCharts.charts has Field(max_length=2) — 1-or-2 chart constraint at validation time
- All list fields use default_factory=list (not []) to avoid mutable default sharing
- width/height default to 1200x675 (16:9 Twitter) so chart_spec can omit them
"""
from __future__ import annotations

from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class ChartType(str, Enum):
    """Supported chart types for infographic rendering."""

    bar = "bar"
    horizontal_bar = "horizontal_bar"
    line = "line"
    multi_line = "multi_line"
    area = "area"
    stacked_area = "stacked_area"
    stat_callouts = "stat_callouts"
    comparison_table = "comparison_table"
    timeline = "timeline"


class DataPoint(BaseModel):
    """A single data point for bar/line/area chart types."""

    label: str  # XAxis category or date string
    value: float  # Primary series value
    value2: Optional[float] = None  # Second series for multi_line/stacked_area


class StatCallout(BaseModel):
    """A large-number hero stat for the stat_callouts chart type."""

    value: str  # Pre-formatted string, e.g. "2,400"
    label: str  # Label below the value, e.g. "Gold $/oz"
    source: Optional[str] = None  # Optional source citation


class TableRow(BaseModel):
    """A data row for the comparison_table chart type."""

    label: str  # Left column (row label)
    col1: str  # First data column
    col2: str  # Second data column
    col3: Optional[str] = None  # Optional third data column


class TimelineEvent(BaseModel):
    """An event marker for the timeline chart type."""

    date: str  # Date string, e.g. "Jan 2024" or "2024-Q1"
    label: str  # Event description
    highlight: bool = False  # If True, render in gold accent (#D4AF37)


class ChartSpec(BaseModel):
    """Specification for a single chart to be rendered by the Node chart renderer.

    The renderer accepts one ChartSpec JSON per stdin line and returns PNG bytes.
    Only the data fields relevant to the chosen type need to be populated.
    """

    type: ChartType
    title: str  # Headline above chart, left-aligned, bold
    subtitle: Optional[str] = None  # Optional sub-headline
    source: Optional[str] = None  # Citation, displayed bottom-right
    x_label: Optional[str] = None  # X-axis label (for bar/line types)
    y_label: Optional[str] = None  # Y-axis label
    unit: Optional[str] = None  # Unit label for Y-axis, e.g. "$/oz", "%", "tonnes"

    # Data fields — only one is typically populated per chart type
    data: list[DataPoint] = Field(default_factory=list)  # bar/line/area types
    stats: list[StatCallout] = Field(default_factory=list)  # stat_callouts
    rows: list[TableRow] = Field(default_factory=list)  # comparison_table
    events: list[TimelineEvent] = Field(default_factory=list)  # timeline

    # comparison_table column headers (optional — renderer defaults to "A", "B", "C")
    col1_header: Optional[str] = None
    col2_header: Optional[str] = None
    col3_header: Optional[str] = None

    # Render target dimensions — default to Twitter 16:9
    width: int = 1200
    height: int = 675

    # For multi_line: legend labels for the two series
    series_labels: Optional[list[str]] = None


class BundleCharts(BaseModel):
    """Top-level wrapper for an infographic bundle's chart specifications.

    What Sonnet emits and what goes in draft_content for infographic format.
    Validated via BundleCharts.model_validate() in content_agent._research_and_draft().
    On ValidationError, the bundle is downgraded to format=thread.
    """

    charts: list[ChartSpec] = Field(max_length=2)  # 1-or-2 charts per infographic
    twitter_caption: str  # 1-3 sentences for X in senior analyst voice
