---
task: quick-260420-nnh
verified: 2026-04-20T17:45:00Z
status: passed
verdict: PASS
---

# Quick Task 260420-nnh Verification Report

**Task:** Content agent rejects stories whose primary subject is a specific gold/mining company
**Verified:** 2026-04-20
**Verdict:** PASS — all checklist items satisfied

---

## Checklist Results

### 1. `is_gold_relevant_or_systemic_shock()` return shape

PASS. Function at `content_agent.py:459` returns `dict` with shape `{"keep": bool, "reject_reason": str|None, "company": str|None}` (not bool).

Three return paths:
- `_KEEP = {"keep": True, "reject_reason": None, "company": None}` — bypass and fail-open path
- `{"keep": False, "reject_reason": "not_gold_relevant", "company": None}` — off-topic/listicle
- `{"keep": False, "reject_reason": "primary_subject_is_specific_miner", "company": company}` — specific miner

### 2. Haiku prompt content

PASS. Prompt at `content_agent.py:510–553` covers:

**Reject examples — all 5 operator fixtures named:**
- `'B2Gold expects lower Q2 output from Goose mine' (B2Gold)` — present line 530
- `'McLaren Completes Drone MAG Program at Blue Quartz Gold Property' (McLaren)` — present line 531
- `'Barrick acquires Kinross in $8B deal' (Barrick+Kinross)` — present line 532
- `'Newmont posts record Q2, raises guidance' (Newmont)` — present line 533
- `'Seva Mining hits 12g/t gold at Timmins drill hole 42' (Seva Mining)` — present line 534

**Keep examples — all 6 operator fixtures named:**
- Goldman forecasts (Goldman is a source) — present line 543
- Central banks / World Gold Council — present line 544
- Gold miners index (sector-wide) — present line 545
- ETF flows — present line 546
- US CPI / Fed cut odds — present line 547
- China rare-earth restrictions — present line 548

**Financial-institution allowlist — explicitly named:**
Goldman Sachs, BlackRock, JPMorgan, Morgan Stanley, World Gold Council, IMF, Federal Reserve, central banks — present line 519–522

### 3. `max_tokens=100`

PASS. `content_agent.py:508` — `max_tokens=100`. Not 5, not 60.

### 4. Fail-open paths

PASS.

- Config bypass (`content_gold_gate_enabled=false`): returns `_KEEP` at line 498, no LLM call.
- Anthropic API exception: `except Exception` at line 585 returns `_KEEP`.
- Malformed JSON (`json.loads` failure): inner `except (json.JSONDecodeError, ValueError)` at line 560 returns `_KEEP` with warning log.

All three paths return `{"keep": True, "reject_reason": None, "company": None}`.

### 5. Production call site

PASS. Pipeline loop at `content_agent.py:1630–1654`:

- Calls `gate_decision = await is_gold_relevant_or_systemic_shock(story, gate_config, client=self.anthropic)`
- Branches on `gate_decision["keep"]`
- When `reason == "primary_subject_is_specific_miner"` and `company` is truthy, logs:
  `"ContentAgent: rejected story %r — primary subject is specific miner (%s)."` (title:120, company)
- When `reason == "primary_subject_is_specific_miner"` and no company, logs without parenthetical
- `skipped_by_gate` counter preserved; end-of-run summary log preserved at line 1745

### 6. Test file — 10 prior call sites migrated to dict contract

PASS. All 10 existing gate call sites use `result["keep"]`, `result["reject_reason"]`, `result["company"]` assertions. Zero stale `assert result is True/False` against the gate function. (The two remaining `assert result is False` are in `check_compliance()` tests — correct.)

Migrated tests confirmed:
1. `test_gate_accepts_direct_gold_story` (was n4f `test_gate_accepts_gold_price_story`) — dict contract
2. `test_gate_accepts_systemic_shock_strait_of_hormuz` (was n4f `test_gate_accepts_systemic_shock_story`) — dict contract
3. `test_gate_rejects_generic_option_traders` (was n4f `test_gate_rejects_off_topic_story`) — dict contract
4. `test_gate_rejects_private_credit` — dict contract
5. `test_gate_fails_open_on_api_error` — dict contract
6. `test_gate_bypassed_when_disabled` — dict contract
7. `test_gate_rejects_listicle_top_5_gold_stocks` — dict contract
8. `test_gate_rejects_listicle_best_performing` — dict contract
9. `test_gate_rejects_single_company_earnings_under_nnh` (inverted from rqx) — dict contract, reject shape
10. `test_gate_rejects_barrick_ma_under_nnh` (inverted from rqx) — dict contract, reject shape

### 7. Inverted rqx tests

PASS.

