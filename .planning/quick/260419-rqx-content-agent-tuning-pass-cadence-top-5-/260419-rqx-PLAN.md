---
phase: quick-260419-rqx
plan: 01
type: execute
wave: 1
depends_on: []
files_modified:
  - scheduler/worker.py
  - scheduler/seed_content_data.py
  - scheduler/tests/test_worker.py
  - scheduler/agents/content_agent.py
  - scheduler/tests/test_content_agent.py
autonomous: true
requirements: []

must_haves:
  truths:
    - "Content agent runs on a 3-hour interval (not 2-hour)"
    - "Recency weight is 0.40 in DB seed defaults and Railway force-overwrite"
    - "Pipeline scores at most 5 stories per run, with breaking_news and fresh (<3h) stories prioritized"
    - "Lightweight Haiku classifier assigns predicted_format before slice selection"
    - "Gold gate rejects listicle/stock-pick roundups and generic buy-advice articles"
    - "Import sanity passes: ContentAgent, classify_format_lightweight, select_qualifying_stories all importable"
    - "108 existing + ~12 new tests pass; ruff 0 errors"
  artifacts:
    - path: "scheduler/worker.py"
      provides: "content_agent_interval_hours default=3, upsert overrides for cadence+recency+top5+window"
    - path: "scheduler/seed_content_data.py"
      provides: "Updated CONFIG_DEFAULTS with recency 0.40, interval 3, max_stories 5, window 3"
    - path: "scheduler/agents/content_agent.py"
      provides: "classify_format_lightweight helper, updated select_qualifying_stories, updated _run_pipeline, extended gold gate prompt"
    - path: "scheduler/tests/test_content_agent.py"
      provides: "12 new tests covering format classifier, qualifying story selection, and listicle gate rejection"
  key_links:
    - from: "scheduler/agents/content_agent.py (_run_pipeline)"
      to: "classify_format_lightweight"
      via: "asyncio.gather concurrent Haiku calls on scored stories"
      pattern: "asyncio.gather.*classify_format_lightweight"
    - from: "scheduler/agents/content_agent.py (_run_pipeline)"
      to: "select_qualifying_stories"
      via: "max_count + breaking_window_hours params"
      pattern: "select_qualifying_stories.*max_count"
    - from: "scheduler/worker.py (upsert_agent_config)"
      to: "DB config table"
      via: "overrides dict force-write on startup"
      pattern: "content_agent_interval_hours.*3"
---

<objective>
Three-commit content agent tuning pass: cadence to 3h, recency weight bump to 0.40, top-5 cap with format-first breaking priority, and listicle rejection in the gold gate.

Purpose: Reduce API spend and noise from too-frequent runs; surface breaking/fresh stories first; prevent roundup articles polluting the queue.
Output: Updated worker.py, seed_content_data.py, content_agent.py, and tests.
</objective>

<execution_context>
@$HOME/.claude/get-shit-done/workflows/execute-plan.md
@$HOME/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/STATE.md

Prior quick tasks relevant to this file set:
- quick-260419-n4f: introduced is_gold_relevant_or_systemic_shock (line ~405) and restored threshold 7.0
- quick-260419-r0r: long_form 400-char floor + sharpen thread/long_form prompts (3 local commits, NOT yet pushed to origin — do NOT push)
- Content agent is ~1730+ lines
- self._run_metrics does NOT exist; quick-r0r used self._skipped_short_longform instance attr; local dict skipped_by_gate used in _run_pipeline for gate counter
- Test mocking pattern for gold gate: mock_client = AsyncMock(); mock_response.content = [MagicMock(text="yes/no")]; mock_client.messages.create = AsyncMock(return_value=mock_response)
- published field in story dicts is a datetime object (set by RSS/SerpAPI ingest); recency_score() receives datetime — _is_within_window must mirror same approach
</context>

<tasks>

<task type="auto">
  <name>Task 1: Cadence change + recency weight bump (Commit 1)</name>
  <files>scheduler/worker.py, scheduler/seed_content_data.py, scheduler/tests/test_worker.py</files>
  <action>
