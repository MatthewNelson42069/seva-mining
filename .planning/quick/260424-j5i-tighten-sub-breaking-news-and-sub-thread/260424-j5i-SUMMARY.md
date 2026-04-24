---
task: 260424-j5i
type: quick
shipped: 2026-04-24
outcome: "sub_breaking_news and sub_threads now select the 'top of top' stories via composite-score sort + top-N cap + min_score=6.5 floor; recency curve gains a <48h=0.3 bucket; 'rare earth restrictions' SERPAPI keyword removed; sub_threads cadence flipped 4h → 3h."
commits:
  - hash: 62205bb
    message: "test(j5i): add failing tests for top-of-top tightening (RED)"
    phase: T1 (RED)
  - hash: e45fb74
    message: "feat(j5i): tighten breaking_news + threads selection (GREEN)"
    phase: T2 (GREEN)
  - hash: 2120598
    message: "test(j5i): reconcile D8/D9 breakage in existing assertions"
    phase: T3 (TEST-ADJUST)
  - hash: 223cfe1
    message: "docs(j5i): SUMMARY + STATE.md update"
    phase: T4 (DOCS)
tests_run: 175
ruff: clean
decisions_realized: [D1, D2, D3, D4, D5, D6, D7, D8, D9]
---

# Quick Task 260424-j5i: Tighten sub_breaking_news + sub_threads to "top-of-top" — Summary

## Outcome

`sub_breaking_news` and `sub_threads` now select the highest-signal stories per run via the battle-tested composite-score sort + top-N cap already used by `sub_infographics`, plus a new `min_score=6.5` floor that silently drops stories below the threshold (preferred UX over forcing mediocre content into the top-N slots). Two folded-in user directives are baked into the same commit boundary: (a) removed `"rare earth restrictions"` from SERPAPI keywords (pulled too many off-theme rare-earth policy pieces that did not map to gold); (b) flipped `sub_threads` cadence from 4h to 3h (halfway back from the vxg 4h rebalance). Recency curve gains a `<48h=0.3` bucket to soften the 24h→48h cliff for credible late-catch stories. Rich telemetry at `agent_run.notes` now covers `breaking_news`/`thread`/`infographic` uniformly and exposes `floored_by_min_score` for post-launch observability.

## Date Shipped

2026-04-24

## What Shipped — Substantive Production Changes (9, mapping D1–D9)

### D1 — Top-N cap with composite-score sort
- `scheduler/agents/content/breaking_news.py::run_draft_cycle` now passes `max_count=3, sort_by="score", min_score=BREAKING_NEWS_MIN_SCORE` to `run_text_story_cycle` (was: no `max_count`, no `sort_by` — approved everything).
- `scheduler/agents/content/threads.py::run_draft_cycle` now passes `max_count=2, sort_by="score", min_score=THREADS_MIN_SCORE` (was: `max_count=2` only, sorted by `published_at` default — switched to composite sort).
- Both call-sites use the same parameter shape as `sub_infographics` so operators can scan three call-sites and reason about behavior uniformly.

### D2 — Minimum composite-score floor (new filter)
- Added module-level constant `BREAKING_NEWS_MIN_SCORE: float = 6.5` at `scheduler/agents/content/breaking_news.py:31`.
- Added module-level constant `THREADS_MIN_SCORE: float = 6.5` at `scheduler/agents/content/threads.py:26`.
- Extended `run_text_story_cycle` signature at `scheduler/agents/content/__init__.py` with trailing keyword-only parameter `min_score: float | None = None` (default disables check → zero-impact for other 4 sub-agents).
- Floor check inserted inside the `if compliance_ok:` branch BEFORE `items_queued += 1`: stories below `min_score` are logged + skipped (continue), the ContentBundle row is still persisted with `compliance_passed=True` (D6), only the DraftItem is not created.

### D3 — Recency curve softening (<48h=0.3 bucket)
- Grew `recency_score` at `scheduler/agents/content_agent.py:111-133` from 5 buckets to 6: added `if age_hours < 48: return 0.3` between the `<24h=0.4` and terminal `return 0.2` branches. Curve is now strictly monotonic — no story gets LESS recency signal than before, some (24h–48h old) get MORE.
- Affects ALL 6 sub-agents' sorting (D3 impact scope), not just the two j5i targets. Acceptable per plan — change is strictly monotonic.

