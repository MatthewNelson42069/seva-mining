# Phase 5: Foundation — Tabs + DB + Backend Stubs — Research

**Researched:** 2026-05-18
**Domain:** Alembic migrations, SQLAlchemy 2.0 dual-model parity, FastAPI router stubs, React Router v7 + shadcn Tabs route restructure
**Confidence:** HIGH — all findings grounded in direct codebase reads

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| TAB-01 | Install shadcn `Tabs` into `frontend/src/components/ui/` via `npx shadcn@latest add tabs` | `tabs.tsx` already exists using `@base-ui/react/tabs` — skip install step; use the file already present |
| TAB-02 | Introduce `TabbedDashboard.tsx` — thin wrapper rendering `<TabNav />` then `<Outlet />` under `<AppShell />` | Confirmed: AppShell renders AppHeader + Outlet; TabbedDashboard slots between as a nested route element |
| TAB-03 | Introduce `TabNav.tsx` — 3-NavLink strip with active-state driven by `useLocation()`, NOT local state | Confirmed pitfall: shadcn Tabs value must map from `useLocation().pathname`, not `defaultValue`/state |
| TAB-04 | Restructure `App.tsx`: `/`, `/calendar`, `/viral` nested under `TabbedDashboard`; all v2.0 routes preserved | Confirmed: exact v2.0 route tree read from file; restructure pattern documented below |
| TAB-05 | Leave `AppShell.tsx` and `AppHeader.tsx` structurally unchanged | Confirmed: both files verified; AppShell is 15 lines; AppHeader uses `max-w-[720px]` constraint |
| DB-01 | Alembic 0011: `calendar_items` table with `date DATE NOT NULL` (not DateTime), tag CHECK, ix_calendar_items_date | Template: 0010_add_daily_summaries.py; exact DDL documented below |
| DB-02 | Alembic 0012: `weekly_sweeps` table with JSONB, status CHECK, agent_run_id FK SET NULL, ix_weekly_sweeps_generated_at | Template: same 0010 pattern; exact DDL documented below |
| DB-03 | Dual-model parity: 4 SQLAlchemy model files (2 backend + 2 scheduler), structurally identical, local base imports | Template: backend/app/models/daily_summary.py vs scheduler/models/daily_summary.py confirmed byte-identical |
| DB-04 | Register `calendar_router` and `weekly_sweeps_router` in `backend/app/main.py` | Confirmed: main.py pattern documented; 2 import lines + 2 include_router calls |
| DB-05 | `alembic heads` must return exactly one head before writing migrations; each migration sets prior head as `down_revision` | Confirmed: 0010 is current HEAD; no 0011+ exists; command and verification pattern documented |
</phase_requirements>

---

## Overview

Phase 5 is a pure scaffolding phase: no feature logic, no real data, no UI beyond stubs. It creates the surface that Phases 6 and 7 fill in. The integration surface is narrow but precision-critical — a wrong `down_revision`, a missed `Column(Date)` vs `Column(DateTime)`, or a Tabs value wired to local state instead of `useLocation()` will produce bugs that are invisible in development and only surface in production (Railway UTC server, browser Back/Forward nav).

Everything in this phase is modeled on confirmed v2.0 patterns read directly from the codebase. The planner can treat the v2.0 files as authoritative templates: `0010_add_daily_summaries.py` is the migration template, `backend/app/models/daily_summary.py` and `scheduler/models/daily_summary.py` are the dual-model parity templates (confirmed byte-identical structure), `summaries.py` is the router template, `summaries.ts` is the API client template, and `App.tsx` is the route tree to restructure.

One important discovery: `frontend/src/components/ui/tabs.tsx` already exists. The project does NOT use Radix UI for its tabs primitive — it uses `@base-ui/react` (`^1.3.0` confirmed in `package.json`). The existing `tabs.tsx` exports `Tabs`, `TabsList`, `TabsTrigger`, and `TabsContent` with a `variant="line"` option suitable for a sub-header tab strip. TAB-01's `npx shadcn@latest add tabs` install step can be skipped; the file is already present and uses the correct Tailwind v4 CSS-custom-property color tokens.

---

## v2.0 Patterns to Mirror

### Migration Template (`backend/alembic/versions/0010_add_daily_summaries.py`)

```python
"""Add daily_summaries table for v2.0 daily summary feed.

Phase 1, Plan 01 — Hand-written migration; NO --autogenerate (Pitfall MOD-2:
autogenerate risks emitting spurious DDL against the ApprovalState enum from
migration 0009). Only op.create_table + op.create_check_constraint + op.create_index.

Revision ID: 0010
Revises: 0009
Create Date: 2026-05-05
"""
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "0010"
down_revision = "0009"       # <-- must match `alembic heads` output exactly
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "daily_summaries",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("generated_at", sa.DateTime(timezone=True), nullable=False),
        # ... columns ...
        sa.Column("agent_run_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("agent_runs.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  nullable=False, server_default=sa.text("now()")),
    )
    op.create_check_constraint(
        "ck_daily_summaries_status",
        "daily_summaries",
        "status IN ('completed', 'failed', 'partial')",
    )
    op.create_index(
        "ix_daily_summaries_generated_at",
        "daily_summaries",
        ["generated_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_daily_summaries_generated_at", table_name="daily_summaries")
    op.drop_constraint("ck_daily_summaries_status", "daily_summaries", type_="check")
    op.drop_table("daily_summaries")
```

