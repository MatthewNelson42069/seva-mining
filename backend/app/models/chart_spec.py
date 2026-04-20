"""
ChartSpec — Pydantic v2 schema for structured chart specifications.

Backend mirror of scheduler/models/chart_spec.py.
Per the established dual-copy pattern: scheduler/models/ mirrors backend/app/models/ —
scheduler has no access to backend package and vice versa.

Used by:
- Backend API responses that expose chart_spec data to the frontend (if ever needed)
- Type-safe serialization of BundleCharts from ContentBundle.draft_content JSONB

NOTE: Keep in sync with scheduler/models/chart_spec.py manually.
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
    """Specification for a single chart to be rendered by the Node chart renderer."""

    type: ChartType
    title: str
    subtitle: Optional[str] = None
    source: Optional[str] = None
    x_label: Optional[str] = None
    y_label: Optional[str] = None
    unit: Optional[str] = None

    data: list[DataPoint] = Field(default_factory=list)
    stats: list[StatCallout] = Field(default_factory=list)
    rows: list[TableRow] = Field(default_factory=list)
    events: list[TimelineEvent] = Field(default_factory=list)

    col1_header: Optional[str] = None
    col2_header: Optional[str] = None
    col3_header: Optional[str] = None

    width: int = 1200
    height: int = 675

    series_labels: Optional[list[str]] = None


class BundleCharts(BaseModel):
    """Top-level wrapper for an infographic bundle's chart specifications."""

    charts: list[ChartSpec] = Field(max_length=2)
    twitter_caption: str
