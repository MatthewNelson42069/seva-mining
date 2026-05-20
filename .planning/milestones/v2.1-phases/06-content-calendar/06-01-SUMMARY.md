---
phase: 06-content-calendar
plan: "01"
subsystem: backend-schema-contract
tags: [pydantic-v2, alembic, sqlalchemy-parity, requirements-rescope]
requires:
  - "phase-05-plan-02 (Alembic 0011/0012 baseline DDL)"
  - "phase-05-plan-03 (dual-model parity scaffolding)"
provides:
  - "backend/alembic/versions/0013_calendar_title_nullable_unique_date.py"
  - "backend/app/schemas/calendar.py (CalendarItemCreate/Update/Response/RangeResponse)"
  - "calendar_items.title nullable + UNIQUE(date) DB invariant"
  - "REQUIREMENTS.md CAL-02..CAL-08 rephrased for single-text-blob model"
affects:
  - "Phase 06-02 (CRUD router) — schemas + DB invariant ready"
  - "Phase 06-03 (frontend) — {date, body} API contract locked"
  - "Verification step — REQUIREMENTS.md wording matches new scope"
tech-stack:
  added: []
  patterns:
    - "Pydantic v2 `populate_by_name=True` for alias safety against minor-version regressions"
    - "Static-content migration tests instead of live SQLite alembic round-trip (Postgres DDL primitives not portable)"
key-files:
  created:
    - "backend/alembic/versions/0013_calendar_title_nullable_unique_date.py"
    - "backend/app/schemas/calendar.py"
    - "backend/tests/test_calendar_migration_0013.py"
    - "backend/tests/test_calendar_schemas.py"
  modified:
    - ".planning/REQUIREMENTS.md"
    - "backend/app/models/calendar_item.py"
    - "scheduler/models/calendar_item.py"
decisions:
  - "body field in API response is aliased from notes_md ORM column — keeps DB schema name from Phase 5 while exposing semantically-correct API name"
  - "no title in API request bodies — server may write synthetic title or leave NULL forever (title column kept for backward-compat with Phase 5 migration 0011)"
  - "no tag in API request bodies — CAL-TAGS-v22 deferred per 06-CONTEXT.md"
  - "static content-check tests for migration 0013 instead of live Alembic SQLite round-trip — SQLite does not support all Postgres DDL primitives; live round-trip deferred to Railway deploy"
  - "populate_by_name=True on CalendarItemResponse — defensive against Pydantic minor-version alias-handling regressions"
metrics:
  duration_seconds: 161
  completed_at: "2026-05-19T02:51:55Z"
  tasks: 4
  files_changed: 7
  commits: 6
requirements_addressed: [CAL-02, CAL-03, CAL-06, CAL-07, CAL-08]
---

# Phase 6 Plan 01: Schema Contract Lock-In Summary

Locked the v2.1 Content Calendar data contract before any router or UI work — rephrased five CAL-* requirements to the simplified single-text-blob shape, shipped Alembic migration 0013 (title nullable + UNIQUE(date)), updated both SQLAlchemy parity models, and defined Pydantic v2 request/response schemas with explicit `populate_by_name=True` alias safety.

## What Was Built

Single source of truth for the Phase 6 Calendar API contract. Future plans (router in 06-02, hooks/page in 06-03) build directly against `app.schemas.calendar` and the migrated `calendar_items` table without ambiguity. The DB now enforces "one row per date" via a UNIQUE constraint, which is defense-in-depth against double-POST races even though the app contract also tracks single-row-per-date via the upsert-by-date flow.

## Tasks Completed

| Task | Name                                                     | Commits                      | Files                                                                                                            |
| ---- | -------------------------------------------------------- | ---------------------------- | ---------------------------------------------------------------------------------------------------------------- |
| 1    | Rephrase CAL-02..CAL-08 in REQUIREMENTS.md              | `c0ce858`                    | `.planning/REQUIREMENTS.md`                                                                                      |
| 2    | Alembic migration 0013 + static check tests             | `45f04fe` (RED), `4aaae25` (GREEN) | `backend/alembic/versions/0013_calendar_title_nullable_unique_date.py`, `backend/tests/test_calendar_migration_0013.py` |
| 3    | Update parity SQLAlchemy models                         | `001536b`                    | `backend/app/models/calendar_item.py`, `scheduler/models/calendar_item.py`                                       |
| 4    | Pydantic v2 calendar schemas                             | `38c9bd8` (RED), `059a07f` (GREEN) | `backend/app/schemas/calendar.py`, `backend/tests/test_calendar_schemas.py`                                       |

## Requirements Rephrasing — Diff Snippet

```diff
- - [ ] **CAL-02**: System exposes `POST /calendar` accepting `{date, title, notes_md?, tag?}`...
+ - [ ] **CAL-02**: System exposes `POST /calendar` accepting `{date, body}` and returning `201 + CalendarItemResponse`; `body` is a non-empty `str` stored in `notes_md`...

- - [ ] **CAL-03**: System exposes `PATCH /calendar/{item_id}` accepting partial fields...
+ - [ ] **CAL-03**: System exposes `PATCH /calendar/{item_id}` accepting `{body}` (only)...

- - [ ] **CAL-06**: System renders calendar items as chips inside their day cell with tag-color-coded backgrounds...
+ - [ ] **CAL-06**: System renders the per-day text body inside its day cell as plain text with `whitespace-pre-wrap`...

- - [ ] **CAL-07**: System renders a "+ Add" hover-reveal button on empty cells...
+ - [ ] **CAL-07**: System makes every day cell click-to-focus...

- - [ ] **CAL-08**: System renders an edit dialog (shadcn `Dialog`)...
+ - [ ] **CAL-08**: System auto-saves on textarea blur — on `onBlur`, if text differs from last-saved value: POST.../PATCH.../DELETE...
```

