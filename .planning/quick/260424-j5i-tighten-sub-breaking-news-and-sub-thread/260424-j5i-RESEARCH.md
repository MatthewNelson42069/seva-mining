# Quick Task 260424-j5i: Tighten sub_breaking_news + sub_threads — Research

**Researched:** 2026-04-24
**Scope:** de-risk locked decisions D1-D9 only (no new decisions)
**Confidence:** HIGH (all findings grounded in file contents + live DB)

## Summary

1. **Every locked decision is GREEN or near-GREEN.** No hidden call-sites, no schema surprises, no infrastructure blockers. The `story["score"]` key is populated inside `fetch_stories()` at `content_agent.py:1103` — every candidate carries a composite score by the time it reaches `run_text_story_cycle`, so `min_score` can be checked cheaply against `story["score"]`.
2. **`recency_score` has exactly one production caller + one test reference**, both inside `content_agent.py`. The proposed `<48h=0.3` bucket is strictly monotonic and affects no test assertion directly (the only test reference uses `patch.object(..., return_value=0.9)`, not a behavioral assertion).
3. **Live DB distribution supports 6.5 as a "top-of-top" floor but it is on the stricter side of user expectations.** Over the last 7 days: breaking_news retains **41%** at >=6.5 (103/251 compliance-passed rows) and thread retains **50%** (26/52). User wording "top of top" lines up with this — but worth noting to the planner that 6.5 is stricter than the CONTEXT.md "50-80% retain" target for breaking_news. Recommend monitoring, not re-opening.
4. **D8 test impact is minor** — a single-line `assert "rare earth restrictions" in SERPAPI_KEYWORDS` style membership check, plus two total-count assertions (`== 18`) that must drop to `17`.
5. **D9 test impact is precise** — `test_worker.py::test_interval_agents_cadences` line 243-248 hard-codes `sub_threads: 4`; and the `CONTENT_INTERVAL_AGENTS` tuple at `worker.py:117` is the literal to flip. Narrative "4h" comments live at L10, L109, L313, L328.

**Primary recommendation:** the planner can write deterministic diffs for every file — no ambiguity remains.

---

## Q1 — `recency_score(` call-site survey

Run: `grep -rn "recency_score(" scheduler/` (done via Grep tool):

```
scheduler/agents/content_agent.py:111  def recency_score(published: datetime) -> float:  ← the definition
scheduler/agents/content_agent.py:1101       rec = recency_score(story["published"])   ← ONLY production caller
scheduler/tests/test_content_agent.py:174    patch.object(content_agent, "recency_score", return_value=0.9)  ← test mock
```

**Finding:** production usage is a single call inside `fetch_stories()`'s composite-score builder (`content_agent.py:1101`). It is NEVER called from sub-agents or other infrastructure. Adding a `<48h=0.3` bucket is safe — no caller reads the raw return value expecting a specific legacy bucket.

**Status:** GREEN.

---

## Q2 — `recency_score` test assertion impact

Grep `recency_score` across `scheduler/tests/` shows exactly one match:

```python
# scheduler/tests/test_content_agent.py:174
patch.object(content_agent, "recency_score", return_value=0.9),
```

This is a `unittest.mock.patch.object` replacement — the real `recency_score` isn't executed, so the new `<48h` bucket is completely invisible to this test. **No test file asserts `recency_score(now - Xh) == <value>` for any concrete hour.**

Notably, the CONTEXT.md example `tests/test_content_agent.py:L217 — recency_score(now - 25h) == 0.2` does NOT exist in the codebase. The planner does NOT need to update any existing assertion. The planner SHOULD ADD one new positive test (per CONTEXT.md specifics L141) asserting `recency_score(now - timedelta(hours=25)) == 0.3` to lock the new bucket in place.

**Status:** GREEN. No test breakage; only one new test to add.

---

## Q3 — `run_text_story_cycle` signature + `min_score` insertion point

**Current signature** (`scheduler/agents/content/__init__.py:84-93`):

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

Extend with `min_score: float | None = None` — default None preserves byte-for-byte behavior for every caller that doesn't opt in (same pattern used by `max_count` and `source_whitelist`).

**Exact insertion point for the floor check** — after compliance, before `items_queued += 1` (per CONTEXT.md D6). The critical region is `content/__init__.py:306-328`. 10-line context:

