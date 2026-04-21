---
phase: quick-260420-pwh
plan: 01
subsystem: scheduler/services, scheduler/agents
tags: [bugfix, metalpriceapi, haiku-deprecation, market-snapshot, content-agent]
dependency_graph:
  requires: [quick-260420-oa1]
  provides: [correct-gold-silver-spot-prices, working-haiku-calls]
  affects: [market_snapshots-table, content_agent-gold-gate, content_agent-format-classifier]
tech_stack:
  added: []
  patterns: [direct-price-read, model-alias-verification]
key_files:
  modified:
    - scheduler/services/market_snapshot.py
    - scheduler/tests/test_market_snapshot.py
    - scheduler/agents/content_agent.py
    - scheduler/seed_content_data.py
    - scheduler/tests/test_content_agent.py
decisions:
  - "metalpriceapi USDXAU/USDXAG with base=USD are direct USD/oz prices — the original oa1 docstring claiming reciprocal trap was incorrect; live response USDXAU=4816.39 confirmed this"
  - "claude-haiku-4-5 used as model alias (not the dated SKU) — live probe confirmed alias resolves correctly to claude-haiku-4-5-20251001"
metrics:
  duration: "~10 minutes"
  completed: "2026-04-20"
  tasks_completed: 2
  tasks_total: 3
  files_modified: 5
---

# Quick Task 260420-pwh: Fix metalpriceapi reciprocal inversion + Haiku model deprecation

One-liner: Remove 1/rate inversion from metalpriceapi fetcher ($0.0002 gold → $4816.39) and swap deprecated `claude-3-5-haiku-latest` to live-verified `claude-haiku-4-5`.

## Tasks Completed

### Task 1: Fix metalpriceapi direct-price read (Bug 1)

**Commit:** `87878e1` — `fix(scheduler): metalpriceapi returns direct USD/oz, not reciprocal`

**Problem:** `MetalpriceAPIFetcher.fetch()` applied `1.0 / xau` and `1.0 / xag` to `USDXAU` and `USDXAG` values. The API with `base=USD` returns these as direct USD-per-oz prices (USDXAU=4816.39 = gold spot). The inversion turned $4816.39 gold into $0.000207/oz in the `market_snapshots` table. The class docstring was also incorrect, claiming the response uses a "reciprocal rate trap."

**Fix applied:**
- `scheduler/services/market_snapshot.py`: Removed the `xau`/`xag` intermediary variables and both `1.0 / x` inversions. Now reads `gold = rates.get("USDXAU")` and `silver = rates.get("USDXAG")` directly. Rewrote class docstring to accurately describe the response shape.
- `scheduler/tests/test_market_snapshot.py`: Updated `METALS_GOOD` fixture from reciprocal values (`USDXAU: 0.000426, USDXAG: 0.035842`) to direct values (`USDXAU: 4816.39, USDXAG: 79.58`). Renamed `test_metalpriceapi_reciprocal_conversion` to `test_metalpriceapi_direct_price_read` and flipped assertions from `approx(2347.42)` / `approx(27.90)` to `approx(4816.39)` / `approx(79.58)`. Updated header docstring line 8.

**Verify outputs:**
- `grep -c "1.0 /" scheduler/services/market_snapshot.py` → `0`
- `grep -c "reciprocal rate trap" scheduler/services/market_snapshot.py` → `0`
- `grep -c "2347\.42" scheduler/tests/test_market_snapshot.py` → `0`
- `grep -c "27\.90" scheduler/tests/test_market_snapshot.py` → `0`
- `uv run pytest tests/test_market_snapshot.py -x -q` → `12 passed in 0.46s`
- `uv run ruff check services/market_snapshot.py tests/test_market_snapshot.py` → `All checks passed!`

---

### Task 2: Swap deprecated claude-3-5-haiku-latest → claude-haiku-4-5 (Bug 2)

**Commit:** `50720f1` — `fix(scheduler): swap deprecated claude-3-5-haiku-latest → claude-haiku-4-5`

**Live probe transcript (Step A):**

Probe run from `/Users/matthewnelson/seva-mining/scheduler/` (main worktree — Railway linked there; worktree at `worktrees/agent-a3fc7cb6/` had no Railway link):

```
$ npx @railway/cli run uv run python -c "from anthropic import Anthropic; c = Anthropic(); r = c.messages.create(model='claude-haiku-4-5', max_tokens=10, messages=[{'role':'user','content':'hi'}]); print('OK:', r.model, '|', r.content[0].text)"

OK: claude-haiku-4-5-20251001 | Hey! How's it going? What can I
```

**VERIFIED_HAIKU = `claude-haiku-4-5`** (alias resolves to `claude-haiku-4-5-20251001`).

**Code sites swapped (4 locations in content_agent.py + 1 seed row):**

