---
quick_task: 260423-lvp
slug: add-analytical-historical-fallback-to-sub-infographics
subsystem: scheduler/agents/content/infographics + scheduler/agents/content_agent
tags: [infographics, fallback, analytical-historical, 2-per-day-guarantee, serpapi, tdd]
created: 2026-04-23
mode: quick
commit_strategy: atomic-per-task (6 commits, TDD-ordered)
context_input: .planning/quick/260423-lvp-add-analytical-historical-fallback-to-su/260423-lvp-CONTEXT.md
autonomous: true

files_modified:
  - scheduler/agents/content_agent.py
  - scheduler/agents/content/__init__.py
  - scheduler/agents/content/infographics.py
  - scheduler/tests/test_infographics.py
  - scheduler/tests/test_content_agent.py

files_unchanged_explicit_preservation:
  - scheduler/agents/content/gold_history.py
  - scheduler/agents/content/gold_history_stories/
  - scheduler/agents/content_agent.py::SERPAPI_KEYWORDS        # unchanged; new list is SEPARATE
  - scheduler/agents/content_agent.py::fetch_stories()         # unchanged; new helper SIDE-BY-SIDE
  - scheduler/agents/content/infographics.py::_draft           # unchanged; no prompt edits
  - scheduler/agents/content/infographics.py::BRAND_PREAMBLE   # unchanged
  - scheduler/worker.py                                        # no cron changes
  - frontend/                                                  # no UI changes
  - alembic/                                                   # no migration

architectural_choices_locked:
  - "items_queued signal: Path A — run_text_story_cycle return type None → int. Lower blast radius than a DB re-query. Other 3 callers (breaking_news, threads, quotes) ignore the return; no caller edits."
  - "Agent run row for fallback: SEPARATE AgentRun row with agent_name=AGENT_NAME and notes={'phase':'analytical_fallback','shortfall':N,'queued':M}. Cleaner telemetry than extending the news row."
  - "Query rotation: deterministic shuffle seeded by date.today().toordinal(); take top (shortfall + 2) queries to give a small buffer for empty/rejected fetches."
  - "Fetch helper: content_agent.fetch_analytical_historical_stories(queries: list[str]) -> list[dict]. Mirrors _fetch_all_serpapi pattern. NOT cached (rare calls, query-specific)."
  - "Fallback helper: infographics._run_analytical_fallback(shortfall: int) -> int. Returns queued count for logging parity."

must_haves:
  truths:
    - "sub_infographics produces exactly 2 infographics per day, regardless of news availability"
    - "Fallback fires ONLY when news phase items_queued < 2"
    - "Fallback queues exactly (2 - news_items_queued) items"
    - "Analytical queries consume ZERO SerpAPI credits on days when news phase already produced 2"
    - "sub_gold_history remains fully independent and unchanged (every-other-day cadence, narrative format)"
    - "All 4 existing run_text_story_cycle callers (breaking_news, threads, quotes, infographics) still pass their tests after return-type change"
    - "Fallback infographics surface identically to news infographics in the /agents/infographics UI (content_type='infographic')"
  artifacts:
    - path: "scheduler/agents/content_agent.py"
      contains: "async def fetch_analytical_historical_stories"
    - path: "scheduler/agents/content/infographics.py"
      contains: "ANALYTICAL_HISTORICAL_QUERIES"
      contains_also: "_run_analytical_fallback"
      contains_also: "_select_analytical_queries"
    - path: "scheduler/agents/content/__init__.py"
      contains: "-> int"  # run_text_story_cycle new return type
  key_links:
    - from: "infographics.run_draft_cycle"
      to: "run_text_story_cycle"
      via: "await news_items_queued = ..."
      broken_if: "news_items_queued is None OR fallback does not read this int"
    - from: "infographics._run_analytical_fallback"
      to: "content_agent.fetch_analytical_historical_stories"
      via: "queries list passed through"
      broken_if: "fallback calls fetch_stories() instead"
    - from: "ANALYTICAL_HISTORICAL_QUERIES"
      to: "SERPAPI_KEYWORDS"
      relation: "DISJOINT — two separate lists"
      broken_if: "analytical queries appended to SERPAPI_KEYWORDS"
---

<goal>

Add an analytical-historical fallback tier to `sub_infographics` that guarantees exactly 2 infographics per day. When the existing news pipeline (`run_text_story_cycle`) produces fewer than 2 items_queued, a second phase fires: fetch analytical-historical gold stories via SerpAPI (e.g. "gold during major wars"), run them through the SAME `_draft` function with the SAME prompts, and persist as `content_type="infographic"` to fill the shortfall. On normal news days (2+ queued), the fallback does not fire and zero SerpAPI credits are consumed by analytical queries. `sub_gold_history` is untouched; `_draft`, `BRAND_PREAMBLE`, `SERPAPI_KEYWORDS`, and `fetch_stories()` are untouched.

