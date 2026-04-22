# Quick Task 260422-ep9: Enrich market_snapshot with temporal anchors — Context

**Gathered:** 2026-04-22
**Status:** Ready for planning

<domain>
## Task Boundary

Enrich `scheduler/services/market_snapshot.py` with **temporal anchor data** (24h/52w highs/lows + prior close) so Sonnet drafters can fact-check directional claims like "hitting highs today / ATH / breakout / intraday $X move" against real reference values.

**Origin bug:** 2026-04-22 breaking_news draft claimed "GOLD whipsaws $100+ intraday" and "gold and equities hitting highs SIMULTANEOUSLY today". Gold did NOT hit highs today — the article was about gold *giving back* Trump Taco rally gains after Warsh boosted dollar. The current snapshot has no temporal anchor to catch this class of hallucination, and the existing `_HARD_INSTRUCTION` explicitly permits "near recent highs" as qualitative hedge — drafter exploited that to claim "hitting highs SIMULTANEOUSLY today".

**Goal:** Drafter sees gold_52w_high, prior_close, 24h range in every prompt; `_HARD_INSTRUCTION` forbids "hit highs / ATH / record / breakout / intraday $X move" unless the snapshot emits a clean `at_52w_high: true` binary signal.

**Data source:** Our own `market_snapshots` table (populated hourly-ish via `fetch_market_snapshot()` since 2026-04-21). No new APIs.

</domain>

<decisions>
## Implementation Decisions

### Backfill strategy
**Decision:** No backfill. Graceful `[UNAVAILABLE — tracking since YYYY-MM-DD, N days of history]` for any anchor window longer than available data.

- Zero new API cost.
- Anchors become real once the `market_snapshots` table has >24h / >52w of data.
- Matches Option B framing: no new API integrations.
- Drafter hard instruction must remain binding even when anchors are [UNAVAILABLE] — they must hedge ("near recent highs") rather than assert ("at highs").

### Anchor scope
**Decision:** **Gold only — 5 anchors.**

- `gold_24h_high: Optional[float]`
- `gold_24h_low: Optional[float]`
- `gold_prior_close: Optional[float]` (most recent row before current, regardless of how long ago)
- `gold_52w_high: Optional[float]`
- `gold_52w_low: Optional[float]`

No silver anchors (defer to future task if silver drafts become a problem). Keeps prompt block tight.

### Compute cadence
**Decision:** **On every fetch, SQL window query.**

- Inside `fetch_market_snapshot()`, after the metalpriceapi call succeeds and before returning the `MarketSnapshot` dict, query `market_snapshots` table for:
  - `MAX(gold_usd_per_oz), MIN(gold_usd_per_oz)` WHERE `fetched_at >= NOW() - interval '24 hours'` → 24h high/low
  - `MAX(gold_usd_per_oz), MIN(gold_usd_per_oz)` WHERE `fetched_at >= NOW() - interval '52 weeks'` → 52w high/low
  - Most recent `gold_usd_per_oz` WHERE `fetched_at < NOW() - interval '1 second'` ORDER BY fetched_at DESC LIMIT 1 → prior_close
  - `MIN(fetched_at)` → used to compute `tracking_since` for graceful fallback labels
- Single transaction, read-only. `market_snapshots.fetched_at` index already exists (created in oa1 migration 0007).
- ~8760 rows/year → trivial query.
- No new ORM columns, no new migration, no new scheduled job.

### ATH tolerance
**Decision:** **Strict equality only.**

- Snapshot emits `at_52w_high: true` iff `current_spot >= gold_52w_high` (inclusive equality for the case where current IS the new 52w high).
- Same rule for `at_52w_low: true` (inverse).
- No fuzzy tolerance. Drafter gets a clean binary signal in the prompt block.
- If `gold_52w_high is None` (< 52w of history), emit `at_52w_high: [UNAVAILABLE]` (hedge required, not true/false).