Make these exact changes, then commit with the specified message.

**scheduler/worker.py — _read_schedule_config defaults dict (line ~197):**
Change `"content_agent_interval_hours": "2"` to `"content_agent_interval_hours": "3"`.
twitter_interval_hours stays "2" — do NOT change it.

**scheduler/worker.py — upsert_agent_config() overrides dict (line ~295):**
Add two entries after the existing `content_quality_threshold` line:
```python
"content_agent_interval_hours": "3",   # Railway overwrites live DB on startup
"content_recency_weight": "0.40",      # bump from 0.30 — favours fresher stories
```

**scheduler/seed_content_data.py — CONFIG_DEFAULTS list:**
- Change `("content_recency_weight", "0.30")` to `("content_recency_weight", "0.40")`
- Change `("content_agent_interval_hours", "2")` to `("content_agent_interval_hours", "3")`

**scheduler/tests/test_worker.py:**
Grep for `content_agent_interval_hours` in the file. The test `test_read_schedule_config_defaults_no_expiry_sweep` uses `inspect.getsource` to assert the string `"content_agent_interval_hours"` is present — that test still passes since the key remains present. No numeric assertion on the value exists, so no test change is needed UNLESS a test hard-codes the string `"2"` next to `content_agent_interval_hours`. Verify by inspection; only edit if a hard-coded "2" assertion fails.

**Atomic commit (run from scheduler/ root or repo root):**
```
git commit -m "feat(quick-260419-rqx): content agent to 3h cadence + recency weight 0.40"
```
Stage only: scheduler/worker.py, scheduler/seed_content_data.py (and test_worker.py if modified).
  </action>
  <verify>
    <automated>cd /Users/matthewnelson/seva-mining/scheduler && uv run pytest tests/test_worker.py -q 2>&1 | tail -5</automated>
  </verify>
  <done>test_worker.py passes; worker.py _read_schedule_config defaults show "3" for content_agent_interval_hours; upsert_agent_config overrides dict includes content_agent_interval_hours="3" and content_recency_weight="0.40"; seed_content_data.py CONFIG_DEFAULTS reflects both changes; commit created with exact message above.</done>
</task>

<task type="auto">
  <name>Task 2: Top-5 cap with format-first breaking priority (Commit 2)</name>
  <files>scheduler/agents/content_agent.py, scheduler/worker.py, scheduler/seed_content_data.py, scheduler/tests/test_content_agent.py</files>
  <action>
Four sub-changes in one commit. Make all changes, verify tests pass, then commit.

---

### (a) New module-level helper: `classify_format_lightweight`

Place near `is_gold_relevant_or_systemic_shock` (around line 400). Add a module-level helper function `_is_within_window` as well (needed by both the classifier and _run_pipeline):

```python
def _is_within_window(
    published,
    window_hours: float,
    now: "datetime | None" = None,
) -> bool:
    """Return True if published is within window_hours of now.

    Accepts datetime objects (as stored by RSS/SerpAPI ingest) or ISO strings.
    Mirrors recency_score() timezone handling.
    """
    if now is None:
        now = datetime.now(timezone.utc)
    if isinstance(published, str):
        try:
            published = datetime.fromisoformat(published.replace("Z", "+00:00"))
        except ValueError:
            return False
    if published.tzinfo is None:
        published = published.replace(tzinfo=timezone.utc)
    age_hours = (now - published).total_seconds() / 3600
    return age_hours <= window_hours


async def classify_format_lightweight(story: dict, *, client) -> str:
    """Lightweight Haiku format classifier for slice-priority decision.

    Uses claude-3-5-haiku-latest (cheap) — full Sonnet format+draft call happens
    later only for the top-N selected stories.

    Returns one of: breaking_news | thread | long_form | infographic | quote.
    Fail-open: returns "thread" (current ambiguous default) on any error or
    unexpected output.
    """
    valid_formats = {"breaking_news", "thread", "long_form", "infographic", "quote"}
    try:
        response = await client.messages.create(
            model="claude-3-5-haiku-latest",
            max_tokens=20,
            system="You are a content format classifier. Reply with one word.",
            messages=[{
                "role": "user",
                "content": (
                    f"Title: {story['title']}\n"
                    f"Summary: {story.get('summary', '')[:500]}\n"
                    f"Published: {story.get('published', '')}\n\n"
                    "Which content format best fits? Choose exactly one: "
                    "breaking_news | thread | long_form | infographic | quote. "
                    "Reply with ONLY the format name."
                ),
            }],
        )
        result = response.content[0].text.strip().lower()
        if result in valid_formats:
            return result
        logger.warning(
            "classify_format_lightweight returned unexpected value '%s' — defaulting to 'thread'",
            result,
        )
        return "thread"
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "classify_format_lightweight failed (%s) — defaulting to 'thread'",
            type(exc).__name__,
        )
        return "thread"
```

