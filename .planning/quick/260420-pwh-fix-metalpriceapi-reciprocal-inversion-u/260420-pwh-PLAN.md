---
phase: quick-260420-pwh
plan: 01
type: execute
wave: 1
depends_on: []
files_modified:
  - scheduler/services/market_snapshot.py
  - scheduler/tests/test_market_snapshot.py
  - scheduler/agents/content_agent.py
  - scheduler/seed_content_data.py
  - scheduler/tests/test_content_agent.py
autonomous: false
requirements:
  - pwh-bug1-metalpriceapi-inversion
  - pwh-bug2-haiku-model-deprecation

must_haves:
  truths:
    - "metalpriceapi.com with base=USD returns USDXAU and USDXAG as direct USD-per-oz prices; no 1/rate inversion is needed (verified live 2026-04-21 via railway run: USDXAU=4816.39 = gold spot, XAU=0.0002076 = reciprocal)"
    - "Anthropic deprecated claude-3-5-haiku-latest after Haiku 4.5 shipped in Oct 2025; the current stable alias is claude-haiku-4-5 (must be live-verified against prod ANTHROPIC_API_KEY before swap — fallback claude-haiku-4-5-20251001 if alias fails)"
    - "Pre-fix baseline: 138/138 scheduler tests pass locally (oa1-era baseline); post-fix test count must remain green with the flipped inversion test and the updated haiku model id"
    - "Prod DB configs table currently holds an active row with key='content_gold_gate_model' and value='claude-3-5-haiku-latest' — updating seed file + code defaults does NOT retroactively update this row; explicit prod UPDATE required"
    - "Fail-open semantics for both the gold gate and the lightweight classifier remain unchanged: model fixes eliminate the NotFoundError silent fail-open (which was defaulting every story to thread and bypassing the gold gate), but structural exception handling is preserved"
    - "Both fixes land in scheduler/ only — no backend/, frontend/, or infra changes; each bug commits independently so either can be reverted in isolation"
  artifacts:
    - path: "scheduler/services/market_snapshot.py"
      provides: "MetalpriceAPIFetcher.fetch() reading USDXAU/USDXAG as direct USD/oz (no 1/rate inversion); docstring rewritten to describe correct response shape"
      contains: "rates.get(\"USDXAU\")"
    - path: "scheduler/tests/test_market_snapshot.py"
      provides: "test_metalpriceapi_reciprocal_conversion renamed/rewritten to assert direct-price read (USDXAU=4816.39 → gold=4816.39, USDXAG=79.58 → silver=79.58); any 0.000426/2347.42 assertions removed"
      contains: "pytest.approx(4816"
    - path: "scheduler/agents/content_agent.py"
      provides: "3 occurrences of 'claude-3-5-haiku-latest' replaced with the live-verified Haiku 4.5 identifier at lines 287 (hardcoded), 503 (fallback), 1535 (fallback)"
      contains: "claude-haiku-4-5"
    - path: "scheduler/seed_content_data.py"
      provides: "CONTENT_CONFIG_DEFAULTS seed row for content_gold_gate_model updated to the live-verified Haiku 4.5 identifier"
      contains: "claude-haiku-4-5"
    - path: "scheduler/tests/test_content_agent.py"
      provides: "All ~22 test-fixture occurrences of 'claude-3-5-haiku-latest' swapped to the live-verified Haiku 4.5 identifier via single Edit replace_all (consistency only — no behavior change)"
      contains: "claude-haiku-4-5"
    - path: "prod configs table row"
      provides: "UPDATE configs SET value = '<verified_haiku_id>' WHERE key = 'content_gold_gate_model' executed via `npx @railway/cli run` one-off — rowcount captured in SUMMARY"
  key_links:
    - from: "scheduler/services/market_snapshot.py:210-214"
      to: "metalpriceapi.com /v1/latest?base=USD response shape"
      via: "direct dict read (gold = rates['USDXAU']) with no arithmetic inversion"
      pattern: "gold = rates\\.get\\(\"USDXAU\"\\)"
    - from: "scheduler/agents/content_agent.py:287"
      to: "Anthropic Messages API (classify_format_lightweight Haiku call)"
      via: "AsyncAnthropic.messages.create(model=<verified_haiku_id>)"
      pattern: "model=\"claude-haiku-4-5"
    - from: "scheduler/agents/content_agent.py:503, 1535"
      to: "configs table content_gold_gate_model row (runtime-read fallback only)"
      via: "config.get/._get_config with default=<verified_haiku_id>"
      pattern: "\"content_gold_gate_model\", \"claude-haiku-4-5"
    - from: "parent task 260420-oa1-SUMMARY.md"
      to: "this plan"
      via: "bug discovery context — oa1's inversion comment and live-log haiku failures are the evidence trail"
      pattern: ".planning/quick/260420-oa1-real-time-market-snapshot-injection-to-s/260420-oa1-SUMMARY.md"
