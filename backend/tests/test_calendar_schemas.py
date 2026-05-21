"""Pydantic schema tests for backend/app/schemas/calendar.py — Phase 6 Plan 01."""
from datetime import date as date_type
from datetime import datetime
from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.schemas.calendar import (
    CalendarItemCreate,
    CalendarItemResponse,
    CalendarItemUpdate,
    CalendarRangeResponse,
)


def test_create_accepts_date_and_body():
    m = CalendarItemCreate(date=date_type(2026, 5, 20), body="hello world")
    assert isinstance(m.date, date_type)
    assert not isinstance(m.date, datetime)  # P1: date NEVER datetime
    assert m.body == "hello world"


def test_create_rejects_blank_body():
    with pytest.raises(ValidationError):
        CalendarItemCreate(date=date_type(2026, 5, 20), body="")
    with pytest.raises(ValidationError):
        CalendarItemCreate(date=date_type(2026, 5, 20), body="   ")


def test_create_parses_date_string():
    m = CalendarItemCreate(date="2026-05-20", body="hello")
    assert m.date == date_type(2026, 5, 20)


def test_update_only_exposes_body():
    m = CalendarItemUpdate(body="new")
    assert m.body == "new"
    # P4 defense: updated_at must NOT be settable from the client
    assert "updated_at" not in CalendarItemUpdate.model_fields
    assert "date" not in CalendarItemUpdate.model_fields
    assert "tag" not in CalendarItemUpdate.model_fields
    assert "title" not in CalendarItemUpdate.model_fields


def test_response_serializes_from_orm_attributes():
    # Simulate an ORM row using a SimpleNamespace
    from types import SimpleNamespace
    row = SimpleNamespace(
        id=uuid4(),
        date=date_type(2026, 5, 20),
        notes_md="hello",
        created_at=datetime(2026, 5, 18, 12, 0, 0),
        updated_at=datetime(2026, 5, 18, 12, 0, 0),
    )
    r = CalendarItemResponse.model_validate(row)
    assert r.body == "hello"
    assert r.date == date_type(2026, 5, 20)


def test_range_response_wraps_list():
    from types import SimpleNamespace
    row = SimpleNamespace(
        id=uuid4(),
        date=date_type(2026, 5, 20),
        notes_md="hello",
        created_at=datetime(2026, 5, 18, 12, 0, 0),
        updated_at=datetime(2026, 5, 18, 12, 0, 0),
    )
    wrap = CalendarRangeResponse(
        items=[CalendarItemResponse.model_validate(row)], total=1
    )
    assert wrap.total == 1
    assert wrap.items[0].body == "hello"