### D4 — Haiku gate prompt byte-for-byte preserved
- `is_gold_relevant_or_systemic_shock` prompt at `content_agent.py:443-500` is untouched. The two narrative `rare-earth` mentions at `L455` (systemic-shock framing example) and `L502` (KEEP example) survive verbatim — they are example-language in the gate prompt, not ingestion keywords. Grep proof: `grep -n "rare-earth" scheduler/agents/content_agent.py` returns 4 matches (2 new narrative comment lines at L78-79 explaining the D8 keyword removal, plus 2 preserved Haiku prompt lines at L455/L502).

### D5 — Draft prompts untouched
- No changes to `_draft` / `_research_and_draft` prompt text in `breaking_news.py` or `threads.py`. Only constants + call-site kwargs changed. This is a selection-tuning task, not a voice-tuning task. Verified by inspection of the git diff.

### D6 — min_score placement AFTER compliance; ContentBundle persisted, DraftItem skipped
- Floor check sits AFTER Haiku gate AND AFTER compliance review, so floored items produce ContentBundle rows with `compliance_passed=True` (full observability: we see how often the floor actually kicks in) but do NOT produce DraftItem rows. Implementation at `scheduler/agents/content/__init__.py` — floor is the FIRST guard inside the `if compliance_ok:` block.

### D7 — Rich telemetry broadened
- The rich-telemetry branch at `content/__init__.py` was `if content_type == "infographic":` — broadened to `if content_type in ("infographic", "breaking_news", "thread"):` (content_type strings match exact call-site values; verified by reading breaking_news.py + threads.py before writing T2).
- Payload now includes `"floored_by_min_score": floored_by_min_score` alongside existing `candidates`, `top_by_score`, `drafted`, `compliance_blocked`, `queued`. Minimal else-branch `{"candidates": N}` preserved for quotes/gold_media/gold_history.
- Infographics retain the same key (counter stays 0 because infographics never opt into min_score) — no behavior change for that sub-agent.

### D8 — "rare earth restrictions" keyword removed
- Deleted the `"rare earth restrictions",` entry from `SERPAPI_KEYWORDS` at `scheduler/agents/content_agent.py:79`. Updated surrounding htu-era expansion comment from "8 additions" → "7 additions" for honesty.
- `SERPAPI_KEYWORDS` length drops 18 → 17.
- Grep proof: `grep -c "rare earth restrictions" scheduler/agents/content_agent.py` = 0 in production; hyphenated `rare-earth` at Haiku prompt L455/L502 preserved.

### D9 — sub_threads cadence 4h → 3h
- Flipped the 6th tuple element in the `CONTENT_INTERVAL_AGENTS` tuple for `sub_threads` at `scheduler/worker.py:118` from `4` → `3`. Tuple now reads `("sub_threads", threads.run_draft_cycle, "Threads", 1011, 17, 3)`.
- Updated narrative "4h" references at L10, L109, L314, L328 to "3h". Preserved the historical `260422-vxg` changelog-style line at L27 because that line narrates vxg-era state as a historical reference (still correct for the period it describes).
- `sub_breaking_news` interval UNCHANGED at 2h (explicit no-diff verified).

## Test Changes (RED + TEST-ADJUST, total +9 new tests, 167 → 175 passing)

### T1 (RED, `62205bb`) — 9 new failing tests locking expected behavior before production code changes