| File | Location | Old | New |
|------|----------|-----|-----|
| `scheduler/agents/content_agent.py` | line 276 (docstring) | `claude-3-5-haiku-latest` | `claude-haiku-4-5` |
| `scheduler/agents/content_agent.py` | line 287 (hardcoded in `classify_format_lightweight`) | `claude-3-5-haiku-latest` | `claude-haiku-4-5` |
| `scheduler/agents/content_agent.py` | line 503 (gold gate default) | `claude-3-5-haiku-latest` | `claude-haiku-4-5` |
| `scheduler/agents/content_agent.py` | line 1535 (pipeline config read default) | `claude-3-5-haiku-latest` | `claude-haiku-4-5` |
| `scheduler/seed_content_data.py` | line 46 (seed row value) | `claude-3-5-haiku-latest` | `claude-haiku-4-5` |

**Test-mock sweep:**
- `scheduler/tests/test_content_agent.py`: `replace_all=true` on `claude-3-5-haiku-latest` → `claude-haiku-4-5`

**Verify outputs:**
- `grep -r "claude-3-5-haiku-latest" scheduler/ --exclude-dir=.venv` → (empty, 0 matches)
- `grep -c "claude-haiku-4-5" scheduler/agents/content_agent.py` → `4`
- `grep -c "claude-haiku-4-5" scheduler/seed_content_data.py` → `1`
- `grep -c "claude-haiku-4-5" scheduler/tests/test_content_agent.py` → `22`
- `uv run pytest tests/test_content_agent.py -x -q` → `70 passed in 4.02s`
- `uv run ruff check agents/content_agent.py seed_content_data.py tests/test_content_agent.py` → `All checks passed!`
- `uv run pytest tests/ -q` → `138 passed, 1 warning in 1.50s` (oa1 baseline preserved)

---

### Task 3: Prod DB UPDATE of configs.content_gold_gate_model — PENDING HUMAN

**Status: CHECKPOINT — awaiting orchestrator execution**

Task 3 is a `checkpoint:human-verify` gate. The production `configs` table still holds:
```sql
key = 'content_gold_gate_model', value = 'claude-3-5-haiku-latest'
```

The seed change (Task 2) is NOT retroactive — the seed only sets defaults when the key is absent. The runtime code reads this DB row at pipeline start (content_agent.py line 1535), so the scheduler will continue failing with `NotFoundError` until the DB is updated.

**Command for orchestrator to run (from `/Users/matthewnelson/seva-mining/scheduler/`):**

```bash
npx @railway/cli run uv run python -c "
import asyncio
from sqlalchemy import text
from database import engine
async def main():
    async with engine.begin() as conn:
        result = await conn.execute(
            text(\"UPDATE configs SET value = :v WHERE key = 'content_gold_gate_model'\"),
            {'v': 'claude-haiku-4-5'}
        )
        print(f'UPDATE rowcount: {result.rowcount}')
        check = await conn.execute(text(\"SELECT value FROM configs WHERE key = 'content_gold_gate_model'\"))
        print(f'Post-update value: {check.scalar_one()}')
asyncio.run(main())
"
```

**Expected output:**
```
UPDATE rowcount: 1
Post-update value: claude-haiku-4-5
```

**Post-update content_agent verification (trigger a run and check logs):**
- Zero `classify_format_lightweight failed (NotFoundError)` lines
- Zero `Gold gate API failed ... (NotFoundError)` lines
- One or more `ContentAgent: market snapshot fetched (status=ok)` entries
- Latest `market_snapshots` row: `gold_usd_per_oz` in $4,000–$5,500 range; `silver_usd_per_oz` in $60–$100 range

---

## Deviations from Plan

**1. [Rule 3 - Blocking] Railway CLI not linked in worktree — probe run from main worktree**

- **Found during:** Task 2, Step A (live probe)
- **Issue:** `npx @railway/cli run` returned "No linked project found" in the agent worktree at `/Users/matthewnelson/seva-mining/.claude/worktrees/agent-a3fc7cb6/`. This was anticipated by the plan constraints.
- **Fix:** Ran the probe from `/Users/matthewnelson/seva-mining/scheduler/` (the main worktree, which has Railway linked). Probe succeeded and returned `claude-haiku-4-5-20251001`.
- **Impact:** None — model verified, swaps proceeded normally.

---

## Known Stubs

None — all changes are literal string replacements or arithmetic removals. No stub data flows.

---

## Self-Check

**Checking files exist:**
- [x] `scheduler/services/market_snapshot.py` — FOUND (modified)
- [x] `scheduler/tests/test_market_snapshot.py` — FOUND (modified)
- [x] `scheduler/agents/content_agent.py` — FOUND (modified)
- [x] `scheduler/seed_content_data.py` — FOUND (modified)
- [x] `scheduler/tests/test_content_agent.py` — FOUND (modified)

**Checking commits exist:**
- [x] `87878e1` — Task 1 (metalpriceapi fix)
- [x] `50720f1` — Task 2 (Haiku model swap)

Both pushed to `origin/main` (verified: `baffc28..50720f1 HEAD -> main`).

## Self-Check: PASSED
