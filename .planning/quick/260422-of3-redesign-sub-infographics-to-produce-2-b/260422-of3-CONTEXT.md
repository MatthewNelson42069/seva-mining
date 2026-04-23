# Quick Task 260422-of3: Redesign sub_infographics for "2 best per day, may reuse breaking_news stories" - Context

**Gathered:** 2026-04-23
**Status:** Ready for planning
**Discuss mode:** Orchestrator pre-surfaced 6 gray areas with recommendations; user responded "All clear — push it" — decisions below are locked.

<domain>
## Task Boundary

Redesign the daily `sub_infographics` cron so it produces the **2 best infographics per day by quality/score** — not volume-dependent — and allow it to **claim stories already drafted by `breaking_news`**. Triggered by the user's ask:

> "I want it to claim the same stories the breaking news agent does, so it can have the best infographics of recent news. If breaking news has a really good piece of news in the morning that the infographic agent can create something about, it should still use it. Infographic agent should be creating the 2 best infographics it possibly can everyday"

The problem today: `breaking_news` runs every 2h and by the time `sub_infographics` fires at 12:00 PT, `_is_already_covered_today` has already blocked infographics from re-drafting any of the morning's strongest gold stories. Also, when `max_count` is set, `run_text_story_cycle` sorts by `published_at` desc — "best" stories aren't picked by score. Both need to change for infographics specifically.

**In scope:**
- `scheduler/agents/content/infographics.py` — pass `max_count=2`, `sort_by="score"`, `dedup_scope="same_type"`; populate structured `notes` telemetry on the `AgentRun` row.
- `scheduler/agents/content/__init__.py::run_text_story_cycle` — add two orthogonal kwargs: `sort_by: Literal["published_at", "score"] = "published_at"` and `dedup_scope: Literal["cross_agent", "same_type"] = "cross_agent"`. Default values preserve existing behavior for all 4 other callers. Wire `sort_by` into the cap-sort at L143-149; wire `dedup_scope` into the `_is_already_covered_today` call at L165-172 (or into the helper itself).
- `scheduler/agents/content/__init__.py::_is_already_covered_today` — accept an optional `content_type` argument; when set, scope the existing-bundle SELECT to `content_type = :content_type`.
- Test coverage for all new paths in the matching `scheduler/tests/` modules.

**Out of scope:**
- Frontend (no4 already consumes notes telemetry — infographics rows will light up automatically with the new counters).
- Quotes, breaking_news, threads, long_form, gold_media, gold_history behavior (this change is infographics-only; the default kwargs keep existing behavior byte-for-byte).
- Schema/migration changes (uses existing `AgentRun.notes` + existing `ContentBundle.content_type` column).
- No new dependencies.
- Historical-infographic fallback (curated whitelist like gold_history) — user's "recent news" emphasis rules this out; 0-infographic days are acceptable and visible in no4 UX.

</domain>

<decisions>
## Implementation Decisions

### D-01 — Sort mechanism for "best 2"
**Decision:** Composite `(score desc, published_at desc)` (Recommended: B)

Rationale: Ties in `story["score"]` are not hypothetical — `fetch_stories()` blends SerpAPI + RSS and two stories covering the same event frequently land with identical gold-gate scores. Recency-as-tiebreaker picks the fresher of the two so the morning's latest update wins over yesterday's leftover. Pure score sort would stable-sort by fetch order, which is an artifact of the feed merge and not semantically meaningful.

Implementation shape: when `sort_by="score"`, sort by `(-float(s.get("score", 0.0)), s.get("published_at", ""))` reversed-as-needed — or equivalently sort twice (stable) with published_at as secondary key. Keep it simple; a tuple key is fine.

### D-02 — Dedup scope for infographics
**Decision:** Narrow to same content_type only, via a new `dedup_scope` kwarg (Recommended: B via C)

Rationale: The user's ask is "claim the same stories breaking_news does," so we must bypass the cross-agent block. But we still want to prevent double-drafting within infographics itself (e.g., manual trigger + scheduled run on the same day). Scoping dedup to `content_type="infographic"` is the minimum change that satisfies both constraints.