---

### (b) Update `select_qualifying_stories` (line ~302)

Replace the existing function signature and body. Preserve existing behavior when max_count is None (backward compat):

```python
def select_qualifying_stories(
    stories: list[dict],
    threshold: float,
    *,
    max_count: int | None = None,
    breaking_window_hours: float | None = None,
    now: datetime | None = None,
) -> list[dict]:
    """Return stories scoring above threshold, optionally capped at max_count.

    When max_count is None: returns ALL qualifying sorted by score desc (unchanged).
    When max_count is set: breaking_news format and fresh stories (within
    breaking_window_hours) are prioritized — they fill the front of the slice
    regardless of score; remaining slots go to highest-score regular stories.

    Args:
        stories: List of story dicts, each with a 'score' key (float).
                 Format-classified stories have 'predicted_format' set.
        threshold: Minimum score (strictly >).
        max_count: Maximum stories to return. None = no cap (backward compat).
        breaking_window_hours: Stories published within this window are treated
                               as priority. None = no recency-based priority.
        now: Reference time for recency check. Defaults to datetime.now(UTC).
             Inject in tests for determinism.

    Returns:
        Qualifying stories, priority-first, sorted by score desc within each tier.
        At most max_count if set.
    """
    qualifying = [s for s in stories if s.get("score", 0) > threshold]
    if not qualifying:
        return []

    if max_count is None:
        qualifying.sort(key=lambda s: s.get("score", 0), reverse=True)
        return qualifying

    # Priority split: breaking_news format OR within recency window
    _now = now or datetime.now(timezone.utc)

    def _is_priority(s: dict) -> bool:
        if s.get("predicted_format") == "breaking_news":
            return True
        if breaking_window_hours is not None:
            return _is_within_window(s.get("published"), breaking_window_hours, _now)
        return False

    priority = [s for s in qualifying if _is_priority(s)]
    regular = [s for s in qualifying if not _is_priority(s)]

    priority.sort(key=lambda s: s.get("score", 0), reverse=True)
    regular.sort(key=lambda s: s.get("score", 0), reverse=True)

    combined = priority + regular
    return combined[:max_count]
```

---

### (c) Update `_run_pipeline` (line ~1436)

In the `_run_pipeline` method, after the scoring loop (step 4) and before the `select_qualifying_stories` call (step 5), insert the concurrent format classification block. Then update the `select_qualifying_stories` call and add a summary log line.

Replace this section:
```python
        # 5. Select all qualifying stories (multi-story)
        qualifying = select_qualifying_stories(scored, threshold=threshold)
```

With:
```python
        # 4b. Classify format per story for slice-priority decision (format-first pipeline).
        # Uses cheap Haiku call — full Sonnet draft happens later only for top-N selected.
        format_labels = await asyncio.gather(*[
            classify_format_lightweight(s, client=self.anthropic) for s in scored
        ])
        for s, fmt in zip(scored, format_labels):
            s["predicted_format"] = fmt

        # 5. Select top-N qualifying stories (multi-story, breaking/fresh priority)
        max_count = int(await self._get_config(session, "content_agent_max_stories_per_run", "5"))
        breaking_window = float(await self._get_config(session, "content_agent_breaking_window_hours", "3"))
        qualifying = select_qualifying_stories(
            scored,
            threshold=threshold,
            max_count=max_count,
            breaking_window_hours=breaking_window,
        )
        priority_count = sum(
            1 for s in qualifying
            if s.get("predicted_format") == "breaking_news"
            or _is_within_window(s.get("published"), breaking_window)
        )
        logger.info(
            "Top-%d slice: %d priority (breaking/fresh) + %d regular",
            len(qualifying), priority_count, len(qualifying) - priority_count,
        )
```

