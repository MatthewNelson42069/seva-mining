"""Pydantic v2 schemas for the v2.1 Content Calendar — Phase 6.

Simplified scope (per 06-CONTEXT.md): one text body per date, plain text only,
no tags, no titles in request bodies. The body lives in the `notes_md` column
on the ORM model but is exposed to the API as `body` for clarity.

Pitfall P1 defense: ALL date fields are `datetime.date` (DAY only) — never
`datetime`. Frontend sends "YYYY-MM-DD" strings; Pydantic parses to date;
SQLAlchemy stores DATE; the column round-trips without UTC off-by-one.

Pitfall P4 defense: CalendarItemUpdate intentionally has NO `updated_at`
field — the router handler sets it explicitly on every PATCH.
"""
import uuid
from datetime import date as date_type, datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator


class CalendarItemCreate(BaseModel):
    """Request body for POST /calendar — the operator types text into a day cell."""
    date: date_type
    body: str = Field(min_length=1)

    @field_validator("body")
    @classmethod
    def body_not_blank(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("body must not be blank")
        return v


class CalendarItemUpdate(BaseModel):
    """Request body for PATCH /calendar/{id} — body text only.

    Intentionally does NOT expose `updated_at` (server-managed; Pitfall P4)
    or `date` (date is keyed via the URL param; rescheduling is not a v2.1
    feature — deferred to CAL-DnD-v22).
    """
    body: str = Field(min_length=1)

    @field_validator("body")
    @classmethod
    def body_not_blank(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("body must not be blank")
        return v


class CalendarItemResponse(BaseModel):
    """Single calendar item as returned by the API.

    `body` is mapped from the ORM model's `notes_md` column via an alias —
    the ORM column name is retained for schema-history reasons (Phase 5
    migration 0011 used `notes_md`), but the API contract surfaces it as
    the more semantically-correct `body`.

    v3.0 Phase 9 (TENANT-04): `company_id` surfaced as optional for debug
    visibility — the URL prefix carries authoritative tenant scope, but the
    response field makes cross-tenant leaks observable.
    """
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    id: uuid.UUID
    company_id: str | None = None  # v3.0 P9 — debug visibility (TENANT-04)
    date: date_type
    body: str | None = Field(default=None, alias="notes_md")
    created_at: datetime
    updated_at: datetime


class CalendarRangeResponse(BaseModel):
    """Wrapper for GET /calendar?start=&end= — items + total count."""
    items: list[CalendarItemResponse]
    total: int