Success = 6 atomic commits (5 impl + 1 validation gate), scheduler pytest grows 127 → ~132-134, ruff clean, and on simulated zero-news day the cycle queues exactly 2 analytical infographics.

</goal>

<non_goals>

- Do NOT modify `sub_gold_history.py`, its whitelist, or its cron. (Locked Q1 + Q5 + Q6.)
- Do NOT touch `_draft`, `BRAND_PREAMBLE`, or `image_prompt` construction. (Locked Q7.)
- Do NOT add analytical queries to `SERPAPI_KEYWORDS`. Keep lists disjoint.
- Do NOT modify `fetch_stories()` or its cache — add a new helper alongside.
- Do NOT change `scheduler/worker.py` cron offsets or cadence.
- Do NOT write a DB migration. Schema unchanged.
- Do NOT touch frontend. Fallback rows surface as normal `content_type='infographic'`.
- Do NOT edit 3 of the 4 `run_text_story_cycle` callers (breaking_news, threads, quotes) — they ignore the new int return.

</non_goals>

<success_criteria>

- [ ] `uv run pytest scheduler/tests/test_infographics.py -x -v` — all green; 4-6 new tests pass
- [ ] `uv run pytest scheduler/tests/test_content_agent.py -x -v` — all green; 1-2 new tests pass
- [ ] `uv run pytest scheduler/ -x` — 127 → ~132-134 (all green)
- [ ] `uv run pytest -x` (repo root) — all suites green
- [ ] `uv run ruff check scheduler/` — clean
- [ ] `uv run ruff format --check scheduler/` — clean
- [ ] `grep -n "ANALYTICAL_HISTORICAL_QUERIES" scheduler/agents/content/infographics.py` — ≥2 matches (definition + usage)
- [ ] `grep -rn "_run_analytical_fallback\|fetch_analytical_historical_stories" scheduler/` — matches in infographics.py + content_agent.py + both test files
- [ ] `grep -rn "gold_history_stories\|sub_gold_history" scheduler/agents/content/infographics.py` — 0 matches (no coupling)
- [ ] `git diff main -- scheduler/agents/content/gold_history.py` — empty
- [ ] `git diff main -- scheduler/agents/content/gold_history_stories/` — empty
- [ ] `git diff main -- scheduler/worker.py` — empty
- [ ] `git diff main -- frontend/` — empty
- [ ] Simulated zero-news scenario (T5 test) queues exactly 2 analytical infographics
- [ ] Simulated 2-news scenario (T5 test) queues 0 analytical infographics AND invokes zero SerpAPI calls on the fallback path

</success_criteria>

<tasks>

## T1 — Add `fetch_analytical_historical_stories` helper to content_agent.py (RED+GREEN)

**Files:**
- `scheduler/agents/content_agent.py` (additive — new function alongside `_fetch_all_serpapi`)
- `scheduler/tests/test_content_agent.py` (additive — 2 new tests)

**Action:**

1. **RED (test first):** In `test_content_agent.py`, add 2 tests:
   - `test_fetch_analytical_historical_stories_returns_story_shape`: mock `serpapi.Client`, pass `queries=["gold during wars", "gold recessions 2008"]`, assert returned list has dicts with keys `title, link, published, summary, source_name` (same shape as `fetch_stories()` per-story dict before scoring).
   - `test_fetch_analytical_historical_stories_handles_no_client`: pass `serpapi_client=None` OR invoke with SerpAPI key missing — function returns `[]` and logs a warning (no crash). If the helper always fetches its own client from settings, simulate by monkeypatching settings or by patching `serpapi.Client` to raise.

2. **GREEN:** In `content_agent.py`, add immediately after `_fetch_all_serpapi` (around L776):