`test_gate_rejects_single_company_earnings_under_nnh` (line 822):
- Renamed from `test_gate_accepts_single_company_earnings`
- Stub returns `{"is_gold_relevant": True, "primary_subject_is_specific_miner": True, "company": "Newmont"}`
- Asserts `result["keep"] is False`, `result["reject_reason"] == "primary_subject_is_specific_miner"`, `result["company"] == "Newmont"`
- Inline comment: `# quick-260420-nnh: inverts rqx-era behavior...`

`test_gate_rejects_barrick_ma_under_nnh` (line 1068):
- Renamed from `test_gate_accepts_single_company_ma`
- Stub returns `{"is_gold_relevant": True, "primary_subject_is_specific_miner": True, "company": "Barrick"}`
- Asserts `result["keep"] is False`, `result["reject_reason"] == "primary_subject_is_specific_miner"`, `"Barrick" in result["company"]`
- Inline comment: `# quick-260420-nnh: inverts rqx-era behavior...`

NOTE: The Barrick inversion test uses a different fixture title ("Barrick Announces $5B Acquisition of X Mining") rather than the plan's exact example ("Barrick acquires Kinross in $8B deal"). The operator-exact Kinross fixture is covered separately by `test_gate_rejects_barrick_kinross_ma` (line 1139). Both tests are present and pass — the coverage is complete, just split across two tests.

### 8. 11 new operator-fixture tests

PASS. All 11 tests present and passing:

**5 reject tests:**
- `test_gate_rejects_b2gold_production_update` (line 1095) — title matches operator example exactly
- `test_gate_rejects_mclaren_drone_program` (line 1117) — title matches operator example exactly
- `test_gate_rejects_barrick_kinross_ma` (line 1139) — "Barrick acquires Kinross in $8B deal"
- `test_gate_rejects_newmont_guidance` (line 1162) — "Newmont posts record Q2, raises guidance"
- `test_gate_rejects_seva_mining_drill_result` (line 1184) — "Seva Mining hits 12g/t gold at Timmins drill hole 42"

**6 keep tests:**
- `test_gate_keeps_goldman_forecast_as_source` (line 1206)
- `test_gate_keeps_wgc_central_bank_report` (line 1228)
- `test_gate_keeps_miners_index_sector_move` (line 1250)
- `test_gate_keeps_etf_flows` (line 1272)
- `test_gate_keeps_cpi_macro` (line 1294)
- `test_gate_keeps_rare_earth_geopolitics` (line 1316)

### 9. Malformed JSON fail-open robustness test

PASS. `test_gate_fails_open_on_malformed_json` (line 1338) — stubs Haiku to return bare `"yes"`, asserts `result["keep"] is True`, `result["reject_reason"] is None`, `result["company"] is None`.

### 10. Test suite

PASS. `cd scheduler && uv run pytest tests/test_content_agent.py -x` — **62 passed in 0.61s**, 0 failed, 0 errors.

### 11. Ruff

PASS. `uv run ruff check scheduler/` — `All checks passed!`

### 12. Git commits

PASS. `git log --oneline main..worktree-agent-a7d2e2cd`:

```
a81ef50 docs(quick-260420-nnh): record nnh task in STATE.md quick tasks log
15df673 feat(content-agent): reject stories whose primary subject is a specific miner (quick-260420-nnh)
```

Both commits present with correct messages. `15df673` is the implementation; `a81ef50` is the STATE.md log entry.

### 13. Scope check — twitter_agent.py

PASS. `git diff main worktree-agent-a7d2e2cd -- scheduler/agents/twitter_agent.py` — empty. No changes to Twitter agent.

### 14. Operator intent — Seva Mining not exempted

PASS. The Haiku prompt explicitly lists `'Seva Mining hits 12g/t gold at Timmins drill hole 42' (Seva Mining)` as a REJECT example with no conditional carve-out. The prompt does not exempt Seva Mining from the specific-miner rule. A prompt evaluation of "Seva Mining hits 12g/t gold at Timmins drill hole 42" would plausibly return `{"is_gold_relevant": true, "primary_subject_is_specific_miner": true, "company": "Seva Mining"}`, triggering rejection.

---

## Notes and Observations

**Prompt schema vs return schema:** The Haiku prompt requests `{"is_gold_relevant", "primary_subject_is_specific_miner", "company"}` while the function returns `{"keep", "reject_reason", "company"}`. The translation is clean and explicit in lines 568–583. This is a valid design — the prompt uses semantically clearer field names for the model; the caller gets the application-level contract. No concern.

**Barrick inversion test title divergence:** The plan called for inverting a test using the exact Barrick/Kinross title. The inverted test (`test_gate_rejects_barrick_ma_under_nnh`) uses a slightly different stub title, but the operator-exact "Barrick acquires Kinross in $8B deal" fixture is covered by the separate `test_gate_rejects_barrick_kinross_ma` test. Full coverage is achieved.

**No new dependencies added.** Model remains `claude-3-5-haiku-latest`. Single LLM call per invocation preserved.

---

_Verified: 2026-04-20_
_Verifier: Claude (gsd-verifier)_