---

<objective>
Fix two production bugs surfaced during the oa1/p8h verification run:

1. **Bug 1 — metalpriceapi reciprocal inversion (wrong direction):** `MetalpriceAPIFetcher.fetch()` at `scheduler/services/market_snapshot.py:210-214` calls `1.0 / xau` and `1.0 / xag`. Live API response with `base=USD` returns `USDXAU` and `USDXAG` already as direct USD-per-oz prices (verified via `railway run`: USDXAU=4816.39 = gold spot; XAU=0.0002076 is the reciprocal). The current code inverts direct prices into raw reciprocals, which is why the latest `market_snapshots` row shows `gold_usd_per_oz: 0.00020758869999999794` instead of ~$4,816. The "reciprocal rate trap" docstring at lines 192-193 is itself inverted from reality and must be rewritten.

2. **Bug 2 — `claude-3-5-haiku-latest` deprecated:** Anthropic deprecated this alias after Haiku 4.5 shipped in Oct 2025. Every Haiku call (gold gate + lightweight format classifier) is currently returning `NotFoundError`, silently fail-opening to "keep story" in the gold gate and defaulting every story's format to `thread`. Current stable Haiku alias is `claude-haiku-4-5` (to be live-verified against prod key before swap; fallback `claude-haiku-4-5-20251001` if alias call fails). Four code sites + one seed row + ~22 test-mock occurrences must be updated; the prod DB config row must also be UPDATE'd out-of-band since the seed change is not retroactive.

Purpose: Restore accurate gold/silver prices in `market_snapshots.data` JSONB (drafter currently consuming nonsensical ~$0.0002/oz figures or [UNAVAILABLE] fallback), and restore both Haiku calls in the content pipeline (gold gate rejections and format-aware slice priority both broken).

Output: 5 modified scheduler files across 2 independent commits + 1 prod DB UPDATE (no commit). Fixes are reverted-independently by design — Bug 1 commit touches market_snapshot.py + test_market_snapshot.py; Bug 2 commit touches content_agent.py + seed_content_data.py + test_content_agent.py; Task 3 is a DB-side operation with no repo change.
</objective>

<execution_context>
@$HOME/.claude/get-shit-done/workflows/execute-plan.md
@$HOME/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/STATE.md
@.planning/quick/260420-oa1-real-time-market-snapshot-injection-to-s/260420-oa1-SUMMARY.md
@scheduler/services/market_snapshot.py
@scheduler/tests/test_market_snapshot.py
@scheduler/agents/content_agent.py
@scheduler/seed_content_data.py

<interfaces>
<!-- Exact current call sites and response shapes the executor needs. -->
<!-- No codebase exploration required — literals + line numbers below. -->

# Bug 1 — current buggy code (scheduler/services/market_snapshot.py:189-216)

```python
class MetalpriceAPIFetcher:
    """Fetches spot gold + silver from metalpriceapi.com.

    Handles reciprocal rate trap: response gives USDXAU=0.000426 (USD per oz of gold
    expressed as reciprocal), so price = 1 / rate to get USD per oz.
    """

    def __init__(self, api_key: str) -> None:
        self.api_key = api_key

    async def fetch(self, client: httpx.AsyncClient) -> dict | None:
        params = {
            "api_key": self.api_key,
            "base": "USD",
            "currencies": "XAU,XAG",
        }
        try:
            r = await client.get(METALS_URL, params=params, timeout=10.0)
            r.raise_for_status()
            data = r.json()
            rates = data.get("rates", {})
            xau = rates.get("USDXAU")            # ← line 210
            xag = rates.get("USDXAG")            # ← line 211
            gold = (1.0 / xau) if xau else None  # ← line 212 WRONG (inverts direct price)
            silver = (1.0 / xag) if xag else None # ← line 213 WRONG (inverts direct price)
            return {"gold_usd_per_oz": gold, "silver_usd_per_oz": silver}
        except Exception as exc:
            raise exc
```

