# Quick Task 260422-of3 — SUMMARY

**Task:** Redesign `sub_infographics` to always produce the 2 best infographics per day by quality/score, and allow it to reuse stories already drafted by `breaking_news`.

**User ask (verbatim):**

> "I want it to claim the same stories the breaking news agent does, so it can have the best infographics of recent news. If breaking news has a really good piece of news in the morning that the infographic agent can create something about, it should still use it. Infographic agent should be creating the 2 best infographics it possibly can everyday"

**Commit:** `23ce6fb` — `feat(scheduler): sub_infographics picks 2 best by score, reuses breaking_news stories (of3)`

**Date:** 2026-04-23

---

## What Changed

### Shared pipeline (`scheduler/agents/content/__init__.py`)

1. **Two orthogonal kwargs** on `run_text_story_cycle` with backward-compatible defaults:
   ```python
   sort_by: Literal["published_at", "score"] = "published_at",
   dedup_scope: Literal["cross_agent", "same_type"] = "cross_agent",
   ```
   - `sort_by="score"` → composite `(score desc, published_at desc)` sort when `max_count` trims candidates (D-01).
   - `dedup_scope="same_type"` → passes `content_type` into `_is_already_covered_today` so dedup only blocks stories already drafted as the same type (D-02).
   - Defaults preserve byte-for-byte existing behavior for breaking_news / threads / long_form / quotes (D-03).

2. **`_is_already_covered_today`** gained optional keyword-only `content_type: str | None = None`. When set, the SELECT is scoped to `ContentBundle.content_type == :content_type`. When None (existing callers), cross-type dedup preserved.

3. **Counters** added inside the draft loop:
   - `drafted_count` — stories where `draft_fn` returned non-None.
   - `compliance_blocked_count` — drafts that failed `content_agent.review()`.

4. **Structured notes telemetry** for infographics (mirrors gmb schema family, consumed by no4 `parseRunNotes`):
   ```json
   {"candidates": N, "top_by_score": 2, "drafted": M, "compliance_blocked": K, "queued": Q}
   ```
   Gated on `content_type == "infographic"` — other sub-agents retain their existing `{"candidates": N}` payload (D-05 surgical scope).

5. **Empty-candidates early-return** also writes zero-filled notes for infographics so no4's subtitle has something to render on 0-content days (D-06 — no historical fallback, just honest zeros).

### Infographics sub-agent (`scheduler/agents/content/infographics.py`)

`run_draft_cycle()` now passes:
```python
max_count=2,                 # D-04: produce 2 best per day
sort_by="score",             # D-01: best by score, not recency
dedup_scope="same_type",     # D-02: may reuse breaking_news stories
```

Function docstring updated to reference the decision IDs.

### Tests

**`scheduler/tests/test_content_init.py` (+5 tests)**
- `test_sort_by_score_picks_top_by_score` — [3, 9, 5, 9, 7] scored stories → top 2 by score=9 win.
- `test_sort_by_score_breaks_ties_by_recency` — tied scores → fresher `published_at` wins (D-01).
- `test_sort_by_default_is_published_at` — omitting `sort_by` yields identical output to explicit `"published_at"`.
- `test_dedup_scope_same_type_passes_content_type` — patch-and-record proves `_is_already_covered_today` gets `content_type="quote"` when `dedup_scope="same_type"` and `content_type=None` when `"cross_agent"`.
- `test_is_already_covered_today_scopes_by_content_type` — compiles the SELECT and inspects the WHERE clause; proves the content_type predicate is present iff the arg is not None.

**`scheduler/tests/test_infographics.py` (+3 tests)**
- `test_run_draft_cycle_passes_new_kwargs` — patches `run_text_story_cycle`, asserts `max_count=2, sort_by="score", dedup_scope="same_type"`.
- `test_run_draft_cycle_writes_structured_notes` — end-to-end run with 3 stories → notes JSON has `{candidates: 2, top_by_score: 2, drafted: 2, compliance_blocked: 1, queued: 1}`.
- `test_run_draft_cycle_writes_notes_on_empty_candidates` — empty stories → zero-filled notes payload.

---

## Files Modified

| File | Change | Lines |
|------|--------|-------|
| `scheduler/agents/content/__init__.py` | +cap-sort branch, +dedup kwarg passthrough, +counters, +content_type-gated notes | +72 / -10 |
| `scheduler/agents/content/infographics.py` | +3 kwargs on `run_text_story_cycle` call, docstring update | +13 / -1 |
| `scheduler/tests/test_content_init.py` | +5 tests, helper extended with `sort_by` / `dedup_scope` kwargs, doc updated | +209 / -11 |
| `scheduler/tests/test_infographics.py` | +3 tests | +147 / 0 |