CAL-01, CAL-04, CAL-05, CAL-09, CAL-10 are byte-unchanged.

## Migration 0013 Round-Trip Evidence

`alembic heads` confirms the chain advances correctly:

```
$ uv run alembic heads
0013 (head)
```

Live `alembic upgrade head` / `downgrade -1` round-trip against dev DB was attempted from the executor shell, but `DATABASE_URL` is not loaded in this shell environment (`sqlalchemy.exc.NoSuchModuleError: Can't load plugin: sqlalchemy.dialects:driver`). The live round-trip is deferred to the next Railway deploy where the env var is wired. The 4 static content-check tests gate the migration file's correctness in the meantime:

```
tests/test_calendar_migration_0013.py ....                               [100%]
test_migration_0013_revision_chain
test_migration_0013_upgrade_alters_title_nullable
test_migration_0013_upgrade_adds_unique_date_constraint
test_migration_0013_downgrade_reverses_changes
```

## Parity Diff Evidence

```
$ diff <(sed 's|from app.models.base|from BASE|' backend/app/models/calendar_item.py) \
       <(sed 's|from models.base|from BASE|' scheduler/models/calendar_item.py)
(no output — exits 0)
```

The two files differ only on the `from {app.models|models}.base import Base` line.

## Schema Test Names + Pass Status

```
tests/test_calendar_schemas.py ......                                    [100%]
test_create_accepts_date_and_body              PASSED  (P1: date is datetime.date, NEVER datetime)
test_create_rejects_blank_body                 PASSED  (Field(min_length=1) + body_not_blank validator)
test_create_parses_date_string                 PASSED  (Pydantic v2 date parser on "YYYY-MM-DD")
test_update_only_exposes_body                  PASSED  (P4: updated_at/date/tag/title absent from model_fields)
test_response_serializes_from_orm_attributes   PASSED  (from_attributes + alias notes_md→body)
test_range_response_wraps_list                 PASSED  (items + total count wrapper)
```

## Combined Verification

```
$ cd backend && uv run pytest tests/test_calendar_migration_0013.py tests/test_calendar_schemas.py tests/test_model_parity.py
14 passed in 0.02s

$ cd backend && uv run pytest
137 passed, 5 skipped, 15 warnings in 1.33s
```

Full backend suite green — no regression from the model nullable change or the new schemas.

## Decisions Made

1. **`body` is aliased from `notes_md` in `CalendarItemResponse`** — keeps the DB schema column name from Phase 5 migration 0011 stable while exposing the more semantically-correct `body` to the API. The alias is the only response-side mapping; the request schemas just use `body` directly (router will write to `notes_md` explicitly).
2. **No `title` in API request bodies** — title column stays nullable forever per migration 0013. Server may write a synthetic title if useful later (e.g. first 80 chars of body) without breaking the contract.
3. **No `tag` in API request bodies or response** — CAL-TAGS-v22 deferred per 06-CONTEXT.md. Tag column stays but is unused.
4. **Static migration content-check tests instead of live Alembic round-trip** — SQLite in-memory doesn't support all Postgres DDL primitives we use; the static checks gate the file's correctness at test time, and the live round-trip happens on Railway deploy.
5. **`populate_by_name=True` on `CalendarItemResponse`** — defensive against Pydantic minor-version regressions in how alias-only fields are handled. The plan calls this out as a future-proofing line and the acceptance check greps for it explicitly.

## Deviations from Plan

None — plan executed exactly as written. One environmental note (not a deviation): the live Alembic upgrade/downgrade against dev DB was deferred to Railway deploy because `DATABASE_URL` is not in the executor shell environment. This is contemplated by the plan ("If the dev DB is unavailable... document it as deferred to deploy").

## Self-Check: PASSED

Files created/modified — all present:

- `.planning/REQUIREMENTS.md` — FOUND (CAL-02..CAL-08 rephrased)
- `backend/alembic/versions/0013_calendar_title_nullable_unique_date.py` — FOUND
- `backend/app/models/calendar_item.py` — FOUND (title nullable=True, UniqueConstraint present)
- `scheduler/models/calendar_item.py` — FOUND (identical to backend mod-Base-import)
- `backend/app/schemas/calendar.py` — FOUND
- `backend/tests/test_calendar_migration_0013.py` — FOUND
- `backend/tests/test_calendar_schemas.py` — FOUND

Commits — all present in `git log`:

- `c0ce858` — FOUND (Task 1: REQUIREMENTS rephrase)
- `45f04fe` — FOUND (Task 2 RED: failing migration test)
- `4aaae25` — FOUND (Task 2 GREEN: migration 0013)
- `001536b` — FOUND (Task 3: parity models)
- `38c9bd8` — FOUND (Task 4 RED: failing schema tests)
- `059a07f` — FOUND (Task 4 GREEN: calendar schemas)
