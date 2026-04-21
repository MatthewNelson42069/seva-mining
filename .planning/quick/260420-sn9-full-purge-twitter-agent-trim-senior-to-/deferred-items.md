# Deferred items (quick-260420-sn9)

Pre-existing issues discovered during sn9 execution that are out of scope:

## backend/alembic/versions/0007_add_market_snapshots.py

**Issue:** Ruff I001 — import block unsorted. `sqlalchemy` and `alembic` imports not alphabetized.

**Origin:** Introduced in commit `b28780b` (quick-260420-oa1 — market snapshot service).

**Why deferred:** Pre-existing at sn9 start; unrelated to Twitter/Senior purge. Follow-up
task should run `uv run ruff check . --fix` across backend alembic/versions to clean up.

**Impact:** `ruff check .` returns 1 error on this file regardless of sn9 changes.
Backend tests pass. No functional regression.

**RESOLVED 2026-04-21:** Fixed via `uv run ruff check . --fix` — one-line change
(blank line between third-party and first-party imports). Backend `ruff check .`
now clean; `pytest -q` → 66 passed, 5 skipped.
