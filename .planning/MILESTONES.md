# Milestones

## v2.0 Daily Summary Feed (Shipped: 2026-05-06)

**Phases completed:** 4 phases, 9 plans, 23 tasks

**Key accomplishments:**

- Alembic migration 0010 creating daily_summaries table, dual SQLAlchemy parity models (backend + scheduler), and Pydantic schemas with strict RawSources JSONB validator (HIGH-4 closed)
- react-markdown ^10.1.0 + rehype-sanitize ^6.0.0 installed; getSummaries(limit) + useSummaries() hook wired to GET /summaries with 5-min refetch interval and no window-focus refetch
- One-liner:
- GET /summaries auth-gated read endpoint (FEED-05) — router-level JWT gate, limit param (1..120, default 60), generated_at DESC ordering, raw_sources_jsonb omitted from response
- v2.0 daily_summary cron: run_daily_summary() with CRIT-3 idempotency, GOLD-01/02/03 gold news section via Sonnet, Ontario stubs, SUM-04 telemetry, SUM-05 status assembly, WHA-01 teaser + MOD-6 failure alert — plus CRIT-1/CRIT-2/OPS-02 worker.py wiring with midday_digest deregistration in same atomic commit
- 3 components + 19 tests + App.tsx route swap — Instagram-style vertical feed at `/` with rehype-sanitize XSS defence and conditional status badges
- SerpAPI + NRCan concurrent ingestion + claude-haiku-4-5 relevance filter + last_known_law JSONB continuity wired into daily_summary cron — replaces Phase 1 stub entirely
- StatCan WDS direct vector poll replacing the Phase 1 stub — fresh/no_new_data/error state machine with JSONB snapshot persistence and 3 new telemetry keys
- 30-day daily_summaries retention cron at 03:00 PT (lock 1018), 6 v1.0 sub-agent crons deregistered via CONTENT_CRON_AGENTS=[], and OPS-04 audit confirming retire-via-deregistration discipline upheld

---