---

### (d) scheduler/worker.py — upsert_agent_config() overrides dict

Add two more entries to the overrides dict (alongside the ones added in Task 1):
```python
"content_agent_max_stories_per_run": "5",
"content_agent_breaking_window_hours": "3",
```

### (e) scheduler/seed_content_data.py — CONFIG_DEFAULTS

Add two entries to CONFIG_DEFAULTS (after the existing content_agent_interval_hours entry):
```python
("content_agent_max_stories_per_run",  "5"),
("content_agent_breaking_window_hours", "3"),
```

---

### (f) scheduler/tests/test_content_agent.py — 8 new tests

Add the following 8 tests at the end of the file. Mirror the mocking pattern from existing test_gate_* tests (AsyncMock client, MagicMock response, response.content = [MagicMock(text=...)]).

```python
# ---------------------------------------------------------------------------
# quick-260419-rqx: classify_format_lightweight tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_classify_format_lightweight_returns_valid_format():
    """classify_format_lightweight returns the format name when Haiku responds correctly."""
    ca = _get_content_agent()
    story = {"title": "Fed signals rate cut as inflation cools", "summary": "Breaking macro news.", "published": ""}
    mock_client = AsyncMock()
    mock_response = MagicMock()
    mock_response.content = [MagicMock(text="breaking_news")]
    mock_client.messages.create = AsyncMock(return_value=mock_response)
    result = await ca.classify_format_lightweight(story, client=mock_client)
    assert result == "breaking_news"


@pytest.mark.asyncio
async def test_classify_format_lightweight_fails_open_to_thread():
    """classify_format_lightweight returns 'thread' when Haiku raises."""
    ca = _get_content_agent()
    story = {"title": "Gold rally", "summary": "", "published": ""}
    mock_client = AsyncMock()
    mock_client.messages.create = AsyncMock(side_effect=Exception("API down"))
    result = await ca.classify_format_lightweight(story, client=mock_client)
    assert result == "thread"


@pytest.mark.asyncio
async def test_classify_format_lightweight_clamps_invalid_output():
    """classify_format_lightweight returns 'thread' when Haiku returns garbage."""
    ca = _get_content_agent()
    story = {"title": "Barrick earnings", "summary": "", "published": ""}
    mock_client = AsyncMock()
    mock_response = MagicMock()
    mock_response.content = [MagicMock(text="garbage response xyz")]
    mock_client.messages.create = AsyncMock(return_value=mock_response)
    result = await ca.classify_format_lightweight(story, client=mock_client)
    assert result == "thread"


# ---------------------------------------------------------------------------
# quick-260419-rqx: select_qualifying_stories — top-N + priority tests
# ---------------------------------------------------------------------------

def test_select_qualifying_stories_respects_max_count():
    """select_qualifying_stories(max_count=5) returns exactly 5 when >5 qualify."""
    ca = _get_content_agent()
    now = datetime(2026, 4, 20, 12, 0, 0, tzinfo=timezone.utc)
    old = now - timedelta(hours=48)
    stories = [
        {"title": f"Story {i}", "score": 7.5 + i * 0.1, "published": old, "predicted_format": "thread"}
        for i in range(10)
    ]
    result = ca.select_qualifying_stories(stories, threshold=7.0, max_count=5, now=now)
    assert len(result) == 5
    # Sorted descending by score
    scores = [s["score"] for s in result]
    assert scores == sorted(scores, reverse=True)


def test_select_qualifying_stories_prioritizes_breaking_format():
    """Breaking_news stories appear before higher-scored regular stories in the slice."""
    ca = _get_content_agent()
    now = datetime(2026, 4, 20, 12, 0, 0, tzinfo=timezone.utc)
    old = now - timedelta(hours=48)
    breaking = [
        {"title": f"Breaking {i}", "score": s, "published": old, "predicted_format": "breaking_news"}
        for i, s in enumerate([7.5, 7.3, 7.1])
    ]
    regular = [
        {"title": f"Regular {i}", "score": s, "published": old, "predicted_format": "thread"}
        for i, s in enumerate([9.0, 8.9, 8.8, 8.7, 8.6])
    ]
    result = ca.select_qualifying_stories(
        breaking + regular, threshold=7.0, max_count=5, now=now
    )
    assert len(result) == 5
    # All 3 breaking news stories in first 3 slots
    assert result[0]["predicted_format"] == "breaking_news"
    assert result[1]["predicted_format"] == "breaking_news"
    assert result[2]["predicted_format"] == "breaking_news"
    # Breaking sorted desc by score
    assert result[0]["score"] == 7.5
    assert result[1]["score"] == 7.3
    # Regular stories fill remaining slots, highest score first
    assert result[3]["score"] == 9.0
    assert result[4]["score"] == 8.9


def test_select_qualifying_stories_prioritizes_fresh_by_recency():
    """Fresh stories (within breaking_window_hours) appear before older higher-scored ones."""
    ca = _get_content_agent()
    now = datetime(2026, 4, 20, 12, 0, 0, tzinfo=timezone.utc)
    fresh = [
        {"title": f"Fresh {i}", "score": s, "published": now - timedelta(hours=1), "predicted_format": "thread"}
        for i, s in enumerate([7.4, 7.2])
    ]
    old = [
        {"title": f"Old {i}", "score": s, "published": now - timedelta(hours=48), "predicted_format": "thread"}
        for i, s in enumerate([9.0, 8.9, 8.8, 8.7, 8.6, 8.5, 8.4, 8.3, 8.2, 8.1])
    ]
    result = ca.select_qualifying_stories(
        fresh + old, threshold=7.0, max_count=5, breaking_window_hours=3.0, now=now
    )
    assert len(result) == 5
    # Fresh stories occupy first 2 slots
    fresh_titles = {s["title"] for s in result[:2]}
    assert "Fresh 0" in fresh_titles
    assert "Fresh 1" in fresh_titles


def test_select_qualifying_stories_fewer_than_cap_returns_all():
    """When fewer stories than max_count qualify, returns all qualifying."""
    ca = _get_content_agent()
    now = datetime(2026, 4, 20, 12, 0, 0, tzinfo=timezone.utc)
    old = now - timedelta(hours=48)
    stories = [
        {"title": f"Story {i}", "score": 7.5 + i * 0.1, "published": old, "predicted_format": "thread"}
        for i in range(3)
    ]
    result = ca.select_qualifying_stories(stories, threshold=7.0, max_count=5, now=now)
    assert len(result) == 3


def test_select_qualifying_stories_no_max_count_unchanged_behavior():
    """Without max_count, returns all qualifying sorted desc (backward compat)."""
    ca = _get_content_agent()
    stories = [
        {"title": "A", "score": 8.5},
        {"title": "B", "score": 9.2},
        {"title": "C", "score": 6.9},  # below threshold
        {"title": "D", "score": 7.8},
    ]
    result = ca.select_qualifying_stories(stories, threshold=7.0)
    assert len(result) == 3
    assert result[0]["score"] == 9.2
    assert result[1]["score"] == 8.5
    assert result[2]["score"] == 7.8
```

