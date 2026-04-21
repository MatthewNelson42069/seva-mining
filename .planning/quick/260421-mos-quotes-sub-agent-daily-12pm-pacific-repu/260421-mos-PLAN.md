---
phase: quick-260421-mos
plan: 01
type: execute
wave: 1
depends_on: []
files_modified:
  - scheduler/worker.py
  - scheduler/agents/content/__init__.py
  - scheduler/agents/content/quotes.py
  - scheduler/tests/test_worker.py
  - scheduler/tests/test_quotes.py
  - scheduler/tests/test_content_init.py
autonomous: true
requirements:
  - QUICK-260421-mos
user_setup: []

must_haves:
  truths:
    - "sub_quotes fires once per day at 12:00 America/Los_Angeles (cron), NOT on a 2h interval"
    - "The other 6 sub-agents continue firing on their existing interval cadences (breaking_news=1h, others=2h)"
    - "run_text_story_cycle(max_count=N) caps candidates to the top N by published_at desc"
    - "run_text_story_cycle(source_whitelist=frozenset) drops candidates whose source_name does not substring-match any whitelist pattern (case-insensitive)"
    - "quotes._draft returns None when the Claude response body is {\"reject\": true, ...}, triggering the existing stub-bundle path (compliance_passed=False, no draft_item)"
    - "The other 4 sub-agents using run_text_story_cycle (breaking_news, threads, long_form, infographics) see zero behavior change — max_count and source_whitelist default to None (no-op)"
    - "Scheduler ruff clean; scheduler pytest green; total test count increased vs pre-change baseline of 74"
  artifacts:
    - path: "scheduler/worker.py"
      provides: "CONTENT_INTERVAL_AGENTS (6 rows) + CONTENT_CRON_AGENTS (1 row, sub_quotes) + CronTrigger registration loop"
      contains: "CONTENT_CRON_AGENTS"
    - path: "scheduler/agents/content/__init__.py"
      provides: "run_text_story_cycle with max_count + source_whitelist kwargs (both None-default)"
      contains: "source_whitelist"
    - path: "scheduler/agents/content/quotes.py"
      provides: "REPUTABLE_SOURCES frozenset + run_draft_cycle wiring + _draft reject-path handler"
      contains: "REPUTABLE_SOURCES"
    - path: "scheduler/tests/test_content_init.py"
      provides: "4 filter-logic unit tests for run_text_story_cycle"
      contains: "test_source_whitelist_filters_stories"
  key_links:
    - from: "scheduler/worker.py::CONTENT_CRON_AGENTS"
      to: "scheduler/worker.py::build_scheduler cron loop"
      via: "7-tuple unpacking into CronTrigger"
      pattern: "CronTrigger\\(hour=hour, minute=minute, timezone=tz\\)"
    - from: "scheduler/agents/content/quotes.py::run_draft_cycle"
      to: "scheduler/agents/content/__init__.py::run_text_story_cycle"
      via: "max_count=2 + source_whitelist=REPUTABLE_SOURCES kwargs"
      pattern: "max_count=2"
    - from: "scheduler/agents/content/quotes.py::_draft reject path"
      to: "scheduler/agents/content/__init__.py stub-bundle branch"
      via: "return None triggers the if draft_content is None branch at __init__.py L160-171"
      pattern: "if parsed.get\\(.reject.\\) is True"
---

<objective>
Pivot the Quotes sub-agent from its current 2h IntervalTrigger to a daily cron at 12:00 America/Los_Angeles, add a tier-1 reputable-source whitelist + top-2 cap to the shared text-story pipeline (opt-in via kwargs; other 4 sub-agents unaffected), and add a drafter-side quality gate that lets Claude return `{"reject": true, "rationale": "..."}` when no quote in an article clears the quality bar.

Purpose: The Quotes content type is fundamentally different from the other text formats — quote value is ALL about who said it and whether the statement itself lands standalone. Running every 2h on the full news firehose produces too many weak drafts (anonymous strategists, filler commentary). This change (a) narrows the input to a curated list of tier-1 financial / gold-specialist / institutional sources, (b) caps to the top 2 candidates per day so total Claude spend stays bounded, (c) lets the drafter itself kill a story outright when no quote in it meets the 4-criterion quality bar (named credible speaker + specific substance + freshness + clarity), and (d) runs the whole pipeline once daily at 12pm Pacific (post-US-morning-news, pre-market-close) instead of 12x/day.

Output:
- `scheduler/worker.py`: split `CONTENT_SUB_AGENTS` → `CONTENT_INTERVAL_AGENTS` (6 rows) + `CONTENT_CRON_AGENTS` (1 row = sub_quotes); add `CronTrigger` import; add a second registration loop for cron agents; update 4 docstrings + the startup log line
- `scheduler/agents/content/__init__.py`: extend `run_text_story_cycle` signature with `max_count: int | None = None` and `source_whitelist: frozenset[str] | None = None`; implement the whitelist filter and top-N cap between the `candidates` list comprehension and the `if not candidates:` early-exit
- `scheduler/agents/content/quotes.py`: add module-level `REPUTABLE_SOURCES` frozenset (≥20 patterns); pass `max_count=2` and `source_whitelist=REPUTABLE_SOURCES` from `run_draft_cycle`; extend the `_draft` user prompt with a 4-criterion quality bar + reject-path JSON contract; add a reject handler before the `draft_content = parsed.get(...)` line that returns None
- `scheduler/tests/test_worker.py`: rename `CONTENT_SUB_AGENTS` imports → `CONTENT_INTERVAL_AGENTS` + import `CONTENT_CRON_AGENTS`; rescope 3 existing tests; add 1 new test (`test_quotes_is_daily_cron`)
- `scheduler/tests/test_quotes.py`: add 3 new tests (REPUTABLE_SOURCES populated; _draft returns None on reject; run_draft_cycle passes the two filter kwargs)
- `scheduler/tests/test_content_init.py`: NEW file with 4 tests covering the filter logic's 4 states (whitelist filters; max_count caps; both None-default no-op)
- ONE atomic commit on branch `quick/260421-mos-quotes-daily-noon-reputable` covering all 6 files, subject: `feat(scheduler): quotes sub-agent → daily 12pm Pacific + reputable whitelist + quality gate (quick-260421-mos)`
</objective>

<execution_context>
@$HOME/.claude/get-shit-done/workflows/execute-plan.md
@$HOME/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/STATE.md
@CLAUDE.md

# Task context:
@.planning/quick/260421-mos-quotes-sub-agent-daily-12pm-pacific-repu/260421-mos-CONTEXT.md

# Immediately prior quick task — same branch lineage, same file patterns for shape reference:
@.planning/quick/260421-m9k-breaking-news-sub-agent-hourly-cadence-o/260421-m9k-PLAN.md
@.planning/quick/260421-m9k-breaking-news-sub-agent-hourly-cadence-o/260421-m9k-SUMMARY.md

# Files being modified (read fully during execution):
@scheduler/worker.py
@scheduler/agents/content/__init__.py
@scheduler/agents/content/quotes.py
@scheduler/tests/test_worker.py
@scheduler/tests/test_quotes.py
@scheduler/tests/conftest.py