# Bug 1 — live metalpriceapi response shape (verified 2026-04-21):

```json
{
  "success": true,
  "rates": {
    "USDXAU": 4816.3942353541,   ← direct USD/oz (what we want — READ AS-IS)
    "USDXAG": 79.5853058021,     ← direct USD/oz (what we want — READ AS-IS)
    "XAU": 0.0002076242,         ← reciprocal (DO NOT read)
    "XAG": 0.0125651336          ← reciprocal (DO NOT read)
  }
}
```

# Bug 1 — current test that must be flipped (scheduler/tests/test_market_snapshot.py:426-455)

Test `test_metalpriceapi_reciprocal_conversion` currently asserts:
- Mock input:  `USDXAU: 0.000426, USDXAG: 0.035842`
- Assertions:  `gold == approx(2347.42, rel=1e-4)` and `silver == approx(27.90, rel=1e-4)`
Plus METALS_GOOD fixture at lines 114-120 uses the same reciprocal values (this fixture is used in tests 1, 5, 9, 12 — see below).

# Bug 2 — current call sites (verified via grep):

- scheduler/agents/content_agent.py:287   `model="claude-3-5-haiku-latest"` (hardcoded in classify_format_lightweight)
- scheduler/agents/content_agent.py:503   `config.get("content_gold_gate_model", "claude-3-5-haiku-latest")` (default)
- scheduler/agents/content_agent.py:1535  `await self._get_config(session, "content_gold_gate_model", "claude-3-5-haiku-latest")` (default)
- scheduler/seed_content_data.py:46       `("content_gold_gate_model", "claude-3-5-haiku-latest")` (seed row)
- scheduler/tests/test_content_agent.py   ~22 test-fixture occurrences (consistency sweep, no behavior change)

Total file count with the string: 3 files (1 + 4 + 22 = 27 occurrences).
</interfaces>

<evidence>
Bug 1 evidence (live metalpriceapi response verified 2026-04-21):
- `rates.USDXAU = 4816.3942353541` — this IS gold spot USD/oz
- `rates.XAU     = 0.0002076242`   — this is the reciprocal
- Latest market_snapshots DB row: `gold_usd_per_oz: 0.00020758869999999794` ≈ 1/4816.39 — confirms 1/rate was applied to direct prices

Bug 2 evidence (live content_agent log via railway run):
- ~80× `classify_format_lightweight failed (NotFoundError) — defaulting to 'thread'`
- Multiple × `Gold gate API failed ... (NotFoundError) — fail-open (keeping story)`
- Anthropic model catalog (Oct 2025): `claude-3-5-haiku-latest` DEPRECATED; current stable alias `claude-haiku-4-5`
</evidence>
</context>

<tasks>

<task type="auto">
  <name>Task 1: Fix metalpriceapi direct-price read + flip inversion test + rewrite docstring (Bug 1, single commit)</name>
  <files>scheduler/services/market_snapshot.py, scheduler/tests/test_market_snapshot.py</files>
  <action>
**File 1: scheduler/services/market_snapshot.py**

1. At lines 210-213 (inside `MetalpriceAPIFetcher.fetch()`), replace:

   ```python
   xau = rates.get("USDXAU")
   xag = rates.get("USDXAG")
   gold = (1.0 / xau) if xau else None
   silver = (1.0 / xag) if xag else None
   ```

   With:

   ```python
   gold = rates.get("USDXAU")
   silver = rates.get("USDXAG")
   ```

   Keep the `return {"gold_usd_per_oz": gold, "silver_usd_per_oz": silver}` line at 214 unchanged. Preserve the surrounding try/except — no exception-handling change.

