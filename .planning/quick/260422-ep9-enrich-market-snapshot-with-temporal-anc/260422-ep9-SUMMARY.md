---
task: 260422-ep9
type: quick
status: complete
branch: quick/260422-ep9-market-snapshot-temporal-anchors
files_modified:
  - scheduler/services/market_snapshot.py
  - scheduler/tests/test_market_snapshot.py
tests: 98 passed (90 baseline + 8 new)
ruff: clean
---

# Quick Task 260422-ep9: Enrich market_snapshot with temporal anchors — Summary

## One-liner
`MarketSnapshot` TypedDict gains 5 gold temporal anchors + `at_52w_high` binary + `tracking_since` (computed via a single SQL window query against the `market_snapshots` JSONB table BEFORE the current row is added) so Sonnet drafters can fact-check "at highs / ATH / $X intraday" directional claims against real reference data, and `_HARD_INSTRUCTION` forbids that phrase family unless `at_52w_high: true` appears in the snapshot.

## Origin bug
The 2026-04-22 `breaking_news` draft hallucinated "GOLD whipsaws $100+ intraday" and "gold and equities hitting highs SIMULTANEOUSLY today" when gold was actually *giving back* Trump Taco rally gains after Warsh boosted the dollar. The snapshot had no temporal anchor, so the drafter had nothing to check its directional claims against — it exploited the old hard instruction's "near recent highs" allowance to assert "hitting highs today".

## Implementation

### TypedDict extension (7 new fields, all Optional, total=False preserved)
```python
gold_24h_high:    Optional[float]
gold_24h_low:     Optional[float]
gold_prior_close: Optional[float]
gold_52w_high:    Optional[float]
gold_52w_low:     Optional[float]
at_52w_high:      Optional[bool]  # None → [UNAVAILABLE], strict equality when known
tracking_since:   Optional[str]   # ISO date, matches cpi_observation_date style
```

