---
phase: quick-260420-nnh
plan: 01
type: execute
wave: 1
depends_on: []
files_modified:
  - scheduler/agents/content_agent.py
  - scheduler/tests/test_content_agent.py
autonomous: true
requirements:
  - NNH-01  # Reject stories whose primary subject is a specific gold/mining company
  - NNH-02  # Allow financial-institution sources (Goldman, WGC, JPM, etc.) as cited sources for macro/sector stories
  - NNH-03  # Preserve existing gold gate behavior: macro, sector flows, systemic shocks, listicle rejection
  - NNH-04  # Preserve Haiku-based single-call classifier (no cost upgrade, no new LLM call)
  - NNH-05  # Emit rejection log line identifying company-specific rejection reason

must_haves:
  truths:
    - "Content agent rejects any candidate story whose primary subject is a specific gold/mining company (Barrick, Newmont, B2Gold, McLaren, Seva Mining, etc.) before it reaches the drafter."
    - "Content agent KEEPS macro/sector/market commentary (gold price moves, sector ETF flows, central bank buying, CPI, rare-earth restrictions, miners-index moves)."
    - "Financial-institution sources (Goldman, BlackRock, JPM, Morgan Stanley, WGC, IMF, Fed) cited as SOURCES in a macro/forecast story do NOT trigger the company-specific rejection — they are sources, not subjects."
    - "When a story is rejected for being company-specific, the scheduler logs a line identifying the reason and (when known) the company name."
    - "The filter is implemented as a SINGLE Haiku call (bolted onto the existing gold gate prompt) — no second LLM call, no Sonnet upgrade."
    - "Existing n4f gold-gate behavior (macro/systemic shock acceptance) and rqx listicle rejection behavior still hold."
    - "`cd scheduler && uv run pytest tests/test_content_agent.py -x` is green."
    - "`ruff check scheduler/` is clean."

  artifacts:
    - path: "scheduler/agents/content_agent.py"
      provides: "Updated is_gold_relevant_or_systemic_shock() returning a structured decision (keep/reject + reason + optional company), plus updated call site in the pipeline loop that logs the specific reject reason."
      contains: "is_gold_relevant_or_systemic_shock"
    - path: "scheduler/tests/test_content_agent.py"
      provides: "New test cases covering company-specific rejection (B2Gold / McLaren / Barrick-Kinross M&A / Newmont / Seva Mining) and macro-keep cases (Goldman forecast / WGC central-bank report / miners-index move / ETF flow / CPI / rare-earth). Existing rqx `test_gate_accepts_single_company_earnings` is inverted to reject (Newmont single-company earnings is now REJECTED under nnh). Existing rqx `test_gate_accepts_single_company_ma` is inverted to reject (Barrick M&A is now REJECTED under nnh)."
      contains: "test_gate_rejects_primary_subject_is_specific_miner"

  key_links:
    - from: "scheduler/agents/content_agent.py::is_gold_relevant_or_systemic_shock"
      to: "AsyncAnthropic.messages.create (Haiku)"
      via: "single LLM call returning structured JSON with pass/reject fields"
      pattern: "content_gold_gate_model"
    - from: "scheduler/agents/content_agent.py pipeline loop (~line 1565)"
      to: "is_gold_relevant_or_systemic_shock return value"
      via: "branch on reject reason to emit the appropriate log line"
      pattern: "primary subject is specific miner"
    - from: "scheduler/tests/test_content_agent.py"
      to: "is_gold_relevant_or_systemic_shock"
      via: "mocked AsyncAnthropic client returning structured JSON strings, exercising the operator's exact fixture examples"
      pattern: "B2Gold|McLaren|Barrick|Newmont|Seva Mining|Goldman|World Gold Council|CPI|rare-earth"
---