```python
async def fetch_analytical_historical_stories(queries: list[str]) -> list[dict]:
    """Fallback fetch for sub_infographics — analytical-historical gold topics.

    Mirrors _fetch_all_serpapi pattern but accepts a custom query list. Used by
    sub_infographics.run_draft_cycle when the news phase produces <2 queued
    items (quick-260423-lvp). Intentionally NOT cached: invoked rarely and the
    query list is caller-specific.

    Returns story dicts in the same shape as fetch_stories() per-story entries
    BEFORE scoring (keys: title, link, published, summary, source_name). The
    caller is responsible for gold-gate + draft + review + persist.

    Returns [] if SerpAPI is not configured or if all queries fail.
    """
    settings = get_settings()
    if not settings.serpapi_api_key:
        logger.warning(
            "fetch_analytical_historical_stories: SerpAPI not configured — returning []",
        )
        return []
    serpapi_client = serpapi.Client(api_key=settings.serpapi_api_key)
    loop = asyncio.get_event_loop()
    tasks = []
    for q in queries:
        def _call(query=q):
            return serpapi_client.search({
                "engine": "google_news",
                "q": query,
                "num": 5,
            })
        tasks.append(loop.run_in_executor(None, _call))
    results = await asyncio.gather(*tasks, return_exceptions=True)
    stories: list[dict] = []
    for query, result in zip(queries, results):
        if isinstance(result, Exception):
            logger.warning(
                "fetch_analytical_historical_stories: query '%s' failed: %s",
                query, result,
            )
            continue
        for item in result.get("news_results", [])[:5]:
            iso_date = item.get("date")
            if iso_date:
                try:
                    published = datetime.fromisoformat(iso_date.replace("Z", "+00:00"))
                except ValueError:
                    try:
                        published = datetime.strptime(
                            iso_date, "%m/%d/%Y, %I:%M %p, +0000 UTC",
                        ).replace(tzinfo=timezone.utc)
                    except ValueError:
                        published = datetime.now(timezone.utc)
            else:
                published = datetime.now(timezone.utc)
            source_name = (item.get("source") or {}).get("name", "unknown")
            stories.append({
                "title": item.get("title", ""),
                "link": item.get("link", ""),
                "published": published,
                "summary": item.get("snippet", ""),
                "source_name": source_name,
            })
    logger.info(
        "fetch_analytical_historical_stories: %d queries → %d stories",
        len(queries), len(stories),
    )
    return stories
```

Do NOT modify `SERPAPI_KEYWORDS` or `fetch_stories()`. The new function is fully side-by-side.

**Verify:**
```bash
uv run pytest scheduler/tests/test_content_agent.py::test_fetch_analytical_historical_stories_returns_story_shape scheduler/tests/test_content_agent.py::test_fetch_analytical_historical_stories_handles_no_client -x -v
grep -c "SERPAPI_KEYWORDS" scheduler/agents/content_agent.py  # unchanged count
grep -n "def fetch_stories" scheduler/agents/content_agent.py  # unchanged signature
```

**Done:** 2 new tests green. Grep confirms SERPAPI_KEYWORDS unchanged and fetch_stories() signature unchanged.

**Commit message:**
```
feat(scheduler): add fetch_analytical_historical_stories helper (quick 260423-lvp T1)

Side-by-side with _fetch_all_serpapi — accepts a custom query list, returns
pre-scoring story dicts. Used by sub_infographics fallback phase. SERPAPI_KEYWORDS
and fetch_stories() are unchanged.

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>
```

---

## T2 — Change `run_text_story_cycle` return type `None → int` (GREEN, regression-protected)

**Files:**
- `scheduler/agents/content/__init__.py`

**Action:**

1. Update signature (around L82-91):
   ```python
   async def run_text_story_cycle(
       *,
       agent_name: str,
       content_type: str,
       draft_fn,
       max_count: int | None = None,
       source_whitelist: frozenset[str] | None = None,
       sort_by: Literal["published_at", "score"] = "published_at",
       dedup_scope: Literal["cross_agent", "same_type"] = "cross_agent",
   ) -> int:
   ```
2. Update docstring: add a final `Returns:` block stating `int — items_queued (0 if no candidates, fetch failure, or all candidates filtered/compliance-blocked). Callers other than sub_infographics may ignore this value; it is preserved for sub_infographics' two-phase fallback (quick-260423-lvp).`
3. Return `items_queued` at ALL exit paths:
   - Empty-candidates early-return (currently `return` at L216): change to `return items_queued` (will be 0 at that point).
   - Normal completion at end of `try` block (after `agent_run.status = "completed"` L344): add `return items_queued`.
   - Exception branch (L345-348): the current `except` sets status=failed and falls through to `finally`. After `finally`, add `return items_queued` at the function's top level (outside try/except/finally) so exception-path callers get 0 (or whatever was queued before the exception). Equivalent: inside the `except`, set `items_queued = 0` if you want strict zero-on-error semantics — BUT that discards partial progress. Prefer: preserve whatever `items_queued` reached and return it.

   Concrete structure:
   ```python
   async with AsyncSessionLocal() as session:
       agent_run = AgentRun(...)
       session.add(agent_run); await session.commit()
       items_queued = 0
       try:
           # ... all existing logic ...
           if not candidates:
               # existing notes-writing branch
               agent_run.status = "completed"
               # DO NOT return here anymore — fall through to finally
           else:
               # existing iteration + agent_run.items_queued = items_queued + notes
               agent_run.status = "completed"
       except Exception as exc:
           agent_run.status = "failed"
           agent_run.errors = str(exc)
           logger.error(...)
       finally:
           agent_run.ended_at = datetime.now(timezone.utc)
           await session.commit()
   return items_queued
   ```

   **CAUTION:** The current code has an early `return` at L216 inside `if not candidates:`. Refactor that to set `agent_run.status = "completed"` and fall through, OR change the `return` to `return items_queued` (with `items_queued` currently 0 at that point). The latter is a smaller diff but requires the `finally` block's `agent_run.ended_at` + `await session.commit()` to ALSO run on that path — which it already does because `return` inside `try` triggers `finally`. Smaller diff:
   - Change L216 `return` → `return items_queued`
   - Add `return items_queued` at the very end of the function (after the `async with` block closes).

