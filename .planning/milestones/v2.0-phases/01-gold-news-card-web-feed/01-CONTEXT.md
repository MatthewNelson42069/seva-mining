# Phase 1: Gold News Card + Web Feed - Context

**Gathered:** 2026-04-27
**Status:** Ready for planning
**Mode:** Smart-discuss (autonomous), 16/16 recommendations accepted

<domain>
## Phase Boundary

Ship the full v2.0 daily-summary stack end-to-end with the Gold News section running on real data (`fetch_stories()` + Sonnet) and Ontario sections rendering as stub empty states. The operator can read a summary card in the browser at `/` and receive a WhatsApp teaser within minutes of the 08:00 PT cron firing.

**In scope:**
- Alembic migration `0010_add_daily_summaries_table.py` (hand-written; CREATE TABLE + index only; touches NO other schema)
- Dual SQLAlchemy models: `backend/app/models/daily_summary.py` + `scheduler/models/daily_summary.py` (byte-for-byte parity)
- Pydantic schemas with a `RawSources` model validating the `raw_sources_jsonb` shape on write
- `GET /summaries` FastAPI router (auth-gated via existing `get_current_user`, modeled on `digests.py`)
- `scheduler/agents/daily_summary.py` — `run_daily_summary()` orchestrator + `_build_gold_news_section()` (real) + Ontario section stubs
- `scheduler/worker.py` modifications:
  - Add lock IDs `1017` (daily_summary), `1018` (daily_summary_prune)
  - Add startup assertion: `assert len(set(JOB_LOCK_IDS.values())) == len(JOB_LOCK_IDS)` (OPS-02 ships in Phase 1)
  - Register `daily_summary` cron via `_make_daily_summary_job(engine)` factory (NOT in `CONTENT_CRON_AGENTS` — it's a complex job, mirrors `midday_digest` pattern)
  - REMOVE the `midday_digest` `scheduler.add_job(...)` call from `build_scheduler()` in the SAME commit (factory + lock-id-entry remain as dead code)
- WhatsApp delivery (`scheduler/services/whatsapp.py` reuse) — teaser <400 chars + link, gated by `WHATSAPP_DELIVERY_ENABLED` env var (default `false`)
- WhatsApp failure-alert (separate try/except so a Twilio outage doesn't loop or cascade)
- Frontend feed page: `frontend/src/pages/SummaryFeedPage.tsx` + `SummaryCard.tsx` + `SectionBlock.tsx`
- Frontend API: `frontend/src/api/summaries.ts` + `useSummaries()` TanStack Query hook
- `App.tsx` — route swap: `/` shows the feed; `/queue` and `/agents/:slug` redirect to `/` via `<Navigate to="/" replace />`
- `npm install react-markdown@^10.1.0 rehype-sanitize@^6.0.0` (the only npm installs in v2.0)
- Tests at every layer (scheduler pytest, backend pytest, frontend vitest)

**Out of scope (deferred to later phases):**
- Real Ontario law ingestion (Phase 2)
- Real Ontario stats ingestion (Phase 3)
- 30-day prune cron (Phase 4)
- v1.0 sub-agent dead-code retirement audit (Phase 4)
- Cross-summary continuity (deferred to v2.1+ — CSC-01)

**Requirements covered (19):** SUM-01..06, GOLD-01..03, FEED-01..06, WHA-01..03, OPS-02

</domain>

<decisions>
## Implementation Decisions

### Sonnet Prompt for Gold News Section

- **Section structure:** "Why it matters" 1-sentence lead, followed by 3-5 adaptive bullets. Axios pattern (per FEATURES research). The lead is what feeds the WhatsApp teaser body.
- **Bullet count:** Adaptive 3-5 — Sonnet decides based on the top stories' newsworthiness; not padded to a fixed count.
- **Source citation:** Inline at end of each bullet `(Source Name)`. No separate footnote section.
- **Empty-state copy:** `No major moves in gold today — prices ranging $X–$Y.` Pulls `$X-$Y` range from existing `services/market_snapshot.py` data; falls back to `No major moves in gold today.` if snapshot unavailable.

### WhatsApp Teaser + Failure Alert

- **Teaser format:** `📊 Summary {time PT}: {1-sentence lead from gold-news section}. Read full → {feed_url}` — max 400 chars (asserted at write time).
- **Feed URL source:** New env var `FEED_BASE_URL` (e.g. `https://seva-mining-smm.vercel.app`). Fall back to `https://seva-mining-smm.vercel.app` constant if env unset (defensive default for dev).
- **Failure alert format:** `⚠️ Summary {time PT} FAILED: section(s) {failed_sections}. agent_run_id: {short_id}` — separate Twilio call wrapped in its own try/except so a Twilio outage does not cascade.
- **Simulate gate:** New env `WHATSAPP_DELIVERY_ENABLED` (default `false`). When `false`: log the message and the teaser char-length, do NOT call Twilio. When `true`: actually call `send_whatsapp_message()`. This mirrors the Phase B `X_POSTING_ENABLED` simulate-mode pattern.

### Frontend Feed Page UX

- **Card density:** Single-column, full-width cards with vertical scroll. Instagram-feed-style per user spec ("should look like an Instagram feed, except text obviously"). Max width ~720px on desktop, responsive shrink for narrower viewports (preserved from v1.0 layout decisions).
- **Empty feed state (no rows yet):** Renders "Waiting for first summary. Next fire at {next_cron_PT}." Computes `next_cron_PT` client-side from current PT time.
- **Status badge visibility:** Show ONLY when `status` is `partial` or `failed` (clean default for `completed` — most rows). When shown: amber pill for `partial`, red for `failed`.
- **Refetch behavior:** 5-minute interval ONLY (per FEED-06). Do NOT refetch on window focus — user said this is read-only intelligence, no need for hyperactive freshness.

### Backend Schema Shape & Cross-Summary Continuity

- **`raw_sources_jsonb` Pydantic shape:** Defined Pydantic model `RawSources(BaseModel)` with strict typing:
  ```python
  class RawSources(BaseModel):
      gold_news: list[GoldNewsSource]  # {title, link, source_name, score, published_at}
      ontario_law: OntarioLawState     # {hits: list[OntarioLawHit], last_known_law: OntarioLawHit | None}
      ontario_stats: OntarioStatsState # {snapshot_date: str, last_known_figure: float | None, fresh_data: dict | None}
  ```
  Validated via `model_dump_json()` on write; round-trip-tested. Phase 1 ships with `ontario_law` and `ontario_stats` as empty stubs (Phase 2/3 populate them).
- **CSC-01 (cross-summary continuity):** DEFER to v2.1+. Pure prompt-engineering addition; low risk to delay. Phase 1 prompts do NOT receive the prior-summary context. Easy to add later — single line in the user-prompt template.
- **Migration FK constraint:** `daily_summaries.agent_run_id UUID REFERENCES agent_runs(id) ON DELETE SET NULL`. Preserves summary forensic value if the agent_runs row is later swept (rare; reconcile_stale_runs only updates status, doesn't delete rows — but defensive).
- **Frontend markdown sanitizer:** `rehype-sanitize` default schema. Allows headings (h1-h6), lists (ul/ol/li), paragraphs, emphasis (em/strong), links (a with href). Strips `<script>`, `<iframe>`, `<style>`, `<form>`, event handlers, `javascript:` URLs. The default schema is well-tested and Claude's markdown output won't generate anything outside this whitelist.

### Cross-cutting (locked from research, not re-decided here)

- Lock IDs: `daily_summary` = 1017, `daily_summary_prune` = 1018
- WhatsApp pattern: teaser <400 chars + link; never `build_chunks()` for daily_summary
- Score floor for gold news: `>= 6.0` (broader than 7.0 sub-agent threshold; summaries need coverage)
- StatCan Table: `16-10-0019-01` (monthly, M+2 lag) — not Phase 1 but locked for Phase 3
- `midday_digest` deregistration: SAME commit as daily_summary registration
- Dead-code-only retirement: do NOT delete v1.0 sub-agent source files
- React markdown: `react-markdown ^10.1.0` + `rehype-sanitize ^6.0.0`
- Migration 0010 hand-written — `op.create_table` + `op.create_index` only, no autogenerate

</decisions>

<code_context>
## Existing Code Insights

### Reusable Assets

- `scheduler/agents/content_agent.py` — `fetch_stories()` returns `list[dict]` with `score` (0-10 composite), `predicted_format`, `title`, `link`, `source_name`, `summary`, `published`. Filter to `score >= 6.0`, take top 5. No refactor needed.
- `scheduler/agents/content_agent.py` — `AsyncAnthropic(timeout=30.0)` pattern (post-kro) — replicate for daily_summary section builders.
- `scheduler/services/whatsapp.py` — `send_whatsapp_message(message: str)` is the only helper needed; do NOT call `build_chunks()` for daily_summary (teaser pattern only).
- `scheduler/services/market_snapshot.py` — provides spot-price ranges for the gold-news empty-state copy.
- `scheduler/worker.py` — `_make_midday_digest_job(engine)` is the correct factory pattern to mirror for `_make_daily_summary_job(engine)` (NOT `_make_sub_agent_job` which is for the simple CONTENT_CRON_AGENTS tuple shape).
- `scheduler/models/agent_run.py` — existing telemetry model; daily_summary writes to this same table.
- `backend/app/routers/digests.py` — auth pattern, SQLAlchemy `select`, Pydantic schema style — model `summaries.py` after this.
- `backend/alembic/versions/0009_add_x_post_state_to_draft_items.py` — migration style to mirror (hand-written, minimal, with `down_revision` chain).
- `frontend/src/api/digests.ts` — API call + TanStack Query hook pattern; mirror for `summaries.ts` + `useSummaries()`.
- `frontend/src/components/ui/badge.tsx` — existing pill component for status badge.

### Established Patterns

- **Dual-model parity:** Backend AND scheduler both have full SQLAlchemy models. The Phase B parity test (`scheduler/tests/test_draft_item_model.py`) is the precedent — must add `test_daily_summary_model.py` to enforce parity.
- **CronTrigger registration:** post-m49 pattern — `(job_id, run_fn, name, lock_id, cron_kwargs: dict)` for simple sub-agents in `CONTENT_CRON_AGENTS`; complex jobs use a dedicated factory function called directly in `build_scheduler()`.
- **Advisory lock pattern:** `pg_try_advisory_lock(lock_id)` at start of run_fn, release in finally block. Returns `False` → log + skip + return cleanly (idempotency for misfire-induced double-fires).
- **Reconcile_stale_runs:** boot-time orphan sweeper marks `running` rows as `failed` with error `"scheduler restart — run abandoned (process killed before finally block)"`. Daily_summary inherits this safety net.
- **Pydantic v2 patterns:** `model_config = ConfigDict(from_attributes=True)` for ORM serialization. JSONB validation via nested Pydantic models with `model_validate(json_dict)` on read.
- **React feed/list patterns:** TanStack Query hooks with `refetchInterval`; Tailwind v4 utilities for layout; shadcn/ui primitives via the tailwind-v4 branch.

### Integration Points

- **Backend `main.py`:** add `app.include_router(summaries.router, prefix="/summaries", tags=["summaries"])`.
- **Scheduler `worker.py`:** modify `JOB_LOCK_IDS` dict, add `_make_daily_summary_job` factory, modify `build_scheduler()` to register daily_summary + REMOVE midday_digest's `add_job` call, add startup uniqueness assertion.
- **Frontend `App.tsx`:** swap `/` route to `<SummaryFeedPage />`, add `<Navigate to="/" replace />` for `/queue` and `/agents/:slug` legacy routes (keep `/login`, `/digest/:date`, `/settings` intact for emergency access).
- **Alembic chain:** migration `0010` `down_revision = '0009_add_x_post_state_to_draft_items'`.

</code_context>

<specifics>
## Specific Ideas

- User explicitly said "should look like an Instagram feed, except text obviously" → vertical scroll, single-column, full-width cards.
- User said "Tell me if it failed" → WhatsApp failure alert is a hard requirement (WHA-02), implemented even when `WHATSAPP_DELIVERY_ENABLED=false` (the alert always logs at minimum).
- User said "Just 30 days" → retention enforced by Phase 4's prune cron; Phase 1 doesn't need to enforce it (can manually clean if needed during dev).
- User said the feed should be at `/` and replace `/queue` → that's locked.
- The 08:00 PT and 12:00 PT cron times are firm — do not negotiate.

</specifics>

<deferred>
## Deferred Ideas

- **CSC-01** (cross-summary continuity, "Building on this morning..." in 12:00 fire): deferred to v2.1+ per locked decision. One-line prompt template addition when ready.
- **URL-01** (click-through source URLs per bullet): deferred to v2.1+. Requires storing `link` per bullet in JSONB and rendering as `<a>` tags.
- **ANC-01** (section anchor links `#gold-news`, etc.): deferred to v2.1+.
- **ADD-01** (OMA RSS as 4th Ontario law source): deferred to v2.1+; check feed URL availability later.

</deferred>
