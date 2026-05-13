# Quick Task 260512-oxr — Tighten gold prompt (bullet → bull-case rule) — SUMMARY

**Shipped:** 2026-05-12
**Branch:** `main` (single-file prompt tweak; orchestrator-inline execution, ~10 min)

## Why

Immediate iteration on the just-shipped quick-260512-of1 prompt. User feedback verbatim: *"And then when you give me a headline / Give me the bullet points on how it releates back to gold and its bull case."*

The of1 prompt restructured Gold News into 4 sub-sections, but Sonnet's bullets were still reading descriptively. Example from the May 12 12:00 PT card:

> **US Inflation Heats Up in April as Iran War Stokes ECB Rate-Hike Fears**
> * US inflation rose in April, driven by gas, rent, and food costs, dampening market enthusiasm amid tech sector cooling. (Bloomberg)
> * JPMorgan CEO Jamie Dimon warned of "too much" market exuberance... (Bloomberg)

Each bullet describes what happened but doesn't explicitly state how it advances the gold bull thesis. The user wants every bullet to make the gold connection inline — fact + mechanism, not just fact.

## Fix

Three surgical edits to `GOLD_NEWS_SYSTEM_PROMPT` in `scheduler/agents/daily_summary.py`:

### 1. New top-level rule

Inserted right after the "Stories that DO NOT advance the bull thesis..." paragraph, before the section headers:

> **Bullet rule (applies to all sections):** Every bullet must explicitly tie the fact back to the gold bull case. State the fact, then make the connection — e.g., "Fed paused rate hikes" + "real yields drop, gold's inflation-hedge thesis strengthens". Descriptive bullets ("X happened") without the gold connection should be rewritten or dropped.

This is the master instruction. Sonnet now sees the rule UP FRONT, before any section-specific guidance.

### 2. Per-bullet word limit 25 → 35

Three occurrences updated (Top Gold Headlines, Top Macro Headlines, Analyst & Bank Predictions sections). The extra 10 words gives Sonnet room to land both the fact AND the gold-mechanism connection in one bullet without truncating either. Bullets that were tight at 25 words ("X happened, source") can now expand to "X happened — drives gold's Y thesis because Z, source."

### 3. Three worked example bullets at the bottom

New section header: `### Example bullets (use these as a model)`. Three examples — one per major section — modelling exactly what good looks like:

```
* **Top Gold Headlines example:** Spot gold surged 3.6% on May 6, topping $4,700 — confirms safe-haven bid as Iran-deal hopes briefly cooled then reignited the geopolitical risk premium that supports gold. (mining.com)
* **Top Macro Headlines example:** US April CPI rose driven by gas, rent, and food costs — sticky inflation keeps real yields suppressed and undermines Fed rate-cut optimism, supports gold's inflation-hedge thesis. (Bloomberg)
* **Analyst & Bank Predictions example:** Lassonde points to $40T US debt as the catalyst — debasement risk plus political unwillingness to allow real fiscal pain drives gold's monetary premium higher. (Kitco)
```

Few-shot prompting is well-established: showing the model 1-3 in-domain examples of the desired output style dramatically improves adherence. Cost is ~400 extra prompt characters (input tokens only, negligible) and `SONNET_MAX_TOKENS` stays at 1500.

## Tests

`scheduler/tests/agents/test_daily_summary.py` — 4 changes:

- **UPDATED** `test_gold_news_system_prompt_contains_word_limit` — asserts `"≤ 35 words"` is present at least 3 times AND the legacy `"≤ 25 words"` does NOT linger
- **NEW** `test_gold_news_system_prompt_contains_bullet_rule` — asserts the top-level rule is present, including the keywords `"Bullet rule (applies to all sections)"`, `"tie the fact back to the gold bull case"`, and `"Descriptive bullets"`
- **NEW** `test_gold_news_system_prompt_contains_example_bullets` — asserts the example-bullets section header is present and all 3 worked example substrings are intact (`"Spot gold surged 3.6%"`, `"sticky inflation keeps real yields suppressed"`, `"Lassonde points to $40T US debt"`)

Existing 47 daily_summary tests from quick-260512-of1 all continue to pass (assertions are additive, no prior assertion contradicted).

## Validation

- `cd scheduler && uv run pytest tests/agents/test_daily_summary.py -x` → **49 passed** (was 47, +2 new)
- `cd scheduler && uv run pytest -x` → **318 passed, 1 skipped** (was 314 + 1, +4 net — 2 oxr + carryover from of1)
- `cd scheduler && uv run ruff check .` → clean
- Smoke: `grep -c "≤ 35 words"` returns **3**, `grep -c "≤ 25 words"` returns **0**
- Preservation diff: `git diff main -- backend/ frontend/ scheduler/agents/content_agent.py scheduler/agents/ontario_law.py scheduler/agents/ontario_stats.py scheduler/worker.py` returns 0 bytes ✓

## Operational impact

- Next 12:00 PT fire (after Railway deploy lag) produces bullets that explicitly state the gold-mechanism connection alongside each fact
- Anthropic Sonnet input cost: ~400 extra prompt chars per fire = negligible (~$0.001 per fire)
- Output cost unchanged (`SONNET_MAX_TOKENS` stays 1500)
- Better social-media content for the user: every bullet now self-documents WHY it matters for gold, which is the share-worthy framing

## Out of scope (preserved)

- Section structure (4 sub-sections + Bearish Risk) — unchanged from of1
- `GOLD_TOP_N=12`, `SONNET_MAX_TOKENS=1500`, `GOLD_SCORE_FLOOR=6.0`, `SONNET_MODEL="claude-sonnet-4-6"` — all unchanged
- Ontario Law section, Ontario Stats section, fetch_stories, frontend, worker.py — zero diff
- v1.0 dead code — preserved

## Workflow note

Ran `/gsd:quick` default mode (no `--full`, `--discuss`, or `--research`) — this is a tight iterative refinement to a freshly-shipped prompt; the of1 plan-check loop already validated the surrounding structure 10 minutes ago, so no additional ceremony added value here. Orchestrator-inline execution (no subagent spawn) — single-file constant edit + 4 test additions, mechanical and well-specified.