Key rules from this template:
- Hand-written only; never `--autogenerate`
- `op.create_table` + `op.create_check_constraint` + `op.create_index` are three separate calls (not inline)
- `server_default=sa.text("gen_random_uuid()")` for UUID PKs
- `ondelete="SET NULL"` for FK to `agent_runs.id`
- `downgrade()` reverses in exact reverse order (index → constraint → table)

### Backend Model Template (`backend/app/models/daily_summary.py`)

```python
import uuid
from datetime import datetime

from sqlalchemy import Column, DateTime, ForeignKey, Index, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID

from app.models.base import Base          # <-- backend import path


class DailySummary(Base):
    __tablename__ = "daily_summaries"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    generated_at = Column(DateTime(timezone=True), nullable=False)
    # ... columns ...
    raw_sources_jsonb = Column(JSONB, nullable=True)
    status = Column(String(20), nullable=False, server_default="completed")
    agent_run_id = Column(
        UUID(as_uuid=True),
        ForeignKey("agent_runs.id", ondelete="SET NULL"),
        nullable=True,
    )
    created_at = Column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)

    __table_args__ = (
        Index("ix_daily_summaries_generated_at", "generated_at"),
    )
```

### Scheduler Model Template (`scheduler/models/daily_summary.py`)

Structurally byte-identical to the backend model. The **only difference** is the import path:

```python
from models.base import Base              # <-- scheduler import path (no 'app.' prefix)
```

All column definitions, `__tablename__`, and `__table_args__` are identical. Parity is verified by inspection — if either model diverges, the scheduler writes rows the backend cannot read correctly.

### Router Template (`backend/app/routers/summaries.py`)

```python
from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_user
from app.models.daily_summary import DailySummary
from app.schemas.daily_summary import SummaryCardResponse, SummaryFeedResponse

router = APIRouter(
    prefix="/summaries",
    tags=["summaries"],
    dependencies=[Depends(get_current_user)],  # auth at router level — all routes inherit
)


@router.get("", response_model=SummaryFeedResponse)
async def list_summaries(
    limit: int = Query(60, ge=1, le=120),
    db: AsyncSession = Depends(get_db),
) -> SummaryFeedResponse:
    stmt = (
        select(DailySummary)
        .order_by(DailySummary.generated_at.desc())
        .limit(limit)
    )
    result = await db.execute(stmt)
    rows = result.scalars().all()
    cards = [SummaryCardResponse.model_validate(r) for r in rows]
    return SummaryFeedResponse(summaries=cards, total=len(cards))
```

### Pydantic Schema Template (`backend/app/schemas/daily_summary.py`)

Critical patterns:

```python
from pydantic import BaseModel, ConfigDict
from typing import Literal

class SummaryCardResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)   # required for ORM → Pydantic

    id: uuid.UUID
    status: str   # Literal preferred for enum fields in v2.1 schemas
    # ...

class SummaryFeedResponse(BaseModel):
    summaries: list[SummaryCardResponse]
    total: int
```

For v2.1 schemas, `Literal[...]` is the pattern for enum columns (see `tag` and `status` in calendar/weekly_sweep schemas).

### API Client Template (`frontend/src/api/summaries.ts`)

```typescript
import { useQuery } from '@tanstack/react-query'
import { apiFetch } from './client'

export interface SummaryCard { /* mirrors Pydantic schema */ }
export interface SummaryFeedResponse { summaries: SummaryCard[]; total: number }

export async function getSummaries(limit = 60): Promise<SummaryFeedResponse> {
  return apiFetch<SummaryFeedResponse>(`/summaries?limit=${limit}`)
}

export function useSummaries(limit = 60) {
  return useQuery({
    queryKey: ['summaries', limit],
    queryFn: () => getSummaries(limit),
    refetchInterval: 5 * 60 * 1000,
    refetchOnWindowFocus: false,
    staleTime: 5 * 60 * 1000,
  })
}
```

### App.tsx Current Route Tree (read directly — v2.0 state)

```tsx
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import { ProtectedRoute } from '@/components/layout/ProtectedRoute'
import { AppShell } from '@/components/layout/AppShell'
import { LoginPage } from '@/pages/LoginPage'
import { DigestPage } from '@/pages/DigestPage'
import { SettingsPage } from '@/pages/SettingsPage'
import { SummaryFeedPage } from '@/pages/SummaryFeedPage'

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/login" element={<LoginPage />} />
        <Route element={<ProtectedRoute />}>
          <Route element={<AppShell />}>
            <Route path="/" element={<SummaryFeedPage />} />
            <Route path="/queue" element={<Navigate to="/" replace />} />
            <Route path="/agents/:slug" element={<Navigate to="/" replace />} />
            <Route path="/digest" element={<DigestPage />} />
            <Route path="/settings" element={<SettingsPage />} />
          </Route>
        </Route>
      </Routes>
    </BrowserRouter>
  )
}
```

### AppShell.tsx (confirmed — 15 lines; MUST NOT change)

```tsx
import { Outlet } from 'react-router-dom'
import { AppHeader } from './AppHeader'

export function AppShell() {
  return (
    <div className="min-h-screen bg-background flex flex-col">
      <AppHeader />
      <main className="flex-1 overflow-auto">
        <Outlet />
      </main>
    </div>
  )
}
```

