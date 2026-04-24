---
quick_task: 260423-lvp
slug: add-analytical-historical-fallback-to-sub-infographics
subsystem: scheduler/agents/content/infographics + scheduler/agents/content_agent
tags: [infographics, fallback, analytical-historical, 2-per-day-guarantee, serpapi]
created: 2026-04-23
mode: quick --discuss
---

# Quick Task 260423-lvp: Add Analytical-Historical Fallback to `sub_infographics`

## User's verbatim ask

> "I want it to create 2 infographics every single day"
>
> "It should prioritize stuff that is relevant news"
>
> "If no relevant news to make infographics from, it should make historical infographics"

## User's follow-up clarifications (during discuss phase)

> "Sub gold history should be separate from sub infographics. They should both do their own agent pulls from online. Infographic stuff and historic stories will be different information. Historical infographics should be more of an analytical perspective. For example, 'what gold does during wars' or something like that"

> "Every other day" (for `sub_gold_history` cadence — stays unchanged)

> "You dont need to make the infographics. Keep the prompts to what we already have and what the infographic agent already does."

## One-liner

Add an analytical-historical fallback tier to `sub_infographics` that triggers when the daily news pipeline produces fewer than 2 infographic-drafts. The fallback queries SerpAPI with analytical-historical gold topics (e.g., "gold price during major wars", "gold during recessions", "central bank gold buying trends") and feeds the results through the **existing** `_draft` function — same drafter, same prompts, same output format (`content_type="infographic"`). Guarantees 2 infographics per day.

## Design lock (from --discuss phase)

| # | Question | Decision | Implication |
|---|----------|----------|-------------|
| Q1 | Architecture — fallback wiring | **`sub_gold_history` and `sub_infographics` stay fully separate and independent.** Each does its own online pulls. `sub_infographics` handles ALL infographic production (news + analytical-historical fallback). No cross-agent coordination. | `sub_gold_history.py` is UNCHANGED. `sub_infographics.py` and possibly `content_agent.py` are the only files touched on the scheduler side. |
| Q2 | Fallback trigger | **`items_queued < 2` after news pipeline completes.** If news produces 0 infographics, fallback produces 2. If news produces 1, fallback produces 1. If news produces 2+, fallback doesn't fire. | Need to capture `items_queued` from `run_text_story_cycle` return value OR query `agent_runs` row. Currently `run_text_story_cycle` returns `None` — may need to change signature to return `int`. |
| Q3 | Curated pool | **No new curated pool.** Fallback pulls from **online** via SerpAPI using analytical-historical query strings. | Zero new JSON story files. Zero new directories. Small module-level list of ~10 analytical query strings. |
| Q4 | Dedup | **Shared within `sub_infographics` — same_type 30-day window.** The existing `dedup_scope="same_type"` (of3) already prevents same-story re-drafting within the day; analytical-historical entries use the same mechanism. No coupling to `sub_gold_history`'s used_topics. | Fallback uses `dedup_scope="same_type"` same as the news phase. The 30-day horizon the user mentioned is loose — for infographics, same-day dedup is sufficient because analytical queries rotate daily and return different headlines. |
| Q5 | `sub_gold_history` cadence | **Every other day — unchanged.** | Zero changes to `sub_gold_history.py`, its cron registration, or its whitelist. |
| Q6 | `sub_gold_history` format | **Thread + carousel — unchanged.** Remains narrative storytelling format. | `sub_gold_history` covers narrative events (Nixon 1971, Klondike, Hunt Brothers). `sub_infographics` fallback covers analytical patterns (gold during wars, central bank trends). These are distinct editorial lanes. |
| Q7 | Prompt changes | **None.** `_draft` in `infographics.py` is unchanged. `BRAND_PREAMBLE` unchanged. `image_prompt` construction unchanged. | The drafter treats analytical-historical stories identically to news stories — both are just "story" inputs with title, summary, data. |
| Q8 | Fetch mechanism | **SerpAPI with ~10 curated analytical query strings.** Reuses existing `serpapi.Client` infrastructure. | A new module-level constant `ANALYTICAL_HISTORICAL_QUERIES` in `infographics.py` (or a new helper in `content_agent.py`). A new fetch helper that runs SerpAPI searches against these queries and returns story dicts in the same shape as `fetch_stories()` output. |