<objective>
Add a "no specific mining company" filter to the content agent's existing gold gate (from quick tasks n4f + rqx) so that stories whose primary SUBJECT is any specific gold or mining company — including Seva Mining itself — are rejected before reaching the drafter. Macro/sector/market commentary and stories that cite financial institutions (Goldman, WGC, JPM, Fed, etc.) as SOURCES are preserved.

Purpose: The operator posts company-specific news manually. The agent's job is to draft macro/sector/thematic content only. Letting company-specific drilling/earnings/M&A stories into the drafter wastes Sonnet tokens and produces drafts the operator will always reject.

Output: Updated `is_gold_relevant_or_systemic_shock()` in `scheduler/agents/content_agent.py` that returns a structured decision (keep vs. reject-with-reason) from a SINGLE Haiku call, a call-site branch that logs the new rejection reason, and a fixture-backed test suite green under `uv run pytest`.
</objective>

<execution_context>
@$HOME/.claude/get-shit-done/workflows/execute-plan.md
</execution_context>

<context>
@.planning/STATE.md

# Prior lineage (cited for reference — do NOT blindly reread in execution; the relevant code is already embedded below)
# - quick-260419-n4f: introduced the two-bucket gold gate (commits 502ae3e / 010926d / 2cfc9cb)
# - quick-260419-rqx: added listicle rejection inside the gold gate prompt (commits 663d6d8 / 7fb5517 / af37d3c)

@scheduler/agents/content_agent.py
@scheduler/tests/test_content_agent.py

<interfaces>
<!-- Key interfaces the executor must preserve. Extracted from scheduler/agents/content_agent.py. -->

Current signature (content_agent.py, line ~459):
```python
async def is_gold_relevant_or_systemic_shock(
    story: dict,
    config: dict,
    client: "AsyncAnthropic | None" = None,
) -> bool:
```

Current return contract: plain bool. True = keep, False = reject. Fail-open on API error.

Current call site (content_agent.py, line ~1565, inside the qualifying-stories pipeline loop):
```python
gate_pass = await is_gold_relevant_or_systemic_shock(
    story, gate_config, client=self.anthropic
)
if not gate_pass:
    skipped_by_gate += 1
    logger.info(
        "Gold gate rejected (skipped_by_gate=%d): '%s'",
        skipped_by_gate, story["title"][:60],
    )
    continue
```

Config keys (read upstream at ~line 1461):
- `content_gold_gate_enabled` (default "true")
- `content_gold_gate_model` (default "claude-3-5-haiku-latest")
</interfaces>

<decision_context>
Operator-confirmed (locked, do not revisit):
- Scope is the content agent only. Twitter agent is untouched.
- Reject rule is SEMANTIC ("primary subject is a specific gold/mining company"), not keyword.
- Financial institutions cited as SOURCES for forecasts/data (Goldman, BlackRock, JPM, Morgan Stanley, WGC, IMF, Fed, central banks) are NOT triggers for rejection.
- Option A (bolt onto existing Haiku prompt, single LLM call, structured output) is preferred. Option B (dedicated second-pass classifier method) is permitted only if structural clarity demands it. This plan specifies Option A.
- Keep Haiku (cheap model). Do NOT upgrade to Sonnet.
- Preserve existing `content_gold_gate_enabled` bypass and fail-open behavior.

Fixture examples the operator listed (these ARE the test cases):

REJECT (primary subject is a specific miner):
- "B2Gold expects lower Q2 output from Goose mine" → B2Gold
- "McLaren Completes Drone MAG Program at Blue Quartz Gold Property" → McLaren
- "Barrick acquires Kinross in $8B deal" → Barrick + Kinross (two miners)
- "Newmont posts record Q2, raises guidance" → Newmont
- "Seva Mining hits 12g/t gold at Timmins drill hole 42" → Seva Mining