TAB-05 locks this file unchanged. `TabbedDashboard` renders as a nested route element under `AppShell`, not inside `AppShell` itself.

### AppHeader.tsx (confirmed — 35 lines; MUST NOT change)

Uses `max-w-[720px] mx-auto` constraint for brand + logout row. The `TabNav` sub-header strip must live outside this constraint in its own `<nav>` element rendered by `TabbedDashboard` — NOT inside AppHeader. TabNav uses its own width (full-width or `max-w-[720px]` matching content below).

---

## Alembic Migration Specifics

### Current Head Verification

```bash
cd backend && alembic heads
```

**Expected output:** `0010 (head)`

This must be verified as the first action. If anything other than exactly `0010 (head)` is returned, STOP — investigate before writing any migration files.

Existing migrations: `0001` through `0010_add_daily_summaries.py`. Confirmed: no `0011+` files exist.

### Migration 0011: `calendar_items`

```python
"""Add calendar_items table — v2.1 Phase 5.

Hand-written; NO --autogenerate.

Revision ID: 0011
Revises: 0010
Create Date: 2026-05-18
"""
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from alembic import op

revision = "0011"
down_revision = "0010"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "calendar_items",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("date", sa.Date(), nullable=False),           # Date NOT DateTime
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("notes_md", sa.Text(), nullable=True),
        sa.Column("tag", sa.String(length=20), nullable=True),  # nullable; CHECK below
        sa.Column("created_at", sa.DateTime(timezone=True),
                  nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True),
                  nullable=False, server_default=sa.text("now()")),
    )
    op.create_check_constraint(
        "ck_calendar_items_tag",
        "calendar_items",
        "tag IN ('thread', 'video', 'podcast', 'tweet', 'idea', 'other')",
    )
    op.create_index(
        "ix_calendar_items_date",
        "calendar_items",
        ["date"],
    )


def downgrade() -> None:
    op.drop_index("ix_calendar_items_date", table_name="calendar_items")
    op.drop_constraint("ck_calendar_items_tag", "calendar_items", type_="check")
    op.drop_table("calendar_items")
```

**Critical: `sa.Date()` not `sa.DateTime(timezone=True)`** — the `date` column stores a day only, no time component. Using `DateTime` causes UTC off-by-one on Railway (PT user + UTC server). See Pitfall CAL-DATE below.

### Migration 0012: `weekly_sweeps`

```python
"""Add weekly_sweeps table — v2.1 Phase 5.

Hand-written; NO --autogenerate.

Revision ID: 0012
Revises: 0011
Create Date: 2026-05-18
"""
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from alembic import op

revision = "0012"
down_revision = "0011"       # chains off 0011, not 0010
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "weekly_sweeps",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("generated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("week_start", sa.Date(), nullable=False),
        sa.Column("week_end", sa.Date(), nullable=False),
        sa.Column("reddit_top_md", sa.Text(), nullable=True),
        sa.Column("story_virality_md", sa.Text(), nullable=True),
        sa.Column("content_angles_md", sa.Text(), nullable=True),
        sa.Column("raw_sources_jsonb",
                  postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False,
                  server_default="completed"),
        sa.Column("error_text", sa.Text(), nullable=True),
        sa.Column("agent_run_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("agent_runs.id", ondelete="SET NULL"), nullable=True),
    )
    op.create_check_constraint(
        "ck_weekly_sweeps_status",
        "weekly_sweeps",
        "status IN ('completed', 'failed', 'partial')",
    )
    op.create_index(
        "ix_weekly_sweeps_generated_at",
        "weekly_sweeps",
        ["generated_at"],
        postgresql_ops={"generated_at": "DESC"},   # matches query ORDER BY generated_at DESC
    )


def downgrade() -> None:
    op.drop_index("ix_weekly_sweeps_generated_at", table_name="weekly_sweeps")
    op.drop_constraint("ck_weekly_sweeps_status", "weekly_sweeps", type_="check")
    op.drop_table("weekly_sweeps")
```

Note: `week_start` and `week_end` are `sa.Date()` (day only) — same reason as `calendar_items.date`.

### Downgrade Strategy

Both migrations ship together in Phase 5. They are two separate files with independent downgrade operations. To roll back:

```bash
alembic downgrade -1   # removes 0012 (weekly_sweeps)
alembic downgrade -1   # removes 0011 (calendar_items)
```

Or to go directly to pre-Phase-5:

```bash
alembic downgrade 0010
```

### DB-05 Pre-Check Command

Before writing any migration file:

```bash
cd backend && alembic heads
# Must output: 0010 (head)
# If multiple heads or different revision: STOP and investigate
```

After writing both files, verify the chain is intact before running:

```bash
cd backend && alembic check
# Should report: No new upgrade operations detected. (chain is consistent)
```

---

## SQLAlchemy Model Specifics

### `backend/app/models/calendar_item.py` (new file)