2. At lines 189-194, rewrite the class docstring. Replace the current text:

   ```
   """Fetches spot gold + silver from metalpriceapi.com.

   Handles reciprocal rate trap: response gives USDXAU=0.000426 (USD per oz of gold
   expressed as reciprocal), so price = 1 / rate to get USD per oz.
   """
   ```

   With:

   ```
   """Fetches spot gold + silver from metalpriceapi.com.

   Response shape with base=USD returns USDXAU and USDXAG as direct USD-per-oz
   prices (e.g. USDXAU≈4816.39 means gold is $4,816.39/oz); read as-is, no
   inversion. The reciprocal fields XAU/XAG (without the USD prefix) are ignored.
   """
   ```

   (The critical change: remove all "reciprocal rate trap" / "1/rate" language. State plainly that USDXAU is direct USD/oz.)

**File 2: scheduler/tests/test_market_snapshot.py**

3. Update the `METALS_GOOD` fixture at lines 114-120. Replace:

   ```python
   METALS_GOOD = {
       "rates": {
           "USDXAU": 0.000426,
           "USDXAG": 0.035842,
       },
       "timestamp": 1745280000,
   }
   ```

   With realistic direct-price fixture values (current spot range):

   ```python
   METALS_GOOD = {
       "rates": {
           "USDXAU": 4816.39,
           "USDXAG": 79.58,
       },
       "timestamp": 1745280000,
   }
   ```

   This fixture is read by tests 1 (happy path), 5 (missing FRED key), 9 (dot fallback case B), and 12 (CPI YoY). None of those four tests assert on specific gold/silver dollar values — they only assert `!= None` — so updating the fixture in-place is safe and keeps the tests green.

4. Rewrite `test_metalpriceapi_reciprocal_conversion` at lines 422-455. Rename it to `test_metalpriceapi_direct_price_read` and replace the body so:
   - Mock input: `USDXAU: 4816.39, USDXAG: 79.58` (the same realistic fixture values)
   - Assertions: `snap["gold_usd_per_oz"] == pytest.approx(4816.39, rel=1e-4)` and `snap["silver_usd_per_oz"] == pytest.approx(79.58, rel=1e-4)`
   - Replace the docstring on line 428 (currently `"""USDXAU=0.000426 → gold=$2347.42/oz; USDXAG=0.035842 → silver=$27.90/oz."""`) with `"""USDXAU=4816.39 → gold=$4816.39/oz; USDXAG=79.58 → silver=$79.58/oz (direct USD/oz, no inversion)."""`
   - Keep the local `metals_response` dict (lines 431-437) but use the new fixture values.
   - Remove any comment or assertion commentary that mentions "reciprocal trap" or "reciprocal conversion".

5. Scan the rest of the test file for any residual reference to `0.000426`, `0.035842`, `2347.42`, `27.90`, or the phrase "reciprocal" — the only expected hits are the ones in METALS_GOOD (handled in step 3) and the inversion test body (handled in step 4). If any others surface, update consistently.

6. Update the header docstring at lines 1-17 — change line 10 from `8.  metalpriceapi reciprocal rate conversion` to `8.  metalpriceapi direct price read (no inversion)`.

**Preserve:** exception-handling structure (try/except in `MetalpriceAPIFetcher.fetch()`), all other tests (1, 2, 3, 4, 5, 6, 7, 9, 10, 11, 12) pass unchanged.

**Commit:**
```
fix(scheduler): metalpriceapi returns direct USD/oz, not reciprocal

USDXAU/USDXAG with base=USD are already USD-per-oz — remove 1/rate
inversion that was turning $4816.39 gold into $0.000207/oz. Rewrite
the class docstring and flip the corresponding unit test. Fixture
values updated from reciprocal (0.000426) to direct ($4816.39).

Fixes: market_snapshots table rows showing ~$0.0002 gold since oa1.
```
Message via HEREDOC with `Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>` trailer.
  </action>
  <verify>
    <automated>cd /Users/matthewnelson/seva-mining/scheduler && uv run pytest tests/test_market_snapshot.py -x -q && uv run ruff check services/market_snapshot.py tests/test_market_snapshot.py && grep -c "1.0 /" services/market_snapshot.py | grep -q '^0$' && grep -c "reciprocal rate trap" services/market_snapshot.py | grep -q '^0$' && grep -c "2347\.42" tests/test_market_snapshot.py | grep -q '^0$' && grep -c "27\.90" tests/test_market_snapshot.py | grep -q '^0$'</automated>
  </verify>
  <done>