```python
# scheduler/agents/content/__init__.py L306-328
review_result = await content_agent.review(draft_content)
compliance_ok = bool(review_result.get("compliance_passed", False))
if not compliance_ok:
    compliance_blocked_count += 1

bundle = ContentBundle(
    story_headline=story["title"],
    story_url=story["link"],
    source_name=story.get("source_name"),
    content_type=content_type,
    score=story.get("score", 0.0),
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
    items_queued += 1             # ← NEW CHECK belongs immediately BEFORE this
```

**Minimal patch** — inside the `if compliance_ok:` block, BEFORE `items_queued += 1`:

```python
if compliance_ok:
    # NEW (j5i): min_score floor — evaluated AFTER Haiku+compliance, BEFORE persist.
    # Bundle is already written with compliance_passed=True for observability;
    # only the draft_item (what actually gets queued to the dashboard) is skipped.
    if min_score is not None and float(story.get("score", 0.0)) < min_score:
        floored_by_min_score += 1
        logger.info(
            "%s: floored (score %.2f < min_score %.2f): %r",
            agent_name, float(story.get("score", 0.0)), min_score,
            story["title"][:60],
        )
        continue
    item = content_agent.build_draft_item(bundle, rationale)
    ...
```

**Design note for planner:** the counter `floored_by_min_score` must be initialized alongside `drafted_count = 0` and `compliance_blocked_count = 0` at L244-245.

**Caveat — bundle gets persisted even when floored.** With the patch above, `ContentBundle` rows for floored items are still written (just without a `DraftItem`). That matches infographics' existing pattern (compliance-failed items are persisted for forensics). If the user instead wants floored items NOT persisted at all, the check must move UP to before the `ContentBundle(...)` construction at L311. CONTEXT.md D6 doesn't explicitly rule on this — flag for plan-checker.

**Status:** GREEN on mechanics; YELLOW on the "persist floored bundles?" sub-question.

---

## Q4 — `story["score"]` availability

**Confirmed:** `story["score"]` is always populated before `run_text_story_cycle` iterates candidates. Evidence at `scheduler/agents/content_agent.py:1092-1103`:

```python
# Score and classify each unique story (relevance + recency + credibility).
rel_weight, rec_weight, cred_weight = 0.4, 0.3, 0.3
scored: list[dict] = []
for story in unique_stories:
    relevance = await _score_relevance(...)
    rec = recency_score(story["published"])
    cred = credibility_score(story.get("source_name", ""))
    story["score"] = (relevance * rel_weight + rec * rec_weight + cred * cred_weight) * 10
    scored.append(story)
```

Every story returned from `fetch_stories()` has the `"score"` key set to a float in the 0-10 range. The existing persistence code at `content/__init__.py:294` and L316 already reads `story.get("score", 0.0)` defensively — the same idiom works for the `min_score` check.

**Status:** GREEN.

---

## Q5 — DB score distribution (6.5 floor calibration)

**DB IS reachable locally** via the `DATABASE_URL` in `.env`. Queried against live Neon Postgres on 2026-04-24.

### All content_bundles, last 7 days (includes compliance-failed rows)

| content_type | total | >=6.5 | >=7.0 | avg | median | min | max |
|--------------|------:|------:|------:|----:|-------:|----:|----:|
| breaking_news | 296 | 122 | 88 | 6.42 | 6.40 | 3.20 | 10.08 |
| thread        |  57 |  30 | 28 | 6.91 | 6.80 | 3.20 |  9.00 |

### compliance_passed=TRUE only (what `min_score` would actually filter)

| content_type | approved | >=6.0 | >=6.5 | >=7.0 | avg | min | max |
|--------------|---------:|------:|------:|------:|----:|----:|----:|
| breaking_news | 251 | 155 (62%) | 103 (**41%**) | 75 (30%) | 6.42 | 3.20 | 10.08 |
| thread        |  52 |  35 (67%) |  26 (**50%**) | 24 (46%) | 6.87 | 3.20 |  9.00 |

### Interpretation

- **breaking_news retains 41% at >=6.5** — below CONTEXT.md's "50-80% retain" sanity band. Interpretation: 6.5 is a genuine "top-of-top" cut that rejects the majority of currently-approved items. That matches the user's "top of top" language but is operationally stricter than the CONTEXT.md hint. Per run (2h cadence, ~12 runs/day), breaking_news currently persists ~36 approvals/day; with 6.5 applied, expect ~15/day max (before also applying `max_count=3`).
- **thread retains 50% at >=6.5** — at the low edge of the CONTEXT.md band. Fine.
- **Both content types have a wide spread (3.2 to 10.08)** — the floor is well-defined; there's no clumping at the boundary that would make 6.5 a knife-edge.
- **7.0 would be too strict for breaking_news** (30% retain). 6.5 is the right choice.