## Scope — code surfaces to touch

### MODIFY (scheduler/)

| File | Changes |
|------|---------|
| `scheduler/agents/content/infographics.py` | **Major**. Add `ANALYTICAL_HISTORICAL_QUERIES` list (~10 entries). Modify `run_draft_cycle` to a two-phase pipeline: (1) call existing `run_text_story_cycle` for news phase, (2) check items_queued, (3) if <2, invoke new fallback helper. Add `_run_analytical_fallback(shortfall: int)` helper that fetches via analytical queries, runs through the same gold-gate + `_draft` + review + persist flow. **`_draft` itself is NOT modified.** Update docstring with lvp decision-ID bullet following the of3/d30 style. |
| `scheduler/agents/content_agent.py` | **Additive**. Add a new function `fetch_analytical_historical_stories(queries: list[str]) -> list[dict]` that mirrors `_fetch_all_serpapi` but accepts a custom query list. Returns story dicts in the same shape as `fetch_stories()`. Reuses existing `serpapi.Client` instantiation. Existing `fetch_stories()` and `SERPAPI_KEYWORDS` list are UNCHANGED. |
| `scheduler/agents/content/__init__.py` | **Optional**. If the cleanest implementation requires `run_text_story_cycle` to return `int` instead of `None` (so the fallback trigger check doesn't need a separate DB query), update signature + docstring. All 4 existing callers (breaking_news, threads, quotes, infographics) continue to work — they just ignore the return value. Alternative: fallback queries the `agent_runs` table directly for today's items_queued. Planner/executor picks the lower-blast-radius approach. |
| `scheduler/tests/test_infographics.py` | Add 3-4 new tests: (a) fallback fires when news items_queued < 2, (b) fallback does NOT fire when items_queued >= 2, (c) fallback produces `content_type="infographic"` rows, (d) analytical queries rotation/selection logic. Existing news-phase tests unchanged. |
| `scheduler/tests/test_content_agent.py` | Add 1-2 tests for `fetch_analytical_historical_stories` if that helper is added. |

### UNCHANGED (explicit preservation)

| File | Rationale |
|------|-----------|
| `scheduler/agents/content/gold_history.py` | Q1 + Q5 + Q6 locked. Fully unchanged. |
| `scheduler/agents/content/gold_history_stories/*.json` | No pool changes. Curated whitelist stays as-is. |
| `scheduler/agents/content/infographics.py` `_draft` function | Q7 locked. No prompt changes. |
| `scheduler/agents/content/infographics.py` `BRAND_PREAMBLE` | Q7 locked. |
| `scheduler/agents/content_agent.py` `SERPAPI_KEYWORDS` list | Keep as-is (news phase queries). Analytical queries are a NEW separate list, not an addition to this. |
| `scheduler/agents/content_agent.py` `fetch_stories()` | Keep as-is. Not mutated; new helper added alongside. |
| `scheduler/agents/content_agent.py` `is_gold_relevant_or_systemic_shock` (gold gate) | Keep as-is. Analytical-historical stories about gold patterns should pass naturally. If they don't, that's a separate tuning decision not in scope for lvp. |
| `scheduler/worker.py` | No cron changes. sub_infographics stays at daily 12:00 PT. sub_gold_history stays every-other-day 12:00 PT. |

### UNCHANGED (deliberate — not in scope)

- DB schema — no migration
- `sub_breaking_news`, `sub_threads`, `sub_quotes`, `sub_gold_media` — unchanged
- Frontend — no UI changes; new fallback rows surface as normal `content_type='infographic'` entries in `/agents/infographics`
- Docs (CLAUDE.md) — minor update to the infographics topology description if needed, OR add a one-line note in STATE.md's Last Activity

## Analytical-historical query candidates (starting point)

These are **examples** — planner/executor may refine wording for better SerpAPI results. Aim for ~10 queries covering distinct analytical angles:

1. `gold price performance during major wars historical`
2. `gold bull markets historical analysis 1970-2025`
3. `central bank gold purchases trends 2020-2025`
4. `gold inflation correlation 50 years historical`
5. `gold during recessions analysis 1973 2008 2020`
6. `gold vs dollar weakness historical pattern`
7. `safe haven asset performance gold historical`
8. `gold ETF flows historical trends 2010-2025`
9. `gold mining output decline historical analysis`
10. `gold crisis performance historical comparison`

Selection strategy (planner's call): rotate through queries deterministically by day-of-year modulo len(queries), OR pick top-scoring stories across ALL queries on each fallback fire, OR randomize. Rotation is cheapest and most predictable.

## Implementation sketch (for planner)

```python
# scheduler/agents/content/infographics.py

ANALYTICAL_HISTORICAL_QUERIES = [
    "gold price performance during major wars historical",
    "gold bull markets historical analysis 1970-2025",
    ...
]

async def run_draft_cycle() -> None:
    # Phase 1: news-based (existing, unchanged)
    news_items_queued = await run_text_story_cycle(
        agent_name=AGENT_NAME,
        content_type=CONTENT_TYPE,
        draft_fn=_draft,
        max_count=2,
        sort_by="score",
        dedup_scope="same_type",
    )
    # If run_text_story_cycle still returns None, query agent_runs for today's row.

    if news_items_queued < 2:
        shortfall = 2 - news_items_queued
        await _run_analytical_fallback(shortfall=shortfall)


async def _run_analytical_fallback(shortfall: int) -> None:
    """Fallback phase: fetch analytical-historical stories via SerpAPI,
    draft infographics to fill today's 2-per-day target.

    Uses the same _draft function as the news phase — no prompt changes.
    """
    # 1. Pick analytical queries (rotation by day-of-year recommended)
    # 2. Fetch stories via content_agent.fetch_analytical_historical_stories(queries)
    # 3. For each candidate up to `shortfall` count:
    #    - Run gold gate (is_gold_relevant_or_systemic_shock)
    #    - Call _draft(story, deep_research, market_snapshot, client=...)
    #    - Run content_agent.review(draft)
    #    - Persist as ContentBundle + DraftItem with content_type="infographic"
    # 4. Record agent_run row (or extend the news-phase row) with telemetry:
    #    notes: {"news_queued": N, "analytical_queued": M, "total_queued": N+M}
```

## Validation gates

```bash
# Scheduler
uv run pytest scheduler/tests/test_infographics.py -x -v
  → All green. New tests pass (3-4 added).

uv run pytest scheduler/ -x
  → 127 → ~130-131 (127 + 3-4 new tests). All green.

uv run ruff check scheduler/
  → Clean.

# Grep confirmations
grep -n "ANALYTICAL_HISTORICAL_QUERIES" scheduler/agents/content/infographics.py
  → 1-2 matches (list definition + usage site).

grep -n "_run_analytical_fallback\|fetch_analytical_historical_stories" scheduler/
  → Handful of matches in infographics.py, content_agent.py, test files.

grep -rn "gold_history_stories\|sub_gold_history" scheduler/agents/content/infographics.py
  → Zero matches (no coupling to sub_gold_history).

# sub_gold_history preservation check
git diff main -- scheduler/agents/content/gold_history.py
  → Empty (no changes).

git diff main -- scheduler/agents/content/gold_history_stories/
  → Empty (no changes).

# Drafter preservation check
git diff main -- scheduler/agents/content/infographics.py | grep -E "^[+-].*BRAND_PREAMBLE|^[+-].*_draft\(|image_prompt"
  → Only additive context lines; no modifications to these existing surfaces.
```

## Runtime behavior (post-deploy)

**Normal news day (news produces 2+ infographics):**
- 12:00 PT: sub_infographics fires news phase → produces 2 infographics → fallback doesn't trigger
- `agent_runs` row: items_queued=2, notes shows news-only pipeline
- Historical-analytical queries consume zero SerpAPI credits that day

**Sparse news day (news produces 0-1 infographics):**
- 12:00 PT: sub_infographics fires news phase → produces 0 or 1
- Immediately fires fallback phase → fetches analytical-historical stories → produces enough to hit 2 total
- `agent_runs` row: items_queued=2 (combined), notes shows news_queued + analytical_queued breakdown

**Budget impact:**
- SerpAPI: ~10 additional searches per fallback fire. If fallback fires on 30% of days, that's ~3 additional searches/day average. Well within monthly budget.
- Anthropic: fallback calls `_draft` (Sonnet) and `content_agent.review` (Haiku) for each analytical story. Same cost structure as news drafts. Small marginal impact.

## Related recent work

- **`260422-of3`** — sub_infographics independence (`dedup_scope="same_type"`, `max_count=2`, `sort_by="score"`). This task BUILDS ON of3's foundation — no regression to of3 behavior.
- **`260423-hq7`** — `max_count` break-after-N-successes semantics. lvp relies on hq7: the news phase's max_count=2 now correctly iterates past dedup hits, so a low items_queued means genuinely few gate-passing stories (not an early-loop trim bug).
- **`260423-j7x`** — bearish-toward-gold filter. Analytical-historical stories about "gold during wars" or "gold during recessions" should PASS the j7x filter because they're frame-neutral pattern analyses (not bearish predictions). If j7x rejects analytical content, that's a tuning discussion separate from lvp.
- **`260423-k8n`** — sub_long_form removal (just shipped). Topology is now 6 sub-agents. lvp does NOT change the sub-agent count.
- **`260421-eoe`** — the 7→1 monolith split that created sub_infographics originally.
- **`260422-lbb`** — sub_gold_history curated whitelist + every-other-day cadence. lvp explicitly PRESERVES all of lbb (Q5 + Q6 locked).

## Scope constraints

- **No changes to `sub_gold_history`.** Zero touches to that agent, its tests, its whitelist, its cron.
- **No drafter prompt changes.** `_draft`, `BRAND_PREAMBLE`, `image_prompt` construction all unchanged.
- **No cron changes.** Both agents keep current cadence.
- **No DB migration.** Schema unchanged.
- **No frontend changes.** Fallback rows surface as normal `content_type='infographic'` entries.
- **Single atomic commit** if the diff stays small enough. If the test additions balloon, a 2-commit sequence (impl + tests) is acceptable.

## Self-check for planner

- [ ] `sub_gold_history.py` is NOT in the list of files modified
- [ ] `gold_history_stories/*.json` is NOT in the list of files modified
- [ ] `infographics.py::_draft` is preserved (no prompt changes)
- [ ] `infographics.py::BRAND_PREAMBLE` is preserved
- [ ] `content_agent.py::SERPAPI_KEYWORDS` is preserved (new list is SEPARATE)
- [ ] `content_agent.py::fetch_stories()` is preserved (new helper is SIDE-BY-SIDE)
- [ ] All 4 existing callers of `run_text_story_cycle` (breaking_news, threads, quotes, infographics) continue to work identically if the return type changes from `None` → `int`
- [ ] Fallback fires ONLY when news items_queued < 2
- [ ] Fallback produces exactly `2 - news_items_queued` items when it fires
- [ ] Analytical queries don't consume SerpAPI on non-fallback days
- [ ] Tests cover all three scenarios: 0 news → 2 analytical, 1 news → 1 analytical, 2 news → 0 analytical
