"""v3.1 Phase 15 — JUNO_SWEEPER_X_QUERY constant invariants (D-01, D-02 + RESEARCH §1, §3).

Tests the post-research corrected D-02 handle set is encoded correctly + that
the query stays inside X API Basic-tier 512-char limit + that the explicit
anti-feature (defence-prime cashtags) does NOT slip in.

These tests catch regressions where a future contributor reverts to the
CONTEXT.md original (uncorrected) handle spellings OR accidentally adds a
cashtag against PROJECT.md anti-feature.
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))


def _query() -> str:
    from companies.juno.x_queries import JUNO_SWEEPER_X_QUERY
    return JUNO_SWEEPER_X_QUERY


def test_query_constant_exists_and_nonempty():
    """D-01 — JUNO_SWEEPER_X_QUERY importable + non-empty."""
    q = _query()
    assert isinstance(q, str)
    assert len(q) > 0


def test_query_length_within_basic_tier_cap():
    """RESEARCH §3 — X API Basic tier query length cap is 512 chars (NOT 1024,
    which is the Academic Research tier). Query must be strictly less than 512."""
    q = _query()
    assert len(q) < 512, (
        f"JUNO_SWEEPER_X_QUERY length {len(q)} exceeds X API Basic-tier "
        f"512-char limit per RESEARCH §3"
    )


def test_query_contains_all_corrected_handles():
    """D-02 + RESEARCH §1 — all 11 corrected handles must appear in the query.

    Verifies the post-research corrections + Tier-2 Canadian additions are
    encoded; a regression to CONTEXT.md original spelling would fail here.
    """
    q = _query()
    # Think-tanks (3)
    assert "from:RUSI_org" in q
    assert "from:CSIS" in q
    assert "from:IISS_org" in q
    # Defence press (4) — RESEARCH §1 corrections applied
    assert "from:defense_news" in q
    assert "from:BreakingDefense" in q
    assert "from:DefenseScoop" in q
    assert "from:JanesINTEL" in q
    # Canadian (4) — RESEARCH §1 + §2 corrections + additions applied
    assert "from:CDAInstitute" in q
    assert "from:CanadianForces" in q
    assert "from:DavePerryCGAI" in q
    assert "from:Murray_Brewster" in q


def test_query_contains_both_hashtags():
    """D-02 — #defence + #NATO hashtags present."""
    q = _query()
    assert "#defence" in q
    assert "#NATO" in q


def test_query_contains_modifiers():
    """D-01 + RESEARCH §3 — -is:retweet (exclude retweets) + lang:en filters."""
    q = _query()
    assert "-is:retweet" in q
    assert "lang:en" in q


def test_query_excludes_defence_prime_cashtags():
    """PROJECT.md anti-feature — equity/financial signals on defence primes
    are explicitly EXCLUDED. Verify no defence-prime cashtag slipped in."""
    q = _query()
    for cashtag in ("$LMT", "$RTX", "$LDOS", "$BAESY", "$GD", "$NOC", "$BA"):
        assert cashtag not in q, (
            f"PROJECT.md anti-feature violated: defence-prime cashtag "
            f"{cashtag!r} must NOT appear in JUNO_SWEEPER_X_QUERY"
        )


def test_query_excludes_wrong_spelling_handles():
    """RESEARCH §1 — these handle spellings would return 0 hits if used.

    Catches regression to CONTEXT.md original D-02 spellings.
    """
    q = _query()
    # RESEARCH §1 wrong spellings:
    # - @DefenseNews -> use defense_news (snake_case)
    # - @CDA_CDAI    -> use CDAInstitute
    # - @canadaforces -> use CanadianForces
    # We assert the LITERAL substring "from:DefenseNews" does not appear; the
    # corrected "from:defense_news" IS present (see test above).
    assert "from:DefenseNews" not in q
    assert "from:CDA_CDAI" not in q
    assert "from:canadaforces" not in q


def test_query_is_balanced_parentheses():
    """X API v2 Boolean grouping with parentheses — outer group must be balanced
    per RESEARCH §3 'Boolean grouping with parentheses'."""
    q = _query()
    assert q.count("(") == q.count(")"), (
        f"JUNO_SWEEPER_X_QUERY has unbalanced parentheses: "
        f"{q.count('(')} '(' vs {q.count(')')} ')'"
    )