```python
import uuid
from datetime import datetime, date

from sqlalchemy import Column, Date, DateTime, Index, String, Text
from sqlalchemy.dialects.postgresql import UUID

from app.models.base import Base


class CalendarItem(Base):
    __tablename__ = "calendar_items"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    date = Column(Date, nullable=False)                 # Date NOT DateTime
    title = Column(Text, nullable=False)
    notes_md = Column(Text, nullable=True)
    tag = Column(String(20), nullable=True)             # CHECK in migration
    created_at = Column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)

    __table_args__ = (
        Index("ix_calendar_items_date", "date"),
    )
```

Note: No `onupdate=` on `updated_at` — Postgres has no `ON UPDATE` equivalent for column defaults. The PATCH handler sets `updated_at = datetime.utcnow()` explicitly.

### `backend/app/models/weekly_sweep.py` (new file)

```python
import uuid
from datetime import datetime

from sqlalchemy import Column, Date, DateTime, ForeignKey, Index, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID

from app.models.base import Base


class WeeklySweep(Base):
    __tablename__ = "weekly_sweeps"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    generated_at = Column(DateTime(timezone=True), nullable=False)
    week_start = Column(Date, nullable=False)
    week_end = Column(Date, nullable=False)
    reddit_top_md = Column(Text, nullable=True)
    story_virality_md = Column(Text, nullable=True)
    content_angles_md = Column(Text, nullable=True)
    raw_sources_jsonb = Column(JSONB, nullable=True)
    status = Column(String(20), nullable=False, server_default="completed")
    error_text = Column(Text, nullable=True)
    agent_run_id = Column(
        UUID(as_uuid=True),
        ForeignKey("agent_runs.id", ondelete="SET NULL"),
        nullable=True,
    )

    __table_args__ = (
        Index("ix_weekly_sweeps_generated_at", "generated_at"),
    )
```

### `scheduler/models/calendar_item.py` (new file)

Structurally identical to `backend/app/models/calendar_item.py`. **Only difference**: import path.

```python
from models.base import Base              # scheduler path — no 'app.' prefix
```

All other lines — `__tablename__`, every `Column(...)` definition, `__table_args__` — must be character-for-character identical to the backend version.

### `scheduler/models/weekly_sweep.py` (new file)

Structurally identical to `backend/app/models/weekly_sweep.py`. Same rule: only the import path changes.

```python
from models.base import Base              # scheduler path
```

### Dual-Model Parity Proof

Current confirmed parity for `daily_summary.py`:
- Both files: `__tablename__ = "daily_summaries"`
- Both files: identical column list in identical order
- Both files: identical `__table_args__` tuple
- Difference: `from app.models.base import Base` (backend) vs `from models.base import Base` (scheduler)

New models for Phase 5 must follow this exact pattern. The scheduler model for `weekly_sweep` is immediately used by Phase 7's `weekly_sweeper.py`. The scheduler model for `calendar_item` is not used by any Phase 5-7 code (no scheduler writes to `calendar_items`) but must exist per the dual-model parity convention.

---

## Backend Router + Schema Specifics

### `backend/app/routers/calendar.py` — Phase 5 stub

```python
"""Calendar router stub — Phase 5.

Full CRUD (GET/POST/PATCH/DELETE) ships in Phase 6.
Phase 5 stubs: GET returns {items:[], total:0}; POST returns 501.
Auth gated at router level via Depends(get_current_user).
"""
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_user

router = APIRouter(
    prefix="/calendar",
    tags=["calendar"],
    dependencies=[Depends(get_current_user)],    # auth at router level
)


@router.get("")
async def list_calendar_items(
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Phase 5 stub — returns empty list. Full implementation in Phase 6."""
    return {"items": [], "total": 0}
```

The POST/PATCH/DELETE routes are NOT stubbed in Phase 5 — only the GET is needed for the frontend to confirm 200 OK with empty payload. This avoids creating incomplete endpoint signatures that Phase 6 will need to fully replace.

### `backend/app/routers/weekly_sweeps.py` — Phase 5 stub

```python
"""Weekly sweeps router stub — Phase 5.

Full GET /weekly-sweeps?limit=12 ships in Phase 7.
Phase 5 stub: returns {sweeps:[], total:0}.
Auth gated at router level via Depends(get_current_user).
"""
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_user

router = APIRouter(
    prefix="/weekly-sweeps",
    tags=["weekly-sweeps"],
    dependencies=[Depends(get_current_user)],    # auth at router level
)


@router.get("")
async def list_weekly_sweeps(
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Phase 5 stub — returns empty list. Full implementation in Phase 7."""
    return {"sweeps": [], "total": 0}
```

No Pydantic schemas are needed in Phase 5 for the stubs. Schemas (`backend/app/schemas/calendar.py`, `backend/app/schemas/weekly_sweep.py`) are Phase 6 and Phase 7 deliverables respectively. Phase 5 stubs return raw `dict` — FastAPI serializes without a `response_model`.

---

## main.py Integration

Current `backend/app/main.py` ends its router registrations at line 63:

```python
app.include_router(summaries_router)  # Phase 1, Plan 04 (v2.0 daily summary feed)
```

Add two lines immediately after, maintaining the comment-per-router convention:

```python
from app.routers.calendar import router as calendar_router
from app.routers.weekly_sweeps import router as weekly_sweeps_router

# ... (existing imports above) ...

app.include_router(summaries_router)       # Phase 1, Plan 04 (v2.0 daily summary feed)
app.include_router(calendar_router)        # Phase 5 (v2.1 Content Calendar)
app.include_router(weekly_sweeps_router)   # Phase 5 (v2.1 Weekly Viral Sweeper)
```

