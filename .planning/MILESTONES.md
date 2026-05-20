# Milestones

## v3.0 Multi-Tenant Dashboards — Juno Industries Onboarding (Shipped: 2026-05-19)

**Phases completed:** 2 phases (9-10), 10 plans, ~30 tasks

**Audit:** `passed` with `tech_debt` (8 non-blocking follow-ups for v3.0.1/v3.1+; 20/20 requirements satisfied — TENANT-01..10 + DEF-01..10). See `milestones/v3.0-MILESTONE-AUDIT.md`.

**Key accomplishments:**

- **Phase 9 (Multi-Tenant Foundation):** Single atomic deploy converted single-tenant Seva → two-tenant Seva+Juno platform. Alembic 0014 added `company_id VARCHAR(20) NOT NULL` with `server_default='seva'` + CHECK + composite indexes to `daily_summaries`/`calendar_items`/`weekly_sweeps` (atomic backfill in same DDL transaction — no race). Cross-tenant leak defense via `backend/app/queries/scoped.py` + `scheduler/queries/scoped.py` helpers + CI grep gate `scripts/verify-tenant-isolation.sh`. Backend routers refactored to `/api/{company}/...` prefix with `Depends(get_current_company)`. Frontend `<Route path=":company">` wrapper + bookmark grace redirects + `CompanyScopedRoute` + `CompanySwitcher` segmented control + centralized `queryKeys.ts` factory + Zustand persist. **AppHeader.tsx Phase 5 byte-freeze formally lifted** with documented v3.0 rationale in 3 locations. Per-company scheduler: `juno_daily_summary=1020` REGISTERED at `CronTrigger(hour="8,12", minute=5)`; `juno_weekly_sweeper=1021` slot-only (v3.1+). Critical pre-prod bug fix: Juno idempotency filter extended to include `'partial'` status — without this catch, every Juno cron run would have inserted a duplicate row.
- **Phase 10 (Juno Defence News Funnel):** Config-only build on Phase 9 infrastructure. Populated `scheduler/companies/juno/{feeds, prompts, serpapi}.py` with 13 HTTP-validated Tier-1 RSS feeds (Defense News × 8 + Breaking Defense + DefenseScoop + RUSI ×2 + SIPRI), 10 SerpAPI queries (7 Canadian procurement + 3 fallback for war.gov/nato.int/canada.ca), and a Janes/CSIS-voice production Sonnet 4.6 system prompt with explicit anti-tactical clause (per Anthropic-Pentagon dispute precedent). New `juno_relevance.py` Haiku 4.5 classifier using GA `client.messages.parse(output_format=DefenceRelevance)` syntax filters World Events at `confidence >= 0.7` across 9 inclusion categories. New `juno_refusal_detector.py` (7 substring patterns + retry-with-framing-nudge + SECTION_UNAVAILABLE_COPY fallback). New `juno_health_check.py` (bozo + empty + `<30%` of 7-day avg flagging). `run_juno_daily_summary` extended (+715 LOC) with real 3-section synthesis. SerpAPI gated morning-only (08:05 PT) to save ~$2-4/mo. `SummaryCard.tsx` per-tenant rendering via `companySectionConfig.ts` (single component, both tenants). `JUNO_CRON_ENABLED` env var two-gate safety (voice UAT APPROVED + env true). Voice UAT operator-APPROVED against 8 hand-curated stories (5/7 automated criteria PASS + corpus-bounded + qualitative). Manual smoke fire wrote `status='completed'` Juno row (Defence News 2709 chars + World Events 3464 chars). Visual QA at 1440×900 APPROVED 10/10.
- **Tests at milestone close:** backend 184 pass (+28 from pre-v3.0 baseline of 156) / scheduler 328 pass (+64) / frontend 168 pass (+27). 19/19 cross-tenant isolation tests GREEN. CI grep gate exit 0 (zero raw selects outside `scoped_*()` helpers).
- **Operator action remaining:** Flip `JUNO_CRON_ENABLED=true` in Railway env-vars for production. Local-dev already set. Next 08:05 PT cron after flip writes the first real Juno defence intelligence brief.

---

## v2.1 Three-Tab Content Engine + UI Polish (Shipped: 2026-05-19)

**Phases completed:** 4 phases (5-8), 20 plans

**Key accomplishments:**

- **Phase 5 (Foundation):** 3-tab dashboard shell + Alembic 0011/0012 migrations (`calendar_items` + `weekly_sweeps`) + dual-model SQLAlchemy parity (4 model files) + 2 auth-gated stub routers + frontend `TabbedDashboard` + `TabNav` with URL-driven NavLink active state.
- **Phase 6 (Content Calendar):** Full async CRUD over `calendar_items` (GET range / POST / PATCH / DELETE) with TZ-safe date round-trip, explicit `updated_at` on PATCH, UNIQUE(date) constraint, router-level JWT auth. Frontend weekly Mon-Sun grid with optimistic mutations + rollback + Alembic 0013 (title nullable + UNIQUE(date)). Plain text only; auto-save on blur; no tags/dialogs/chips per simplification.
- **Phase 7 (Weekly Viral Sweeper — X-API pivot):** Sunday 08:00 PT APScheduler cron ingests top gold-sector tweets via `tweepy.AsyncClient.search_recent_tweets` (replaces originally specced Reddit/asyncpraw — reuses existing $100/mo X API Basic tier). Computes story virality over past 7 days of `daily_summaries.raw_sources_jsonb.gold_news[]` (URL canonicalize + cross-reference rank). Calls Sonnet 4.6 for 3 content angles. Persists `weekly_sweeps` row with status mapping (completed/partial/failed). Tab 3 React UI renders the latest sweep card + history week-picker + SWEEP-14 empty-state. SWEEP-01/02 dropped per X-API pivot.
- **Phase 8 (UI Polish + Dead-Code Strip):** 3 semantic amber tokens (`--color-brand-accent[-hover/-subtle]`) added to Tailwind v4 `@theme inline`. UI-04 `border-zinc-800` + `hover:border-zinc-700 transition-colors` unified across SummaryCard/SweeperCard/SectionBlock/DayCell. X-handle pill via rehype-based plugin + shared MarkdownContent wrapper (replaces UI-05's Reddit `r/gold` spec post-X-pivot). Dead-code strip removed `scheduler/agents/content/` directory entirely (15 files, ~5100 lines); `JOB_LOCK_IDS` shrunk to 4 keys; OPS-02 assertion still passes; DB rows preserved per `260420-sn9`/`260423-k8n` precedent. UI-07 visual QA at 1440x900 PASSED.

---

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