4. No caller-side edits in breaking_news.py, threads.py, quotes.py. They currently use `await run_text_story_cycle(...)` with the result discarded; `-> int` return doesn't break discard-pattern callers. Verify by re-reading each of the 3 caller modules:
   ```bash
   grep -n "run_text_story_cycle" scheduler/agents/content/breaking_news.py scheduler/agents/content/threads.py scheduler/agents/content/quotes.py
   ```
   Each should show `await run_text_story_cycle(...)` as a statement (not `x = await run_text_story_cycle(...)`). If any caller DOES capture the return, verify the new int doesn't break their logic.

5. Also update the docstring reference in `scheduler/agents/content/__init__.py` L92 to say `Used by 4 of the 6 sub-agents (breaking_news, threads, quotes, infographics). Returns items_queued — sub_infographics uses it for the two-phase fallback check; the other 3 callers discard it.`

**Verify:**
```bash
uv run pytest scheduler/tests/test_content_init.py -x -v  # existing coverage for this module
uv run pytest scheduler/tests/test_breaking_news.py scheduler/tests/test_threads.py scheduler/tests/test_quotes.py scheduler/tests/test_infographics.py -x
grep -n "-> int" scheduler/agents/content/__init__.py | head -1  # confirms new signature present
```

**Done:** All existing scheduler tests still pass with the new int return. No caller-side edits needed. `grep -n "return items_queued"` shows 2 return sites inside `run_text_story_cycle`.

**Commit message:**
```
refactor(scheduler): run_text_story_cycle returns int items_queued (quick 260423-lvp T2)

Prepares the pipeline for sub_infographics' two-phase fallback (T5). The other
3 callers (breaking_news, threads, quotes) discard the return value — no
caller-side changes needed.

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>
```

---

## T3 — Add `ANALYTICAL_HISTORICAL_QUERIES` + `_select_analytical_queries` to infographics.py (GREEN + test)

**Files:**
- `scheduler/agents/content/infographics.py`
- `scheduler/tests/test_infographics.py`

**Action:**

1. **RED:** Add test `test_select_analytical_queries_deterministic_and_rotates`:
   - Asserts `_select_analytical_queries(2)` called twice on the same day returns the same list (deterministic).
   - Asserts when simulating two consecutive days via `monkeypatch` on `date.today`, the output lists differ OR the ordering differs (rotation).
   - Asserts returned count equals `min(shortfall + buffer, len(ANALYTICAL_HISTORICAL_QUERIES))`.

2. **GREEN:** At module top of `infographics.py` (after the existing module docstring + CONTENT_TYPE/AGENT_NAME constants, around L24):

```python
ANALYTICAL_HISTORICAL_QUERIES: list[str] = [
    "gold price performance during major wars historical",
    "gold bull markets historical analysis 1970-2025",
    "central bank gold purchases trends 2020-2025",
    "gold inflation correlation 50 years historical",
    "gold during recessions analysis 1973 2008 2020",
    "gold vs dollar weakness historical pattern",
    "safe haven asset performance gold historical",
    "gold ETF flows historical trends 2010-2025",
    "gold mining output decline historical analysis",
    "gold crisis performance historical comparison",
]


def _select_analytical_queries(shortfall: int, *, buffer: int = 2) -> list[str]:
    """Pick (shortfall + buffer) queries with a day-seeded deterministic shuffle.

    Rotation strategy (quick-260423-lvp): seed random.Random with
    date.today().toordinal() so every invocation on the same day returns the
    same list, but the list differs across consecutive days. Buffer compensates
    for fetches that return empty or get gold-gate-rejected.

    Clamped to len(ANALYTICAL_HISTORICAL_QUERIES).
    """
    import random as _random  # noqa: PLC0415 — local import keeps module surface minimal
    from datetime import date as _date  # noqa: PLC0415

    count = min(shortfall + buffer, len(ANALYTICAL_HISTORICAL_QUERIES))
    rng = _random.Random(_date.today().toordinal())
    shuffled = list(ANALYTICAL_HISTORICAL_QUERIES)
    rng.shuffle(shuffled)
    return shuffled[:count]
```

