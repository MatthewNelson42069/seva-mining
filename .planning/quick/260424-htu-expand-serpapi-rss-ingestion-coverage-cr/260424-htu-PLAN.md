---
quick_task: 260424-htu
slug: expand-serpapi-rss-ingestion-coverage-cr
subsystem: scheduler/agents/content_agent (SERPAPI_KEYWORDS + RSS_FEEDS)
mode: plan
date: 2026-04-24
---

# PLAN — 260424-htu

## Goal

Expand `SERPAPI_KEYWORDS` by 8 high-signal entries (10→18) and swap the dead Reuters RSS feed for BNN Bloomberg in `RSS_FEEDS`, so the ingestion pipeline stops missing critical-minerals and sovereign-gold-sale stories (Azerbaijan $3B drawdown + EU/US critical minerals deal).

## Context references

- `.planning/quick/260424-htu-expand-serpapi-rss-ingestion-coverage-cr/260424-htu-CONTEXT.md` — 9 locked decisions, DB diagnostic, SerpAPI budget math, success criteria.
- `scheduler/agents/content_agent.py:52-60` — `RSS_FEEDS` list (current 7 entries; drop Reuters, add BNN Bloomberg → still 7).
- `scheduler/agents/content_agent.py:66-77` — `SERPAPI_KEYWORDS` list (current 10 entries; +8 → 18).
- `scheduler/tests/test_content_agent.py:50-59` — existing length assertions on both constants. See Note A under T2.
- `CLAUDE.md` — uv-managed Python, ruff, pytest-asyncio, 6-sub-agent topology.

## Scope locked (from CONTEXT, do not revisit)

**MODIFY:**
- `scheduler/agents/content_agent.py` — add 8 SERPAPI_KEYWORDS; drop broken Reuters RSS tuple; add BNN Bloomberg RSS tuple.
- `scheduler/tests/test_content_agent.py` — add 4 new tests; adjust existing length assertion at L58 (`== 10` → `== 18`). L52 length assertion stays at `== 7` (drop 1 + add 1 = net 0).

**ZERO DIFF (preservation-verified):**
- All 6 sub-agents under `scheduler/agents/content/`
- `scheduler/worker.py`
- `scheduler/agents/senior_agent.py`
- `backend/`, `frontend/`, `alembic/`, `scheduler/models/`

**New keywords (CONTEXT Q1 — LOCKED, exact strings):**
1. `critical minerals`
2. `rare earth restrictions`
3. `strategic metals`
4. `sovereign wealth fund gold`
5. `treasury gold sale`
6. `gold mining M&A`
7. `US China metals`
8. `mineral supply chain`

**RSS changes (CONTEXT Q2 + Q3 — LOCKED):**
- DROP: `("https://feeds.reuters.com/reuters/businessNews", "reuters.com")`
- ADD: `("https://www.bnnbloomberg.ca/feed/", "bnnbloomberg.ca")`

## Tasks

### T1 — RED tests for keyword + RSS coverage

**Files:** `scheduler/tests/test_content_agent.py`

**Tests to add (append after existing constant-preservation tests around L59):**

```python
def test_serpapi_keywords_critical_minerals_coverage():
    """New keywords for critical-minerals + sovereign-gold coverage (htu)."""
    required = [
        "critical minerals",
        "rare earth restrictions",
        "strategic metals",
        "sovereign wealth fund gold",
        "treasury gold sale",
        "gold mining M&A",
        "US China metals",
        "mineral supply chain",
    ]
    for kw in required:
        assert kw in content_agent.SERPAPI_KEYWORDS, f"missing keyword: {kw}"


def test_serpapi_keywords_existing_preserved():
    """Original 10 keywords must remain after expansion (htu)."""
    original = [
        "gold exploration", "gold price", "central bank gold", "gold ETF",
        "junior miners", "gold reserves", "gold inflation hedge", "Fed gold",
        "dollar gold", "recession gold",
    ]
    for kw in original:
        assert kw in content_agent.SERPAPI_KEYWORDS, f"pre-existing keyword dropped: {kw}"


def test_serpapi_keywords_total_count_and_unique():
    """Total = 18, no duplicates (htu)."""
    assert len(content_agent.SERPAPI_KEYWORDS) == 18
    assert len(set(content_agent.SERPAPI_KEYWORDS)) == 18


def test_rss_feeds_reuters_dropped_bnn_added():
    """Dead Reuters feed removed, BNN Bloomberg added (htu)."""
    urls = [u for u, _ in content_agent.RSS_FEEDS]
    assert not any("feeds.reuters.com" in u for u in urls), "dead Reuters feed still present"
    assert any("bnnbloomberg.ca" in u for u in urls), "BNN Bloomberg feed missing"
```