**Status:** GREEN (6.5 is operationally defensible). Minor YELLOW flag for plan-checker: the breaking_news retention is 41%, not the 50-80% target — planner/executor should surface this in the PR description so the user can tune post-launch via the new module-level constants. Per CONTEXT.md D2, the constants are exposed precisely so this is a one-line tuning if needed.

---

## Q6 — "rare earth restrictions" assertion shape

**Exact test at `scheduler/tests/test_content_agent.py:62-75`:**

```python
def test_serpapi_keywords_critical_minerals_coverage():
    """New keywords for critical-minerals + sovereign-gold coverage (htu)."""
    required = [
        "critical minerals",
        "rare earth restrictions",   # ← L66: THIS line must be removed
        "strategic metals",
        "sovereign wealth fund gold",
        "treasury gold sale",
        "gold mining M&A",
        "US China metals",
        "mineral supply chain",
    ]
    for kw in required:
        assert kw in content_agent.SERPAPI_KEYWORDS, f"missing keyword: {kw}"
```

**Executor action:** delete line 66 (the `"rare earth restrictions",` entry inside the `required` list). The `for kw in required: assert kw in ...` loop shape is preserved.

**Also:** two count assertions must drop from `18` → `17`:
- `scheduler/tests/test_content_agent.py:58` — `assert len(content_agent.SERPAPI_KEYWORDS) == 18`
- `scheduler/tests/test_content_agent.py:98-99` — `assert len(...) == 18` and `assert len(set(...)) == 18`

**Grep proof that `"rare earth restrictions"` ONLY appears where CONTEXT.md claims:**

```
scheduler/agents/content_agent.py:79    "rare earth restrictions",       ← DELETE per D8
scheduler/tests/test_content_agent.py:66    "rare earth restrictions",   ← DELETE per D8
```

**Haiku gate narrative (preserve per D4)** — grep "rare earth" broader:
```
scheduler/agents/content_agent.py:449  "oil supply shock, currency crisis, rare-earth restrictions).\n"
scheduler/agents/content_agent.py:496  "'China imposes new rare-earth export restrictions' (geopolitics/systemic shock).\n\n"
```

Note: the Haiku prompt uses the **hyphenated** form `rare-earth`. The SERPAPI keyword uses the **unhyphenated** form `rare earth`. This ensures a `grep -n "rare earth restrictions"` (no hyphen) after j5i lands returns ZERO matches (the CONTEXT.md proof), while `grep -n "rare-earth"` (with hyphen) still shows the 2 prompt lines — which is exactly what D4 preserves.

**Status:** GREEN.

---

## Q7 — `test_worker.py` sub_threads interval assertion

**Exact assertion at `scheduler/tests/test_worker.py:242-248`:**

```python
def test_interval_agents_cadences():
    """Post-k8n interval cadences: BN=2h, Threads=4h (sub_long_form removed per quick-260423-k8n)."""
    cadences = {t[0]: t[5] for t in CONTENT_INTERVAL_AGENTS}
    assert cadences == {
        "sub_breaking_news": 2,
        "sub_threads": 4,                  # ← must become 3 per D9
    }
```

**Executor action:** change `"sub_threads": 4` to `"sub_threads": 3`. Docstring on L243 says "Threads=4h" — also update to "Threads=3h" for honesty (narrative-only).

**No other test asserts the `sub_threads` interval value.** The only `4` appearance for `sub_threads` outside this line is `worker.py:117` (the tuple literal — the production diff D9 targets).

**Status:** GREEN.

---

## Q8 — test_breaking_news.py / test_threads.py / test_content_wrapper.py state

| File | Exists? | Relevant assertions for j5i |
|------|---------|------------------------------|
| `scheduler/tests/test_breaking_news.py` | YES (92 lines) | Covers `_draft` JSON parse + `run_draft_cycle` smoke. NO assertion of `max_count`/`sort_by`/`min_score`/constants. Planner should ADD: `assert breaking_news.BREAKING_NEWS_MIN_SCORE == 6.5`; assert `run_text_story_cycle` is called with `max_count=3, sort_by="score", min_score=6.5`. |
| `scheduler/tests/test_threads.py` | YES (89 lines) | Same shape as test_breaking_news.py. NO assertion of `max_count`/`sort_by`/`min_score`. Planner should ADD: `assert threads.THREADS_MIN_SCORE == 6.5`; assert `run_text_story_cycle` is called with `max_count=2, sort_by="score", min_score=6.5`. |
| `scheduler/tests/test_content_wrapper.py` | YES (focused on i8b firehose only) | NO tests of `sort_by`/`min_score`/`max_count`/`floored_by_min_score`. Planner MUST ADD: `min_score` filters stories below threshold; `floored_by_min_score` counter populated; empty run (all stories floored) → `status="completed"`, `items_queued=0`. |