- scheduler/services/market_snapshot.py:210-214 reads `rates.get("USDXAU")` / `rates.get("USDXAG")` directly with NO `1.0 /` arithmetic
- scheduler/services/market_snapshot.py:189-194 docstring no longer contains the string "reciprocal rate trap" or "1 / rate"
- scheduler/tests/test_market_snapshot.py METALS_GOOD fixture uses 4816.39 / 79.58 (not 0.000426 / 0.035842)
- scheduler/tests/test_market_snapshot.py has zero matches for `2347.42` or `27.90` in assertions
- Renamed `test_metalpriceapi_direct_price_read` asserts `approx(4816.39)` / `approx(79.58)`
- All 12 tests in test_market_snapshot.py pass
- Commit landed on main with the described message
  </done>
</task>

<task type="auto">
  <name>Task 2: Live-verify Haiku 4.5 model ID, then swap 4 code sites + ~22 test-mock occurrences (Bug 2, single commit)</name>
  <files>scheduler/agents/content_agent.py, scheduler/seed_content_data.py, scheduler/tests/test_content_agent.py</files>
  <action>
**STEP A — Live-verify the Haiku 4.5 model ID against prod ANTHROPIC_API_KEY (BEFORE any code edits).**

Run this probe first:

```bash
npx @railway/cli run uv run python -c "from anthropic import Anthropic; c = Anthropic(); r = c.messages.create(model='claude-haiku-4-5', max_tokens=10, messages=[{'role':'user','content':'hi'}]); print('OK:', r.model, '|', r.content[0].text)"
```

- If it prints `OK: claude-haiku-4-5-... | <text>` → **use `claude-haiku-4-5` as the verified model ID for all swaps below.** Record the actual model string returned (e.g. `claude-haiku-4-5-20251001`) in the SUMMARY.
- If it fails with `NotFoundError` or any API error → retry with the dated SKU:
  ```bash
  npx @railway/cli run uv run python -c "from anthropic import Anthropic; c = Anthropic(); r = c.messages.create(model='claude-haiku-4-5-20251001', max_tokens=10, messages=[{'role':'user','content':'hi'}]); print('OK:', r.model, '|', r.content[0].text)"
  ```
  If the dated SKU succeeds → **use `claude-haiku-4-5-20251001` for all swaps.**
- If both fail → STOP and escalate to the operator. Do NOT proceed with code edits until one model ID is confirmed live. Post the exact error text in the checkpoint.

Let `<VERIFIED_HAIKU>` denote the confirmed model ID string from the probe above. All subsequent edits use this exact literal.

**STEP B — Code swaps (4 locations):**

1. `scheduler/agents/content_agent.py:287` — change `model="claude-3-5-haiku-latest"` → `model="<VERIFIED_HAIKU>"` (hardcoded in `classify_format_lightweight`)
2. `scheduler/agents/content_agent.py:277` — update the docstring line referencing `claude-3-5-haiku-latest` to `<VERIFIED_HAIKU>` (keep surrounding prose intact)
3. `scheduler/agents/content_agent.py:503` — change default string in `config.get("content_gold_gate_model", "claude-3-5-haiku-latest")` → `config.get("content_gold_gate_model", "<VERIFIED_HAIKU>")`
4. `scheduler/agents/content_agent.py:1535` — change default string in `await self._get_config(session, "content_gold_gate_model", "claude-3-5-haiku-latest")` → `await self._get_config(session, "content_gold_gate_model", "<VERIFIED_HAIKU>")`
5. `scheduler/seed_content_data.py:46` — change `("content_gold_gate_model", "claude-3-5-haiku-latest")` → `("content_gold_gate_model", "<VERIFIED_HAIKU>")`

**STEP C — Test-mock consistency sweep (single replace_all in Edit tool):**

In `scheduler/tests/test_content_agent.py`, use a single `Edit` call with `replace_all=true` to swap every literal `"claude-3-5-haiku-latest"` → `"<VERIFIED_HAIKU>"`. Expected count: ~22 occurrences. No behavior change — these are test config-dict fixture values only.

**STEP D — Zero-match verification:**

After all edits, the string `claude-3-5-haiku-latest` must have ZERO matches across `scheduler/**` (no file, no docstring, no test). The new string `<VERIFIED_HAIKU>` must appear in at least the 4 code sites above + the seed row + the test file.

