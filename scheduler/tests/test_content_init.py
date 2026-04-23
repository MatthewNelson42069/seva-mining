"""Tests for agents.content.run_text_story_cycle filter kwargs (quick-260421-mos).

Covers the 4 filter-logic states:
- source_whitelist drops non-whitelisted sources
- max_count = "break after N successful drafts" (quick-260423-hq7 fix)
- source_whitelist=None is a no-op (all stories reach drafter)
- max_count=None is a no-op (all whitelist-matches reach drafter)

Also covers new kwargs from quick-260422-of3:
- sort_by="score" picks top N by composite (score desc, published_at desc) — D-01
- dedup_scope="same_type" passes content_type into _is_already_covered_today — D-02/D-03
- SELECT scoping when content_type arg is provided to _is_already_covered_today — D-02

quick-260423-hq7: max_count semantics changed from "trim candidates to top N before
the dedup loop" to "break out of the for-loop after N compliance-passing persists."
The 4 sort/cap tests below are rewritten to assert the break semantics rather than
the trim semantics; observable output is the same for the all-succeed case.

Three new tests assert the iterate-past-dedup behavior (the actual fix):
- test_max_count_iterates_past_dedup_hits: loop continues past dedup-blocked stories
- test_max_count_exhausts_if_insufficient_successes: full list consumed when not enough successes
- test_max_count_none_still_iterates_all: max_count=None regression guard for breaking_news

Note (debug 260422-zid): predicted_format is no longer used as a routing gate
— candidates = list(stories). The predicted_format field on story fixtures here
is inert / for realism only.

Does NOT re-test the 4 other sub-agents using run_text_story_cycle
(breaking_news, threads, long_form, infographics) — they pass neither whitelist
kwarg so the None-default no-op tests here cover them by construction.
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
from agents.content import _is_already_covered_today, run_text_story_cycle  # noqa: E402


def _session_ctx():
    """Build an async-context-manager mock yielding an AsyncMock session."""
    session = AsyncMock()
    ctx = AsyncMock()
    ctx.__aenter__ = AsyncMock(return_value=session)
    ctx.__aexit__ = AsyncMock(return_value=False)
    return ctx, session


def _story(idx, source_name, published_at="2026-04-21T00:00:00Z", predicted_format="quote", score=5.0):
    return {
        "title": f"Headline {idx}",
        "link": f"http://example.com/{idx}",
        "source_name": source_name,
        "predicted_format": predicted_format,
        "score": score,
        "summary": "body",
        "published_at": published_at,
    }


async def _run_with_stories(
    stories,
    *,
    max_count=None,
    source_whitelist=None,
    sort_by="published_at",
    dedup_scope="cross_agent",
):
    """Drive stories through run_text_story_cycle and return the list the drafter saw.

    draft_fn returns None → stub-bundle path; avoids review/build_draft_item coupling.
    Use _run_with_stories_succeeding() when you need the compliance+persist path to run.
    """
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
            sort_by=sort_by,
            dedup_scope=dedup_scope,
        )

    return drafter_saw


async def _run_with_stories_succeeding(
    stories,
    *,
    max_count=None,
    source_whitelist=None,
    sort_by="published_at",
    dedup_scope="cross_agent",
    dedup_returns_true_for: frozenset[str] | None = None,
    stories_draft_returns_none: frozenset[str] | None = None,
    content_type: str = "quote",
):
    """Drive stories through run_text_story_cycle in drafter-succeeds mode.

    Unlike _run_with_stories, this helper:
    - draft_fn returns a real draft dict so the compliance+persist+items_queued path runs
    - Mocks content_agent.review() to pass compliance
    - Mocks content_agent.build_draft_item() to return a sentinel
    - Supports per-story dedup overrides (dedup_returns_true_for: set of story titles)
    - Supports per-story draft_fn=None overrides (stories_draft_returns_none: set of titles)

    Returns (drafter_saw, items_queued) where drafter_saw is the list of stories
    that actually reached draft_fn (after dedup/gold-gate), and items_queued is
    the final count of successfully persisted drafts.
    """
    drafter_saw: list[dict] = []
    dedup_true_set = dedup_returns_true_for or frozenset()
    draft_none_set = stories_draft_returns_none or frozenset()

    async def draft_fn(story, deep_research, market_snapshot, *, client):
        drafter_saw.append(story)
        if story["title"] in draft_none_set:
            return None
        return {
            "format": content_type,
            "_rationale": "r",
            "_key_data_points": [],
            "post": "test draft content",
        }

    async def fake_dedup(session, url, headline, *, content_type=None):
        return headline in dedup_true_set

    ctx, session = _session_ctx()
    # session.flush() must be awaitable but return nothing
    session.flush = AsyncMock(return_value=None)

    with patch("agents.content.AsyncSessionLocal", return_value=ctx), \
         patch("agents.content.fetch_market_snapshot", new=AsyncMock(return_value=None)), \
         patch("agents.content._is_already_covered_today", side_effect=fake_dedup), \
         patch.object(content_agent, "fetch_stories", new=AsyncMock(return_value=stories)), \
         patch.object(content_agent, "is_gold_relevant_or_systemic_shock",
                      new=AsyncMock(return_value={"keep": True})), \
         patch.object(content_agent, "fetch_article",
                      new=AsyncMock(return_value=("body", True))), \
         patch.object(content_agent, "search_corroborating",
                      new=AsyncMock(return_value=[])), \
         patch.object(content_agent, "review",
                      new=AsyncMock(return_value={"compliance_passed": True, "rationale": "ok"})), \
         patch.object(content_agent, "build_draft_item",
                      new=MagicMock(return_value=MagicMock())):

        # We need to capture items_queued — patch AgentRun to a spy
        agent_run_instance = MagicMock()
        agent_run_instance.items_queued = 0
        # Track items_queued by wrapping: after run completes, pull from agent_run.items_queued
        # Simpler approach: count calls to build_draft_item (each call = 1 successful persist)
        build_draft_item_mock = content_agent.build_draft_item

        await run_text_story_cycle(
            agent_name="test_agent",
            content_type=content_type,
            draft_fn=draft_fn,
            max_count=max_count,
            source_whitelist=source_whitelist,
            sort_by=sort_by,
            dedup_scope=dedup_scope,
        )

        items_queued = build_draft_item_mock.call_count

    return drafter_saw, items_queued


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
    """With 5 whitelist-matching stories, max_count=2 breaks after the top 2 by published_at desc succeed.

    Rewritten for quick-260423-hq7: sort controls iteration order, break-after-N-successes
    stops the loop. When all drafts succeed (mock returns real draft), only 2 are seen.
    """
    whitelist = frozenset({"reuters"})
    stories = [
        _story(1, "Reuters", "2026-04-21T09:00:00Z"),
        _story(2, "Reuters", "2026-04-21T12:00:00Z"),  # newest
        _story(3, "Reuters", "2026-04-21T08:00:00Z"),
        _story(4, "Reuters", "2026-04-21T11:00:00Z"),  # 2nd newest
        _story(5, "Reuters", "2026-04-21T10:00:00Z"),
    ]
    drafter_saw, items_queued = await _run_with_stories_succeeding(
        stories, source_whitelist=whitelist, max_count=2
    )
    # Top 2 by published_at desc are story 2 (12:00) + story 4 (11:00).
    # Sort puts them first; break fires after 2 successes so only those 2 are seen.
    titles = {s["title"] for s in drafter_saw}
    assert titles == {"Headline 2", "Headline 4"}, f"Expected top-2-by-recency, got {titles}"
    assert items_queued == 2


@pytest.mark.asyncio
async def test_source_whitelist_none_is_noop():
    """source_whitelist=None (default) = all stories reach drafter — no whitelist or format gate applied."""
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


# ---------------------------------------------------------------------------
# New tests for quick-260423-hq7: break-after-N-successes / iterate-past-dedup
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_run_text_story_cycle_max_count_iterates_past_dedup_hits():
    """Core regression test for quick-260423-hq7 bug fix.

    The top 3 most-recent stories are dedup-blocked (_is_already_covered_today=True).
    Stories 4+5 are fresh. With max_count=2, the loop must continue past the
    dedup hits and draft stories 4+5.

    CURRENT BEHAVIOR (pre-fix): trim keeps stories 1+2 only → loop exits with
    items_queued=0. This test MUST FAIL before the fix.

    POST-FIX BEHAVIOR: all 5 candidates in list; loop skips 1-3 (dedup blocked),
    drafts 4+5, breaks after 2nd success.
    """
    stories = [
        _story(1, "Reuters", "2026-04-21T12:00:00Z"),  # newest — dedup blocked
        _story(2, "Reuters", "2026-04-21T11:00:00Z"),  # 2nd newest — dedup blocked
        _story(3, "Reuters", "2026-04-21T10:00:00Z"),  # 3rd newest — dedup blocked
        _story(4, "Reuters", "2026-04-21T09:00:00Z"),  # 4th — fresh
        _story(5, "Reuters", "2026-04-21T08:00:00Z"),  # 5th — fresh
    ]
    # Top 3 (by recency) are dedup-blocked
    dedup_blocked = frozenset({"Headline 1", "Headline 2", "Headline 3"})

    drafter_saw, items_queued = await _run_with_stories_succeeding(
        stories,
        max_count=2,
        dedup_returns_true_for=dedup_blocked,
    )

    # draft_fn must have been called only for stories 4 and 5 (the fresh ones)
    drafted_titles = {s["title"] for s in drafter_saw}
    assert drafted_titles == {"Headline 4", "Headline 5"}, (
        f"Expected loop to skip dedup hits and draft stories 4+5, got {drafted_titles}"
    )
    assert items_queued == 2, (
        f"Expected items_queued=2 after iterating past 3 dedup hits, got {items_queued}"
    )


@pytest.mark.asyncio
async def test_max_count_exhausts_if_insufficient_successes():
    """When draft_fn returns None for 9/10 stories, the full list is consumed.

    Validates the "no infinite-retry, no artificial padding" exit condition:
    all 10 stories are attempted, only 1 succeeded, items_queued=1 (not 2).
    """
    stories = [
        _story(i, "Reuters", f"2026-04-21T{i:02d}:00:00Z") for i in range(1, 11)
    ]
    # Only Headline 5 returns a real draft; all others return None
    draft_none_set = frozenset(
        f"Headline {i}" for i in range(1, 11) if i != 5
    )

    drafter_saw, items_queued = await _run_with_stories_succeeding(
        stories,
        max_count=2,
        stories_draft_returns_none=draft_none_set,
    )

    # draft_fn should have been called for all 10 stories (no trim, full exhaust)
    assert len(drafter_saw) == 10, (
        f"Expected draft_fn called for all 10 stories, got {len(drafter_saw)}"
    )
    # Only 1 draft succeeded — items_queued should be 1, not 2
    assert items_queued == 1, (
        f"Expected items_queued=1 (only 1 success out of 10), got {items_queued}"
    )


@pytest.mark.asyncio
async def test_max_count_none_still_iterates_all():
    """Regression guard for breaking_news (max_count=None): all 10 stories are drafted.

    With max_count=None, no break is injected. All 10 candidates should reach
    the drafter and be persisted.
    """
    stories = [
        _story(i, "Reuters", f"2026-04-21T{i:02d}:00:00Z") for i in range(1, 11)
    ]

    drafter_saw, items_queued = await _run_with_stories_succeeding(
        stories,
        max_count=None,  # breaking_news shape
    )

    assert len(drafter_saw) == 10, (
        f"max_count=None should draft all 10 candidates, got {len(drafter_saw)}"
    )
    assert items_queued == 10, (
        f"Expected all 10 to be persisted when max_count=None, got {items_queued}"
    )


# ---------------------------------------------------------------------------
# New tests for quick-260422-of3: sort_by + dedup_scope kwargs
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_sort_by_score_picks_top_by_score():
    """Covers D-01: sort_by="score" iterates top-2-by-score first and breaks after 2 successes.

    Rewritten for quick-260423-hq7: break-after-N-successes semantics.
    5 stories with scores [3, 9, 5, 9, 7], max_count=2 → drafter sees the two
    stories with score=9 first (loop breaks after 2nd success).
    """
    stories = [
        _story(1, "Reuters", "2026-04-21T10:00:00Z", score=3.0),
        _story(2, "Reuters", "2026-04-21T11:00:00Z", score=9.0),
        _story(3, "Reuters", "2026-04-21T09:00:00Z", score=5.0),
        _story(4, "Reuters", "2026-04-21T08:00:00Z", score=9.0),
        _story(5, "Reuters", "2026-04-21T12:00:00Z", score=7.0),
    ]
    drafter_saw, items_queued = await _run_with_stories_succeeding(
        stories, max_count=2, sort_by="score"
    )
    titles = {s["title"] for s in drafter_saw}
    assert titles == {"Headline 2", "Headline 4"}, f"Expected score=9 stories, got {titles}"
    assert items_queued == 2


@pytest.mark.asyncio
async def test_sort_by_score_breaks_ties_by_recency():
    """Covers D-01 (composite sort): tied scores → fresher published_at wins.

    Rewritten for quick-260423-hq7: break-after-N-successes semantics.
    Two stories both score=9. Story A at 12:00, story B at 09:00. With
    max_count=1 and sort_by="score", the 12:00 story (more recent) should win and break.
    """
    stories = [
        _story(1, "Reuters", "2026-04-21T09:00:00Z", score=9.0),  # older
        _story(2, "Reuters", "2026-04-21T12:00:00Z", score=9.0),  # newer → should win
    ]
    drafter_saw, items_queued = await _run_with_stories_succeeding(
        stories, max_count=1, sort_by="score"
    )
    assert len(drafter_saw) == 1, f"Expected break after 1 success, drafter_saw={[s['title'] for s in drafter_saw]}"
    assert drafter_saw[0]["title"] == "Headline 2", (
        "Fresher story (12:00) should win the tie-break — "
        f"got {drafter_saw[0]['title']}"
    )
    assert items_queued == 1


@pytest.mark.asyncio
async def test_sort_by_default_is_published_at():
    """Covers D-03: omitting sort_by yields identical output to sort_by='published_at'.

    Rewritten for quick-260423-hq7: break-after-N-successes semantics.
    Both calls with 5 stories should produce the same top-2 by recency.
    """
    stories = [
        _story(1, "Reuters", "2026-04-21T09:00:00Z", score=1.0),
        _story(2, "Reuters", "2026-04-21T12:00:00Z", score=3.0),  # newest
        _story(3, "Reuters", "2026-04-21T08:00:00Z", score=5.0),
        _story(4, "Reuters", "2026-04-21T11:00:00Z", score=7.0),  # 2nd newest
        _story(5, "Reuters", "2026-04-21T10:00:00Z", score=9.0),
    ]
    # Default (no sort_by) should pick the 2 most recent
    default_saw, default_queued = await _run_with_stories_succeeding(stories, max_count=2)
    explicit_saw, explicit_queued = await _run_with_stories_succeeding(
        stories, max_count=2, sort_by="published_at"
    )
    assert {s["title"] for s in default_saw} == {s["title"] for s in explicit_saw}
    # Both should be the 2 newest by published_at: story 2 (12:00) + story 4 (11:00)
    assert {s["title"] for s in default_saw} == {"Headline 2", "Headline 4"}
    assert default_queued == 2
    assert explicit_queued == 2


@pytest.mark.asyncio
async def test_dedup_scope_same_type_passes_content_type():
    """Covers D-02 + D-03: dedup_scope="same_type" passes content_type into _is_already_covered_today.

    Patches _is_already_covered_today and records its kwargs.
    - When dedup_scope="same_type": content_type kwarg == the cycle's content_type ("quote").
    - When dedup_scope="cross_agent" (default): content_type kwarg is None.
    """
    story = _story(1, "Reuters")
    ctx, _ = _session_ctx()

    recorded_kwargs: list[dict] = []

    async def fake_is_already_covered(session, url, headline, *, content_type=None):
        recorded_kwargs.append({"content_type": content_type})
        return False

    async def draft_fn(s, dr, ms, *, client):
        return None

    with patch("agents.content.AsyncSessionLocal", return_value=ctx), \
         patch("agents.content.fetch_market_snapshot", new=AsyncMock(return_value=None)), \
         patch("agents.content._is_already_covered_today", side_effect=fake_is_already_covered), \
         patch.object(content_agent, "fetch_stories", new=AsyncMock(return_value=[story])), \
         patch.object(content_agent, "is_gold_relevant_or_systemic_shock",
                      new=AsyncMock(return_value={"keep": True})), \
         patch.object(content_agent, "fetch_article",
                      new=AsyncMock(return_value=("body", True))), \
         patch.object(content_agent, "search_corroborating",
                      new=AsyncMock(return_value=[])):
        # same_type: should receive content_type="quote"
        await run_text_story_cycle(
            agent_name="test_agent",
            content_type="quote",
            draft_fn=draft_fn,
            dedup_scope="same_type",
        )

    same_type_kwargs = recorded_kwargs[:]
    recorded_kwargs.clear()

    with patch("agents.content.AsyncSessionLocal", return_value=ctx), \
         patch("agents.content.fetch_market_snapshot", new=AsyncMock(return_value=None)), \
         patch("agents.content._is_already_covered_today", side_effect=fake_is_already_covered), \
         patch.object(content_agent, "fetch_stories", new=AsyncMock(return_value=[story])), \
         patch.object(content_agent, "is_gold_relevant_or_systemic_shock",
                      new=AsyncMock(return_value={"keep": True})), \
         patch.object(content_agent, "fetch_article",
                      new=AsyncMock(return_value=("body", True))), \
         patch.object(content_agent, "search_corroborating",
                      new=AsyncMock(return_value=[])):
        # cross_agent (default): should receive content_type=None
        await run_text_story_cycle(
            agent_name="test_agent",
            content_type="quote",
            draft_fn=draft_fn,
            dedup_scope="cross_agent",
        )

    cross_agent_kwargs = recorded_kwargs[:]

    assert same_type_kwargs, "Expected at least one _is_already_covered_today call"
    assert same_type_kwargs[0]["content_type"] == "quote", (
        f"same_type scope should pass content_type='quote', got {same_type_kwargs[0]}"
    )
    assert cross_agent_kwargs, "Expected at least one _is_already_covered_today call"
    assert cross_agent_kwargs[0]["content_type"] is None, (
        f"cross_agent scope should pass content_type=None, got {cross_agent_kwargs[0]}"
    )


@pytest.mark.asyncio
async def test_is_already_covered_today_scopes_by_content_type():
    """Covers D-02: _is_already_covered_today adds content_type filter when arg is not None.

    Uses a fake session that records the SELECT statement. Verifies:
    - content_type=None → no content_type filter in WHERE
    - content_type="quote" → ContentBundle.content_type == "quote" included in WHERE
    """
    # Build a fake scalars() result that yields no bundles (so the function returns False)
    fake_result = MagicMock()
    fake_result.scalars.return_value.all.return_value = []

    # We'll capture the WHERE clauses by inspecting what session.execute receives.
    # Use two separate sessions and record the compiled SQL for comparison.
    session_no_ct = AsyncMock()
    session_no_ct.execute = AsyncMock(return_value=fake_result)

    session_with_ct = AsyncMock()
    session_with_ct.execute = AsyncMock(return_value=fake_result)

    # Call without content_type → cross-agent scope
    result_no_ct = await _is_already_covered_today(
        session_no_ct, "http://x.com/1", "Gold headline", content_type=None
    )
    # Call with content_type="quote" → same-type scope
    result_with_ct = await _is_already_covered_today(
        session_with_ct, "http://x.com/1", "Gold headline", content_type="quote"
    )

    # Both should return False (no matching bundles)
    assert result_no_ct is False
    assert result_with_ct is False

    # Inspect the SELECT statements passed to execute()
    stmt_no_ct = session_no_ct.execute.call_args[0][0]
    stmt_with_ct = session_with_ct.execute.call_args[0][0]

    # Compile to text for string inspection
    from sqlalchemy.dialects import postgresql  # noqa: PLC0415
    sql_no_ct = str(stmt_no_ct.compile(dialect=postgresql.dialect(), compile_kwargs={"literal_binds": True}))
    sql_with_ct = str(stmt_with_ct.compile(dialect=postgresql.dialect(), compile_kwargs={"literal_binds": True}))

    # `content_type` appears in the SELECT column list regardless; the WHERE
    # clause is what we actually care about. Extract the WHERE portion via regex
    # so we're not sensitive to SQLAlchemy's formatting (which puts WHERE on a
    # new line).
    import re as _re  # noqa: PLC0415
    where_no_ct_m = _re.search(r"\bWHERE\b(.*)", sql_no_ct, _re.DOTALL)
    where_with_ct_m = _re.search(r"\bWHERE\b(.*)", sql_with_ct, _re.DOTALL)
    where_no_ct = where_no_ct_m.group(1) if where_no_ct_m else ""
    where_with_ct = where_with_ct_m.group(1) if where_with_ct_m else ""

    # The no-content_type query's WHERE should NOT mention content_type
    assert "content_type" not in where_no_ct, (
        f"Expected no content_type predicate when arg=None, but found it in WHERE: {where_no_ct}"
    )
    # The with-content_type query's WHERE SHOULD include content_type = 'quote'
    assert "content_type" in where_with_ct, (
        f"Expected content_type predicate when arg='quote', but missing from WHERE: {where_with_ct}"
    )
    assert "'quote'" in where_with_ct, (
        f"Expected literal 'quote' in WHERE predicate, got: {where_with_ct}"
    )
