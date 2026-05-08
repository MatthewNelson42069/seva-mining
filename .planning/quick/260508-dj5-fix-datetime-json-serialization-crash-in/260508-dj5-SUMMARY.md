# Quick Task 260508-dj5 — Fix datetime-JSON-serialization crash in gold news fallback path — SUMMARY

**Shipped:** 2026-05-08
**Branch:** `main`

## Why

The 2026-05-08 08:00 PT cron fire crashed (agent_runs row `50875012`):

```
StatementError: (builtins.TypeError) Object of type datetime is not JSON serializable
[SQL: INSERT INTO daily_summaries (..., raw_sources_jsonb, ...)]
```

The Sonnet write call raised (likely a 30s Anthropic timeout — total run 33.67s; the per-request timeout is 30s and the run was clearly bottlenecked there). The fallback path returned `(None, top, counts)` where `top` was the unmodified list of stories from `fetch_stories()` — each with a `datetime` object in `s["published"]`. That list was then assigned to `raw_sources["gold_news"]` and the daily_summaries INSERT crashed because Postgres's JSONB driver cannot serialize Python `datetime` objects directly.

The bug shipped in v2.0 Phase 1 plan 01-05 day one but only triggered today because Sonnet had succeeded on every prior fire. With Sonnet now occasionally hiccuping (this is the third documented Anthropic incident in this codebase: kro 30s timeout, m51 deadlock, now today's hiccup), the bug surfaced.

## Fix

Single targeted change in `scheduler/agents/daily_summary.py`:

**Before (buggy):**
```python
try:
    response = await anthropic_client.messages.create(...)
    md = response.content[0].text.strip()
except Exception:
    return (None, top, counts)   # ← top has datetime objects in s["published"]

raw = [{...isoformat-conversion...} for s in top]   # only on success path
return (md, raw, counts)
```

**After (fixed):**
```python
# Build JSON-safe raw_sources entry up front (HIGH-4 shape).
# quick-260508-dj5: this MUST happen BEFORE the Sonnet try/except so the
# failure path returns JSON-serializable data — datetime objects in
# s["published"] would otherwise crash the daily_summaries INSERT with
# "TypeError: Object of type datetime is not JSON serializable" (this is
# what crashed the 2026-05-08 08:00 PT fire when Sonnet timed out).
raw = [{...isoformat-conversion...} for s in top]

try:
    response = await anthropic_client.messages.create(...)
    md = response.content[0].text.strip()
except Exception:
    return (None, raw, counts)   # ← raw is JSON-safe now

return (md, raw, counts)
```

The `raw` list comprehension is identical to before; only its position moved. Both success and failure paths now return JSON-safe dicts. Forensic value preserved — even when Sonnet fails, the raw stories that WERE selected (with their titles / links / scores / sources) are persisted in `raw_sources_jsonb["gold_news"]` for post-mortem inspection.

## Tests

`scheduler/tests/agents/test_daily_summary.py`:

- **NEW** `test_build_gold_news_section_returns_json_serializable_raw_when_sonnet_raises` — Provides a story dict with a real `datetime(...)` object in `published`, mocks Sonnet to raise `RuntimeError("anthropic hiccup")`, calls `_build_gold_news_section`, then asserts `json.dumps(raw)` does NOT raise. Also asserts forensic value (raw retains story metadata).

**Verified the test catches the bug:** ran the new test against the pre-fix code via `git stash` → test failed with `TypeError: Object of type datetime is not JSON serializable` on the `json.dumps(raw)` line. Restored the fix → test passes. Regression coverage solid.

## Validation

- `cd scheduler && uv run pytest -x` → **314 passed, 1 skipped, 3.76s** (was 313 before; +1 new regression test)
- `cd scheduler && uv run ruff check .` → clean
- Preservation diff outside `scheduler/agents/daily_summary.py` and its tests = 0 bytes ✓ (`git diff main^ -- backend/ frontend/ scheduler/worker.py scheduler/agents/content_agent.py` returns empty)

## Operational impact

- The 2026-05-08 08:00 PT card is **lost** (failure-row landed at `daily_summaries.id=2a7edc4c` with all sections null). Cannot be recovered — RSS feed cache has rotated past those stories by now.
- Next 12:00 PT fire (today, ~2 hours from now) should produce a clean card with the new headline-grouped format from drw. Even if Sonnet hiccups again, the row write will succeed and the gold section will simply be empty / failed-marked instead of the entire row write crashing.
- **The new format (drw) hasn't yet rendered in production** — yesterday's 12:00 PT was on pre-drw code (no `**bold headline**` separators in the gold_news_md from row `178ab253`). After today's 12:00 PT fire, you'll see the new format for the first time.

## Independent finding from today's run telemetry — SerpAPI confirmed not running

The 2026-05-07 19:00 PT run telemetry (post-drw deploy) shows:

```json
{
  "candidates_gold_rss": 84,        ← RSS performing excellently
  "candidates_gold_serpapi": 0,     ← Confirmed: SerpAPI not contributing
  "candidates_gold_total": 84,
  "candidates_gold_after_floor": 43,
}
```

Today's 08:00 PT failure showed the same: `candidates_gold_serpapi: 0`. Two consecutive fires with SerpAPI silently returning empty.

**Action for the user (cannot do this myself per safety rules — Railway env vars):**
1. Open Railway dashboard → seva-mining project → **scheduler** service → Variables tab
2. Confirm `SERPAPI_API_KEY` is set with the same key used for the SerpAPI plan you pay $50/mo for
3. Same key likely needs to be set on the **API/backend** service too (parity)

After that env-var is set + Railway redeploys, the next fire's `candidates_gold_serpapi` should be nonzero (typically 30-60 stories from the 17-keyword sweep). Until then, gold news ingestion is RSS-only — which is still excellent (87 candidates → 46 above floor → top 5 surfaced) but losing the breadth that SerpAPI's Google News index would add.

## Out of scope

- The Sonnet failure root-cause (timeout? bad response? Anthropic 5xx?) — not investigated further; the fix makes the system resilient to ANY Sonnet failure, regardless of underlying cause
- Stripping the legacy v1.0 dead code — separate concern, not blocking
- Anything in backend / frontend / scheduler/worker.py
- The Sonnet prompt itself — drw was right; today's failure was infra, not prompt