**Preserve:** All fail-open semantics. The try/except around `anthropic_client.messages.create(...)` in the gold gate (around content_agent.py:507) and the classify_format_lightweight (around content_agent.py:285) stays exactly as-is. Model id is the only thing changing.

**Commit:**
```
fix(scheduler): swap deprecated claude-3-5-haiku-latest → <VERIFIED_HAIKU>

Anthropic deprecated the 3.5-haiku-latest alias post-Haiku-4.5 (Oct 2025).
Every Haiku call since has returned NotFoundError, silently fail-opening
the gold gate (keeps all stories) and defaulting every story's format
to 'thread' in classify_format_lightweight.

Live-verified <VERIFIED_HAIKU> against prod key. Swapped 4 code sites
(content_agent.py lines 287/277/503/1535, seed_content_data.py line 46)
plus ~22 test-fixture occurrences for consistency.

Note: prod DB configs row for content_gold_gate_model is updated
out-of-band in the follow-up DB UPDATE task — seed change is not
retroactive.
```
Message via HEREDOC with `Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>` trailer.
  </action>
  <verify>
    <automated>cd /Users/matthewnelson/seva-mining/scheduler && uv run pytest tests/test_content_agent.py -x -q && uv run ruff check agents/content_agent.py seed_content_data.py tests/test_content_agent.py && grep -rc "claude-3-5-haiku-latest" . | grep -v ':0$' | wc -l | xargs -I{} test {} -eq 0</automated>
  </verify>
  <done>
- Live probe against prod ANTHROPIC_API_KEY succeeded and a VERIFIED_HAIKU model ID was recorded
- `grep -r "claude-3-5-haiku-latest" scheduler/` returns zero matches
- `grep -r "<VERIFIED_HAIKU>" scheduler/` shows at least 5 matches in code (content_agent.py + seed_content_data.py) + ~22 matches in tests
- All tests in test_content_agent.py pass
- `ruff check scheduler/` is clean on the 3 modified files
- Commit landed on main with VERIFIED_HAIKU substituted into the message body
  </done>
</task>

<task type="checkpoint:human-verify" gate="blocking">
  <name>Task 3: Human-gated prod DB UPDATE of configs.content_gold_gate_model row (no repo commit, capture rowcount in SUMMARY)</name>
  <what-built>
Tasks 1 + 2 have landed on main (and ideally deployed to Railway). But the production `configs` table still holds an active row with `key = 'content_gold_gate_model'` and `value = 'claude-3-5-haiku-latest'` from the original seed. The scheduler reads this row at runtime (content_agent.py:1535) and will continue to fail with `NotFoundError` until the DB row itself is updated — the code default only applies when the row is absent.

This task runs the one-off UPDATE against prod via `npx @railway/cli run` using the same `<VERIFIED_HAIKU>` identifier confirmed in Task 2.
  </what-built>
  <how-to-verify>
1. Confirm Tasks 1 and 2 are fully committed and pushed. `git log --oneline -5` on main should show both fix commits.
2. Confirm the VERIFIED_HAIKU model ID from Task 2's live probe (e.g. `claude-haiku-4-5` or `claude-haiku-4-5-20251001`) — use the EXACT string that passed the live probe.
3. Execute the UPDATE via Railway CLI against the scheduler service's env (which has DATABASE_URL):

   ```bash
   npx @railway/cli run uv run python -c "
   import asyncio
   from sqlalchemy import text
   from database import engine
   async def main():
       async with engine.begin() as conn:
           result = await conn.execute(
               text(\"UPDATE configs SET value = :v WHERE key = 'content_gold_gate_model'\"),
               {'v': '<VERIFIED_HAIKU>'}
           )
           print(f'UPDATE rowcount: {result.rowcount}')
           check = await conn.execute(text(\"SELECT value FROM configs WHERE key = 'content_gold_gate_model'\"))
           print(f'Post-update value: {check.scalar_one()}')
   asyncio.run(main())
   "
   ```

4. Record both log outputs in the SUMMARY.md: the `UPDATE rowcount: 1` line AND the `Post-update value: <VERIFIED_HAIKU>` line. If rowcount is 0, the row is missing — seed may have been wiped; escalate before proceeding.