KEEP (macro/sector OR institution-as-source):
- "Gold hits record $3,200 as Goldman forecasts $4K by year-end" (Goldman is a source)
- "Central banks added 800t of gold in Q1, says World Gold Council" (WGC is a source)
- "Gold miners index hits new high" (sector-wide)
- "ETF flows into gold miners surge" (sector flow)
- "US CPI at 2.1%; gold rallies on Fed cut odds" (macro)
- "China imposes new rare-earth export restrictions" (geopolitics / systemic shock)
</decision_context>

<contract_migration_note>
**Important contract change:** The current `is_gold_relevant_or_systemic_shock` returns `bool`. This plan changes the return type to a structured object (a `dict` like `{"keep": bool, "reject_reason": Optional[str], "company": Optional[str]}`) so the caller can log the specific rejection reason for company-specific rejects versus generic-non-gold rejects.

Every call site of `is_gold_relevant_or_systemic_shock` in the codebase must be updated. Based on grep, there is exactly ONE call site in production code (pipeline loop ~line 1565) and multiple call sites in `tests/test_content_agent.py`. All test call sites must be updated to check the new structured return (e.g., `result["keep"] is True`).

Two existing rqx tests invert under the new rule:
- `test_gate_accepts_single_company_earnings` ("Newmont Reports Record Q1 Gold Production" → currently expects `True`) must be renamed and inverted to expect `keep=False` with `reject_reason="primary_subject_is_specific_miner"` and `company="Newmont"`. Under the nnh rule, Newmont single-company earnings is now a REJECT. Note this in the commit message.
- `test_gate_accepts_single_company_ma` (around line ~1050 in test_content_agent.py — Barrick/Kinross M&A story → currently expects `result is True`) must be renamed to `test_gate_rejects_barrick_ma_under_nnh` and inverted to expect `keep=False` with `reject_reason="primary_subject_is_specific_miner"` and `company` containing "Barrick" (e.g., "Barrick" or "Barrick+Kinross"). Under the nnh rule, Barrick M&A IS a specific-miner story and must reject — this is consistent with the B2Gold / Newmont / Seva Mining rule, not an exception. Note this in the commit message alongside the Newmont inversion.
</contract_migration_note>
</context>

<tasks>