---

**Atomic commit:**
Stage only: scheduler/agents/content_agent.py, scheduler/worker.py, scheduler/seed_content_data.py, scheduler/tests/test_content_agent.py.
```
git commit -m "feat(quick-260419-rqx): top-5 cap with format-first breaking priority"
```
  </action>
  <verify>
    <automated>cd /Users/matthewnelson/seva-mining/scheduler && uv run pytest tests/test_content_agent.py -q 2>&1 | tail -10 && uv run python -c "from agents.content_agent import ContentAgent, classify_format_lightweight, select_qualifying_stories; print('import ok')"</automated>
  </verify>
  <done>All test_content_agent.py tests pass; classify_format_lightweight and select_qualifying_stories importable; _run_pipeline reads content_agent_max_stories_per_run and content_agent_breaking_window_hours config keys; worker.py upsert overrides include all 4 new keys; seed CONFIG_DEFAULTS includes both new keys; commit created with exact message above.</done>
</task>

<task type="auto">
  <name>Task 3: Extend gold gate to reject listicle/stock-pick roundups (Commit 3)</name>
  <files>scheduler/agents/content_agent.py, scheduler/tests/test_content_agent.py</files>
  <action>
Extend the `is_gold_relevant_or_systemic_shock` function and add 4 tests.