5. Trigger a content_agent run on Railway (either wait for next cron or invoke manually via `npx @railway/cli run uv run python -c "import asyncio; from agents.content_agent import ContentAgent; asyncio.run(ContentAgent().run())"`). Collect logs.

6. Confirm in the logs:
   - Zero occurrences of `classify_format_lightweight failed (NotFoundError)`
   - Zero occurrences of `Gold gate API failed ... (NotFoundError)`
   - One or more `ContentAgent: market snapshot fetched (status=ok)` entries
   - At least one `gold_usd_per_oz` value in the `market_snapshots` table (latest row) falling in the $4,000-$5,500 range (current gold spot) and `silver_usd_per_oz` in $60-$100 range

7. If any of the above fails, mark the quick task as NOT VERIFIED in SUMMARY and escalate with the specific log line(s).

Expected outcome: Gold gate rejections start appearing for off-topic stories; format classifier starts returning non-thread values (long_form, infographic, quote, breaking_news) for appropriate stories; market_snapshots rows hold plausible dollar values.
  </how-to-verify>
  <resume-signal>Type "verified" with the UPDATE rowcount and post-update DB value pasted, plus confirmation of a post-fix content_agent run with zero NotFoundError lines and a plausible gold_usd_per_oz — OR describe the specific failure mode so we can diagnose.</resume-signal>
</task>

</tasks>

<verification>
End-to-end checklist the operator will run after Task 3 resume-signal:

- [ ] `grep -r "1.0 /" scheduler/services/market_snapshot.py` → 0 matches (Bug 1 code fix)
- [ ] `grep -r "reciprocal rate trap" scheduler/services/market_snapshot.py` → 0 matches (Bug 1 docstring fix)
- [ ] `grep -r "2347.42" scheduler/tests/test_market_snapshot.py` → 0 matches (Bug 1 test flip)
- [ ] `grep -r "claude-3-5-haiku-latest" scheduler/` → 0 matches (Bug 2 swap complete)
- [ ] `grep -rc "<VERIFIED_HAIKU>" scheduler/agents/content_agent.py` → ≥3 (hardcoded + 2 fallback defaults; docstring mention optional)
- [ ] `grep -c "<VERIFIED_HAIKU>" scheduler/seed_content_data.py` → 1
- [ ] `grep -c "<VERIFIED_HAIKU>" scheduler/tests/test_content_agent.py` → ~22
- [ ] `uv run pytest scheduler/tests/test_market_snapshot.py scheduler/tests/test_content_agent.py` → green
- [ ] `uv run pytest scheduler/tests/` → 138/138 green (oa1 baseline preserved)
- [ ] `uv run ruff check scheduler/` → clean
- [ ] Prod SQL: `SELECT value FROM configs WHERE key='content_gold_gate_model'` → returns `<VERIFIED_HAIKU>`
- [ ] Post-fix Railway content_agent log: zero `NotFoundError` lines
- [ ] Post-fix `market_snapshots` latest row: `gold_usd_per_oz` in $4000-$5500 range, `silver_usd_per_oz` in $60-$100 range
</verification>

<success_criteria>
Quick task verified when:
1. Both fix commits are on main and deployed to Railway
2. Prod DB `configs.content_gold_gate_model` row holds the VERIFIED_HAIKU model ID
3. Post-fix `market_snapshots` row shows plausible direct USD/oz values (no more ~$0.0002 gold)
4. Post-fix content_agent log shows zero `NotFoundError` from Haiku calls
5. All scheduler tests still pass (138/138 baseline from oa1)
6. `ruff check scheduler/` is clean
7. SUMMARY.md records: VERIFIED_HAIKU model string, UPDATE rowcount, post-update DB check value, and a sample post-fix log snippet showing format classifier returning non-thread values
</success_criteria>

<output>
After completion, create `.planning/quick/260420-pwh-fix-metalpriceapi-reciprocal-inversion-u/260420-pwh-SUMMARY.md` with:
- Task 1 commit SHA + test results
- Task 2 commit SHA + live-probe transcript + VERIFIED_HAIKU string + grep counts
- Task 3 UPDATE rowcount + post-update DB value + post-fix log sample (zero NotFoundError, plausible gold price)
- Updated STATE.md row for 260420-pwh in the "Quick Tasks Completed" table
</output>