**Test delta:** 109 → 117 (+8, exceeding plan's 3-6 target by a small margin due to splitting the SELECT-scoping test from the propagation test for clearer failure messages).

---

## Decisions Honored

| ID | Decision | Implementation |
|----|----------|----------------|
| **D-01** | Sort: composite `(score, published_at)` desc | `candidates.sort(key=lambda s: (float(s.get("score", 0.0)), s.get("published_at", "")), reverse=True)` — tuple sort with `reverse=True` handles both dimensions correctly (score primary, recency tiebreaker). Covered by `test_sort_by_score_breaks_ties_by_recency`. |
| **D-02** | Dedup: narrow to same content_type | Optional `content_type` kwarg on `_is_already_covered_today` scopes the SELECT; `run_text_story_cycle` passes `content_type=(content_type if dedup_scope == "same_type" else None)` at the call site. Covered by `test_is_already_covered_today_scopes_by_content_type` + `test_dedup_scope_same_type_passes_content_type`. |
| **D-03** | API shape: two orthogonal kwargs | `sort_by` and `dedup_scope` as independent `Literal`-typed kwargs with backward-compat defaults. Other 4 sub-agents don't pass either → byte-for-byte identical runtime (confirmed by grep + `test_sort_by_default_is_published_at`). |
| **D-04** | Telemetry: gmb-style structured JSON | `{candidates, top_by_score, drafted, compliance_blocked, queued}` on infographics `AgentRun.notes`. Covered by `test_run_draft_cycle_writes_structured_notes` and `test_run_draft_cycle_writes_notes_on_empty_candidates`. |
| **D-05** | Scope: infographics-only | Notes branch gated on `content_type == "infographic"`; kwargs only passed by `infographics.py`. Quotes / threads / long_form / breaking_news unchanged at the call site and receive the minimal `{"candidates": N}` notes payload. |
| **D-06** | No historical fallback | Empty-candidates branch writes zero-filled notes for infographics and returns `status="completed"` — honest 0-infographic day surfaced via no4 UI. |

---

## Preservation Checks

- **zid** (predicted_format gate removal): `grep -n predicted_format scheduler/agents/content/__init__.py` returns only the 2 comment lines documenting the removal. `candidates = list(stories)` untouched. ✓
- **lbb** (gold_history curated whitelist isolation): no changes to `gold_history.py`, `gold_history_stories/`, or `source_whitelist` logic. ✓
- **gmb/no4** (notes telemetry schema family): field names (`candidates`, `top_by_score`, `drafted`, `compliance_blocked`, `queued`) follow the gmb pattern; no4's `parseRunNotes` accepts any integer-valued fields and silently no-ops on absent ones. Frontend change unnecessary. ✓
- **4 other text-story sub-agents**: `grep -A 4 'run_text_story_cycle(' scheduler/agents/content/{breaking_news,threads,long_form,quotes}.py` confirms none pass `sort_by` or `dedup_scope`. Default kwargs = existing behavior. ✓

---

## Validation Gates (all green)

| Gate | Result |
|------|--------|
| `uv run ruff check .` | Clean (0 errors) |
| `uv run pytest -x` | 117/117 passed in 0.83s |
| `grep 'sort_by="score"' scheduler/agents/content/` | Only in `infographics.py` (usage + docstring) |
| `grep 'dedup_scope="same_type"' scheduler/agents/content/` | Only in `infographics.py` (usage + docstring) |
| `grep 'predicted_format' scheduler/agents/content/__init__.py` | Only in 2 comment lines (zid preservation) |
| Other 4 sub-agents unchanged | Confirmed via `grep -A 4 'run_text_story_cycle('` |

---

## Next Observable Step

Tomorrow's **12:00 PT `sub_infographics` cron tick** is the empirical test:

- `agent_runs` row for `sub_infographics` should have `items_queued <= 2` and `notes` containing JSON with all 5 counter fields.
- Per-agent queue UI (no4 `parseRunNotes`) will render an inline subtitle under the RunHeader like `"2 candidates · 2 drafted · 1 blocked · 1 queued"`.
- If `sub_breaking_news` drafted a strong gold story at 08:00 PT, that same story can now be drafted as an infographic at 12:00 PT — the expected behavior per the user's ask.
- If no gold-sector stories pass the gate that day (0 candidates), the UI will show "No content found" (no4 surface) with the zero-filled telemetry subtitle.

No Railway migration needed (no schema changes). Scheduler redeploys on next push.

---

## Handoff Notes

- **Five of five zid follow-ups now closed:** (a) sub_gold_media 0-items via gmb, (b) gold_media/video_clip label rename via mfg, (c) infographics 0-items likely-cause via of3, (d) zero-item run visibility via no4, (e) gold_history hallucination hardening via lbb. Original zid issue resolved.
- **Telemetry retrofit candidates** for future: breaking_news, threads, long_form, quotes, gold_history, gmb's gold_media (already instrumented). One agent-at-a-time retrofit pattern, same no4 subtitle lights up automatically.
- **Quotes behavior review** flagged in CONTEXT.md D-05: if tomorrow's cron shows quotes also missing morning top stories, apply the same pattern (`max_count=N, sort_by="score", dedup_scope="same_type"`). Currently intentionally unchanged.