| File | Test | Assertion |
|------|------|-----------|
| `tests/test_content_agent.py` | `test_recency_score_48h_bucket` | `recency_score(25h_ago) == 0.3`, `47h → 0.3`, `49h → 0.2`, `22h → 0.4` |
| `tests/test_content_wrapper.py` | `test_min_score_filters_below_threshold` | 3 stories (scores 8.0/6.0/5.5) with floor=6.5 → only 8.0 persists a DraftItem; 6.0 + 5.5 persist ContentBundle only |
| `tests/test_content_wrapper.py` | `test_floored_by_min_score_counter_populated` | `notes["floored_by_min_score"] == 2` after above run |
| `tests/test_content_wrapper.py` | `test_all_stories_floored_returns_empty_not_failed` | All stories score=5.0, floor=6.5 → `items_queued == 0`, `status == "completed"` (not "failed"), `build_draft_item.call_count == 0` |
| `tests/test_breaking_news.py` | `test_breaking_news_min_score_constant` | `BREAKING_NEWS_MIN_SCORE == 6.5` |
| `tests/test_breaking_news.py` | `test_breaking_news_passes_selection_kwargs` | Call-kwargs assertion: `max_count=3, sort_by="score", min_score=6.5` |
| `tests/test_threads.py` | `test_threads_min_score_constant` | `THREADS_MIN_SCORE == 6.5` |
| `tests/test_threads.py` | `test_threads_passes_selection_kwargs` | Call-kwargs assertion: `max_count=2, sort_by="score", min_score=6.5` |
| `tests/test_worker.py` | `test_sub_threads_interval_is_three_hours` | `cadences["sub_threads"] == 3` |

### T3 (TEST-ADJUST, `2120598`) — reconciled 5 pre-existing assertions broken by D8/D9/D7 production diffs

| File | Test | Change |
|------|------|--------|
| `tests/test_content_agent.py:58` | `test_serpapi_keywords_present` | `len(SERPAPI_KEYWORDS) == 18` → `== 17` |
| `tests/test_content_agent.py:66` | `test_serpapi_keywords_critical_minerals_coverage` | Removed `"rare earth restrictions"` from required-keywords list (8 → 7 entries) |
| `tests/test_content_agent.py:98-99` | `test_serpapi_keywords_no_duplicates` | Both length assertions `== 18` → `== 17` |
| `tests/test_worker.py:247` | `test_interval_agents_cadences` | `"sub_threads": 4` → `"sub_threads": 3`; docstring updated "Post-k8n...Threads=4h" → "Post-j5i...Threads=3h" |
| `tests/test_infographics.py` | `test_run_draft_cycle_writes_structured_notes` | Added `"floored_by_min_score": 0` key to expected telemetry dict (D7 broadening side-effect — not pre-identified in the plan as a T3 target but same TEST-ADJUST category, bundled here to keep T4 as pure docs/state) |

## What Did NOT Change (Zero-diff proof ran clean)

`git diff main -- <path>` returned 0 lines across all 10 out-of-scope paths:

- `scheduler/agents/content/quotes.py`
- `scheduler/agents/content/infographics.py`
- `scheduler/agents/content/gold_media.py`
- `scheduler/agents/content/gold_history.py`
- `scheduler/services/whatsapp.py`
- `scheduler/agents/senior_agent.py`
- `backend/`
- `frontend/`
- `alembic/`
- `scheduler/models/`

The Haiku compliance gate, all sub-agent draft prompts, and the morning/midday digest plumbing are byte-for-byte identical to main. No DB schema changes, no new Config keys, no new API integrations, no frontend changes.

## Post-Launch Observability Signal (CRITICAL — monitor over first 72h)

Research Q5 probed the live Neon DB to measure what fraction of compliance-passed stories would survive a 6.5 floor over the last 7 days:

| Sub-agent | Compliance-passed rows (n) | Would pass 6.5 floor | Retention % |
|-----------|----------------------------|----------------------|-------------|
| `sub_breaking_news` | 251 | 103 | **41%** |
| `sub_threads` | 52 | 26 | **50%** |

CONTEXT.md's sanity band was **50–80% retention**; `breaking_news` at 41% sits **BELOW the lower bound**.

**Why this is not a blocker:**
- `BREAKING_NEWS_MIN_SCORE` is a one-line module-level constant (`scheduler/agents/content/breaking_news.py:31`). Tuning is a one-character edit + Railway redeploy.
- Empty runs are handled silently per the i8b WhatsApp firehose contract — a quiet run where everything floors is NO WhatsApp, which is the preferred UX over forcing mediocre content.
- The new `floored_by_min_score` telemetry in `agent_run.notes` gives direct visibility into floor behavior per run.