**Verify:**
```bash
uv run pytest scheduler/tests/test_infographics.py::test_select_analytical_queries_deterministic_and_rotates -x -v
grep -n "ANALYTICAL_HISTORICAL_QUERIES" scheduler/agents/content/infographics.py  # expect 2 matches
```

**Done:** New test green. `ANALYTICAL_HISTORICAL_QUERIES` is module-level. `_select_analytical_queries` is pure (no I/O) — easy to test.

**Commit message:**
```
feat(scheduler): add ANALYTICAL_HISTORICAL_QUERIES + rotation helper (quick 260423-lvp T3)

10 analytical-historical gold queries with a day-seeded deterministic shuffle.
No network, no state — pure rotation pick. Consumed by _run_analytical_fallback
in T4.

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>
```

---

## T4 — Add `_run_analytical_fallback(shortfall)` helper to infographics.py (RED + GREEN)

**Files:**
- `scheduler/agents/content/infographics.py`
- `scheduler/tests/test_infographics.py`

**Action:**

1. **RED:** Add 3 tests:
   - `test_run_analytical_fallback_produces_shortfall_items`: mock `fetch_analytical_historical_stories` to return 3 stories, gold gate `keep=True`, draft + review pass. Call `_run_analytical_fallback(shortfall=2)`. Assert 2 DraftItem persists + 2 ContentBundle with `content_type="infographic"`. Fallback returns `2`.
   - `test_run_analytical_fallback_returns_zero_on_empty_fetch`: mock fetch to return `[]`. Call with `shortfall=2`. Assert returns `0`, no exception, AgentRun row persisted with `notes={"phase":"analytical_fallback","shortfall":2,"queued":0}`.
   - `test_run_analytical_fallback_returns_zero_when_gate_rejects_all`: mock fetch returns 3 stories, gold gate `keep=False` for all. Assert returns `0`, zero DraftItems.

2. **GREEN:** Add `_run_analytical_fallback` in `infographics.py`:

```python
async def _run_analytical_fallback(shortfall: int) -> int:
    """Second-phase fallback for sub_infographics — fetch analytical-historical
    stories and draft infographics to fill the daily 2-per-day target.

    Fires ONLY when the news phase returns items_queued < 2 (quick-260423-lvp).
    Uses the SAME _draft function as the news phase — no prompt edits.

    Writes a SEPARATE AgentRun row (agent_name=AGENT_NAME, notes includes
    phase='analytical_fallback') so telemetry is distinct from the news row.

    Returns the number of items queued by the fallback phase (0..shortfall).
    """
    if shortfall <= 0:
        return 0

    settings = get_settings()
    anthropic_client = AsyncAnthropic(api_key=settings.anthropic_api_key)
    queries = _select_analytical_queries(shortfall)

    async with AsyncSessionLocal() as session:
        agent_run = AgentRun(
            agent_name=AGENT_NAME,
            status="running",
            started_at=datetime.now(timezone.utc),
            items_found=0,
            items_queued=0,
            items_filtered=0,
        )
        session.add(agent_run)
        await session.commit()

        items_queued = 0
        try:
            try:
                market_snapshot = await fetch_market_snapshot(session=session)
            except Exception as exc:  # noqa: BLE001
                logger.warning(
                    "%s analytical_fallback: market snapshot failed (%s)",
                    AGENT_NAME, type(exc).__name__,
                )
                market_snapshot = None

            stories = await content_agent.fetch_analytical_historical_stories(queries)
            agent_run.items_found = len(stories)
            if not stories:
                agent_run.notes = json.dumps({
                    "phase": "analytical_fallback",
                    "shortfall": shortfall,
                    "queued": 0,
                })
                agent_run.status = "completed"
                return 0

            gate_config = {
                "content_gold_gate_enabled": "true",
                "content_gold_gate_model": "claude-haiku-4-5",
                "content_bearish_filter_enabled": "true",
            }

            for story in stories:
                if items_queued >= shortfall:
                    break
                try:
                    if await _is_already_covered_today(
                        session, story["link"], story["title"],
                        content_type=CONTENT_TYPE,  # same_type scope (matches news phase)
                    ):
                        continue

                    gate = await content_agent.is_gold_relevant_or_systemic_shock(
                        story, gate_config, client=anthropic_client,
                    )
                    if not gate["keep"]:
                        continue

                    article_text, fetch_ok = await content_agent.fetch_article(
                        story["link"], fallback_text=story.get("summary", ""),
                    )
                    corroborating = await content_agent.search_corroborating(story["title"])
                    deep_research = {
                        "article_text": article_text[:5000],
                        "article_fetch_succeeded": fetch_ok,
                        "corroborating_sources": corroborating,
                        "key_data_points": [],
                    }

                    draft_content = await _draft(
                        story, deep_research, market_snapshot, client=anthropic_client,
                    )
                    if draft_content is None:
                        continue

                    rationale = draft_content.pop("_rationale", "")
                    key_data_points = draft_content.pop("_key_data_points", [])
                    deep_research["key_data_points"] = key_data_points

                    review_result = await content_agent.review(draft_content)
                    compliance_ok = bool(review_result.get("compliance_passed", False))

                    bundle = ContentBundle(
                        story_headline=story["title"],
                        story_url=story["link"],
                        source_name=story.get("source_name"),
                        content_type=CONTENT_TYPE,
                        score=0.0,  # analytical stories skip shared scorer; score=0 is fine
                        deep_research=deep_research,
                        draft_content=draft_content,
                        compliance_passed=compliance_ok,
                    )
                    session.add(bundle)
                    await session.flush()

                    if compliance_ok:
                        item = content_agent.build_draft_item(bundle, rationale)
                        session.add(item)
                        await session.flush()
                        items_queued += 1
                        logger.info(
                            "%s analytical_fallback: queued '%s'",
                            AGENT_NAME, story["title"][:60],
                        )
                except Exception as exc:
                    logger.error(
                        "%s analytical_fallback: error on story %r: %s",
                        AGENT_NAME, story.get("title", "")[:60], exc, exc_info=True,
                    )

            agent_run.items_queued = items_queued
            agent_run.notes = json.dumps({
                "phase": "analytical_fallback",
                "shortfall": shortfall,
                "queued": items_queued,
            })
            agent_run.status = "completed"
        except Exception as exc:
            agent_run.status = "failed"
            agent_run.errors = str(exc)
            logger.error("%s analytical_fallback failed: %s", AGENT_NAME, exc, exc_info=True)
        finally:
            agent_run.ended_at = datetime.now(timezone.utc)
            await session.commit()
    return items_queued
```