<task type="auto" tdd="true">
  <name>Task 1: Add company-specific rejection to the gold gate (single Haiku call, structured return, updated call site)</name>
  <files>scheduler/agents/content_agent.py, scheduler/tests/test_content_agent.py</files>
  <behavior>
    **Stub-shape templates (every migrated test's mocked Haiku call MUST return one of these three shapes, JSON-serialized inside `MagicMock(text="...")`):**

    - **Keep (macro / sector / source story):**
      ```json
      {"keep": true, "reject_reason": null, "company": null}
      ```
    - **Reject — not gold-relevant at all (generic off-topic):**
      ```json
      {"keep": false, "reject_reason": "not_gold_relevant", "company": null}
      ```
    - **Reject — primary subject is a specific miner:**
      ```json
      {"keep": false, "reject_reason": "primary_subject_is_specific_miner", "company": "<name>"}
      ```

    These three shapes are the ONLY acceptable mocked Haiku outputs across all migrated tests. No more bare `"yes"` / `"no"` mock text, no ad-hoc shapes. If a test historically asserted `result is False` for a non-miner, non-gold story (e.g., a sports headline), it must now use the `"not_gold_relevant"` reject stub. If a test asserted `result is False` for a listicle/stock-pick, reuse the `"not_gold_relevant"` reject stub (the gate does not need a dedicated `listicle` reject_reason — the rqx behavior is preserved via the prompt, not the return shape).

    ---

    New tests added to scheduler/tests/test_content_agent.py (place alongside the existing n4f + rqx gate test blocks, under a new header `# quick-260420-nnh: Company-specific rejection tests`):

    Reject cases (Haiku response stubbed to the reject-specific-miner shape above):
    - test_gate_rejects_b2gold_production_update — title "B2Gold expects lower Q2 output from Goose mine", stub `company="B2Gold"`
    - test_gate_rejects_mclaren_drone_program — title "McLaren Completes Drone MAG Program at Blue Quartz Gold Property", stub `company="McLaren"`
    - test_gate_rejects_barrick_kinross_ma — title "Barrick acquires Kinross in $8B deal", stub `company="Barrick"` (OR "Barrick+Kinross" — either is accepted; assert `company` is truthy and contains "Barrick")
    - test_gate_rejects_newmont_guidance — title "Newmont posts record Q2, raises guidance", stub `company="Newmont"`
    - test_gate_rejects_seva_mining_drill_result — title "Seva Mining hits 12g/t gold at Timmins drill hole 42", stub `company="Seva Mining"`

    Keep cases (Haiku response stubbed to the keep shape above):
    - test_gate_keeps_goldman_forecast_as_source — "Gold hits record $3,200 as Goldman forecasts $4K by year-end" → keep=True
    - test_gate_keeps_wgc_central_bank_report — "Central banks added 800t of gold in Q1, says World Gold Council" → keep=True
    - test_gate_keeps_miners_index_sector_move — "Gold miners index hits new high" → keep=True
    - test_gate_keeps_etf_flows — "ETF flows into gold miners surge" → keep=True
    - test_gate_keeps_cpi_macro — "US CPI at 2.1%; gold rallies on Fed cut odds" → keep=True
    - test_gate_keeps_rare_earth_geopolitics — "China imposes new rare-earth export restrictions" → keep=True

    Existing-test migrations (REQUIRED for structured-return contract):
    - Update ALL existing n4f + rqx gate tests (lines ~420–504 and ~760–821 in test_content_agent.py) that currently `assert result is True/False` to instead `assert result["keep"] is True/False`. Mock responses in those tests must return one of the three stub shapes above — keep tests use the keep shape; tests that previously asserted `result is False` for non-miner non-gold (off-topic) stories use the `"not_gold_relevant"` reject shape; tests that previously asserted `result is False` for listicles/stock-picks also use the `"not_gold_relevant"` reject shape.
    - INVERT `test_gate_accepts_single_company_earnings` (Newmont Q1 earnings, existing rqx test): rename to `test_gate_rejects_single_company_earnings_under_nnh`, change stubbed Haiku response to the reject-specific-miner shape with `company="Newmont"`, assert `result["keep"] is False`, `result["reject_reason"] == "primary_subject_is_specific_miner"`, and `result["company"] == "Newmont"`. Add an inline comment: `# quick-260420-nnh: inverts rqx-era behavior — single-company earnings is now a reject under the specific-miner rule.`
    - INVERT `test_gate_accepts_single_company_ma` (Barrick/Kinross M&A story, existing rqx test around line ~1050 of test_content_agent.py, currently asserts `result is True`): rename to `test_gate_rejects_barrick_ma_under_nnh`, change stubbed Haiku response to the reject-specific-miner shape with `company="Barrick"` (or `"Barrick+Kinross"`), assert `result["keep"] is False`, `result["reject_reason"] == "primary_subject_is_specific_miner"`, and `"Barrick" in result["company"]`. Add an inline comment: `# quick-260420-nnh: inverts rqx-era behavior — Barrick M&A is a specific-miner story (two specific miners, same rule) and must reject under nnh. Consistent with B2Gold/Newmont/Seva Mining rejects above.`

    **Explicit migration call-site list (the executor must name-check ALL of these; if a grep turns up any `assert result is True/False` against the gate that is NOT in this list, add it before finishing):**
    1. `test_gate_accepts_gold_price_story` (n4f)
    2. `test_gate_accepts_systemic_shock_story` (n4f)
    3. `test_gate_rejects_off_topic_story` (n4f)
    4. `test_gate_fails_open_on_api_error` (n4f)
    5. `test_gate_bypassed_when_disabled` (n4f)
    6. `test_gate_rejects_listicle_story` (rqx)
    7. `test_gate_rejects_stock_pick_story` (rqx)
    8. `test_gate_accepts_single_company_earnings` (rqx — **INVERT + RENAME**, see above)
    9. `test_gate_accepts_single_company_ma` (rqx — **INVERT + RENAME**, see above — around line 1050)
    10. Any additional `result = await is_gold_relevant_or_systemic_shock(...)` call site the executor finds via `rg -n "is_gold_relevant_or_systemic_shock" scheduler/tests/` that is not in the above list.

    Robustness tests:
    - test_gate_fails_open_on_api_error — Anthropic raises Exception → result is the keep shape (preserve existing fail-open). Update the existing test to assert the new shape.
    - test_gate_bypassed_when_disabled — `content_gold_gate_enabled=false` → result is the keep shape with no LLM call. Update the existing test to assert the new shape.
    - test_gate_fails_open_on_malformed_json — Haiku returns non-JSON text (e.g. "yes") → result is the keep shape (fail-open so a model output format drift never silences real gold stories).

    All test stubs use `AsyncMock()` + `MagicMock(content=[MagicMock(text=<json_string>)])` — match the pattern already used in the n4f/rqx tests.
  </behavior>
  <action>
    Implementation (Option A — bolt onto existing Haiku prompt, single call):

    1. Update `is_gold_relevant_or_systemic_shock` in `scheduler/agents/content_agent.py` (~line 459):

       a. Change return type from `bool` to `dict[str, Any]` with shape:
          ```
          {
              "keep": bool,                     # True = allow through to drafter
              "reject_reason": str | None,      # "primary_subject_is_specific_miner" | "not_gold_relevant" | None
              "company": str | None,            # Name of the specific miner, when rejected for that reason
          }
          ```

       b. Update the bypass-when-disabled branch (~line 484) to return `{"keep": True, "reject_reason": None, "company": None}`.

       c. Rewrite the Haiku system prompt to request structured JSON output AND to teach the model the new rule. The prompt must:
          - Preserve the existing two-bucket acceptance (direct gold/metals/mining macro + systemic shock with plausible gold linkage).
          - Preserve the existing listicle/stock-pick rejection (rqx).
          - ADD the new rejection bucket: "primary subject is a specific gold or mining company" — list the fixture examples (B2Gold, McLaren, Barrick, Newmont, Seva Mining) as REJECT patterns: drilling results, production updates, guidance changes, management changes, financings/raises, M&A between specific miners, project milestones framed as one-company news.
          - Explicitly carve out the financial-institution-as-source allowlist: Goldman Sachs, BlackRock, JPMorgan, Morgan Stanley, World Gold Council, IMF, Federal Reserve, central banks. These appearing as CITED SOURCES for forecasts / data / analysis do NOT trigger the specific-miner rejection. They are sources, not subjects.
          - Instruct the model to respond with a compact JSON object of the form:
            `{"keep": true|false, "reject_reason": null | "not_gold_relevant" | "primary_subject_is_specific_miner", "company": null | "<single company name if reject_reason is primary_subject_is_specific_miner>"}`
          - No other commentary in the response.

          Set `max_tokens=100` explicitly (replaces the existing `max_tokens=5`). Rationale: the longest expected response is a specific-miner reject whose JSON payload can reach ~90 characters — e.g. `{"keep": false, "reject_reason": "primary_subject_is_specific_miner", "company": "Barrick+Kinross"}` — so 100 is a safe ceiling. Do NOT use lower values like 60; they risk truncating the tail of the `company` field and breaking `json.loads`. Do NOT use higher values like 256 — 100 caps Haiku cost at the same order of magnitude as the current 5-token budget.

       d. Parse the response with `json.loads` inside a try/except. On ANY parse error or missing keys, log a warning and return fail-open (`{"keep": True, "reject_reason": None, "company": None}`) — this preserves the "infra blip must not silence real gold stories" guarantee.

       e. On successful parse, sanitize: coerce `keep` to bool, `reject_reason` to `Optional[str]`, `company` to `Optional[str]` (strip/None-if-empty). If `keep` is True, force `reject_reason=None` and `company=None`. If `keep` is False and `reject_reason` is not one of the two known values, treat as `"not_gold_relevant"` (conservative — do not claim a specific-miner rejection the model did not assert).

       f. Preserve the existing fail-open exception handler (Anthropic API error → `{"keep": True, ...}`).

       g. Update the function docstring to describe the new return shape and the company-specific rejection behavior. Reference NNH-01..NNH-05.

    2. Update the pipeline call site in `scheduler/agents/content_agent.py` (~line 1565):

       Replace the existing `if not gate_pass:` branch with a structured branch:
       ```python
       gate_decision = await is_gold_relevant_or_systemic_shock(
           story, gate_config, client=self.anthropic
       )
       if not gate_decision["keep"]:
           skipped_by_gate += 1
           reason = gate_decision.get("reject_reason")
           company = gate_decision.get("company")
           if reason == "primary_subject_is_specific_miner":
               if company:
                   logger.info(
                       "ContentAgent: rejected story %r — primary subject is specific miner (%s).",
                       story["title"][:120], company,
                   )
               else:
                   logger.info(
                       "ContentAgent: rejected story %r — primary subject is specific miner.",
                       story["title"][:120],
                   )
           else:
               # Preserve existing log shape for non-gold / listicle / systemic rejects
               logger.info(
                   "Gold gate rejected (skipped_by_gate=%d): %r",
                   skipped_by_gate, story["title"][:60],
               )
           continue
       ```

       Do NOT change the existing `skipped_by_gate += 1` accumulator or the end-of-run summary log at ~line 1665 — operator's Railway dashboards may already key off `skipped_by_gate`.

    3. Update all test call sites listed in the `<behavior>` block above. Confirm with grep that there are no other callers of `is_gold_relevant_or_systemic_shock` elsewhere in the codebase before finishing:
       `rg -n "is_gold_relevant_or_systemic_shock" scheduler/` — should return only the function def, the pipeline call site, and test call sites.

    4. Do NOT introduce any new dependencies. Do NOT change `content_gold_gate_model` (stays on Haiku). Do NOT change the cron cadence, recency weight, or threshold.

    5. Address the "single Haiku call, no cost upgrade" constraint (NNH-04): one `AsyncAnthropic.messages.create` call per story per gate invocation — same as today. The only change is prompt content + response parsing.

    6. Run `ruff check scheduler/ --fix` after the edit and address any remaining lint warnings manually.
  </action>
  <verify>
    <automated>cd /Users/matthewnelson/seva-mining/scheduler && uv run pytest tests/test_content_agent.py -x && uv run ruff check .</automated>
  </verify>
  <done>
    - `is_gold_relevant_or_systemic_shock` returns a dict `{"keep": bool, "reject_reason": Optional[str], "company": Optional[str]}` from a SINGLE Haiku call.
    - Bypass-when-disabled and fail-open-on-API-error paths both return `{"keep": True, "reject_reason": None, "company": None}`.
    - Haiku prompt rejects any story whose primary subject is a specific gold/mining company (including Seva Mining) and keeps macro/sector/shock stories and stories citing financial institutions as sources.
    - `max_tokens=100` explicitly (not 5, not 60) — safe ceiling for the longest expected JSON reject payload.
    - Pipeline call site logs `ContentAgent: rejected story <title> — primary subject is specific miner (<company>).` when that is the rejection reason (with `(<company>)` omitted if the classifier did not return a name).
    - All operator fixture examples (B2Gold, McLaren, Barrick-Kinross, Newmont, Seva Mining, Goldman, WGC, miners index, ETF flows, CPI, rare-earth) covered by tests.
    - `test_gate_accepts_single_company_earnings` (Newmont earnings) inverted to reject contract and renamed to `test_gate_rejects_single_company_earnings_under_nnh`.
    - `test_gate_accepts_single_company_ma` (Barrick M&A, ~line 1050) inverted to reject contract and renamed to `test_gate_rejects_barrick_ma_under_nnh`.
    - All existing n4f + rqx gate tests migrated to the structured-return contract using one of the three documented stub shapes.
    - `cd scheduler && uv run pytest tests/test_content_agent.py -x` passes (all gate tests green).
    - `ruff check scheduler/` clean.
    - No new dependencies added; Haiku model preserved.
  </done>
</task>

</tasks>

<verification>
Automated checks (run from repo root):

```
cd /Users/matthewnelson/seva-mining/scheduler && uv run pytest tests/test_content_agent.py -x
cd /Users/matthewnelson/seva-mining/scheduler && uv run ruff check .
```

Manual-but-simple spot check:

```
# Confirm no other callers of the gate function exist
rg -n "is_gold_relevant_or_systemic_shock" /Users/matthewnelson/seva-mining/
```

Expected: only the function definition (content_agent.py ~459), the pipeline call site (content_agent.py ~1565), and the tests in test_content_agent.py. Zero additional production callers — the return-type migration is complete.

Operator-owned post-deploy check (NOT part of automated plan verification — documented for the operator to perform after push to Railway):

- On the next `content_agent` cron cycle (3h cadence), scan Railway logs for:
  - `ContentAgent: rejected story ... — primary subject is specific miner` on any company-specific candidate that slipped through scoring.
  - Macro stories (e.g., a CPI print, a WGC central-bank update, a gold-price move) still reaching the drafter (i.e., producing a `ContentBundle`).
- If any company-specific story gets through (e.g., a Barrick earnings piece drafted into a thread), treat as a Haiku prompt-tuning follow-up — not a plan failure.
</verification>

<success_criteria>
- `is_gold_relevant_or_systemic_shock` returns the new structured dict; every production and test call site is migrated to the new contract.
- The existing bool-era `test_gate_accepts_single_company_earnings` (Newmont earnings → keep) is inverted to a reject test under the new nnh rule, renamed, and commented.
- The existing bool-era `test_gate_accepts_single_company_ma` (Barrick M&A → keep) is inverted to a reject test under the new nnh rule, renamed, and commented.
- 11 new tests (5 reject + 6 keep) cover the operator's exact fixture examples.
- A `test_gate_fails_open_on_malformed_json` test guards against Haiku output-format drift.
- `max_tokens` is set explicitly to 100 (safe ceiling for ~90-char specific-miner reject JSON payloads).
- Pipeline call site emits the new `ContentAgent: rejected story <title> — primary subject is specific miner (<company>).` log line with the parenthetical omitted when no company is returned. Existing `skipped_by_gate` counter and end-of-run summary log are preserved.
- `scheduler/` pytest + ruff green. No new dependencies. Haiku model preserved (no upgrade to Sonnet).
- Single Haiku call per gate invocation (cost unchanged vs. n4f/rqx).
</success_criteria>

<output>
After completion, the executor should commit with a message like:

```
feat(content-agent): reject stories whose primary subject is a specific miner (quick-260420-nnh)

- Bolt company-specific rejection onto existing gold gate (single Haiku call, structured JSON return)
- Allowlist financial-institution citations (Goldman, WGC, JPM, Fed, ...) as sources, not subjects
- Log `ContentAgent: rejected story <title> — primary subject is specific miner (<company>).`
- Invert rqx `test_gate_accepts_single_company_earnings` (Newmont earnings) to reject under new rule
- Invert rqx `test_gate_accepts_single_company_ma` (Barrick M&A) to reject under new rule
- Preserve n4f two-bucket acceptance + rqx listicle rejection + fail-open-on-error semantics
- No new deps, no model upgrade (Haiku unchanged)
```

No SUMMARY.md required for this quick task — STATE.md Quick Tasks Completed row is sufficient (operator writes that after Railway verification on the next 3h cron cycle).
</output>