**Monitoring plan (operator should watch for first 72h post-deploy):**
1. `agent_run.notes.floored_by_min_score` — per-run counter. If consistently high (e.g., >70% of `(compliance_blocked + queued + floored_by_min_score)` total on most runs), the floor is too aggressive.
2. Total `sub_breaking_news` WhatsApp firehose volume per 24h window. Target range: 12–20 messages/day (roughly 1–2 per run at 12 runs/day × 41% retention × avg 3-candidate-pool hit rate).
3. If >70% of runs are emitting 0 approved items across a 24h window, drop `BREAKING_NEWS_MIN_SCORE` to 6.0. Research Q5's distribution projection suggests 6.0 would yield ~62% retention for `breaking_news`.

**Threads retention at 50% is at the floor of the sanity band** — no immediate tuning concern but worth monitoring alongside breaking_news.

## Decisions Log

| Decision | Locked Resolution | Realized In |
|----------|-------------------|-------------|
| D1 | Top-N cap + composite score sort: BN `max_count=3, sort_by="score"`; Threads `max_count=2, sort_by="score"` | T2 (breaking_news.py + threads.py call-site kwargs) |
| D2 | `min_score=6.5` floor applied only to BN + threads, as parameter on `run_text_story_cycle` + per-agent module constants | T2 (__init__.py signature + breaking_news.py + threads.py constants) |
| D3 | Recency curve grows `<48h=0.3` bucket between `<24h=0.4` and `≥48h=0.2` | T2 (content_agent.py:133) |
| D4 | No Haiku-gate prompt changes; hyphenated `rare-earth` at L455/L502 preserved verbatim | T2 guard (explicit DO-NOT-TOUCH in plan, verified via diff) |
| D5 | No analyst draft-prompt changes | T2 guard (no draft-prompt text modified; verified via diff) |
| D6 | `min_score` check AFTER compliance review, BEFORE `items_queued += 1`; ContentBundle PERSISTED for floored items, DraftItem SKIPPED | T2 (__init__.py insertion inside `if compliance_ok:` block) |
| D7 | `agent_run.notes` rich-telemetry branch broadened to `("infographic", "breaking_news", "thread")`; new key `floored_by_min_score` | T2 (__init__.py telemetry branch) |
| D8 | Remove `"rare earth restrictions"` from SERPAPI_KEYWORDS; hyphenated form in Haiku prompt preserved | T2 (content_agent.py:79 deletion + comment update) + T3 (test_content_agent.py:58/66/98-99) |
| D9 | `sub_threads` cadence 4h → 3h; `sub_breaking_news` stays at 2h | T2 (worker.py:118 tuple value + 4 narrative "4h" comments) + T3 (test_worker.py:247 cadence dict + docstring) |

Reference: `.planning/quick/260424-j5i-tighten-sub-breaking-news-and-sub-thread/260424-j5i-CONTEXT.md` (D1–D9 lock rationale) and `...-RESEARCH.md` (Q1–Q10 reconnaissance).

## Commits Landed (4 atomic)

| Commit | Phase | Message | Scope |
|--------|-------|---------|-------|
| `62205bb` | T1 RED | `test(j5i): add failing tests for top-of-top tightening (RED)` | +9 tests across 5 files; all fail with clear reasons (AttributeError for constants, KeyError for `floored_by_min_score`, wrong cadence value, wrong recency bucket value) |
| `e45fb74` | T2 GREEN | `feat(j5i): tighten breaking_news + threads selection (GREEN)` | 5 production files: content_agent.py (recency bucket + keyword removal), content/__init__.py (signature + floor check + telemetry broadening), content/breaking_news.py (constant + kwargs), content/threads.py (constant + kwargs), worker.py (cadence flip + comment updates). All T1 tests now PASS; 3 pre-existing D8/D9 tests fail as expected (T3 territory); 1 additional infographics telemetry test broke on D7 side-effect (also T3) |
| `2120598` | T3 TEST-ADJUST | `test(j5i): reconcile D8/D9 breakage in existing assertions` | 3 files: test_content_agent.py (3 length/membership assertions), test_worker.py (cadence value + docstring), test_infographics.py (new telemetry key in expected dict). Full suite green: 175 passed |
| `223cfe1` | T4 DOCS | `docs(j5i): SUMMARY + STATE.md update` | This file + planning artifacts (CONTEXT/PLAN/RESEARCH landed on main) + STATE.md Quick Tasks Completed row + frontmatter `stopped_at` / `last_updated` refresh |