**Acceptance:**
- All 4 new tests fail against current code (critical minerals absent, len==10 not 18, Reuters still present, BNN missing).
- Run: `cd scheduler && uv run pytest tests/test_content_agent.py::test_serpapi_keywords_critical_minerals_coverage tests/test_content_agent.py::test_serpapi_keywords_existing_preserved tests/test_content_agent.py::test_serpapi_keywords_total_count_and_unique tests/test_content_agent.py::test_rss_feeds_reuters_dropped_bnn_added -v` → 4 failures as expected.
- Do NOT modify L52 / L58 in this task — existing assertions are part of the RED baseline (L58 currently `== 10`, passing; will continue passing until T2 where we update it alongside the list change).

**Commit:** `test(content): add keyword + RSS coverage assertions (htu)`

### T2 — GREEN: expand SERPAPI_KEYWORDS + swap Reuters→BNN Bloomberg

**Files:**
- `scheduler/agents/content_agent.py`
- `scheduler/tests/test_content_agent.py` (one-line update, see Note A)

**Changes to `content_agent.py`:**

1. In `RSS_FEEDS` (L52-60): remove the `("https://feeds.reuters.com/reuters/businessNews", "reuters.com")` tuple; insert `("https://www.bnnbloomberg.ca/feed/", "bnnbloomberg.ca")` in the same relative position (keeps credibility ordering sensible). Final list length remains 7.

2. In `SERPAPI_KEYWORDS` (L66-77): append the 8 new keyword strings verbatim from the locked list above. Preserve the existing 10 in their current order. Final list length = 18.

**Change to `test_content_agent.py` (Note A):**

- Update L58 from `assert len(content_agent.SERPAPI_KEYWORDS) == 10` → `assert len(content_agent.SERPAPI_KEYWORDS) == 18`. This is a necessary companion edit — the old assertion encoded the pre-expansion count and must track the new truth. L52 (`len == 7`) stays unchanged.

**Acceptance gates (all must pass):**

```bash
cd scheduler && uv run pytest tests/test_content_agent.py -x -v     # green (all 4 new + updated L58)
cd scheduler && uv run pytest -x                                     # full scheduler suite green
cd scheduler && uv run ruff check agents/content_agent.py tests/test_content_agent.py  # clean
cd scheduler && uv run ruff format --check agents/content_agent.py tests/test_content_agent.py  # clean

grep -n "critical minerals" scheduler/agents/content_agent.py   # 1 match
grep -n "sovereign wealth fund gold" scheduler/agents/content_agent.py  # 1 match
grep -n "bnnbloomberg.ca" scheduler/agents/content_agent.py     # 1 match
grep -n "feeds.reuters.com" scheduler/agents/content_agent.py   # 0 matches
```

**Commit:** `feat(content): expand SerpAPI keywords + swap broken Reuters RSS for BNN Bloomberg (htu)`

**Allowed deviation (per CONTEXT Q9):** Executor MAY collapse T1 + T2 into a single atomic commit if they judge the RED/GREEN ceremony adds no durable signal for a data-list change of this size. If combined, use commit message: `feat(content): expand SerpAPI keywords + swap Reuters→BNN Bloomberg RSS, with coverage tests (htu)`. The validation gates in T2 are the hard requirement either way.

### T3 — Validation sweep + docs + merge

**Actions:**

1. Re-run the full validation gates block (see "Validation gates" section below) from a clean shell. Every command must produce the expected output.

