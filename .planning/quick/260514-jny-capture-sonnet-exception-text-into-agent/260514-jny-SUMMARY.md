# Quick Task 260514-jny — Capture Sonnet exception text into agent_runs.errors — SUMMARY

**Shipped:** 2026-05-14
**Branch:** `main` (single-file diagnostic enrichment + 3 new tests)

## Why

Honest scoping admission after ii6: I'm ~80% confident the May 14 12:00 PT `partial` was a Sonnet timeout, but the broad `except Exception` in `_build_gold_news_section` only logs to Railway logs (which I can't view from this side) — `agent_runs.errors` stays `null`. If tomorrow's 08:00 PT fire ALSO partials, we'd be back to guessing.

User: *"yes ship"* (the diagnostic enrichment).

This task adds exception-text capture into `agent_runs.errors` so future per-section failures are diagnosable from Neon SQL alone, no log access needed.

## Fix

**`scheduler/agents/daily_summary.py` — 3 surgical edits:**

### Edit 1: Gold section captures exception text into `counts["last_error"]`

```diff
- counts: dict[str, int] = {"rss": 0, "serpapi": 0, "total": 0, "after_floor": 0}
+ counts: dict[str, object] = {
+     "rss": 0, "serpapi": 0, "total": 0, "after_floor": 0,
+     "last_error": None,  # quick-260514-jny
+ }

  try:
      stories = await fetch_stories()
- except Exception:
+ except Exception as exc:
      logger.exception(...)
+     counts["last_error"] = f"fetch_stories: {type(exc).__name__}: {exc}"
      return (None, [], counts)
```

And the same pattern around the Sonnet WRITE call:

```diff
  try:
      response = await anthropic_client.messages.create(...)
      md = response.content[0].text.strip()
- except Exception:
+ except Exception as exc:
      logger.exception("daily_summary: Sonnet write call raised")
+     counts["last_error"] = f"sonnet_write: {type(exc).__name__}: {exc}"
      return (None, raw, counts)
```

The format `{stage}: {ExceptionType}: {message}` tells us BOTH which stage failed (fetch_stories vs sonnet_write) AND the actual exception. Future stages added to the gold section just need to set `counts["last_error"]` with their own tag.

### Edit 2: Ontario law section gets the same treatment

```diff
- counts: dict[str, int] = {"serpapi": 0, "nrcan": 0, "after_dedup": 0, "after_filter": 0}
+ counts: dict[str, object] = {
+     "serpapi": 0, "nrcan": 0, "after_dedup": 0, "after_filter": 0,
+     "last_error": None,
+ }

  try:
-     survivors, counts = await fetch_ontario_law_hits(...)
+     survivors, fetched_counts = await fetch_ontario_law_hits(...)
+     counts.update(fetched_counts)
+     counts.setdefault("last_error", None)
- except Exception:
+ except Exception as exc:
      logger.exception(...)
+     counts["last_error"] = f"fetch_ontario_law_hits: {type(exc).__name__}: {exc}"
      return (None, [], previous_last_known_law, counts)
```

(Ontario stats already captured errors in `stats_jsonb.last_error_text` per Phase 3 design — no change needed there.)

### Edit 3: Orchestrator assembles per-section errors into `fresh.errors`

In `run_daily_summary`'s `finally` block, just before writing to AgentRun:

```python
per_section_errors: list[str] = []
if gold_counts.get("last_error"):
    per_section_errors.append(f"gold_news: {gold_counts['last_error']}")
if law_counts.get("last_error"):
    per_section_errors.append(f"ontario_law: {law_counts['last_error']}")
if stats_jsonb.get("last_error_text"):
    per_section_errors.append(f"ontario_stats: {stats_jsonb['last_error_text']}")

combined_errors = [e for e in ([error_text] + per_section_errors) if e]
if combined_errors:
    fresh.errors = combined_errors
```

`agent_runs.errors` is a JSONB column (per the AgentRun model — `array of error strings`). Existing reconcile_stale_runs writes follow the same shape. The new entries fit cleanly into that array.

## Tests

**`scheduler/tests/agents/test_daily_summary.py` — 3 NEW tests** under a `quick-260514-jny` header:

1. **`test_gold_section_captures_sonnet_exception_into_counts`** — uses `AsyncMock` to simulate `anthropic.APITimeoutError` from the Sonnet `messages.create` call. Asserts `counts["last_error"]` is populated with `"sonnet_write:"` prefix AND includes `"APITimeoutError"`.
2. **`test_gold_section_captures_fetch_stories_exception_into_counts`** — patches `fetch_stories` to raise `RuntimeError("network down")`. Asserts `counts["last_error"]` includes `"fetch_stories"`, `"RuntimeError"`, and `"network down"`.
3. **`test_gold_section_counts_has_last_error_key_on_success`** — inspects the source code to verify the counts dict initializes `last_error: None` (so `counts.get("last_error")` works uniformly without KeyError on success paths).

Existing 50 daily_summary tests + new 3 = **53 daily_summary tests**. Total scheduler **322 + 1 skipped** (was 319+1). Ruff clean.

## What the operator sees in production

**Before this fix (May 14 12:00 PT):**

```sql
SELECT id, status, errors, notes
FROM agent_runs
WHERE agent_name = 'daily_summary'
ORDER BY started_at DESC LIMIT 1;
```
```
status: partial
errors: NULL                     ← can't diagnose without Railway logs
notes: {"sections_failed": ["gold_news"], ...}
```

**After this fix (if 08:00 PT tomorrow partials again):**

```
status: partial
errors: ["gold_news: sonnet_write: APITimeoutError: Request timed out after 60.0s"]
                     ^^^^^^^^^^^^^ ← exact stage + exception type + message
notes: {"sections_failed": ["gold_news"], ...}
```

Single query, full diagnostic. Operator knows immediately:
- Which section failed (`gold_news`)
- Which stage within the section (`sonnet_write` vs `fetch_stories`)
- What Anthropic returned (`APITimeoutError`, `RateLimitError`, `BadRequestError`, etc.)
- The exact error message (timeout duration, rate limit window, etc.)

## Validation

- `uv run pytest -x` → **322 passed, 1 skipped, 3.53s** (was 319+1; +3 new tests)
- `uv run pytest tests/agents/test_daily_summary.py -x` → **53 passed** (was 50)
- `uv run ruff check .` → clean
- Preservation diff: `git diff main -- backend/ frontend/ scheduler/agents/content_agent.py scheduler/agents/ontario_law.py scheduler/agents/ontario_stats.py scheduler/worker.py` returns 0 bytes ✓

## Operational impact

- **Best case (tomorrow 08:00 PT completes cleanly):** This code never fires. Zero cost.
- **Worst case (tomorrow 08:00 PT partials again):** `agent_runs.errors` has the exact exception text. Diagnosis goes from "guess + check Railway logs" to "one SQL query."
- **Long-term:** Any future Sonnet / SerpAPI / NRCan / Anthropic failure self-documents to the operator without log access.

**Cost:** Zero — pure observability enrichment, no extra API calls, no extra DB rows. The `agent_runs.errors` column already exists and is JSONB — we just write into it.

## Out of scope (preserved)

- Sonnet timeout from ii6 (still 60s) — untouched
- of1/oxr prompt content — untouched
- Ontario sections' content logic — untouched (just added `last_error` field to law counts dict; existing behavior identical)
- backend/frontend/worker.py — 0-byte diff

## Workflow

`/gsd:quick` default mode (no `--full`, no `--discuss`, no `--research`) — orchestrator-inline execution. Targeted observability enrichment, low blast radius, well-specified.