The imports go in the import block at the top of the file alongside existing router imports. The `include_router` calls go at the bottom of the router registration block.

---

## Frontend Route Restructure Specifics

### Route Tree: Before → After

**Before (v2.0):**
```tsx
<Route element={<ProtectedRoute />}>
  <Route element={<AppShell />}>
    <Route path="/" element={<SummaryFeedPage />} />
    <Route path="/queue" element={<Navigate to="/" replace />} />
    <Route path="/agents/:slug" element={<Navigate to="/" replace />} />
    <Route path="/digest" element={<DigestPage />} />
    <Route path="/settings" element={<SettingsPage />} />
  </Route>
</Route>
```

**After (Phase 5):**
```tsx
<Route element={<ProtectedRoute />}>
  <Route element={<AppShell />}>

    {/* 3-tab surface — TabbedDashboard renders TabNav + Outlet */}
    <Route element={<TabbedDashboard />}>
      <Route index element={<SummaryFeedPage />} />                     // Tab 1: /
      <Route path="calendar" element={<ContentCalendarPage />} />       // Tab 2: /calendar
      <Route path="viral" element={<WeeklyViralSweeperPage />} />       // Tab 3: /viral
    </Route>

    {/* v2.0 bookmark-grace redirects — preserved, inside ProtectedRoute */}
    <Route path="/queue" element={<Navigate to="/" replace />} />
    <Route path="/agents/:slug" element={<Navigate to="/" replace />} />

    {/* v2.0 retained surfaces — no tabs here */}
    <Route path="/digest" element={<DigestPage />} />
    <Route path="/settings" element={<SettingsPage />} />

  </Route>
</Route>
```

**Critical preservation rules:**
1. `/queue` and `/agents/:slug` redirects remain inside `<ProtectedRoute />` — they must not escape to the public route level
2. `/digest` and `/settings` remain outside `<TabbedDashboard />` — tabs only appear on the 3-tab surface
3. `<AppShell />` is not modified — `TabbedDashboard` nests inside its `<Outlet />`

### `TabbedDashboard.tsx` (new file)

Analogous to `AppShell.tsx` but for tabs only:

```tsx
import { Outlet } from 'react-router-dom'
import { TabNav } from './TabNav'

export function TabbedDashboard() {
  return (
    <>
      <TabNav />
      <Outlet />
    </>
  )
}
```

Does not wrap in a container div — `AppShell`'s `<main className="flex-1 overflow-auto">` already provides the outer wrapper.

### `TabNav.tsx` (new file) — useLocation-driven active state

The existing `tabs.tsx` uses `@base-ui/react/tabs` (not Radix UI). The `TabNav` component should use React Router `<NavLink>` styled to match the `variant="line"` visual from `TabsList`/`TabsTrigger`, or wrap the Base UI primitives with `useLocation()` driving the `value` prop.

**Recommended approach: React Router NavLink with Tailwind styling**

This is simpler and more correct — NavLink's `isActive` prop handles active state without needing to sync shadcn/Base UI Tabs internal state with router state:

```tsx
import { NavLink } from 'react-router-dom'

const tabs = [
  { to: '/',         label: 'News Funnel' },
  { to: '/calendar', label: 'Content Calendar' },
  { to: '/viral',    label: 'Weekly Viral' },
]

export function TabNav() {
  return (
    <nav className="border-b border-zinc-800 bg-zinc-900">
      <div className="max-w-[720px] mx-auto px-4 flex gap-1">
        {tabs.map(({ to, label }) => (
          <NavLink
            key={to}
            to={to}
            end={to === '/'}   // 'end' required for index route to not match /calendar
            className={({ isActive }) =>
              `px-3 py-2 text-sm font-medium transition-colors border-b-2 -mb-px ` +
              (isActive
                ? 'border-amber-500 text-white'
                : 'border-transparent text-zinc-400 hover:text-zinc-100')
            }
          >
            {label}
          </NavLink>
        ))}
      </div>
    </nav>
  )
}
```

**Why NavLink over Base UI Tabs controlled by useLocation():**
- Base UI `<Tabs value={...}>` can be driven by `useLocation()` (map pathname → value string), but requires an `onValueChange` that calls `navigate()` in the opposite direction — bidirectional sync with two potential drift points
- `<NavLink>` gives URL-native active state for free; `isActive` updates on every navigation including browser Back/Forward
- The `variant="line"` visual from `tabs.tsx` can be replicated with the Tailwind classes above without importing the Base UI component

**`end={to === '/'}` is required:** Without `end`, NavLink for `"/"` matches every route (since every pathname starts with `/`). The `end` prop makes the index route's active check exact.

### Stub Page Components

Both stub pages use `React.lazy()` from day one to establish the code-splitting boundary:

In `App.tsx`:
```tsx
const ContentCalendarPage = React.lazy(() => import('@/pages/ContentCalendarPage'))
const WeeklyViralSweeperPage = React.lazy(() => import('@/pages/WeeklyViralSweeperPage'))
```

Wrap the `<TabbedDashboard />` route subtree in `<Suspense>`:
```tsx
<Route element={<Suspense fallback={<div className="p-8 text-zinc-500">Loading…</div>}><TabbedDashboard /></Suspense>}>
```