### SQL window query (`_compute_gold_anchors`, new async helper)
- Extracts `gold_usd_per_oz` from the JSONB `data` column via `cast(...data["gold_usd_per_oz"].astext, Float)` — **NOT** a top-level column (critical ORM note from planner).
- Filters to `status in ('ok', 'partial')` AND `gold_usd_per_oz is not null` (status='failed' rows carry null gold and must not contaminate).
- One combined `SELECT` with 5 labelled aggregates (24h MAX/MIN, 52w MAX/MIN, `MIN(fetched_at)` for tracking_since) + one ORDER BY/LIMIT 1 for `prior_close` (can't compose with aggregates).
- Runs BEFORE `session.add(row)` — so `prior_close` reflects the last-written snapshot, not the in-flight one.
- Strict equality for `at_52w_high`: `current_spot >= row.w52_high` (inclusive, no fuzzy tolerance).
- Fail-open: any exception → anchors default dict of all-None + ERROR log.

### Render block extension
Two new lines inserted between `Spot silver:` and `10Y Treasury yield:`:
```
- Gold 24h range: $4,785.12 – $4,821.00/oz (prior close: $4,809.50/oz)
- Gold 52w range: $3,211.00 – $4,821.00/oz (at_52w_high: true)
```

Fallback labels when anchors are null:
- Both null + no tracking_since → `[UNAVAILABLE — first snapshot]`
- Both null + tracking_since set → `[UNAVAILABLE — tracking since YYYY-MM-DD, N day(s) of history]` (singular/plural handled)

### `_HARD_INSTRUCTION` extension
Kept paragraph 1 unchanged. Appended a second paragraph verbatim from CONTEXT.md decisions:
- Forbids "at highs / at a new high / at an all-time high / breaking out / at a record / hitting a new record" unless `at_52w_high: true`.
- Forbids specific intraday moves ("$100+ intraday", "whipsaws $X", "X% move today") unless 24h high-low span supports the magnitude.
- Hedge fallbacks: "elevated", "near recent highs", "volatile intraday".

## Tests (8 new, all passing)

| # | Test | What it locks |
|---|------|--------------|
| 13 | `test_anchors_populated_full_history` | All 7 anchor fields populated; current (4816.39) < 52w_high (4821.00) → at_52w_high = False |
| 14 | `test_anchors_empty_history` | Brand-new DB → all 5 anchors None, at_52w_high = None (not False), tracking_since = None |
| 15 | `test_anchors_partial_history_24h_only` | 24h populated, 52w None → at_52w_high = None, tracking_since set |
| 16 | `test_render_block_anchors_populated` | "Gold 24h range:" + "Gold 52w range:" lines with values + position (after silver, before 10Y) |
| 17 | `test_render_block_anchors_empty` | Both lines show `[UNAVAILABLE — first snapshot]`, no `$None` leaks |
| 18 | `test_render_block_anchors_partial_with_tracking_since` | 24h real + 52w fallback `tracking since 2026-04-21 ... of history` |
| 19 | `test_at_52w_high_strict_equality` | current == 52w_high → true; current = 0.999 × 52w_high → false |
| 20 | `test_hard_instruction_contains_forbidden_phrases` | All 9 forbidden-phrase tokens + `at_52w_high: true` reference present in module constant |

## Verification

### Gates (all passed)
- `uv run ruff check .` → All checks passed.
- `uv run pytest -x` → **98 passed** (90 baseline + 8 new), zero failures, zero errors.
- Plan's `verify` command (market_snapshot + 6 downstream drafter test files) → **47 passed**, no regression.

### Validation greps (all pass)
| Grep | Hits | Purpose |
|------|-----:|---------|
| `gold_52w_high\|gold_24h_high\|gold_prior_close\|at_52w_high` in service | 24 | TypedDict fields exist |
| `breaking out\|at a new high\|at an all-time high\|hitting a new record` in service | 2 | Hard-instruction forbidden phrases present |
| `24h range\|52w range\|prior close` in service | 3 | Render_block emits new lines |
| `tracking since` in service | 3 | Graceful fallback label implemented |
| `at_52w_high` in service | 12 | Binary signal emitted + referenced in hard-instruction |
| `timedelta(hours=24)\|timedelta(weeks=52)` in service | 4 | SQL window bounds in place |
| `gold_52w_high\|gold_prior_close\|at_52w_high` in `scheduler/agents/` | **0** | Anti-regression: drafters do NOT reference anchors by name (opaque text contract preserved) |

### Semantic spot-check
Rendered the three CONTEXT.md target cases (populated, partial gap, first snapshot) in a REPL — all match the target shape exactly, down to the en-dash separator and "of history" pluralization.

## Deviations from plan

None. Plan executed exactly as written. A small addition: the imports were moved to the module header (`from sqlalchemy import Float, and_, cast, func, select` at top of file) rather than inside `_compute_gold_anchors`, for a cleaner import surface and to avoid repeated-import overhead on every fetch. The `from models.market_snapshot import ...` stays inside the function because it's a cross-module ORM dependency intentionally lazy-imported (matches the pattern already used in the DB-write block at `session.add` site).

## Backward compatibility verified

- All 12 pre-existing `test_market_snapshot.py` tests still pass unchanged.
- All 6 downstream drafter test files (`test_breaking_news`, `test_threads`, `test_long_form`, `test_quotes`, `test_content_init`, `test_infographics`) pass unchanged — they patch `fetch_market_snapshot` to return None or minimal dicts, and `render_snapshot_block` uses `.get()` throughout with None-safe fallback labels, so none hit an `AttributeError`.
- No Alembic migration required. No new ORM columns. No new scheduled job. No new API integrations.
- No drafter (`scheduler/agents/content/*.py`) touched. Anti-regression grep confirms zero references to the new anchor field names in drafter code — the snapshot block flows verbatim through `render_snapshot_block` as opaque text.

## Locked CONTEXT.md decisions honored

| # | Decision | Honored how |
|---|----------|-------------|
| 1 | No backfill (graceful `[UNAVAILABLE]`) | `_fmt_gold_range` emits `[UNAVAILABLE — first snapshot]` / `tracking since ... of history` |
| 2 | Gold only, 5 anchors (silver deferred) | Only gold fields added; no silver anchors |
| 3 | On-every-fetch SQL window query | `_compute_gold_anchors` runs inline in `fetch_market_snapshot`, no new job, no new columns |
| 4 | Strict equality for `at_52w_high` | `current_spot >= row.w52_high`, no fuzzy tolerance |
| 5 | Extended `_HARD_INSTRUCTION` with forbidden-phrase list | Two-paragraph string with 6 forbidden phrases + intraday-move clause + `at_52w_high: true` reference |