<interfaces>
<!-- Key signatures / current state the executor must preserve or transform. -->
<!-- No codebase exploration needed — these are the load-bearing anchors. -->

**Current `CONTENT_SUB_AGENTS` (scheduler/worker.py L82-94, post-m9k 6-tuple schema):**
```python
# Tuple shape: (job_id, run_fn, name, lock_id, offset_minutes, interval_hours).
CONTENT_SUB_AGENTS: list[tuple[str, object, str, int, int, int]] = [
    ("sub_breaking_news", breaking_news.run_draft_cycle,  "Breaking News",  1010,   0, 1),
    ("sub_threads",       threads.run_draft_cycle,        "Threads",        1011,  17, 2),
    ("sub_long_form",     long_form.run_draft_cycle,      "Long-form",      1012,  34, 2),
    ("sub_quotes",        quotes.run_draft_cycle,         "Quotes",         1013,  51, 2),   # MOVES to CRON
    ("sub_infographics",  infographics.run_draft_cycle,   "Infographics",   1014,  68, 2),
    ("sub_video_clip",    video_clip.run_draft_cycle,     "Gold Media",     1015,  85, 2),
    ("sub_gold_history",  gold_history.run_draft_cycle,   "Gold History",   1016, 102, 2),
]
```

**Current `build_scheduler` registration loop (scheduler/worker.py L267-277):**
```python
now = datetime.now(timezone.utc)
for job_id, run_fn, name, lock_id, offset, interval_hours in CONTENT_SUB_AGENTS:
    # +10s buffer ensures start_date > scheduler.start() wall clock for offset=0
    # (APScheduler IntervalTrigger skips first fire if start_date <= now).
    start_date = now + timedelta(minutes=offset) + timedelta(seconds=10)
    scheduler.add_job(
        _make_sub_agent_job(job_id, lock_id, run_fn, engine),
        trigger=IntervalTrigger(hours=interval_hours, start_date=start_date),
        id=job_id,
        name=f"{name} — every {interval_hours}h (offset +{offset}m)",
    )
```

**Current `IntervalTrigger` import (scheduler/worker.py L27):**
```python
from apscheduler.triggers.interval import IntervalTrigger
```

**Current `run_text_story_cycle` signature (scheduler/agents/content/__init__.py L63-68):**
```python
async def run_text_story_cycle(
    *,
    agent_name: str,
    content_type: str,
    draft_fn,
) -> None:
```

**Current filter point (scheduler/agents/content/__init__.py L109-113) — the insertion site for the new whitelist + max_count logic:**
```python
stories = await content_agent.fetch_stories()
agent_run.items_found = len(stories)
candidates = [s for s in stories if s.get("predicted_format") == content_type]

if not candidates:
```

**Current `_draft` JSON-parse block (scheduler/agents/content/quotes.py L114-119) — the insertion site for the reject handler:**
```python
parsed = json.loads(raw)
except Exception as exc:
    logger.error("quotes._draft JSON parse failed: %s", exc)
    return None

draft_content = parsed.get("draft_content", {}) or {}
```

**Current `run_draft_cycle` (scheduler/agents/content/quotes.py L143-149) — the call-site for new kwargs:**
```python
async def run_draft_cycle() -> None:
    """Single-tick pipeline: fetch → filter → draft → review → write."""
    await run_text_story_cycle(
        agent_name=AGENT_NAME,
        content_type=CONTENT_TYPE,
        draft_fn=_draft,
    )
```

**Existing stub-bundle path triggered when draft_fn returns None (scheduler/agents/content/__init__.py L160-171):**
```python
if draft_content is None:
    bundle = ContentBundle(
        story_headline=story["title"],
        story_url=story["link"],
        source_name=story.get("source_name"),
        content_type=content_type,
        score=story.get("score", 0.0),
        deep_research=deep_research,
        compliance_passed=False,
    )
    session.add(bundle)
    continue
```
— the reject path in `_draft` reuses this branch verbatim (no pipeline change needed on the __init__.py side for the reject semantics).

**Existing mocking pattern for quotes tests (scheduler/tests/test_quotes.py L65-81) — the test_run_draft_cycle_no_candidates_exits_cleanly fixture pattern that the new test_content_init.py tests adapt:**
```python
session = AsyncMock()
ctx = AsyncMock()
ctx.__aenter__ = AsyncMock(return_value=session)
ctx.__aexit__ = AsyncMock(return_value=False)

with patch("agents.content.AsyncSessionLocal", return_value=ctx), \
     patch("agents.content.fetch_market_snapshot", new=AsyncMock(return_value=None)), \
     patch.object(content_agent, "fetch_stories", new=AsyncMock(return_value=stories)):
    await quotes.run_draft_cycle()
```

The new content-init tests must ALSO patch `content_agent.is_gold_relevant_or_systemic_shock` (return `{"keep": True}`), `content_agent.fetch_article` (return `("body", True)`), `content_agent.search_corroborating` (return `[]`), `content_agent.review` (return `{"compliance_passed": True, "rationale": ""}`), and `content_agent.build_draft_item` (return `MagicMock()`) to drive stories THROUGH the filters into the drafter — `test_run_draft_cycle_no_candidates_exits_cleanly` short-circuits before the drafter so it doesn't need those patches.
</interfaces>

<!-- Branch state: quick/260421-mos-quotes-daily-noon-reputable is checked out on HEAD=3fa7212,
     rebased on top of m9k. The m9k 6-tuple schema + +10s buffer + interval_hours-per-agent
     are already in place. Pre-change scheduler pytest baseline: 74 passing. -->
</context>

<tasks>