Add required imports at top of `infographics.py`:
```python
import json
from datetime import datetime, timezone

from agents import content_agent
from agents.content import _is_already_covered_today
from config import get_settings
from database import AsyncSessionLocal
from models.agent_run import AgentRun
from models.content_bundle import ContentBundle
from services.market_snapshot import fetch_market_snapshot
```

(Some of these may already be implicitly available via `agents.content`'s `run_text_story_cycle` import path — re-verify the existing `infographics.py` top-of-file imports and add only what's missing. `_is_already_covered_today` is currently private to `agents.content`; importing it is acceptable — it's in the same package and already exposed as a module-level async function.)

**Verify:**
```bash
uv run pytest scheduler/tests/test_infographics.py::test_run_analytical_fallback_produces_shortfall_items scheduler/tests/test_infographics.py::test_run_analytical_fallback_returns_zero_on_empty_fetch scheduler/tests/test_infographics.py::test_run_analytical_fallback_returns_zero_when_gate_rejects_all -x -v
grep -n "_run_analytical_fallback" scheduler/agents/content/infographics.py  # expect 1+ (definition; T5 adds call site)
```

**Done:** 3 new tests green. `_draft` and `BRAND_PREAMBLE` diff vs main is empty (verify with `git diff main -- scheduler/agents/content/infographics.py | grep -E "^[+-].*_draft\(|BRAND_PREAMBLE"` — should show only additive context lines, no `-` lines in those surfaces).

**Commit message:**
```
feat(scheduler): add _run_analytical_fallback helper to sub_infographics (quick 260423-lvp T4)

Fetches via fetch_analytical_historical_stories → gold gate → _draft (unchanged)
→ review → persist as content_type='infographic'. Writes a SEPARATE AgentRun row
with notes.phase='analytical_fallback'. Not yet wired into run_draft_cycle — T5
adds the two-phase call site.

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>
```

---

## T5 — Wire two-phase `run_draft_cycle` (RED + GREEN)

**Files:**
- `scheduler/agents/content/infographics.py`
- `scheduler/tests/test_infographics.py`

**Action:**

1. **RED:** Add 3 tests:
   - `test_run_draft_cycle_zero_news_triggers_two_analytical`: patch `run_text_story_cycle` to return `0`. Patch `_run_analytical_fallback` to record its call args. Assert fallback called with `shortfall=2` and returns `2`.
   - `test_run_draft_cycle_one_news_triggers_one_analytical`: patch `run_text_story_cycle` to return `1`. Assert fallback called with `shortfall=1`.
   - `test_run_draft_cycle_two_news_skips_fallback_no_serpapi_call`: patch `run_text_story_cycle` to return `2`. Patch `content_agent.fetch_analytical_historical_stories` with a spy (AsyncMock). Assert `_run_analytical_fallback` NOT called AND `fetch_analytical_historical_stories.await_count == 0` (zero SerpAPI credit consumption on normal news days — locked constraint #11).

2. **GREEN:** Replace the existing `run_draft_cycle` body (L137-156):

```python
async def run_draft_cycle() -> None:
    """Two-phase pipeline — guarantees 2 infographics/day (quick-260423-lvp).

    Phase 1 (news): existing run_text_story_cycle with max_count=2, sort_by='score',
    dedup_scope='same_type' (per quick-260422-of3).

    Phase 2 (analytical-historical fallback): fires ONLY when phase 1 queued <2.
    Fetches via content_agent.fetch_analytical_historical_stories using a day-seeded
    rotation through ANALYTICAL_HISTORICAL_QUERIES. Runs stories through the SAME
    _draft function — no prompt changes.

    Configured per quick-260422-of3:
    - max_count=2: produce the 2 best infographics per day (D-04)
    - sort_by='score': pick best by quality/score (D-01)
    - dedup_scope='same_type': allow reuse of breaking_news stories (D-02)
    """
    news_items_queued = await run_text_story_cycle(
        agent_name=AGENT_NAME,
        content_type=CONTENT_TYPE,
        draft_fn=_draft,
        max_count=2,
        sort_by="score",
        dedup_scope="same_type",
    )
    if news_items_queued < 2:
        shortfall = 2 - news_items_queued
        analytical_queued = await _run_analytical_fallback(shortfall=shortfall)
        logger.info(
            "%s: two-phase summary — news=%d, analytical=%d, total=%d",
            AGENT_NAME, news_items_queued, analytical_queued,
            news_items_queued + analytical_queued,
        )
    else:
        logger.info(
            "%s: news phase queued %d items — fallback skipped",
            AGENT_NAME, news_items_queued,
        )
```

**Caution — existing test impact:** `test_run_draft_cycle_passes_new_kwargs` (test_infographics.py L96-122) mocks `run_text_story_cycle` with `AsyncMock(side_effect=fake_cycle)` where `fake_cycle` returns `None`. After T2 the cycle returns `int`, and after T5 `run_draft_cycle` reads that int. Update `fake_cycle` to `return 2` (or have it return an int so the `< 2` branch is not triggered). Similarly, `test_run_draft_cycle_writes_structured_notes` and `test_run_draft_cycle_writes_notes_on_empty_candidates` currently rely on `run_text_story_cycle` completing and writing notes — with the new wiring, the `run_draft_cycle` wrapper may ALSO fire the fallback if `items_queued < 2`. Patch `_run_analytical_fallback` with `AsyncMock(return_value=0)` in those two tests to prevent the fallback from double-committing AgentRun rows that would break their existing assertions.

**Verify:**
```bash
uv run pytest scheduler/tests/test_infographics.py -x -v  # all tests, old + new
uv run pytest scheduler/ -x  # expect ~132-134 passing
grep -n "_run_analytical_fallback\|fetch_analytical_historical_stories" scheduler/agents/content/infographics.py  # expect 2+
```

**Done:** All tests green. The three-scenario matrix (0→2, 1→1, 2→0) is covered. Zero-SerpAPI-on-news-success constraint enforced via test spy.

**Commit message:**
```
feat(scheduler): wire two-phase run_draft_cycle with analytical fallback (quick 260423-lvp T5)

sub_infographics now guarantees 2 infographics/day: news phase first, then
analytical-historical fallback if items_queued < 2. Zero SerpAPI calls on
normal news days (verified by test spy on fetch_analytical_historical_stories).

Locked constraints honored:
- _draft, BRAND_PREAMBLE, SERPAPI_KEYWORDS, fetch_stories, sub_gold_history
  all unchanged
- Fallback fires only when news_items_queued < 2
- Top-up is exactly 2 - news_items_queued

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>
```

---

## T6 — Final validation gate (no new code)

**Files:** none modified; this task is a validation sweep before declaring done.

**Action:**

Run every command in `<validation_gates>` below. Any non-green result → stop, diagnose, fix, re-run. Do NOT ship until every gate passes.

**Verify:** See `<validation_gates>` section.

**Done:** All gates green. `git status` clean except for staged commits from T1-T5. Ready to ship.

**Commit:** No new commit — this task is validation only. (Alternative: if any small fix is discovered during validation, it lands as T6-commit with a precise message describing the fix.)

</tasks>

<validation_gates>

```bash
# -------- Python test gates --------
cd /Users/matthewnelson/seva-mining

uv run pytest scheduler/tests/test_infographics.py -x -v
# EXPECTED: all green; 4-6 new tests visible in output

uv run pytest scheduler/tests/test_content_agent.py -x -v
# EXPECTED: all green; 2 new tests visible

uv run pytest scheduler/ -x
# EXPECTED: 127 → ~132-134 passing, all green

uv run pytest -x
# EXPECTED: all repo test suites green

uv run ruff check scheduler/
# EXPECTED: All checks passed!

uv run ruff format --check scheduler/
# EXPECTED: clean (no reformat needed)

# -------- Presence grep gates --------
grep -n "ANALYTICAL_HISTORICAL_QUERIES" scheduler/agents/content/infographics.py
# EXPECTED: ≥2 matches (definition at top, usage inside _select_analytical_queries)

grep -rn "_run_analytical_fallback\|fetch_analytical_historical_stories" scheduler/
# EXPECTED: matches in infographics.py (definition + call), content_agent.py (definition),
# test_infographics.py, test_content_agent.py

grep -n "def fetch_analytical_historical_stories" scheduler/agents/content_agent.py
# EXPECTED: 1 match

# -------- Preservation gates (must be empty diffs) --------
git diff main -- scheduler/agents/content/gold_history.py
# EXPECTED: empty

git diff main -- scheduler/agents/content/gold_history_stories/
# EXPECTED: empty

git diff main -- scheduler/worker.py
# EXPECTED: empty

git diff main -- frontend/
# EXPECTED: empty

git diff main -- alembic/
# EXPECTED: empty (no migration)

# -------- Decoupling guard: no cross-coupling between sub_gold_history and sub_infographics --------
grep -rn "gold_history_stories\|sub_gold_history\|gold_history" scheduler/agents/content/infographics.py
# EXPECTED: 0 matches

# -------- _draft / BRAND_PREAMBLE preservation --------
git diff main -- scheduler/agents/content/infographics.py | grep -E "^-.*BRAND_PREAMBLE|^-.*async def _draft|^-.*image_prompt ="
# EXPECTED: 0 lines (no removals from these surfaces)

# -------- SERPAPI_KEYWORDS preservation --------
git diff main -- scheduler/agents/content_agent.py | grep -E "^[+-].*SERPAPI_KEYWORDS"
# EXPECTED: 0 lines (no edits to that list)

# -------- fetch_stories signature preservation --------
git diff main -- scheduler/agents/content_agent.py | grep -E "^-.*async def fetch_stories\("
# EXPECTED: 0 lines (signature unchanged; new helper is side-by-side)
```

**Pass criteria:** Every gate returns the expected output. Any deviation is a regression blocker.

</validation_gates>

<rollback_plan>

All 5 impl commits are atomic and ordered (T1 → T2 → T3 → T4 → T5). If a post-deploy regression surfaces, revert the full range in reverse order:

```bash
# From repo root, with <sha_T1>..<sha_T5> being the commit SHAs from this task:
git revert <sha_T5> <sha_T4> <sha_T3> <sha_T2> <sha_T1>
```

Or the convenience shorthand:
```bash
git revert <sha_T1>..<sha_T5>
```

Partial rollback: because T5 is the only commit that actually wires the new behavior into `run_draft_cycle`, reverting ONLY `<sha_T5>` is the minimum-impact rollback — the helpers stay in the tree (unused, dormant) and the existing one-phase news-only cycle is restored. This is the recommended first rollback step if a production regression appears. The remaining helpers can be cleaned up in a follow-up.

</rollback_plan>

<references>

- **CONTEXT.md (primary):** `.planning/quick/260423-lvp-add-analytical-historical-fallback-to-su/260423-lvp-CONTEXT.md` — all 8 decisions (Q1-Q8) locked.
- **`260423-k8n`** — sub_long_form removal (just shipped). Topology is now 6 sub-agents. This task does NOT change count.
- **`260423-j7x`** — bullish-only filter. Analytical-historical stories should pass naturally (frame-neutral pattern analyses).
- **`260423-hq7`** — `max_count` break-after-N-successes semantics. This task relies on hq7: low news_items_queued reflects genuine story scarcity, not early-loop trim bug.
- **`260422-of3`** — sub_infographics independence (`dedup_scope='same_type'`, `max_count=2`, `sort_by='score'`). This task extends of3's foundation.
- **`260422-lbb`** — sub_gold_history curated whitelist + every-other-day cadence. Explicitly PRESERVED — zero touches.
- **`260421-eoe`** — original 7→1 monolith split that created sub_infographics.

</references>