**Step 1: Read the full `is_gold_relevant_or_systemic_shock` function body (lines ~405-460) before editing to confirm exact prompt structure.**

The function uses a single `system=` parameter string. Extend the system prompt to add the listicle-rejection rules. The current prompt ends at "Generic business news, equity market moves, sector-specific news outside gold/commodities → answer no."

Replace the system prompt string with:
```python
system=(
    "Answer yes or no. Is this news story directly about gold, precious metals, "
    "gold mining, OR about a systemic financial/geopolitical event that would "
    "plausibly move gold prices (major war, sanctions, Strait of Hormuz disruption, "
    "Fed/USD policy shock, oil supply shock, currency crisis)? "
    "Generic business news, equity market moves, sector-specific news outside "
    "gold/commodities → answer no.\n\n"
    "REJECT (answer no) for:\n"
    "- Listicles or rankings of gold stocks (e.g. 'Top 5 Gold Stocks', "
    "'7 Best-Performing Gold Stocks For...', 'Best Gold Stocks to Buy Now', "
    "'Gold Stocks to Watch').\n"
    "- Multi-stock analytical picks roundups or recommendation lists across "
    "several gold companies.\n"
    "- Generic buying advice or educational content about gold investing.\n\n"
    "ACCEPT (answer yes) for:\n"
    "- Specific single-company news: earnings, M&A, production reports, "
    "executive changes, project milestones — even if stock-adjacent.\n"
    "- Gold price, supply, or demand macro news.\n"
    "- Geopolitical/financial systemic shock with plausible gold-price linkage."
),
```

Keep the `messages=` parameter and all other function logic unchanged.

**Step 2: Add 4 new tests at the end of test_content_agent.py:**