**Reference pattern for new tests** — `scheduler/tests/test_infographics.py:120-145` already asserts `sort_by='score'` on a `run_text_story_cycle` call-site via `call_kwargs`. Planner should mirror that idiom.

**Status:** GREEN. All three files exist; j5i additions are pure extensions, not rewrites.

---

## Q9 — Telemetry JSON shape in content/__init__.py

**Current JSON-merge logic lives at `content/__init__.py:368-416`** (not L373 as the ask stated — the merge is specifically the WhatsApp hook at L412-415).

**Two separate JSON writes exist:**

1. **Primary write (L368-382)** — happens unconditionally at the end of the `try:` block:

```python
agent_run.items_queued = items_queued
# D-04: richer telemetry for infographics (consumed by no4 UI subtitle);
# D-05: other callers retain their existing minimal payload.
if content_type == "infographic":
    agent_run.notes = json.dumps({
        "candidates": len(candidates),
        "top_by_score": max_count if max_count is not None else 0,
        "drafted": drafted_count,
        "compliance_blocked": compliance_blocked_count,
        "queued": items_queued,
    })
else:
    agent_run.notes = json.dumps({"candidates": len(candidates)})
```

**Finding:** CONTEXT.md D7 lists `"candidates, drafted, compliance_blocked, queued, top_by_score"` as existing keys — that's true ONLY for `content_type == "infographic"`. For breaking_news + threads (the j5i targets), the current else-branch writes ONLY `{"candidates": N}`. Adding `"floored_by_min_score"` to the breaking_news/threads branch requires either:

- **Option A:** broaden the `if` branch to include breaking_news + threads in the rich-telemetry block; OR
- **Option B:** keep the minimal else-branch but add the new key: `json.dumps({"candidates": len(candidates), "floored_by_min_score": floored_by_min_score})`.

Per CONTEXT.md D7 ("existing keys stay: candidates, drafted, compliance_blocked, queued, top_by_score"), the user intent is Option A — breaking_news + threads should share the richer shape. Planner should confirm with the plan-checker.

2. **Firehose merge (L412-415)** — the JSON-merge hook i8b added:

```python
# MERGE into existing JSON notes — never string-concatenate.
existing_notes = json.loads(agent_run.notes) if agent_run.notes else {}
existing_notes[whatsapp_status_key] = whatsapp_status_val
agent_run.notes = json.dumps(existing_notes)
```

**Finding:** the merge pattern `json.loads(...); dict[key] = val; json.dumps(...)` is already proven safe for adding keys. The new `floored_by_min_score` key is written via the primary write (point 1 above), not via this merge hook. Existing consumers (frontend dashboard, senior_agent digest assembly) read `notes` as a JSON string — adding one integer key is additive and backward-compatible.

**Status:** GREEN on mechanics, YELLOW on the which-branch question (Option A vs B). Planner should confirm.

---

## Derisked Decisions (GREEN/YELLOW/RED per locked item)

