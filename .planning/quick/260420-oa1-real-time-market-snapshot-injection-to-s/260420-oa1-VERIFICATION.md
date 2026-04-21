---
status: passed
---

# Quick 260420-oa1: Real-time Market Snapshot Injection — Verification Report

**Task Goal:** Inject real-time market data (FRED macro + metalpriceapi metals) into the content agent drafter's Sonnet system prompt at all 3 draft call sites so the drafter cites real current numbers OR uses qualitative language — never invents numbers (current OR historical). DB-cached snapshot refreshed per content_agent cron. Fail-open at every layer.

**Verified:** 2026-04-20
**Status:** PASSED
**Score:** 10/10 must-have truths verified

**Note on worktree:** The specified worktree `agent-a62b33e6` no longer exists as a separate checkout. All three commits (`b28780b`, `a3738e3`, `0dfdc28`) have been merged to main (HEAD=`0dfdc28`). Verification was performed against the main checkout at `/Users/matthewnelson/seva-mining`.

---

## Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | `ContentAgent.run()` fetches a fresh market snapshot once per invocation before drafting | VERIFIED | `content_agent.py:1936` — `self._market_snapshot = await fetch_market_snapshot(session=session)` inside `run()`, before `await self._run_pipeline(...)`. Test `test_run_fetches_snapshot_once_per_invocation` passes with `call_count == 1`. |
| 2 | Drafter Sonnet system prompt contains a CURRENT MARKET SNAPSHOT block with either real numbers or [UNAVAILABLE] placeholders | VERIFIED | `render_snapshot_block()` in `market_snapshot.py:431–493` produces both branches. Tests 10, 11 and integration tests OA1-2, 3, 4, 5 all pass. |
| 3 | All three Sonnet draft call sites receive the same snapshot block | VERIFIED | `content_agent.py:1049` (`_draft_video_caption`), `1119` (`_draft_quote_post`), `1275` (`_research_and_draft`) — all three use `render_snapshot_block(self._market_snapshot)` prepended to system_prompt. Integration tests OA1-2, OA1-3, OA1-4 each assert `"CURRENT MARKET SNAPSHOT"`, `"$2,345.67/oz"`, and the hard instruction substring in the captured system kwarg. |
| 4 | Drafter system prompt includes the hard instruction forbidding invention of ANY specific dollar figures, percentages, yields, or rates (current OR historical) | VERIFIED | `market_snapshot.py:66–71` — `_HARD_INSTRUCTION` contains `"current or historical — that do not appear verbatim in this snapshot"`. Verbatim string: `"Do not cite any specific dollar figures, percentages, yields, or rates — current or historical — that do not appear verbatim in this snapshot."` Both populated and fallback branches append it. Tests 10, 11 assert the exact substring. |
| 5 | FRED source failure does not break metals fetch; metals failure does not break FRED fetch (per-source try/except) | VERIFIED | `fetch_market_snapshot()` uses `asyncio.gather(*tasks, return_exceptions=True)`. Each task's exception becomes a `BaseException` result; the loop checks `isinstance(result, BaseException)` per-label independently. Tests 2, 3 confirm: FRED 500 → metals still populated; metals 429 → FRED still populated. |
| 6 | Missing FRED_API_KEY or METALPRICEAPI_API_KEY logs WARNING and uses [UNAVAILABLE] fallback — no crash | VERIFIED | `market_snapshot.py:254–260` logs WARNING via `_LOG_FMT_KEY` and skips that source. Tests 5, 6 assert `caplog` contains the warning and the skipped-source fields are None while the other source still runs. |
| 7 | A market_snapshots row is written per run with status ok|partial|failed; DB write failure logs ERROR but does NOT abort drafting | VERIFIED | `market_snapshot.py:401–422` — `session.add(row)` / `await session.flush()` inside try/except that logs ERROR on failure and returns the in-memory `snap` regardless. Integration test OA1-7 (`test_snapshot_db_write_failure_still_drafts`) passes. |
| 8 | metalpriceapi reciprocal rate is applied correctly — test asserts $2347.42/oz from rate 0.000426 | VERIFIED | `MetalpriceAPIFetcher.fetch()` at line 212: `gold = (1.0 / xau) if xau else None`. Test 8 asserts `snap["gold_usd_per_oz"] == pytest.approx(2347.42, rel=1e-4)` and `snap["silver_usd_per_oz"] == pytest.approx(27.90, rel=1e-4)`. PASSES. |
| 9 | FRED '.' missing-observation sentinel returns [UNAVAILABLE] for that field (not a crash) | VERIFIED | `_parse_rate_value()` iterates observations and skips `"."` values. `_parse_cpi_yoy()` filters with `o.get("value", ".") != "."`. Test 9 Case A asserts fallback to second obs (4.12); Case B (all dots) asserts `cpi_yoy is None` with no crash. Both PASS. |
| 10 | CPI block in prompt includes the observation date (e.g., 'March 2026 print') | VERIFIED | `_fmt_cpi()` in `render_snapshot_block()` at line 460–471 applies `dt.strftime("%B %Y print")` to `cpi_observation_date`. Tests 10 and 12 both assert `"March 2026 print"` in the rendered block. |