`frontend/src/pages/ContentCalendarPage.tsx`:
```tsx
export default function ContentCalendarPage() {
  return <div className="max-w-[720px] mx-auto px-4 py-8 text-zinc-400">Content Calendar — coming soon</div>
}
```

`frontend/src/pages/WeeklyViralSweeperPage.tsx`:
```tsx
export default function WeeklyViralSweeperPage() {
  return <div className="max-w-[720px] mx-auto px-4 py-8 text-zinc-400">Weekly Viral Sweeper — coming soon</div>
}
```

Stub pages use default exports because they're loaded via `React.lazy()` (which requires a default export).

### Existing `tabs.tsx` — Key Finding

`frontend/src/components/ui/tabs.tsx` already exists and uses `@base-ui/react/tabs` (not Radix UI). TAB-01's `npx shadcn@latest add tabs` install step is **a no-op** — the file is already present. The planner should skip the install task. The existing file exports `{ Tabs, TabsList, TabsTrigger, TabsContent, tabsListVariants }` with CSS-custom-property color tokens (`bg-background`, `text-foreground`) — correct for Tailwind v4.

The `variant="line"` option on `TabsList` is the correct style for a sub-header tab strip (no background pill, underline indicator via `after:` pseudo-element in `TabsTrigger`).

---

## Lock ID 1019 Integration

### Where in `worker.py`

**This must be the first code change made in Phase 5** — before any router stub, before any migration file, before any frontend change.

Current `JOB_LOCK_IDS` dict (lines 100-113 of `scheduler/worker.py`):

```python
JOB_LOCK_IDS: dict[str, int] = {
    "midday_digest": 1005,
    "sub_breaking_news": 1010,
    "sub_threads": 1011,
    "sub_quotes": 1013,
    "sub_infographics": 1014,
    "sub_gold_media": 1015,
    "sub_gold_history": 1016,
    "daily_summary": 1017,
    "daily_summary_prune": 1018,
}
```

**Add one entry at the end of the dict, before the closing `}`:**

```python
JOB_LOCK_IDS: dict[str, int] = {
    "midday_digest": 1005,
    "sub_breaking_news": 1010,
    "sub_threads": 1011,
    "sub_quotes": 1013,
    "sub_infographics": 1014,
    "sub_gold_media": 1015,
    "sub_gold_history": 1016,
    "daily_summary": 1017,
    "daily_summary_prune": 1018,
    # v2.1 Phase 5: weekly_sweeper advisory lock (ID 1019 confirmed next-free)
    "weekly_sweeper": 1019,
}
```

### OPS-02 Assertion Verification

The assertion at line 118 is:

```python
assert len(set(JOB_LOCK_IDS.values())) == len(JOB_LOCK_IDS), (
    f"JOB_LOCK_IDS has duplicate values: {JOB_LOCK_IDS}"
)
```

After adding `"weekly_sweeper": 1019`:
- `JOB_LOCK_IDS.values()` = `{1005, 1010, 1011, 1013, 1014, 1015, 1016, 1017, 1018, 1019}` — 10 distinct values
- `len(JOB_LOCK_IDS)` = 10
- Assertion passes: `10 == 10` ✓

The assertion runs at **module import time** — the worker process will refuse to start if there's a collision. After adding 1019, verify this by importing the module locally: `python -c "import worker"` should succeed without AssertionError.

### Ordering Constraint

The lock dict entry is the only Phase 5 change to `worker.py`. No factory function (`_make_weekly_sweeper_job`) and no `build_scheduler()` registration are added in Phase 5 — those are Phase 7 deliverables. Phase 5 only reserves the lock ID so the OPS-02 assertion guards against a future Phase 7 collision.

Lock IDs 1010-1016 are confirmed dead code (sub-agents deregistered in Phase 4, source files retained). 1019 is the next free integer above the highest active ID (1018). Never reuse 1010-1016 for new jobs.

---

## Phase 5-Relevant Pitfalls

### P1: CRITICAL — `down_revision` chain mismatch breaks Railway deploy