2. Preservation invariant check — confirm zero diff on protected paths:
   ```bash
   git diff main -- scheduler/agents/content/
   git diff main -- scheduler/worker.py
   git diff main -- scheduler/agents/senior_agent.py
   git diff main -- backend/ frontend/ alembic/ scheduler/models/
   ```
   All six must return empty.

3. Write `.planning/quick/260424-htu-expand-serpapi-rss-ingestion-coverage-cr/260424-htu-SUMMARY.md` covering: what shipped, why (link back to CONTEXT Q1/Q2/Q3), files touched, validation evidence (paste grep output + pytest counts), open follow-ups (copy from CONTEXT section "Known follow-ups").

4. Append a row to the top of `.planning/STATE.md` under "Quick Tasks Completed": date, task id, one-line summary, commit SHA(s).

5. Fast-forward merge the worktree to main. If the worktree has a single clean commit from a combined T1+T2 deviation, no rebase needed.

**Commit:** `docs(htu): SUMMARY + STATE row` (or fold into T2 if the worktree ends up with a single-commit history).

## Validation gates (hard requirements — from CONTEXT)

```bash
# Pytest
cd scheduler && uv run pytest tests/test_content_agent.py -x -v   # green
cd scheduler && uv run pytest -x                                   # full suite green

# Ruff
cd scheduler && uv run ruff check agents/content_agent.py tests/test_content_agent.py         # clean
cd scheduler && uv run ruff format --check agents/content_agent.py tests/test_content_agent.py # clean

# Grep (positive)
grep -n "critical minerals" scheduler/agents/content_agent.py          # 1 match
grep -n "rare earth restrictions" scheduler/agents/content_agent.py    # 1 match
grep -n "sovereign wealth fund gold" scheduler/agents/content_agent.py # 1 match
grep -n "treasury gold sale" scheduler/agents/content_agent.py         # 1 match
grep -n "strategic metals" scheduler/agents/content_agent.py           # 1 match
grep -n "gold mining M&A" scheduler/agents/content_agent.py            # 1 match
grep -n "US China metals" scheduler/agents/content_agent.py            # 1 match
grep -n "mineral supply chain" scheduler/agents/content_agent.py       # 1 match
grep -n "bnnbloomberg.ca" scheduler/agents/content_agent.py            # 1 match

# Grep (negative — dead feed removed)
grep -n "feeds.reuters.com" scheduler/agents/content_agent.py          # 0 matches
```

## Preservation invariants (must verify via git diff — all empty)

```bash
git diff main -- scheduler/agents/content/          # 6 sub-agents untouched
git diff main -- scheduler/worker.py                # scheduler entry unchanged
git diff main -- scheduler/agents/senior_agent.py   # senior agent untouched
git diff main -- backend/                           # API unchanged
git diff main -- frontend/                          # UI unchanged
git diff main -- alembic/                           # no migrations
git diff main -- scheduler/models/                  # no schema changes
```

## Follow-ups (NOT in scope — document in SUMMARY.md)

1. **SerpAPI plan tier verification (CONTEXT Q6)** — user to confirm current plan + usage at console.serpapi.com. Post-expansion math: ~35,100 calls/mo. Upgrade if on $50 tier.
2. **Recency curve tuning (CONTEXT Q7)** — consider a 24-48h bucket at recency_score=0.5 (between 0.4 and 0.2). Would have helped Azerbaijan story, but risks queue flood. Re-evaluate after ingestion expansion lands in prod for ~1 week.
3. **j7x bullish-filter tuning** — only relevant if Azerbaijan re-surfaces as bearish-filtered post-expansion. DB evidence currently does not implicate j7x.
4. **Dedup horizon review** — cross-agent dedup may be collapsing sovereign-sales stories (France / Russia / Azerbaijan) too aggressively. Separate investigation.
5. **Twilio real-time SMS + X auto-post architecture** — explicitly out of scope; requires its own `/gsd:quick --discuss --research --full` session.
6. **RSS feed expansion phase 2** — candidates (AP business, Dow Jones newswire, Nikkei English gold section) deferred until BNN Bloomberg proves its value in 1-2 weeks of prod.