---

## Required Artifacts

| Artifact | Min Lines | Actual Lines | Status | Details |
|----------|-----------|-------------|--------|---------|
| `scheduler/services/market_snapshot.py` | 200 | 493 | VERIFIED | `fetch_market_snapshot()`, `render_snapshot_block()`, `MetalsFetcher`, `MetalpriceAPIFetcher`, `MarketSnapshot` TypedDict all present |
| `scheduler/models/market_snapshot.py` | 20 | 36 | VERIFIED | SQLAlchemy ORM with id, fetched_at, data JSONB, status VARCHAR(16), error_detail JSONB, CHECK constraint, Index |
| `backend/app/models/market_snapshot.py` | 20 | 41 | VERIFIED | Backend mirror using `app.models.base.Base`; same columns + constraints |
| `backend/alembic/versions/0007_add_market_snapshots.py` | 25 | 50 | VERIFIED | `revision="0007"`, `down_revision="0006"`, creates table + index, offline SQL confirmed |
| `scheduler/tests/test_market_snapshot.py` | 250 | 690 | VERIFIED | All 12 locked test cases present and passing |

---

## Key Links

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `content_agent.py::run()` | `market_snapshot.py::fetch_market_snapshot` | `await fetch_market_snapshot(session=session)` at line 1936 | VERIFIED | Placed in `run()` before `_run_pipeline` (see deviation note) |
| `content_agent.py::_research_and_draft` | `market_snapshot.py::render_snapshot_block` | f-string injection at line 1275–1277 | VERIFIED | Block prepended before "You are a senior gold market analyst" |
| `content_agent.py::_draft_video_caption` | `market_snapshot.py::render_snapshot_block` | f-string injection at line 1049–1051 | VERIFIED | Same pattern |
| `content_agent.py::_draft_quote_post` | `market_snapshot.py::render_snapshot_block` | f-string injection at line 1119–1121 | VERIFIED | Same pattern |
| `market_snapshot.py::fetch_market_snapshot` | market_snapshots table | `MarketSnapshotORM` insert at line 409–415 | VERIFIED | Status + data + error_detail written; DB failure caught |
| `config.py::Settings` | `FRED_API_KEY + METALPRICEAPI_API_KEY` | `Optional[str] = None` at lines 32–33 | VERIFIED | Confirmed in scheduler/config.py |

---

## FRED Implementation

- **httpx-direct (not fredapi SDK):** Confirmed — no `fredapi` import anywhere. Uses `httpx.AsyncClient.get` with `FRED_BASE_URL`.
- **Series fetched:** `DGS10`, `DFII10`, `DFF`, `CPIAUCSL` — confirmed in `FRED_SERIES` dict at lines 38–43.
- **CPI uses limit=13:** Confirmed at line 106: `limit = 13 if is_cpi else 2`.
- **CPI observation date captured:** `_parse_cpi_yoy()` returns `(yoy, latest_date_str)` at line 175.
- **"." sentinel guarded:** `_parse_rate_value()` skips `"."` entries; `_parse_cpi_yoy()` filters them. Both test cases in test 9 pass.

---

## metalpriceapi Implementation

- **Reciprocal rate conversion:** `gold = (1.0 / xau)` at line 212. Test 8 asserts `2347.42/oz` from `USDXAU=0.000426`. PASSES.
- **Both XAU and XAG fetched:** `currencies=XAU,XAG` in params at line 204.

---

## render_snapshot_block() Operator Intent Check

**Populated case** header: `"CURRENT MARKET SNAPSHOT (as of {ts})"` (line 448)  
**Fallback case** header: `"CURRENT MARKET SNAPSHOT (fetch failed at {ts})"` (line 446)

**Hard instruction as rendered verbatim:**
> "Do not cite any specific dollar figures, percentages, yields, or rates — current or historical — that do not appear verbatim in this snapshot. Use qualitative language ('near recent highs', 'elevated', 'multi-year high') or omit the claim entirely."

**Operator bug coverage:** The phrase "current or historical" directly prohibits the "$3,500/oz in 2025" class of historical fabrications, not just current-spot claims. The instruction is present in BOTH the populated branch AND the fallback branch (all-None). A model receiving this system prompt cannot cite "Gold hit all-time highs above $3,500/oz in 2025" without violating an explicit verbatim instruction — the historical claim does not appear in the snapshot, so the instruction applies.

---

## Executor Deviation: fetch in run() vs _run_pipeline

**Plan action (Task 2, Step 2c):** Fetch block at top of `_run_pipeline`, before "1. Read config."