<task type="auto">
  <name>Task 1: Split scheduler registration into interval + cron lists; wire quotes.py to the shared-cycle filters + quality gate; extend run_text_story_cycle with optional max_count + source_whitelist; add 8 new tests across 3 test files</name>
  <files>scheduler/worker.py, scheduler/agents/content/__init__.py, scheduler/agents/content/quotes.py, scheduler/tests/test_worker.py, scheduler/tests/test_quotes.py, scheduler/tests/test_content_init.py</files>
  <action>
    Bundle all 4 sub-changes (scheduler split + helper kwargs + quotes wiring + tests) into ONE atomic implementation commit per the task hard constraints. Work in the order below — each step is chosen to keep the intermediate state compilable so ruff/pytest can be run at any point for fast feedback.

    ---
    **STEP 1 — `scheduler/agents/content/__init__.py` (extend run_text_story_cycle)**

    1a. **Update signature (L63-68)** — add two new kwargs, both defaulting to `None` so existing callers (breaking_news, threads, long_form, infographics) keep identical behavior:
    ```python
    async def run_text_story_cycle(
        *,
        agent_name: str,
        content_type: str,
        draft_fn,
        max_count: int | None = None,
        source_whitelist: frozenset[str] | None = None,
    ) -> None:
    ```

    1b. **Update the docstring (L69-82)** to document the two new kwargs and their None-default no-op semantics. Add roughly:
    ```
        max_count: If not None, cap candidates to the top N by published_at desc
                   AFTER the predicted_format filter and AFTER the whitelist filter.
                   None (default) = no cap — existing behavior.
        source_whitelist: If not None, drop candidates whose source_name does not
                          contain (case-insensitive) any pattern in the set.
                          None (default) = no filter — existing behavior.
    ```

    1c. **Insert the new filter logic** between the `candidates = [...]` list comprehension at L111 and the `if not candidates:` early-exit at L113. The insertion must be INSIDE the existing outer `try:` block at L99 so exceptions still route to the `agent_run.status = "failed"` branch. Exact new block:
    ```python
            stories = await content_agent.fetch_stories()
            agent_run.items_found = len(stories)
            candidates = [s for s in stories if s.get("predicted_format") == content_type]

            # Reputable-source whitelist (case-insensitive substring match on source_name).
            # Opt-in via source_whitelist kwarg; None (default) = no filter.
            if source_whitelist is not None:
                before = len(candidates)
                def _is_reputable(story: dict) -> bool:
                    source = (story.get("source_name") or "").lower()
                    return bool(source) and any(p in source for p in source_whitelist)
                candidates = [s for s in candidates if _is_reputable(s)]
                logger.info(
                    "%s: reputable filter: %d -> %d (dropped %d non-whitelisted sources)",
                    agent_name, before, len(candidates), before - len(candidates),
                )

            # Cap to top max_count by published_at desc (after whitelist).
            # Opt-in via max_count kwarg; None (default) = no cap.
            if max_count is not None and len(candidates) > max_count:
                candidates.sort(key=lambda s: s.get("published_at", ""), reverse=True)
                candidates = candidates[:max_count]
                logger.info("%s: max_count cap: trimmed to top %d by recency", agent_name, max_count)

            if not candidates:
                logger.info(
                    "%s: no %s candidates this cycle", agent_name, content_type,
                )
                agent_run.status = "completed"
                return
    ```

    Important: the whitelist filter runs BEFORE the max_count cap so that `max_count` caps over the already-reputable-filtered set. Both log lines use `%s` placeholders consistent with the existing `logger.info("%s: ...", agent_name, ...)` style in the module. The arrow character in the log format is ASCII `->` (not `→`) for ruff/encoding safety — ruff's default config allows both but ASCII minimizes log-grep friction.

    1d. **Do NOT modify** any other line in `__init__.py` — the stub-bundle path at L160-171 already handles the reject case verbatim (draft_fn returning None creates a compliance_passed=False ContentBundle). No changes to `_is_already_covered_today`, the gold-gate invocation, or the drafter contract.

    ---
    **STEP 2 — `scheduler/agents/content/quotes.py` (REPUTABLE_SOURCES + wire filters + reject handler)**

    2a. **Add module-level constant** immediately after the existing `CONTENT_TYPE` and `AGENT_NAME` constants at L22-23. Keep it tightly documented so a reader understands it's case-insensitive substring matching:
    ```python
    # Tier-1 source patterns for reputable-quote filtering (quick-260421-mos).
    # Matched case-insensitive as substrings against story["source_name"].
    # Deliberate over-inclusion of aliases (e.g. "wall street journal" AND "wsj")
    # to catch both canonical names and common shorthand returned by SerpAPI.
    REPUTABLE_SOURCES: frozenset[str] = frozenset({
        # Tier-1 financial
        "reuters", "bloomberg", "wsj", "wall street journal",
        "financial times", "ft.com", "barron", "marketwatch",
        "cnbc", "economist", "financial post",
        # Gold-specialist
        "kitco", "mining.com", "mining journal", "mining weekly",
        "northern miner", "gold hub",
        # Institutional (WGC, IMF, BIS, central banks, ratings agencies)
        "world gold council", "wgc", "imf", "bis.org",
        "federal reserve", "european central bank",
        "bank of england", "bank of japan", "people's bank",
        "s&p global", "moody's",
    })
    ```

    2b. **Extend the `_draft` user prompt** — insert a new quality-bar block between the current `## Instructions` section (L75-82, ending with "Provide a brief rationale for the format choice (1-2 sentences).") and the existing `Respond in valid JSON with this structure:` block (L83 onward). Exact inserted text (keep as a multi-line f-string fragment — no f-string interpolation needed in this block so it can stay as a plain string append, but since the surrounding user_prompt IS an f-string, continue as f-string with no placeholders):
    ```
    ## Quality bar — a quote is ONLY "solid" if ALL hold:
    1. **Speaker credibility:** Named figure with a verifiable senior role —
       chief economist/strategist at a tier-1 bank, central bank official
       (Fed/ECB/BoE/BoJ/PBoC), World Gold Council staff, IMF/BIS official,
       head of research at a major gold firm, or a well-known commodity
       analyst with a public track record. REJECT: anonymous "strategist at X",
       "market watcher", retail commentators, forum posters, generic
       "analysts at [unnamed firm]".
    2. **Substance:** Verbatim statement containing AT LEAST ONE of:
       - A specific price target or range (e.g. "$2,800 by Q3")
       - A specific percentage (move, probability, allocation)
       - A specific timeframe or catalyst ("if the Fed cuts in September...")
       - A contrarian or non-consensus view with clear reasoning
    3. **Freshness:** Quote is from this article's reporting (not a weeks-old rehash).
    4. **Clarity:** Quote is self-contained — a reader can understand the claim
       without reading the full article.

    ## If NO quote in this article meets the quality bar, respond with:
    {{
      "reject": true,
      "rationale": "1-2 sentence explanation of which criterion failed"
    }}

    Otherwise, respond with the draft JSON as specified below.
    ```
    Note: the `{{` / `}}` curly-brace escaping is required because the surrounding `user_prompt` at L63 is an f-string — double-braces render as literal braces. The subsequent existing `Respond in valid JSON with this structure:\n{{\n  "format": "quote",\n  ...` block already uses this same escaping pattern, so style-parity is preserved.

    2c. **Insert reject handler** in `_draft` immediately after the JSON parse try/except (L114-117, ending with `return None`) and BEFORE the `draft_content = parsed.get("draft_content", {}) or {}` line at L119. Exact insertion:
    ```python
        if parsed.get("reject") is True:
            logger.info(
                "quotes._draft: story rejected by quality gate — %s",
                parsed.get("rationale", "no rationale given"),
            )
            return None  # returning None triggers run_text_story_cycle stub-bundle path
    ```
    Returning None routes to the existing `if draft_content is None:` branch at __init__.py L160-171, which creates a ContentBundle with `compliance_passed=False` and no draft_item. Semantically identical to the JSON-parse-failure path — stub bundle only, no drafted content, no queued draft_item. This is the desired behavior per spec.

    2d. **Update `run_draft_cycle` (L143-149)** — add the two new kwargs and refresh the docstring so the extra pipeline stages are visible from the call site:
    ```python
    async def run_draft_cycle() -> None:
        """Single-tick pipeline: fetch → filter → reputable-only → top-2 → draft (quality-gated) → review → write."""
        await run_text_story_cycle(
            agent_name=AGENT_NAME,
            content_type=CONTENT_TYPE,
            draft_fn=_draft,
            max_count=2,
            source_whitelist=REPUTABLE_SOURCES,
        )
    ```

    2e. **Do NOT modify** the system_prompt (L51-62), the BRAND_PREAMBLE wiring, the image_prompt construction, or any other line in quotes.py. The quality bar lives entirely inside `user_prompt`; the system_prompt already describes the analyst persona and is unchanged.

    ---
    **STEP 3 — `scheduler/worker.py` (split lists + CronTrigger import + cron loop + 4 docstrings + log line)**

    3a. **Add CronTrigger import at L28** (alongside existing IntervalTrigger import at L27):
    ```python
    from apscheduler.triggers.interval import IntervalTrigger
    from apscheduler.triggers.cron import CronTrigger
    ```

    3b. **Replace `CONTENT_SUB_AGENTS` table (L82-94) with TWO tables.** The `sub_quotes` row moves out of the interval list entirely and becomes the single row of the new cron list:
    ```python
    # Content sub-agent registration table — interval-scheduled (quick-260421-eoe).
    # Tuple shape: (job_id, run_fn, name, lock_id, offset_minutes, interval_hours).
    # Stagger offsets spread the 6 interval sub-agents across a 2h window to avoid
    # thundering herds on SerpAPI + Anthropic. sub_breaking_news fires every 1h;
    # the other 5 interval agents fire every 2h. sub_quotes moved to
    # CONTENT_CRON_AGENTS below (quick-260421-mos) — daily at 12pm Pacific.
    CONTENT_INTERVAL_AGENTS: list[tuple[str, object, str, int, int, int]] = [
        ("sub_breaking_news", breaking_news.run_draft_cycle,  "Breaking News",  1010,   0, 1),
        ("sub_threads",       threads.run_draft_cycle,        "Threads",        1011,  17, 2),
        ("sub_long_form",     long_form.run_draft_cycle,      "Long-form",      1012,  34, 2),
        # sub_quotes moved to CONTENT_CRON_AGENTS — daily at 12pm America/Los_Angeles
        ("sub_infographics",  infographics.run_draft_cycle,   "Infographics",   1014,  68, 2),
        ("sub_video_clip",    video_clip.run_draft_cycle,     "Gold Media",     1015,  85, 2),
        ("sub_gold_history",  gold_history.run_draft_cycle,   "Gold History",   1016, 102, 2),
    ]

    # Cron-scheduled sub-agents (quick-260421-mos).
    # Tuple shape: (job_id, run_fn, name, lock_id, hour, minute, timezone).
    # sub_quotes fires once daily at 12:00 America/Los_Angeles — post US morning news,
    # pre market close — with tier-1 reputable-source whitelist + top-2 cap + drafter
    # quality gate applied inside the sub-agent's run_draft_cycle.
    CONTENT_CRON_AGENTS: list[tuple[str, object, str, int, int, int, str]] = [
        ("sub_quotes", quotes.run_draft_cycle, "Quotes", 1013, 12, 0, "America/Los_Angeles"),
    ]
    ```
    Note: the offsets 51 (was sub_quotes) and the lock ID 1013 both survive — 51 is simply absent from the interval list now (offsets become `[0, 17, 34, 68, 85, 102]`, a 6-element sequence), and 1013 moves to the cron list. `JOB_LOCK_IDS` at L70-79 is UNCHANGED — `sub_quotes: 1013` stays there; the lock-ID registry is schedule-shape-agnostic.

    3c. **Update the `build_scheduler` registration loop (L267-277)** — rename the interval loop variable and keep its body identical, then append a NEW cron loop below:
    ```python
    now = datetime.now(timezone.utc)
    for job_id, run_fn, name, lock_id, offset, interval_hours in CONTENT_INTERVAL_AGENTS:
        # +10s buffer ensures start_date > scheduler.start() wall clock for offset=0
        # (APScheduler IntervalTrigger skips first fire if start_date <= now).
        start_date = now + timedelta(minutes=offset) + timedelta(seconds=10)
        scheduler.add_job(
            _make_sub_agent_job(job_id, lock_id, run_fn, engine),
            trigger=IntervalTrigger(hours=interval_hours, start_date=start_date),
            id=job_id,
            name=f"{name} — every {interval_hours}h (offset +{offset}m)",
        )

    for job_id, run_fn, name, lock_id, hour, minute, tz in CONTENT_CRON_AGENTS:
        scheduler.add_job(
            _make_sub_agent_job(job_id, lock_id, run_fn, engine),
            trigger=CronTrigger(hour=hour, minute=minute, timezone=tz),
            id=job_id,
            name=f"{name} — daily at {hour:02d}:{minute:02d} {tz}",
        )
    ```

    3d. **Update 4 docstring sites + 1 log line** to reflect the new 6-interval + 1-cron topology:

       - **L5-10 module docstring:** current reads
         ```
         This module is the entry point for Railway service 2 (scheduler worker).
         Post quick-260421-eoe, it starts AsyncIOScheduler with 8 jobs:

         - morning_digest (daily cron, 08:00 UTC)
         - 7 content sub-agents on IntervalTrigger — sub_breaking_news every 1h,
           the other 6 every 2h — staggered across the 2h window with offsets
           [0, 17, 34, 51, 68, 85, 102] minutes.
         ```
         Change to:
         ```
         This module is the entry point for Railway service 2 (scheduler worker).
         Post quick-260421-mos, it starts AsyncIOScheduler with 8 jobs:

         - morning_digest (daily cron, 08:00 UTC)
         - 6 interval sub-agents on IntervalTrigger — sub_breaking_news every 1h,
           the other 5 every 2h — staggered across the 2h window with offsets
           [0, 17, 34, 68, 85, 102] minutes.
         - 1 cron sub-agent — sub_quotes daily at 12:00 America/Los_Angeles.
         ```
         (Offset 51 is now absent; the sequence is 6 values, not 7.)

       - **L82-85 tuple-shape comment:** replaced entirely by the new 2-block comment in step 3b above.

       - **L231-235 `build_scheduler` docstring:** current reads
         ```
         Build the APScheduler instance with 8 jobs registered.

         - morning_digest: cron at morning_digest_schedule_hour (default 08:00 UTC).
         - 7 content sub-agents: IntervalTrigger with per-agent hours (sub_breaking_news=1,
           others=2) and staggered start_date offsets [0, 17, 34, 51, 68, 85, 102] minutes.
         ```
         Change to:
         ```
         Build the APScheduler instance with 8 jobs registered.

         - morning_digest: cron at morning_digest_schedule_hour (default 08:00 UTC).
         - 6 interval sub-agents: IntervalTrigger with per-agent hours (sub_breaking_news=1,
           others=2) and staggered start_date offsets [0, 17, 34, 68, 85, 102] minutes.
         - 1 cron sub-agent: sub_quotes daily at 12:00 America/Los_Angeles.
         ```

       - **L244-247 startup log line:** current reads
         ```python
         logger.info(
             "Schedule config: digest=cron(%d:00 UTC), content_sub_agents=%d jobs (sub_breaking_news=1h, others=2h)",
             digest_hour, len(CONTENT_SUB_AGENTS),
         )
         ```
         Change to (report BOTH counts):
         ```python
         logger.info(
             "Schedule config: digest=cron(%d:00 UTC), interval_sub_agents=%d jobs (sub_breaking_news=1h, others=2h), cron_sub_agents=%d jobs (sub_quotes daily 12:00 America/Los_Angeles)",
             digest_hour, len(CONTENT_INTERVAL_AGENTS), len(CONTENT_CRON_AGENTS),
         )
         ```

    3e. **Do NOT modify** `JOB_LOCK_IDS` (L70-79), `with_advisory_lock`, `_make_morning_digest_job`, `_make_sub_agent_job`, `_read_schedule_config`, `upsert_agent_config`, `_validate_env`, or `main()`. The advisory-lock mechanics and morning_digest path are entirely unaffected. `sub_quotes: 1013` stays in JOB_LOCK_IDS — that dict is the canonical source of truth for lock IDs and is schedule-shape-agnostic.

    ---
    **STEP 4 — `scheduler/tests/test_worker.py` (rename imports, rescope 3 tests, add 1 test)**

    4a. **Update imports at L30-35** — rename `CONTENT_SUB_AGENTS` → `CONTENT_INTERVAL_AGENTS`, add `CONTENT_CRON_AGENTS`:
    ```python
    from worker import (  # noqa: E402
        CONTENT_INTERVAL_AGENTS,
        CONTENT_CRON_AGENTS,
        JOB_LOCK_IDS,
        build_scheduler,
        with_advisory_lock,
    )
    ```

    4b. **Rename and rescope `test_content_sub_agents_has_seven_entries` (L75-77)** →
    ```python
    def test_sub_agents_total_seven():
        """Interval + cron sub-agent lists together must still cover all 7 sub-agents."""
        assert len(CONTENT_INTERVAL_AGENTS) + len(CONTENT_CRON_AGENTS) == 7
        assert len(CONTENT_INTERVAL_AGENTS) == 6
        assert len(CONTENT_CRON_AGENTS) == 1
    ```

    4c. **Rescope `test_sub_agent_staggering` (L80-83)** — it now iterates only the interval list with 6 entries, and offset 51 is gone (it belonged to sub_quotes):
    ```python
    def test_sub_agent_staggering():
        """Interval offsets are exactly [0, 17, 34, 68, 85, 102] minutes (51 removed — sub_quotes is now cron)."""
        offsets = [t[4] for t in CONTENT_INTERVAL_AGENTS]
        assert offsets == [0, 17, 34, 68, 85, 102]
    ```

    4d. **Rescope `test_sub_agent_lock_ids` (L86-100)** — union the two lists when building the sub_entries dict; the assertion target stays identical (all 7 lock IDs 1010-1016 must appear):
    ```python
    def test_sub_agent_lock_ids():
        """Lock IDs cover 1010-1016 (inclusive) mapped to the sub_* job IDs across both schedule shapes."""
        sub_entries = {job_id: lock_id for job_id, _, _, lock_id, *_ in CONTENT_INTERVAL_AGENTS}
        for job_id, _, _, lock_id, *_ in CONTENT_CRON_AGENTS:
            sub_entries[job_id] = lock_id
        assert sub_entries == {
            "sub_breaking_news": 1010,
            "sub_threads":       1011,
            "sub_long_form":     1012,
            "sub_quotes":        1013,
            "sub_infographics":  1014,
            "sub_video_clip":    1015,
            "sub_gold_history":  1016,
        }
        # Also assert JOB_LOCK_IDS matches.
        for job_id, lock_id in sub_entries.items():
            assert JOB_LOCK_IDS[job_id] == lock_id
    ```
    The `*_` rest-pattern absorbs the trailing tuple fields (interval_hours on interval rows; hour/minute/tz on cron rows) cleanly without needing separate unpackings.

    4e. **Add new test `test_quotes_is_daily_cron`** — place after `test_sub_agent_lock_ids`:
    ```python
    def test_quotes_is_daily_cron():
        """sub_quotes is registered as the sole cron sub-agent at 12:00 America/Los_Angeles."""
        assert len(CONTENT_CRON_AGENTS) == 1
        job_id, _, name, lock_id, hour, minute, tz = CONTENT_CRON_AGENTS[0]
        assert job_id == "sub_quotes"
        assert name == "Quotes"
        assert lock_id == 1013
        assert hour == 12
        assert minute == 0
        assert tz == "America/Los_Angeles"
    ```

    4f. **Leave `test_retired_crons_absent_from_job_lock_ids` (L103-115) UNCHANGED** — `JOB_LOCK_IDS` still has 8 keys including `sub_quotes: 1013` (only the SCHEDULE SHAPE changed, not the lock-ID registry). This test protecting the retired-crons invariant remains correct as-is.

    4g. **Leave `test_scheduler_registers_8_jobs` (L118-138) UNCHANGED** — total job count is still 8 (morning_digest + 6 interval + 1 cron); the expected IDs list is identical.

    4h. **Leave the advisory-lock semantic tests + `test_read_schedule_config_has_no_retired_keys` UNCHANGED.**

    ---
    **STEP 5 — `scheduler/tests/test_quotes.py` (add 3 new tests)**

    Append the 3 new tests at the END of the file, after `test_run_draft_cycle_no_candidates_exits_cleanly` (L81). Do NOT modify any existing test — the shape-parity test at L34-49 must continue to pass against the updated `_draft` (since the example JSON payload omits `reject`, the reject handler at 2c is a no-op for it). Do NOT modify `test_draft_returns_none_on_json_parse_failure` — JSON parse failure still returns None via the existing `except` branch, unchanged by this plan.

    5a. **test_reputable_sources_set_populated:**
    ```python
    def test_reputable_sources_set_populated():
        """REPUTABLE_SOURCES covers tier-1 financial + gold-specialist + institutional aliases."""
        assert isinstance(quotes.REPUTABLE_SOURCES, frozenset)
        assert len(quotes.REPUTABLE_SOURCES) >= 10
        # Spot-check representative entries from each tier.
        assert "reuters" in quotes.REPUTABLE_SOURCES
        assert "bloomberg" in quotes.REPUTABLE_SOURCES
        assert "wgc" in quotes.REPUTABLE_SOURCES
        assert "kitco" in quotes.REPUTABLE_SOURCES
    ```

    5b. **test_draft_returns_none_on_reject:**
    ```python
    @pytest.mark.asyncio
    async def test_draft_returns_none_on_reject(caplog):
        """_draft returns None when Claude responds with {\"reject\": true, ...} and logs the rationale."""
        client = AsyncMock()
        response = MagicMock()
        response.content = [MagicMock(text='{"reject": true, "rationale": "speaker is anonymous"}')]
        client.messages.create = AsyncMock(return_value=response)

        with caplog.at_level("INFO"):
            draft = await quotes._draft(
                {"title": "T", "link": "http://x", "source_name": "kitco"},
                {"article_text": "body", "corroborating_sources": []}, None, client=client,
            )
        assert draft is None
        assert "quality gate" in caplog.text
        assert "speaker is anonymous" in caplog.text
    ```

    5c. **test_run_draft_cycle_passes_filters:**
    ```python
    @pytest.mark.asyncio
    async def test_run_draft_cycle_passes_filters():
        """run_draft_cycle passes max_count=2 and source_whitelist=REPUTABLE_SOURCES to the shared cycle."""
        with patch("agents.content.quotes.run_text_story_cycle", new=AsyncMock()) as mock_cycle:
            await quotes.run_draft_cycle()
        mock_cycle.assert_awaited_once()
        kwargs = mock_cycle.await_args.kwargs
        assert kwargs["agent_name"] == "sub_quotes"
        assert kwargs["content_type"] == "quote"
        assert kwargs["max_count"] == 2
        assert kwargs["source_whitelist"] is quotes.REPUTABLE_SOURCES
        assert callable(kwargs["draft_fn"])
    ```
    Note: `run_text_story_cycle` is imported into `agents.content.quotes` at L17 (`from agents.content import run_text_story_cycle`), so the patch target is `agents.content.quotes.run_text_story_cycle` (the local binding) — NOT `agents.content.run_text_story_cycle` (which would only work if quotes.py accessed it via module attribute lookup). This is the "patch where it's looked up, not where it's defined" pytest idiom.

    ---
    **STEP 6 — CREATE `scheduler/tests/test_content_init.py` (new file, 4 tests)**

    File path: `scheduler/tests/test_content_init.py` (root of `tests/`, NOT in the empty `tests/agents/` subdir per spec). Model the env-bootstrap block after `scheduler/tests/test_quotes.py` L1-24 so `config.get_settings()` lru_cache is populated correctly regardless of collection order.

    The tests must drive stories THROUGH the filters into the drafter, so they need to patch:
    - `agents.content.AsyncSessionLocal` — returns a context manager yielding an AsyncMock session
    - `agents.content.fetch_market_snapshot` — returns None (skip market snapshot path)
    - `agents.content_agent.fetch_stories` — returns the test's story list
    - `agents.content_agent.is_gold_relevant_or_systemic_shock` — returns `{"keep": True}`
    - `agents.content_agent.fetch_article` — returns `("body", True)`
    - `agents.content_agent.search_corroborating` — returns `[]`
    - `agents.content_agent.review` — returns `{"compliance_passed": True, "rationale": ""}`
    - `agents.content_agent.build_draft_item` — returns a MagicMock()
    - `agents.content._is_already_covered_today` — returns False (skip dedup path)
    - `anthropic.AsyncAnthropic` — the helper instantiates this at L84; irrelevant if draft_fn is a pure-Python stub (no Claude call), but patch to `MagicMock()` to be safe

    The `draft_fn` passed to `run_text_story_cycle` is a plain async helper that records which stories it was called with (so the tests can assert how many stories reached the drafter).

    Full file content:
    ```python
    """Tests for agents.content.run_text_story_cycle filter kwargs (quick-260421-mos).

    Covers the 4 filter-logic states introduced in this quick task:
    - source_whitelist drops non-whitelisted sources
    - max_count caps candidates to top N by published_at desc
    - source_whitelist=None is a no-op (all predicted_format matches reach drafter)
    - max_count=None is a no-op (all whitelist-matches reach drafter)

    Does NOT re-test the 4 other sub-agents using run_text_story_cycle
    (breaking_news, threads, long_form, infographics) — they pass neither kwarg
    so the None-default no-op tests here cover them by construction.
    """
    import os
    import sys
    from unittest.mock import AsyncMock, MagicMock, patch

    import pytest

    sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

    os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://fake-pooler.neon.tech/db?sslmode=require")
    os.environ.setdefault("ANTHROPIC_API_KEY", "sk-test-fake")
    os.environ.setdefault("TWILIO_ACCOUNT_SID", "x")
    os.environ.setdefault("TWILIO_AUTH_TOKEN", "x")
    os.environ.setdefault("TWILIO_WHATSAPP_FROM", "whatsapp:+1x")
    os.environ.setdefault("DIGEST_WHATSAPP_TO", "whatsapp:+1x")
    os.environ.setdefault("X_API_BEARER_TOKEN", "test-bearer-token")
    os.environ.setdefault("X_API_KEY", "test-key")
    os.environ.setdefault("X_API_SECRET", "test-secret")
    os.environ.setdefault("SERPAPI_API_KEY", "x")
    os.environ.setdefault("FRONTEND_URL", "https://x.com")

    from agents import content_agent  # noqa: E402
    from agents.content import run_text_story_cycle  # noqa: E402


    def _session_ctx():
        """Build an async-context-manager mock yielding an AsyncMock session."""
        session = AsyncMock()
        ctx = AsyncMock()
        ctx.__aenter__ = AsyncMock(return_value=session)
        ctx.__aexit__ = AsyncMock(return_value=False)
        return ctx, session


    def _story(idx, source_name, published_at="2026-04-21T00:00:00Z", predicted_format="quote"):
        return {
            "title": f"Headline {idx}",
            "link": f"http://example.com/{idx}",
            "source_name": source_name,
            "predicted_format": predicted_format,
            "score": 5.0,
            "summary": "body",
            "published_at": published_at,
        }


    async def _run_with_stories(stories, *, max_count=None, source_whitelist=None):
        """Drive stories through run_text_story_cycle and return the list the drafter saw."""
        drafter_saw: list[dict] = []

        async def draft_fn(story, deep_research, market_snapshot, *, client):
            drafter_saw.append(story)
            return None  # triggers stub-bundle path; avoids review/build_draft_item coupling

        ctx, _ = _session_ctx()

        with patch("agents.content.AsyncSessionLocal", return_value=ctx), \
             patch("agents.content.fetch_market_snapshot", new=AsyncMock(return_value=None)), \
             patch("agents.content._is_already_covered_today", new=AsyncMock(return_value=False)), \
             patch.object(content_agent, "fetch_stories", new=AsyncMock(return_value=stories)), \
             patch.object(content_agent, "is_gold_relevant_or_systemic_shock",
                          new=AsyncMock(return_value={"keep": True})), \
             patch.object(content_agent, "fetch_article",
                          new=AsyncMock(return_value=("body", True))), \
             patch.object(content_agent, "search_corroborating",
                          new=AsyncMock(return_value=[])):
            await run_text_story_cycle(
                agent_name="test_agent",
                content_type="quote",
                draft_fn=draft_fn,
                max_count=max_count,
                source_whitelist=source_whitelist,
            )

        return drafter_saw


    @pytest.mark.asyncio
    async def test_source_whitelist_filters_stories():
        """Only stories whose source_name substring-matches the whitelist reach the drafter."""
        whitelist = frozenset({"reuters", "bloomberg"})
        stories = [
            _story(1, "Reuters"),        # matches "reuters" (case-insensitive)
            _story(2, "Bloomberg News"), # matches "bloomberg"
            _story(3, "Some Random Blog"),  # no match
        ]
        drafter_saw = await _run_with_stories(stories, source_whitelist=whitelist)
        seen_sources = {s["source_name"] for s in drafter_saw}
        assert seen_sources == {"Reuters", "Bloomberg News"}
        assert len(drafter_saw) == 2


    @pytest.mark.asyncio
    async def test_max_count_caps_candidates():
        """With 5 whitelist-matching stories, max_count=2 keeps only the top 2 by published_at desc."""
        whitelist = frozenset({"reuters"})
        stories = [
            _story(1, "Reuters", "2026-04-21T09:00:00Z"),
            _story(2, "Reuters", "2026-04-21T12:00:00Z"),  # newest
            _story(3, "Reuters", "2026-04-21T08:00:00Z"),
            _story(4, "Reuters", "2026-04-21T11:00:00Z"),  # 2nd newest
            _story(5, "Reuters", "2026-04-21T10:00:00Z"),
        ]
        drafter_saw = await _run_with_stories(stories, source_whitelist=whitelist, max_count=2)
        # Top 2 by published_at desc are story 2 (12:00) + story 4 (11:00).
        titles = {s["title"] for s in drafter_saw}
        assert titles == {"Headline 2", "Headline 4"}
        assert len(drafter_saw) == 2


    @pytest.mark.asyncio
    async def test_source_whitelist_none_is_noop():
        """source_whitelist=None (default) = all predicted_format matches reach drafter — breaking_news/threads/long_form/infographics parity."""
        stories = [
            _story(1, "Reuters"),
            _story(2, "Some Random Blog"),
            _story(3, "Another No-Name Source"),
        ]
        drafter_saw = await _run_with_stories(stories)  # no kwargs
        assert len(drafter_saw) == 3


    @pytest.mark.asyncio
    async def test_max_count_none_is_noop():
        """max_count=None (default) = no cap applied, all matches reach drafter."""
        whitelist = frozenset({"reuters"})
        stories = [_story(i, "Reuters", f"2026-04-21T{i:02d}:00:00Z") for i in range(5)]
        drafter_saw = await _run_with_stories(stories, source_whitelist=whitelist)  # no max_count
        assert len(drafter_saw) == 5
    ```

    ---
    **STEP 7 — Verification commands (run in order, fix failures before proceeding to commit)**

    ```bash
    # 1. Split + CronTrigger + wiring checks (all run from repo root).
    grep -n 'from apscheduler.triggers.cron import CronTrigger' scheduler/worker.py
    # Expected: 1 match, near line 28.

    grep -n 'CronTrigger(hour=' scheduler/worker.py
    # Expected: 1 match, inside the new cron loop in build_scheduler.

    grep -n 'sub_quotes' scheduler/worker.py
    # Expected: sub_quotes appears in CONTENT_CRON_AGENTS tuple + JOB_LOCK_IDS + log line.
    # Expected: sub_quotes does NOT appear in CONTENT_INTERVAL_AGENTS (only in a comment pointer).

    grep -c 'America/Los_Angeles' scheduler/worker.py
    # Expected: exactly 1 match (the tuple entry). Log line text uses "America/Los_Angeles" as descriptive
    # string — if so, this count will be 2. Allow 1-2 matches; fail if 0 or >2.

    grep -n 'CONTENT_INTERVAL_AGENTS' scheduler/worker.py
    # Expected: ≥2 matches (type annotation + loop + log line).

    grep -n 'CONTENT_CRON_AGENTS' scheduler/worker.py
    # Expected: ≥2 matches (type annotation + loop + log line).

    # 2. quotes.py wiring checks.
    grep -n 'REPUTABLE_SOURCES' scheduler/agents/content/quotes.py
    # Expected: ≥2 matches (constant definition + usage in run_draft_cycle).

    grep -n 'max_count=2' scheduler/agents/content/quotes.py
    # Expected: 1 match (run_draft_cycle call site).

    grep -n '"reject"' scheduler/agents/content/quotes.py
    # Expected: matches in _draft reject handler + user_prompt quality-bar block.

    # 3. __init__.py signature + filter logic.
    grep -n 'source_whitelist' scheduler/agents/content/__init__.py
    # Expected: ≥3 matches (signature kwarg + filter block + docstring).

    grep -n 'max_count' scheduler/agents/content/__init__.py
    # Expected: ≥3 matches (signature kwarg + cap block + docstring).

    # 4. Ruff clean.
    cd /Users/matthewnelson/seva-mining/scheduler && uv run ruff check .
    # Expected: "All checks passed!"

    # 5. Pytest green; count STRICTLY greater than pre-change baseline (74).
    cd /Users/matthewnelson/seva-mining/scheduler && uv run pytest -x
    # Expected: all pass. Count increase breakdown:
    #   - test_worker.py: +1 (test_quotes_is_daily_cron; test_content_sub_agents_has_seven_entries renamed to test_sub_agents_total_seven = same count)
    #   - test_quotes.py: +3 (test_reputable_sources_set_populated, test_draft_returns_none_on_reject, test_run_draft_cycle_passes_filters)
    #   - test_content_init.py: +4 (all NEW)
    #   - Total: 74 baseline → 74 + 1 + 3 + 4 = 82 tests
    # Acceptance: final count ≥ 82 (executor may adjust if they split/merge tests).

    # 6. Branch-level sanity: confirm exactly 6 files changed (vs m9k base).
    git diff quick/260421-m9k-breaking-news-hourly --stat
    # Expected: exactly 6 files touched:
    #   scheduler/worker.py
    #   scheduler/agents/content/__init__.py
    #   scheduler/agents/content/quotes.py
    #   scheduler/tests/test_worker.py
    #   scheduler/tests/test_quotes.py
    #   scheduler/tests/test_content_init.py (NEW)
    ```

    ---
    **STEP 8 — Commit**

    Stage exactly the 6 files listed above and create ONE atomic commit. Do NOT push. Commit message (exactly, including trailing quick-task tag):
    ```
    feat(scheduler): quotes sub-agent → daily 12pm Pacific + reputable whitelist + quality gate (quick-260421-mos)
    ```
    Commit body should bullet-summarize the 4 sub-changes (split + helper kwargs + quotes wiring + tests) so reviewers see the scope at a glance. Orchestrator handles the separate planning-artifacts commit.

    **Do NOT:**
    - Push to origin / main / any remote
    - Create a second commit for implementation (planning-artifacts is a separate commit handled by orchestrator)
    - Modify the other 4 sub-agents (breaking_news.py, threads.py, long_form.py, infographics.py) — the kwargs default to None so they're already no-op
    - Modify video_clip.py or gold_history.py (they don't use run_text_story_cycle)
    - Write any Alembic migration (zero schema changes)
    - Clean up or migrate existing pending Quote drafts in prod DB (per user instruction — leave alone)
  </action>
  <verify>
    <automated>cd /Users/matthewnelson/seva-mining/scheduler && uv run ruff check . && uv run pytest -x</automated>
  </verify>
  <done>
    - `grep 'from apscheduler.triggers.cron import CronTrigger' scheduler/worker.py` → 1 match near L28
    - `grep 'CronTrigger(hour=' scheduler/worker.py` → 1 match inside `build_scheduler`
    - `grep 'CONTENT_INTERVAL_AGENTS' scheduler/worker.py` → ≥2 matches (definition + loop)
    - `grep 'CONTENT_CRON_AGENTS' scheduler/worker.py` → ≥2 matches (definition + loop)
    - `grep -c 'America/Los_Angeles' scheduler/worker.py` → 1-2 matches
    - `grep 'REPUTABLE_SOURCES' scheduler/agents/content/quotes.py` → ≥2 matches (definition + run_draft_cycle kwarg)
    - `grep 'max_count=2' scheduler/agents/content/quotes.py` → 1 match in run_draft_cycle
    - `grep '"reject"' scheduler/agents/content/quotes.py` → ≥2 matches (quality-bar prompt + reject handler)
    - `grep 'source_whitelist' scheduler/agents/content/__init__.py` → ≥3 matches
    - `grep 'max_count' scheduler/agents/content/__init__.py` → ≥3 matches
    - `cd scheduler && uv run ruff check .` → clean
    - `cd scheduler && uv run pytest -x` → green, count ≥ 82 (baseline 74 + ≥8 new tests)
    - `git diff quick/260421-m9k-breaking-news-hourly --stat` → exactly 6 files changed
    - ONE commit on branch `quick/260421-mos-quotes-daily-noon-reputable` with subject:
      `feat(scheduler): quotes sub-agent → daily 12pm Pacific + reputable whitelist + quality gate (quick-260421-mos)`
    - Branch NOT pushed to origin (orchestrator handles that post-review)
  </done>
</task>

</tasks>

<verification>
**Automated checks (executor runs all in order during Task 1 verify block):**

1. `grep -n 'from apscheduler.triggers.cron import CronTrigger' scheduler/worker.py` → 1 match near L28.
2. `grep -n 'CronTrigger(hour=' scheduler/worker.py` → 1 match in cron registration loop.
3. `grep -n 'sub_quotes' scheduler/worker.py` → appears in `CONTENT_CRON_AGENTS`, NOT as a row in `CONTENT_INTERVAL_AGENTS`.
4. `grep -c 'America/Los_Angeles' scheduler/worker.py` → 1-2 matches (tuple entry + optional log-line descriptor).
5. `grep -n 'CONTENT_INTERVAL_AGENTS' scheduler/worker.py` → ≥2 matches.
6. `grep -n 'CONTENT_CRON_AGENTS' scheduler/worker.py` → ≥2 matches.
7. `grep -n 'REPUTABLE_SOURCES' scheduler/agents/content/quotes.py` → frozenset defined + passed to `run_text_story_cycle`.
8. `grep -n 'max_count=2' scheduler/agents/content/quotes.py` → 1 match in `run_draft_cycle`.
9. `grep -n '"reject"' scheduler/agents/content/quotes.py` → quality-gate reject handler + user_prompt quality bar.
10. `grep -n 'source_whitelist\|max_count' scheduler/agents/content/__init__.py` → both kwargs in signature + filter logic + docstring.
11. `cd scheduler && uv run ruff check .` → clean.
12. `cd scheduler && uv run pytest -x` → green, count ≥ 82 (74 baseline + 1 worker + 3 quotes + 4 content_init).
13. `git diff quick/260421-m9k-breaking-news-hourly --stat` → exactly 6 files touched.

**Not verified here (operator confirms post-deploy; explicitly out of this task's scope per spec):**

- `sub_quotes` logs `agent_run` row exactly once per day at 12:00 PT after next Railway redeploy.
- The other 6 sub-agents continue firing on their existing cadences (visible in `agent_runs` table).
- Low-reputation sources stop appearing as source_name on new Quote ContentBundle rows.
- Drafter quality gate produces visible `compliance_passed=False, draft_content IS NULL` stub bundles for rejected articles.
</verification>

<success_criteria>
- Scheduler registers exactly 8 jobs: `morning_digest` + 6 interval sub-agents + 1 cron sub-agent (`sub_quotes`)
- `sub_quotes` uses `CronTrigger(hour=12, minute=0, timezone="America/Los_Angeles")` — NOT `IntervalTrigger`
- `run_text_story_cycle` accepts `max_count` + `source_whitelist` kwargs; both default to None (no-op)
- Whitelist filter runs BEFORE max_count cap (so max_count caps over the already-reputable-filtered set)
- `quotes._draft` returns None when Claude responds with `{"reject": true, ...}`, routing to the existing stub-bundle path
- `quotes.run_draft_cycle` passes `max_count=2` and `source_whitelist=REPUTABLE_SOURCES`
- `REPUTABLE_SOURCES` is a `frozenset[str]` with ≥20 case-insensitive substring patterns covering tier-1 financial, gold-specialist, and institutional sources
- Zero behavior change for breaking_news, threads, long_form, infographics (None-default no-op confirmed by `test_source_whitelist_none_is_noop` + `test_max_count_none_is_noop`)
- Zero changes to video_clip, gold_history (they don't use the helper)
- Zero schema changes, zero Alembic migrations
- Scheduler ruff + pytest green; total test count ≥ 82 (baseline 74 + 8 new)
- Exactly 6 files modified on the branch
- ONE atomic implementation commit on `quick/260421-mos-quotes-daily-noon-reputable` (planning-artifacts commit handled by orchestrator)
- Branch NOT pushed to origin
</success_criteria>

<output>
After completion, create `.planning/quick/260421-mos-quotes-sub-agent-daily-12pm-pacific-repu/260421-mos-SUMMARY.md` capturing:

1. **What changed, by file** — for each of the 6 files, bullet-list the specific edits (line-range refs + one-line description of each).
2. **Key before → after diffs** — 3 highlights:
   - `CONTENT_SUB_AGENTS` split into `CONTENT_INTERVAL_AGENTS` (6 rows) + `CONTENT_CRON_AGENTS` (1 row)
   - `run_text_story_cycle` signature gained `max_count` + `source_whitelist` kwargs
   - `quotes._draft` gained reject-path handler returning None
3. **Verification outputs** — ruff clean, pytest count (pre-change 74 → post-change N), git diff --stat showing 6 files.
4. **Test count delta** — which test files gained/lost tests and by how many.
5. **Commit SHA** on `quick/260421-mos-quotes-daily-noon-reputable`.
6. **Post-deploy checklist for operator** (4 items):
   - Confirm next Railway deploy logs show 8 jobs registered with `sub_quotes` as cron (not interval).
   - After 12:00 Pacific on deploy day +1, check `agent_runs` for a `sub_quotes` row with `status=completed`.
   - Verify new Quote ContentBundle rows have source_name from REPUTABLE_SOURCES only.
   - Verify drafter quality gate: check recent Quote bundles for `compliance_passed=False` stubs with no `draft_content` (= rejected by quality gate; the existing pending pre-gate Quote drafts in prod are untouched per user instruction).
</output>
</content>
</invoke>