**What goes wrong:** If 0011's `down_revision` is set to `"0009"` (wrong) instead of `"0010"` (correct), `alembic upgrade head` raises `CommandError: Can't locate revision identified by '0009'` and the Railway deploy fails before the app starts.

**Prevention:** Run `alembic heads` as the first task. Copy the output verbatim into `down_revision`. Do not rely on memory.

### P2: CRITICAL — `Column(Date)` not `Column(DateTime)` for `calendar_items.date`

**What goes wrong:** Using `sa.DateTime(timezone=True)` instead of `sa.Date()` for `calendar_items.date` stores a full timestamp. Pydantic serializes it with timezone context. A user in PT clicks "May 20" at 11pm → `2026-05-21T06:00:00Z` stored → calendar item appears on May 21 in the grid.

**Prevention:** `sa.Date()` in the migration, `Column(Date, ...)` in the model, `datetime.date` in the Pydantic schema. Test with `TZ=UTC pytest` — create an item with `date="2026-05-20"`, read it back, assert `response["date"] == "2026-05-20"`.

### P3: CRITICAL — Tab value driven by local state desyncs from URL on browser nav

**What goes wrong:** If `TabNav` uses `defaultValue="news-funnel"` or tracks active tab in React state + `onValueChange → navigate()`, browser Back/Forward changes the URL but does not re-render the tab highlight. The wrong tab appears highlighted while the correct page content renders via React Router `<Outlet />`.

**Prevention:** Use `<NavLink isActive>` (NavLink approach) or drive any Tabs `value` prop from `useLocation().pathname`. Never use `defaultValue` or local state for which tab is active.

### P4: HIGH — v2.0 redirects escape `ProtectedRoute` if restructure is careless

**What goes wrong:** Moving `<AppShell />` nesting can accidentally push `/queue` and `/agents/:slug` redirects outside the `<ProtectedRoute />` subtree, making them publicly accessible.

**Prevention:** The `<Route path="/queue">` and `<Route path="/agents/:slug">` entries stay inside `<Route element={<ProtectedRoute />}>`. Verify by visiting `/queue` while logged out — should redirect to `/login`, not to `/`.

### P5: HIGH — `TabNav` width conflicts with `AppHeader`'s `max-w-[720px]`

**What goes wrong:** If `TabNav` is placed inside `AppHeader.tsx` (which is `max-w-[720px]`), three tab labels plus the brand mark and logout button overflow at 720px.

**Prevention:** `TabNav` renders in `TabbedDashboard.tsx` as its own `<nav>` bar below `AppHeader`. It is never inserted inside `AppHeader`. AppHeader is frozen per TAB-05.

### P6: HIGH — shadcn Tabs from wrong branch renders with wrong classes

**What goes wrong:** Installing shadcn Tabs from the Radix/v3 branch produces a component that conflicts with Tailwind v4 CSS-custom-property tokens.

**Prevention:** This pitfall is already resolved. The existing `tabs.tsx` uses `@base-ui/react/tabs` with CSS-custom-property color tokens. No new install is needed. The planner should note this explicitly in the task list.

### P7: HIGH — Dual-model parity silently diverges

**What goes wrong:** If `scheduler/models/calendar_item.py` adds a column that `backend/app/models/calendar_item.py` is missing (or vice versa), Phase 7's weekly_sweeper writes rows the backend API cannot correctly deserialize.

**Prevention:** Write both model files side-by-side and do a character-level diff. The only permitted difference is the import path. Add a parity assertion test for both table pairs.

### P8: MEDIUM — `React.lazy()` boundary not established from day one

**What goes wrong:** If stub pages are imported statically in `App.tsx`, the Calendar and Viral page chunks are loaded on every auth — even for users who only visit the News Funnel tab. When Phase 6 and 7 add substantive components, this becomes a noticeable cold-start cost.

**Prevention:** Import stub pages via `React.lazy()` in Phase 5. The lazy boundary is established now and naturally preserved through Phase 6 and 7 replacements.

---

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | Vitest 4.1.x (frontend); pytest + pytest-asyncio (backend) |
| Config file | `frontend/vitest.config.ts` (or via `vite.config.ts`) |
| Frontend quick run | `cd frontend && npm run test` |
| Backend quick run | `cd backend && pytest -x` |

Existing test files confirmed: `frontend/src/pages/__tests__/DigestPage.test.tsx`, `SettingsPage.test.tsx`, `PerAgentQueuePage.test.tsx`.

### Phase 5 Requirements → Test Map

| Req ID | Behavior | Test Type | Command / Verification |
|--------|----------|-----------|------------------------|
| DB-05 | `alembic heads` returns exactly one head `0010` | Manual shell | `cd backend && alembic heads` |
| DB-01 | Migration 0011 upgrades cleanly, downgrades cleanly | Manual shell | `alembic upgrade head && alembic downgrade -1` |
| DB-02 | Migration 0012 upgrades cleanly, downgrades cleanly | Manual shell | `alembic upgrade head && alembic downgrade -1` |
| DB-03 | Backend and scheduler models have identical columns | Unit test | `pytest tests/test_model_parity.py` (Wave 0 gap) |
| DB-04 | `GET /calendar` returns 200 OK `{"items":[], "total":0}` | Integration smoke | `curl -H "Authorization: Bearer $TOKEN" $API/calendar` |
| DB-04 | `GET /weekly-sweeps` returns 200 OK `{"sweeps":[], "total":0}` | Integration smoke | `curl -H "Authorization: Bearer $TOKEN" $API/weekly-sweeps` |
| TAB-01 | `tabs.tsx` exists with correct exports | File check | `ls frontend/src/components/ui/tabs.tsx` (already confirmed) |
| TAB-03 | Active tab matches URL on Back/Forward | Manual browser | Navigate `/` → `/calendar` → browser Back; assert News Funnel tab highlighted |
| TAB-04 | `/queue` redirect still works post-restructure | Manual browser | Visit `/queue` while auth'd; assert redirect to `/` + News Funnel tab active |
| TAB-05 | AppShell + AppHeader unchanged | Diff | `git diff frontend/src/components/layout/AppShell.tsx AppHeader.tsx` — should be empty |
| SWEEP-03 | OPS-02 assertion passes after adding 1019 | Unit test | `python -c "import worker"` in scheduler directory — no AssertionError |

### Wave 0 Gaps

- [ ] `backend/tests/test_model_parity.py` — asserts `CalendarItem.__tablename__` + column names match between scheduler and backend; same for `WeeklySweep` — covers DB-03
- [ ] `backend/tests/test_stubs.py` — tests `GET /calendar` and `GET /weekly-sweeps` return 200 + expected empty payload through auth — covers DB-04

*(The scheduler already has tests in a `tests/` directory based on the existing test pattern; parity tests fit naturally there.)*

---

## Open Questions for Planner

1. **Stub page export style:** `SummaryFeedPage.tsx` uses a named export (`export function SummaryFeedPage`). `React.lazy()` requires a default export. The stub pages should use default exports (`export default function ContentCalendarPage`). In Phase 6, when the stub is replaced with the real page, the export style should be consistent. Planner should decide: convert all lazy-loaded pages to default exports, or use a `export { ContentCalendarPage as default }` re-export at the bottom.

2. **`TabNav` max-width:** Should `TabNav`'s inner container use `max-w-[720px]` (matching `AppHeader` and `SummaryFeedPage`) or full-width? The recommendation is `max-w-[720px]` for visual alignment, but this is a judgment call the planner can finalize.

3. **`Suspense` placement:** The lazy-load `<Suspense>` boundary should wrap the `<TabbedDashboard />` route element. But `TabbedDashboard` itself renders `TabNav` + `Outlet` — the `Suspense` fallback will replace the entire tab surface including the tab strip while loading. If that's undesirable, `Suspense` can be placed inside `TabbedDashboard` around just the `<Outlet />`. Planner should decide placement.

4. **`alembic check` availability:** `alembic check` was added in Alembic 1.9. The project uses Alembic 1.14.x (per CLAUDE.md), so `alembic check` is available. Confirm it's in PATH via `cd backend && alembic check` before relying on it in the validation step.

5. **Backend test database:** The `GET /calendar` and `GET /weekly-sweeps` integration smoke tests require a live database with both migrations applied. If the backend test suite uses a test database (separate from dev), `alembic upgrade head` must be run against that test database before the stub tests pass. This is not a Phase 5 concern per se — but the planner should ensure the smoke test step happens after `alembic upgrade head` in the task sequence.

---

## Sources

### Primary (HIGH confidence — direct codebase reads)

- `backend/alembic/versions/0010_add_daily_summaries.py` — migration template (hand-written pattern, server_default, op.create_check_constraint, downgrade reverse-order)
- `backend/app/models/daily_summary.py` — backend model template (UUID pk, Date/DateTime columns, Index in __table_args__, FK with ondelete)
- `scheduler/models/daily_summary.py` — scheduler model template (confirmed byte-identical to backend model except import path)
- `backend/app/routers/summaries.py` — router template (APIRouter args, auth dependency, select pattern, model_validate)
- `backend/app/schemas/daily_summary.py` — Pydantic v2 schema template (ConfigDict from_attributes, Literal, SummaryFeedResponse wrapper)
- `backend/app/main.py` — include_router registration pattern + import block
- `scheduler/worker.py` lines 100-120 — JOB_LOCK_IDS dict, OPS-02 assertion at line 118, confirmed 1019 is next-free
- `scheduler/worker.py` lines 232-277 — _make_daily_summary_job factory pattern (lazy import, inner async def job(), engine.connect() + with_advisory_lock)
- `frontend/src/App.tsx` — v2.0 route tree (all 5 routes confirmed)
- `frontend/src/components/layout/AppShell.tsx` — 15 lines confirmed; AppHeader + Outlet only
- `frontend/src/components/layout/AppHeader.tsx` — max-w-[720px] confirmed; frozen per TAB-05
- `frontend/src/api/summaries.ts` — API client template (apiFetch, useQuery options)
- `frontend/src/components/ui/tabs.tsx` — already exists; uses @base-ui/react/tabs (not Radix); TAB-01 install is a no-op
- `frontend/package.json` — confirmed: `@base-ui/react ^1.3.0`, `react-router-dom ^7.13.2`, `@tanstack/react-query ^5.96.0`, `tailwindcss ^4.2.2`, `vitest ^4.1.2`
- `backend/alembic/versions/` directory listing — confirmed 0010 is the last migration; no 0011+

### Secondary (MEDIUM confidence — cross-referenced with codebase)

- `.planning/research/ARCHITECTURE.md` — DB schema DDL, scheduler factory pattern, route restructure design
- `.planning/research/PITFALLS.md` — 32 pitfalls; Phase 5 cluster: migration chain (P28), dual-model parity (P26), Tabs value sync (P13), lock 1019 first (P25), Column(Date) (P16)
- `.planning/research/STACK.md` — asyncpraw verdict, shadcn Tabs install confirmation, "no new stack" verdict
- `.planning/research/SUMMARY.md` — architecture decisions, phase build order

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — all v2.0 patterns read directly from files; no new dependencies in Phase 5
- Migration structure: HIGH — 0010 template read directly; DDL for 0011/0012 derived from REQUIREMENTS.md + ARCHITECTURE.md
- Frontend route restructure: HIGH — App.tsx current tree read directly; restructure pattern derived from ARCHITECTURE.md
- Lock 1019 placement: HIGH — worker.py dict read directly; 1019 confirmed next-free
- Dual-model parity: HIGH — both daily_summary.py files read and confirmed byte-identical; pattern is clear

**Research date:** 2026-05-18
**Valid until:** 2026-06-18 (stable stack; no fast-moving dependencies in Phase 5)