**Actual implementation:** Fetch in `run()` at line 1936, before `await self._run_pipeline(session, agent_run)`.

**Impact assessment:** This does NOT break any must-have. Analysis:

1. "Called once per run" — SATISFIED. The fetch is still called exactly once per `ContentAgent.run()` invocation. Test OA1-1 (`test_run_fetches_snapshot_once_per_invocation`) patches `_run_pipeline` as a no-op and asserts `call_count == 1`. This only works because the fetch is in `run()`, not inside `_run_pipeline`. If it were inside the patched `_run_pipeline`, the call count would be 0. The executor's reasoning is sound.

2. "Snapshot available to all 3 drafters" — SATISFIED. The fetch sets `self._market_snapshot` on the instance before any drafter call. All three drafters call `getattr(self, "_market_snapshot", None)` which reads the instance attribute set in `run()`.

3. "Before story ranking/drafting" — SATISFIED. The fetch happens before `_run_pipeline`, so it is temporally prior to all story ranking, classification, and drafting.

4. Fail-open wrapper is in `run()` at lines 1937–1954, covering the full fallback snapshot construction.

**Verdict:** The deviation is correct and necessary. The test spec takes precedence over the implementation notes, and the behavioral contract is fully preserved.

---

## Regression Guard

**`is_gold_relevant_or_systemic_shock` dict contract:** Function signature unchanged at `content_agent.py:460–473`. Returns `{"keep": bool, "reject_reason": str|None, "company": str|None}`. Test OA1-8 (`test_gold_gate_dict_contract_unchanged`) passes.

**Twitter agent:** `git show --stat a3738e3 b28780b` confirms zero changes to `scheduler/agents/twitter_agent.py`.

**No frontend/dashboard changes:** Confirmed — no `.ts`, `.tsx`, or frontend files in either commit's diff.

---

## Alembic Chain

- `backend/alembic/versions/0007_add_market_snapshots.py` has `revision = "0007"`, `down_revision = "0006"`. CONFIRMED.
- Offline SQL generation (`DATABASE_URL=postgresql://... alembic upgrade head --sql`) emits:
  - `-- Running upgrade 0006 -> 0007`
  - `CREATE TABLE market_snapshots (..., CONSTRAINT ck_market_snapshots_ck_market_snapshots_status CHECK (status IN ('ok','partial','failed')))`
  - `CREATE INDEX ix_market_snapshots_fetched_at ON market_snapshots (fetched_at);`
  - `UPDATE alembic_version SET version_num='0007' WHERE alembic_version.version_num = '0006';`

---

## Test Suite Results

| Suite | Command | Result |
|-------|---------|--------|
| Market snapshot unit tests (12 new) | `pytest tests/test_market_snapshot.py` | 12/12 PASS |
| Content agent integration tests (8 new) | `pytest tests/test_content_agent.py` | 82/82 PASS (includes 74 pre-existing) |
| Full scheduler suite | `pytest` | 138/138 PASS |
| Ruff lint | `ruff check .` | All checks passed |
| Alembic offline SQL | `alembic upgrade head --sql` | CREATE TABLE market_snapshots emitted |

---

## Minor Observations (Non-Blocking)

1. **MetalsFetcher is an ABC-style class, not `typing.Protocol`:** `MetalsFetcher` at line 182 inherits from no Protocol base and raises `NotImplementedError`. The plan spec says "protocol" but no test exercises Protocol structural subtyping. The pluggable pattern intent is satisfied — `MetalpriceAPIFetcher` is the concrete implementation with the same interface. This is an INFO-level cosmetic deviation with no functional impact.

2. **`try/except raise exc` pattern:** `_fetch_fred_series()` (line 119) and `MetalpriceAPIFetcher.fetch()` (line 215) both `try/except Exception as exc: raise exc`. This is a no-op catch that the linter could flag. Ruff does not flag it (all checks pass), and the behavior is correct — exceptions bubble to `asyncio.gather(return_exceptions=True)`. No functional issue.

3. **Backend mirror uses `datetime.utcnow` (deprecated):** `backend/app/models/market_snapshot.py:30` uses `default=datetime.utcnow` while the scheduler model uses `default=lambda: datetime.now(timezone.utc)`. Python 3.12 deprecates `utcnow()`. This is a pre-existing pattern in the project's backend models (out of scope for this task to fix) and does not affect migration or runtime behavior for this task.

---

## Human Verification Required

None. All must-haves are verifiable programmatically. The operator follow-ups (provision API keys in Railway, watch first cron cycle) are deployment steps documented in the SUMMARY.md, not verification gaps.

---

## Gaps Summary

None. All 10 must-have truths are VERIFIED. All 5 required artifacts exist and pass all three levels (exists, substantive, wired). All 6 key links are confirmed wired. Full test suite passes (138/138). Ruff clean. Migration SQL verified offline.

---

_Verified: 2026-04-20_
_Verifier: Claude (gsd-verifier)_