### Hard instruction extension
**Decision (Claude's Discretion):** Extend `_HARD_INSTRUCTION` with explicit forbidden-phrase list:

Current text (lines 66-71):
> "Do not cite any specific dollar figures, percentages, yields, or rates — current or historical — that do not appear verbatim in this snapshot. Use qualitative language ('near recent highs', 'elevated', 'multi-year high') or omit the claim entirely."

Add a second paragraph:
> "Do NOT claim the current price is 'at highs', 'at a new high', 'at an all-time high', 'breaking out', 'at a record', or 'hitting a new record' unless the snapshot emits `at_52w_high: true`. Do NOT claim specific intraday moves ('$100+ intraday', 'whipsaws $X', 'X% move today') unless the 24h high minus 24h low in this snapshot supports the magnitude. When in doubt, use qualitative hedges ('elevated', 'near recent highs', 'volatile intraday') or omit the claim."

### Claude's Discretion
- Exact format of the snapshot prompt block lines for the new anchors (keep compact, one field per line, consistent with existing `- Spot gold: $X,XXX.XX/oz` pattern).
- Whether to show `at_52w_high: true/false/[UNAVAILABLE]` as a dedicated line or fold it into the gold_52w_high line inline.
- Test fixture shape for the new DB query (seed with 3-5 rows spanning timeframes, assert compute logic).
- Whether to add a dedicated `MarketSnapshot` TypedDict field for the computed `tracking_since: Optional[date]` or keep it prompt-only.

</decisions>

<specifics>
## Specific Ideas

**Target snapshot block shape (post-ep9, populated case):**

```
CURRENT MARKET SNAPSHOT (as of 2026-04-22 20:00 UTC)
- Spot gold: $4,816.39/oz
- Spot silver: $79.58/oz
- Gold 24h range: $4,785.12 – $4,821.00/oz (prior close: $4,809.50/oz)
- Gold 52w range: $3,211.00 – $4,821.00/oz (at_52w_high: true)
- 10Y Treasury yield: 4.23%
- 10Y TIPS (real) yield: 1.87%
- Fed funds effective rate: 4.33%
- CPI (YoY): 3.12% (March 2026 print)

Do not cite any specific dollar figures, percentages, yields, or rates — 
current or historical — that do not appear verbatim in this snapshot. 
Use qualitative language ('near recent highs', 'elevated', 'multi-year high') 
or omit the claim entirely.

Do NOT claim the current price is 'at highs', 'at a new high', 'at an 
all-time high', 'breaking out', 'at a record', or 'hitting a new record' 
unless the snapshot emits `at_52w_high: true`. Do NOT claim specific 
intraday moves ('$100+ intraday', 'whipsaws $X', 'X% move today') unless 
the 24h high minus 24h low in this snapshot supports the magnitude. 
When in doubt, use qualitative hedges ('elevated', 'near recent highs', 
'volatile intraday') or omit the claim.
```

**Target snapshot block shape (post-ep9, partial gap — 24h ok, 52w unavailable):**

```
CURRENT MARKET SNAPSHOT (as of 2026-04-22 20:00 UTC)
- Spot gold: $4,816.39/oz
- Spot silver: $79.58/oz
- Gold 24h range: $4,785.12 – $4,821.00/oz (prior close: $4,809.50/oz)
- Gold 52w range: [UNAVAILABLE — tracking since 2026-04-21, 1 day of history]
- 10Y Treasury yield: ...
- ...

[Hard instructions unchanged — still binding.]
```

**Target snapshot block shape (post-ep9, full gap — brand-new DB):**

```
CURRENT MARKET SNAPSHOT (as of 2026-04-22 20:00 UTC)
- Spot gold: $4,816.39/oz
- Spot silver: $79.58/oz
- Gold 24h range: [UNAVAILABLE — first snapshot]
- Gold 52w range: [UNAVAILABLE — first snapshot]
- ...
```

**Key starting files:**

- `scheduler/services/market_snapshot.py` (L30-88 MarketSnapshot TypedDict, L62-71 _HARD_INSTRUCTION, L222+ fetch_market_snapshot, L430-492 render_snapshot_block)
- `scheduler/models.py` (MarketSnapshot ORM model — for the SQL window query)
- `scheduler/tests/test_market_snapshot.py` (existing test suite — add anchor-compute tests + render-block shape tests + hard-instruction regex tests)
- `scheduler/agents/content/breaking_news.py` (L56 — sees enriched block verbatim, no code change needed; existing tests should continue to pass)

**Validation greps (for planner to convert to plan.must_haves):**

1. `grep "gold_52w_high\|gold_24h_high\|gold_prior_close\|at_52w_high" scheduler/services/market_snapshot.py` — fields defined in MarketSnapshot TypedDict.
2. `grep "breaking out\|at a new high\|at an all-time high\|hitting a new record" scheduler/services/market_snapshot.py` — hard instruction extended with forbidden phrases.
3. `grep "24h range\|52w range\|prior close" scheduler/services/market_snapshot.py` — render_snapshot_block emits the new lines.
4. `grep "tracking since" scheduler/services/market_snapshot.py` — graceful fallback label implemented.
5. `grep "at_52w_high" scheduler/services/market_snapshot.py` — binary signal emitted.
6. `uv run ruff check .` (scheduler) clean.
7. `uv run pytest -x` (scheduler) green with +5 new tests covering: compute logic against seeded market_snapshots fixtures (spanning timestamps inside/outside 24h and 52w windows), graceful [UNAVAILABLE] on empty history, render_block output shape with populated anchors, render_block fallback label includes tracking_since date, hard instruction extension regex.

</specifics>

<canonical_refs>
## Canonical References

- `scheduler/services/market_snapshot.py` — oa1 origin (quick-260420-oa1 delivered 2026-04-21) + pwh fix (quick-260420-pwh 2026-04-21 — reciprocal-rate inversion correction at metalpriceapi boundary).
- `alembic/versions/0007_add_market_snapshots.py` — `market_snapshots` table schema + `fetched_at` index that makes the new SQL window query cheap.
- `.planning/quick/260420-oa1-real-time-market-snapshot-injection-to-s/` — original rationale for hard-instruction injection pattern; ep9 extends the same pattern with temporal reference data.

</canonical_refs>
