# Quick Task 260514-ii6 — Bump daily_summary Sonnet timeout 30s → 60s — SUMMARY

**Shipped:** 2026-05-14
**Branch:** `main` (single-character constant fix + regression test)

## Why

The 2026-05-14 12:00 PT card rendered with status `partial` because the gold-news Sonnet WRITE call hit the 30-second per-request timeout. Live DB telemetry confirmed:

```
sections_completed: ["ontario_law", "ontario_stats"]
sections_failed: ["gold_news"]
candidates_gold: 12              ← top stories ready
candidates_gold_rss: 87
candidates_gold_serpapi: 80      ← SerpAPI quota back online!
candidates_gold_after_floor: 54
whatsapp_sent: false             ← teaser blocked (no lead)
```

Wall-time on the run: 2 min 4 sec. The other two sections finished in seconds; gold ran to timeout.

**Root cause:** quick-260512-of1 + quick-260512-oxr tripled the gold-news Sonnet workload by structural change:
- `GOLD_TOP_N` 5 → 12 (more candidates in user prompt)
- `SONNET_MAX_TOKENS` 800 → 1500 (longer output target)
- Bull-thesis prompt structure (4 sub-sections + bullet-rule + 3 worked examples) adds ~+1400 prompt chars
- Net effective input: ~36-60 KB user-prompt content + ~3.5 KB system prompt

The 30s ceiling was sized for v2.0's original ~5-candidate, single-section, 800-token call. On heavy-news days the bull-thesis brief genuinely needs ~40-50s. Sonnet's `AsyncAnthropic(timeout=30.0)` raised `APITimeoutError`, the broad `except Exception` in `_build_gold_news_section` caught it, returned `(None, raw, counts)`, and the row wrote with `gold_news_md = NULL` + `status = "partial"`. Working as designed — but the practical effect is an empty gold section on the user's card.

## Fix

Single-line bump in `scheduler/agents/daily_summary.py` (line ~473):

```python
# BEFORE
anthropic_client = AsyncAnthropic(
    api_key=settings.anthropic_api_key, timeout=30.0,
)

# AFTER (quick-260514-ii6)
anthropic_client = AsyncAnthropic(
    api_key=settings.anthropic_api_key, timeout=60.0,
)
```

Plus an inline 8-line comment block explaining the bump, citing the of1/oxr structural changes that necessitated it.

### Why 60s, not 45s or 90s

- **45s**: Probably enough but no headroom. If Anthropic has a slow day or response gets queued, we'd still see timeouts.
- **60s**: ~2x typical heavy-news compute. Generous headroom for transient slowdowns. Total fire wall-time stays well under 3 min — no misfire risk against the daily cron cadence.
- **90s+**: Excessive. If Sonnet ever truly hangs past 60s, that's a real upstream issue worth surfacing rather than silently retrying.

### Scope discipline

ONLY the `daily_summary.py` AsyncAnthropic construction changes. The kro-era `fetch_stories()` client in `content_agent.py` (line 1083) stays at `timeout=30.0` — that client is used for the relevance-scoring parallel-gather loop where individual calls are smaller and 30s is appropriate.

## Tests

`scheduler/tests/agents/test_daily_summary.py` — 1 NEW regression test:

- **`test_anthropic_client_timeout_is_60_seconds`** — uses `inspect.getsource(daily_summary)` to verify the `AsyncAnthropic(...)` construction inside `run_daily_summary` uses `timeout=60.0` and explicitly does NOT contain `timeout=30.0`. Scoped to the construction block (not the whole module) so the test won't accidentally interact with content_agent's separate client.

49 existing daily_summary tests untouched — pass unchanged. Net total 49 → 50.

## Validation

- `cd scheduler && uv run pytest tests/agents/test_daily_summary.py -x` → **50 passed** (was 49)
- `cd scheduler && uv run pytest -x` → **319 passed, 1 skipped, 3.41s** (was 318+1)
- `cd scheduler && uv run ruff check .` → clean
- Preservation diff: `git diff main -- backend/ frontend/ scheduler/agents/content_agent.py scheduler/agents/ontario_law.py scheduler/agents/ontario_stats.py scheduler/worker.py` returns 0 bytes ✓

## Operational impact

**Next 08:00 PT fire (May 15, ~14 hrs from now):**
- Sonnet WRITE call gets 60s instead of 30s
- Heavy-news days complete cleanly (status `completed`, not `partial`)
- Card renders all 4 gold sub-sections + WhatsApp teaser delivers (was blocked by gold_news_md=NULL)
- Total fire wall-time: still ~2-2.5 min worst case (Ontario law's Haiku filter is the other slow piece)

**Cost:** ~0 change. Anthropic charges per token, not per second. Longer timeout doesn't increase per-call cost.

**Risk:** Negligible. If Sonnet ever takes >60s on a single call, surfacing the timeout is the right behavior — it indicates a real upstream issue worth knowing about.

## Out of scope (untouched)

- Ontario Law / Ontario Stats sections — untouched
- `content_agent.py` fetch_stories Anthropic client — stays at 30s (different use case, smaller calls in parallel)
- `GOLD_TOP_N=12`, `SONNET_MAX_TOKENS=1500`, prompt content — all from of1/oxr, preserved
- v1.0 dead code — preserved

## Workflow

Default `/gsd:quick` mode — orchestrator-inline execution. Tight constant change + 1 regression test. No subagent ceremony needed.