| Decision | Status | Why |
|----------|--------|-----|
| **D1** — `max_count=3` breaking_news, `sort_by="score"` both | GREEN | Identical call-shape to `infographics.py:359-364`; the `sort_by="score"` branch in `content/__init__.py:200-208` is battle-tested. |
| **D2** — `min_score=6.5` floor on breaking_news + threads | YELLOW | Mechanics GREEN (Q3, Q4). Calibration: 41% retention for breaking_news is below CONTEXT.md's 50-80% band (Q5). Not a blocker — the constants are per-agent tunable. Surface in PR description. |
| **D3** — Recency curve `<48h=0.3` bucket | GREEN | Single production caller, zero behavioral test assertions (Q1, Q2). |
| **D4** — Haiku gate prompt unchanged | GREEN | Hyphenated `rare-earth` form at L449/L496 survives the D8 keyword delete (different strings; Q6). |
| **D5** — Draft prompts unchanged | GREEN | No j5i change required inside `breaking_news.py::_draft` or `threads.py::_draft`. |
| **D6** — `min_score` check AFTER compliance | GREEN | Insertion point at `content/__init__.py:325-328` is clean (Q3). Flag for plan-checker: "persist floored ContentBundle, skip DraftItem" is the default of the suggested patch — verify this matches intent. |
| **D7** — Telemetry add `floored_by_min_score` | YELLOW | JSON-merge machinery is proven (Q9). Open question: should breaking_news + threads share infographics' rich-telemetry branch, or keep minimal + add one key? Planner to decide. |
| **D8** — Remove `"rare earth restrictions"` keyword | GREEN | Exactly 2 matches in production+tests; `== 18` count assertions become `== 17` at 2 test lines; Haiku prompt preserved via the `rare-earth` hyphenated variant (Q6). |
| **D9** — `sub_threads` 4h → 3h | GREEN | One tuple literal at `worker.py:117`; one assertion dict at `test_worker.py:247`; narrative comments at `worker.py` L10, L109, L313, L328 (Q7). |

---

## Open Questions for Plan-Checker

1. **(D6) Persist-vs-skip floored ContentBundle rows.** The natural patch location (inside `if compliance_ok:` at L325) means floored items DO get a ContentBundle row persisted (compliance_passed=True, score below floor, no DraftItem). This mirrors how compliance-blocked items are handled today. Alternative: move the check earlier to skip bundle persistence entirely. CONTEXT.md D6 implies "AFTER compliance" without ruling on this. Recommend the planner confirm with user: "keep ContentBundle rows for floored items for forensics? (default=YES)".

2. **(D7) Rich-telemetry branch scope.** Currently only `content_type == "infographic"` gets the full `{candidates, top_by_score, drafted, compliance_blocked, queued}` payload. breaking_news + threads get `{candidates}` only. D7 lists `drafted, compliance_blocked, queued, top_by_score` as "existing keys stay" for breaking_news/threads — implying the planner must broaden the rich-telemetry branch to include these content types, THEN add `floored_by_min_score`. Confirm the scope of the if/else restructure so reviewers aren't surprised.

3. **(D2 observability) Retention tracking post-launch.** With 6.5 producing 41% breaking_news retention (Q5), launch-day monitoring should watch (a) the new `floored_by_min_score` counter in `agent_run.notes` — if >70% of compliance-passed stories are floored on any given run, that signals the floor is too aggressive; and (b) the total WhatsApp firehose volume to confirm the "quiet runs = silent" UX is working as expected. Not in scope for j5i itself, but worth flagging in the PR body.

4. **(Cross-task interaction) htu + j5i on SERPAPI_KEYWORDS.** htu (260424-htu) added 8 keywords; D8 removes 1 of them (`rare earth restrictions`). After j5i the test comment "`Original 10 keywords must remain after expansion (htu)`" at L79 still holds; the count drops `18 → 17` cleanly. No interaction with `test_serpapi_keywords_existing_preserved` (L78-93) since that test asserts the ORIGINAL 10 — unchanged.

5. **(Grep proofs) CONTEXT.md validation gate precision.** The grep `grep -cn "^    \"" scheduler/agents/content_agent.py | head` counts four-space-indented quoted strings at start-of-line; SERPAPI_KEYWORDS is a good match for that pattern but other list literals in the file might share it. Executor should cross-check with an explicit `grep -A 1 "SERPAPI_KEYWORDS" ...` or count within the specific slice L68-L86. Not a blocker — just a heads-up that the raw count could be off if any adjacent list is also four-space indented.

---

## Sources

All findings are grounded in direct reads of:
- `scheduler/agents/content_agent.py` (L70-130, L443-500, L1030-1119)
- `scheduler/agents/content/__init__.py` (full file, 425 lines)
- `scheduler/agents/content/breaking_news.py` (full file)
- `scheduler/agents/content/threads.py` (full file)
- `scheduler/agents/content/infographics.py` (L350-380)
- `scheduler/worker.py` (full file, 530 lines)
- `scheduler/tests/test_content_agent.py` (L1-350)
- `scheduler/tests/test_worker.py` (full file, 515 lines)
- `scheduler/tests/test_breaking_news.py` (full file)
- `scheduler/tests/test_threads.py` (full file)
- `scheduler/tests/test_content_wrapper.py` (L1-100, plus scoped grep)
- Live Neon Postgres query against `content_bundles` (7-day window, 2026-04-24)

No external/web sources needed — every question was answerable from the repo + live DB.