## Validation Gate Results

```text
$ cd scheduler && uv run pytest -x
======================= 175 passed, 63 warnings in 0.92s =======================

$ cd scheduler && uv run ruff check .
All checks passed!

$ grep -n "^BREAKING_NEWS_MIN_SCORE" scheduler/agents/content/breaking_news.py
31:BREAKING_NEWS_MIN_SCORE: float = 6.5

$ grep -n "^THREADS_MIN_SCORE" scheduler/agents/content/threads.py
26:THREADS_MIN_SCORE: float = 6.5

$ grep -c "min_score" scheduler/agents/content/__init__.py
12

$ grep -n "age_hours < 48" scheduler/agents/content_agent.py
133:    if age_hours < 48:

$ grep -c "floored_by_min_score" scheduler/agents/content/__init__.py
5

$ grep -c "rare earth restrictions" scheduler/agents/content_agent.py
0

$ grep -c "rare earth restrictions" scheduler/tests/test_content_agent.py
0

$ grep -n "rare-earth" scheduler/agents/content_agent.py
78:    # quick-260424-j5i D8 removed the unhyphenated rare-earth keyword (pulled too
79:    # many off-theme rare-earth policy pieces that did not map to gold). 8 → 7.
455:                "oil supply shock, currency crisis, rare-earth restrictions).\n"
502:                "'China imposes new rare-earth export restrictions' (geopolitics/systemic shock).\n\n"

$ grep -n '"sub_threads"' scheduler/worker.py
98:    "sub_threads": 1011,
118:    ("sub_threads", threads.run_draft_cycle, "Threads", 1011, 17, 3),

$ git diff main -- scheduler/agents/content/quotes.py \
                   scheduler/agents/content/infographics.py \
                   scheduler/agents/content/gold_media.py \
                   scheduler/agents/content/gold_history.py \
                   scheduler/services/whatsapp.py \
                   scheduler/agents/senior_agent.py \
                   backend/ frontend/ alembic/ scheduler/models/ | wc -l
0
```

All 11 validation gates from `PLAN.md::<verification>` pass.

## Observations Worth Flagging to the Verifier

1. **`breaking_news` retention at 41% is below CONTEXT.md's 50-80% sanity band.** Not a blocker (documented + instrumented above), but the verifier should confirm the monitoring plan is acceptable and the 72h observability window is adequate before concluding the task is production-ready. If the operator prefers a pre-deploy floor drop (e.g., to 6.0) to stay inside the sanity band, that is a one-line constant edit + rebuild.

2. **T3 bundled 1 additional assertion-reconcile (`test_infographics.py::test_run_draft_cycle_writes_structured_notes`) that was not pre-identified in PLAN.md as a T3 target.** This was a D7 telemetry-broadening side-effect — infographics retains the same rich-telemetry payload and now includes the `floored_by_min_score: 0` key (infographics never opts into min_score so the counter stays 0). Kept in T3 (not T2) to preserve the atomic commit shape (T1=RED, T2=GREEN production only, T3=TEST-ADJUST); documented in the T3 commit message.

3. **Comment authorship hygiene:** The two new narrative comment lines at `content_agent.py:78-79` use the hyphenated form `rare-earth` (not the unhyphenated `rare earth restrictions`) specifically so the `grep -c "rare earth restrictions"` proof returns 0 on production. This is intentional; the grep is the D8 invariant check and the comment text must not reintroduce the exact-match string.

4. **Historical comment preserved:** `scheduler/worker.py:27` retains a vxg-era changelog reference to "Threads=4h" as historical context (correct for the period it describes). The 4 live narrative comments at L10, L109, L314, L328 were the ones updated to "3h". If the verifier prefers the L27 reference also updated, that's a trivial follow-up but would dilute the historical record.

5. **No changes to the 4 non-targeted sub-agents** (quotes, infographics, gold_media, gold_history), `services/whatsapp.py`, `senior_agent.py`, `backend/`, `frontend/`, `alembic/`, or `scheduler/models/` — verified by `git diff main` returning 0 bytes across all 10 paths. D3's recency-bucket change does benefit all sub-agents' sort order (strictly monotonic, no story gets LESS recency signal) but no code other than `content_agent.py::recency_score` was modified on their behalf.