Implementation shape: extend `_is_already_covered_today(session, link, title)` to accept an optional `content_type: str | None = None` parameter. When provided, add `AND content_type = :content_type` to the existing SELECT. Call site passes `content_type=content_type` iff `dedup_scope == "same_type"`; otherwise passes `None` and behavior is unchanged. All 4 other callers keep default `dedup_scope="cross_agent"` → `content_type=None` → identical SQL as today.

### D-03 — API shape of the new kwargs in `run_text_story_cycle`
**Decision:** Two new orthogonal kwargs with backward-compatible defaults (Recommended: A)

Rationale: Sort and dedup are independent concerns. Bundling them behind a single `top_mode` flag would couple them for future agents (e.g., a hypothetical agent wanting same_type dedup but keeping recency sort). Orthogonal kwargs keep the surface honest.

Final signature:
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
) -> None:
```

### D-04 — Telemetry
**Decision:** Add structured `notes` JSON on the infographics `AgentRun` row (Recommended: B)

Rationale: no4 just shipped the frontend that renders `notes` as an inline subtitle on per-agent queue rows. Giving infographics its own counters makes tomorrow's 12:00 PT cron verification richer — the user can see candidates/accepted/queued at a glance, same as gold_media. Cost is ~5 lines of code; benefit is parity with the UX.

Schema (mirror gmb pattern, adapt field names to this pipeline's stages):
```json
{"candidates": N, "top_by_score": 2, "drafted": M, "compliance_blocked": K, "queued": Q}
```

Where:
- `candidates` — count after gold-gate + whitelist + max_count cap (i.e., what actually enters the draft loop)
- `top_by_score` — the `max_count` value (always 2 for infographics; informational)
- `drafted` — number of stories where `draft_fn` returned non-None
- `compliance_blocked` — number where drafted content failed `content_agent.review()`
- `queued` — final `items_queued` count (drafted - compliance_blocked, equals `agent_run.items_queued`)

Set `agent_run.notes = json.dumps(telemetry)` before commit. Apply only to infographics in this task — other agents retain null notes until separately retrofitted. Frontend tolerates null gracefully (no4 `parseRunNotes`).

### D-05 — Scope: apply this pattern to `quotes` too?
**Decision:** Infographics only (Recommended: A)

Rationale: User specifically named infographics. Quotes has a different UX profile (short standalone gems, lower per-item cost, benefit from volume) and may want the opposite of this treatment. Revisit separately if tomorrow's cron shows quotes has the same "missing the best morning stories" symptom. Keeping this change surgical avoids accidentally homogenizing agent behavior.

### D-06 — Historical fallback when 0 recent stories pass gates
**Decision:** No fallback; honest 0-infographic days (Recommended: A)

Rationale: User's phrasing — "the 2 best infographics of **recent news**" — rules out filler from historical whitelists. If no gold-sector story passes the gate on a given day, the honest answer is zero infographics, surfaced via no4's "No content found" UI. Keeps the content-type semantics clean: `infographics` = real-time gold news visualized; `gold_history` = curated historical stories (already has its whitelist).

### Claude's Discretion
- **Exact telemetry counter names** — decision D-04 proposes `candidates` / `top_by_score` / `drafted` / `compliance_blocked` / `queued`. Implementer may rename to match gmb's gold_media convention (`x_candidates` / `llm_accepted` / `compliance_blocked` / `queued`) if that aligns better with no4's subtitle formatting, OR keep pipeline-specific names if they're clearer. Either is acceptable as long as the field set covers the 4 stages: fetch → cap → draft → review.
- **Whether to add `sort_by` / `dedup_scope` Literals to a shared typing module** or inline as `Literal["..."]` annotations at the function signature. Inline is fine for 2 enums; don't over-engineer.
- **Tuple sort vs. two-pass stable sort** for D-01 composite key. Tuple key with correct sign is cleaner; two-pass is more explicit. Either works.
- **Whether to guard infographics telemetry behind `try/except`** when writing `notes`. If `json.dumps` is called on primitive counters it's effectively infallible, but a bare `try/except Exception` around the counter-increment block costs nothing and prevents a metrics bug from failing the run. Implementer picks.
- **Test file placement** — `scheduler/tests/test_content_infographics.py` probably already exists per the 109-test baseline; new tests go there plus `scheduler/tests/test_run_text_story_cycle.py` (or equivalent shared-pipeline test file) for the sort_by / dedup_scope branches.

</decisions>

<specifics>
## Specific Ideas

**Current state (verified, `scheduler/agents/content/__init__.py`):**
- L63-90: `run_text_story_cycle` signature, kwargs `max_count` and `source_whitelist` already exist with `None` defaults.
- L117-124: all gold-gate-passing stories are candidates for every content type (predicted_format gate removed by zid). **No routing barrier to stories being drafted as infographics.**
- L141-149: cap-sort by `published_at` desc when `max_count` is set. **Change target.**
- L165-172: `_is_already_covered_today(session, link, title)` → cross-agent block. **Change target.**
- `story["score"]` is populated by `content_agent.fetch_stories()` and already persisted on `ContentBundle.score` (L204, L223) — available as a sort key with no additional fetching.

**Current state (verified, `scheduler/agents/content/infographics.py`):**
- L137-143: `run_draft_cycle()` passes only `agent_name`, `content_type="infographic"`, `draft_fn=_draft`. Add `max_count=2`, `sort_by="score"`, `dedup_scope="same_type"`.
- No local telemetry state today. Add counters during the draft loop; write `notes` at run end.

**Existing patterns to match:**
- **gmb (gold_media) notes schema** as the structural reference. `scheduler/agents/content/gold_media.py` writes `agent_run.notes = json.dumps({...})` before status="completed" — follow the same placement.
- **Test harness** — `scheduler/tests/` uses `pytest-asyncio`. Mock `AsyncSessionLocal`, `content_agent.fetch_stories`, `content_agent.is_gold_relevant_or_systemic_shock`, `content_agent.fetch_article`, `content_agent.search_corroborating`, `content_agent.review` the same way existing `run_text_story_cycle` tests do.
- **Worker tuple shape** — `sub_infographics` already in `CONTENT_CRON_AGENTS` at `scheduler/worker.py` L100-104 with daily 12:00 PT cron. No worker change needed.

**Validation gates (planner will formalize):**
- `uv run ruff check scheduler/` clean
- `uv run pytest -x` passes (baseline 109/109; expect +3-6 tests from this task)
- Grep: `sort_by="score"` only in `infographics.py` + the new plumbing in `__init__.py`
- Grep: `dedup_scope="same_type"` only in `infographics.py` + the new plumbing in `__init__.py`
- Grep: `json.dumps` in infographics.py (at least 1 new call site for notes)
- Single atomic commit on `main` (pattern from recent quick tasks)

</specifics>

<canonical_refs>
## Canonical References

- `scheduler/agents/content/infographics.py` — primary change target (new kwargs to pipeline + telemetry)
- `scheduler/agents/content/__init__.py` — shared pipeline; add `sort_by` + `dedup_scope` kwargs, extend `_is_already_covered_today`
- `scheduler/agents/content/gold_media.py` — reference implementation for structured `notes` telemetry (gmb pattern)
- `scheduler/worker.py` L100-104 — confirms `sub_infographics` cron schedule (daily 12:00 PT); no change needed here
- `frontend/src/pages/PerAgentQueuePage.tsx` — consumes `notes` via `parseRunNotes` (no4); infographics subtitle appears automatically once we populate notes
- `.planning/debug/resolved/260422-gmb.md` — source of the `notes` structured schema convention
- `.planning/quick/260422-no4-surface-zero-item-agent-runs-in-per-agen/` — UX consumer of the notes telemetry
- `.planning/quick/260422-zid-*/` — removed predicted_format routing gate (must preserve this removal)

</canonical_refs>