```python
# ---------------------------------------------------------------------------
# quick-260419-rqx: Gold gate listicle/stock-pick rejection tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_gate_rejects_listicle_top_5_gold_stocks():
    """Gate returns False for a 'Top 5 Junior Gold Stocks' listicle article."""
    ca = _get_content_agent()
    story = {
        "title": "Top 5 Junior Gold Stocks of 2026",
        "summary": "Investing News Network rounds up the best junior gold miners to watch this year.",
    }
    mock_client = AsyncMock()
    mock_response = MagicMock()
    mock_response.content = [MagicMock(text="no")]
    mock_client.messages.create = AsyncMock(return_value=mock_response)
    result = await ca.is_gold_relevant_or_systemic_shock(
        story,
        {"content_gold_gate_enabled": "true", "content_gold_gate_model": "claude-3-5-haiku-latest"},
        client=mock_client,
    )
    assert result is False


@pytest.mark.asyncio
async def test_gate_rejects_listicle_best_performing():
    """Gate returns False for a '7 Best-Performing Gold Stocks' listicle."""
    ca = _get_content_agent()
    story = {
        "title": "7 Best-Performing Gold Stocks For Hedging Against Volatility",
        "summary": "NerdWallet analysts pick their top gold equity recommendations for portfolio hedges.",
    }
    mock_client = AsyncMock()
    mock_response = MagicMock()
    mock_response.content = [MagicMock(text="no")]
    mock_client.messages.create = AsyncMock(return_value=mock_response)
    result = await ca.is_gold_relevant_or_systemic_shock(
        story,
        {"content_gold_gate_enabled": "true", "content_gold_gate_model": "claude-3-5-haiku-latest"},
        client=mock_client,
    )
    assert result is False


@pytest.mark.asyncio
async def test_gate_accepts_single_company_earnings():
    """Gate returns True for single-company earnings news."""
    ca = _get_content_agent()
    story = {
        "title": "Newmont Reports Record Q1 Gold Production",
        "summary": "Newmont Corporation posts record quarterly production of 1.6M oz Au.",
    }
    mock_client = AsyncMock()
    mock_response = MagicMock()
    mock_response.content = [MagicMock(text="yes")]
    mock_client.messages.create = AsyncMock(return_value=mock_response)
    result = await ca.is_gold_relevant_or_systemic_shock(
        story,
        {"content_gold_gate_enabled": "true", "content_gold_gate_model": "claude-3-5-haiku-latest"},
        client=mock_client,
    )
    assert result is True


@pytest.mark.asyncio
async def test_gate_accepts_single_company_ma():
    """Gate returns True for single-company M&A news."""
    ca = _get_content_agent()
    story = {
        "title": "Barrick Announces $5B Acquisition of X Mining",
        "summary": "Barrick Gold to acquire X Mining in all-stock deal, expanding Tier 1 asset base.",
    }
    mock_client = AsyncMock()
    mock_response = MagicMock()
    mock_response.content = [MagicMock(text="yes")]
    mock_client.messages.create = AsyncMock(return_value=mock_response)
    result = await ca.is_gold_relevant_or_systemic_shock(
        story,
        {"content_gold_gate_enabled": "true", "content_gold_gate_model": "claude-3-5-haiku-latest"},
        client=mock_client,
    )
    assert result is True
```

**Atomic commit:**
Stage only: scheduler/agents/content_agent.py, scheduler/tests/test_content_agent.py.
```
git commit -m "feat(quick-260419-rqx): extend gold gate to reject listicle/stock-pick roundups"
```

**Final verification after all 3 commits:**
Run the full suite to confirm ~120 pass:
```
cd scheduler && uv run pytest -q
cd backend && uv run pytest -q
cd scheduler && uv run ruff check
cd scheduler && uv run python -c "from agents.content_agent import ContentAgent, classify_format_lightweight, select_qualifying_stories; print('ok')"
```
  </action>
  <verify>
    <automated>cd /Users/matthewnelson/seva-mining/scheduler && uv run pytest -q 2>&1 | tail -5 && uv run ruff check 2>&1 | head -10</automated>
  </verify>
  <done>test_gate_rejects_listicle_top_5_gold_stocks, test_gate_rejects_listicle_best_performing, test_gate_accepts_single_company_earnings, test_gate_accepts_single_company_ma all pass; gold gate system prompt includes listicle REJECT rules and single-company ACCEPT rules; full scheduler test suite passes (~120 tests); ruff 0 errors; commit created with exact message above.</done>
</task>

</tasks>

<verification>
After all 3 commits:
- `cd scheduler && uv run pytest -q` — expect ~120 passed (108 existing + 12 new)
- `cd scheduler && uv run ruff check` — 0 errors
- `cd backend && uv run pytest -q` — 71 unchanged
- `cd scheduler && uv run python -c "from agents.content_agent import ContentAgent, classify_format_lightweight, select_qualifying_stories; print('ok')"` — prints "ok"
- `git log --oneline -3` — shows all 3 feat(quick-260419-rqx) commits in order
</verification>

<success_criteria>
Three atomic commits created in order with exact commit messages. Content agent default interval is 3h. Recency weight is 0.40 in seed + upsert overrides. Pipeline classifies format via Haiku before selecting top-5, with breaking_news and fresh stories in priority slots. Gold gate prompt explicitly rejects listicles and stock-pick roundups while accepting single-company and macro news. All tests pass. Ruff clean.
</success_criteria>

<output>
After completion, create `.planning/quick/260419-rqx-content-agent-tuning-pass-cadence-top-5-/260419-rqx-SUMMARY.md`
</output>
