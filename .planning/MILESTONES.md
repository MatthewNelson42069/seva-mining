# Milestones

## v3.1 Juno Feature Parity + Branding (Shipped: 2026-05-21)

**Phases completed:** 5 phases (12, 13, 14, 15, 16), 19 plans, ~82 commits

**Audit:** verdict `passed` (initial verdict was `tech_debt`; flipped to `passed` after Phase 16 closed all 5 pre-existing carry-over tech-debt items). See `.planning/milestones/v3.1-MILESTONE-AUDIT.md`.

**Regression baseline at close:** scheduler 363 / backend 191 / frontend 181 — all GREEN; both CI grep gates (`verify-anthropic-resolver.sh` + `verify-tenant-isolation.sh`) exit 0; all 25 requirements satisfied (20 user-facing + 5 CLEAN audit cleanup).

**Key accomplishments:**

- **Phase 12 (Per-tenant Anthropic API Key, shipped 2026-05-20):** New `scheduler/anthropic_client.py` resolver routes every Anthropic call through `get_anthropic_client(company_id: Literal["seva","juno"], *, timeout)`. 5 production sites refactored (3 Seva + 2 Juno) + 3 dead functions + 1 orphan helper excised from `content_agent.py`. CI grep gate `scripts/verify-anthropic-resolver.sh` forbids `AsyncAnthropic(` outside resolver module. `scheduler/worker.py::_validate_env` surfaces per-tenant + STRICT env-var status at boot. Fail-closed contract preserved verbatim with WARN-once-on-fallback semantics + opt-in `ANTHROPIC_RESOLVER_STRICT=true` prod safety net. 16/16 invariants verified PASS.

- **Phase 13 (Per-company Branding, shipped 2026-05-20):** `frontend/src/config/companyBrandConfig.ts` registry (mirrors v3.0 Phase 9 D-08 `companySectionConfig.ts` pattern); `useCompanyBrand()` hook resolves URL → Zustand → 'seva' fallback. `/juno/*` shows "Juno Industries" wordmark + "J" navy letter mark + navy palette `oklch(0.58 0.14 245)` via `:root.dark[data-company='juno']` CSS override (specificity 0,2,0 beats Phase 8 `.dark` 0,1,0 — researcher caught the bug during UI-SPEC pass). FOWB-free transitions via `CompanyBrandEffect` single useEffect committing dataset+title+favicon atomically. Polish folded: per-tenant browser tab title + favicon swap + bare-`/` redirect (TENANT-VISITED-v31-redux closed). Operator visual QA APPROVED 10/10 at 1440×900.

- **Phase 14 (Juno Content Calendar Tab 2, shipped 2026-05-20):** Tightest scope in v3.1 — 13-line deletion + 2 new test files. Codebase scout discovered backend + frontend hooks were ALREADY multi-tenant from v2.1 Phase 6 + v3.0 Phase 9; only the Phase 9 D-09 short-circuit at `ContentCalendarPage.tsx:42-54` was gating `/juno/calendar`. Net change: deleted 13 lines + frontend RTL test (TanStack Query key isolation) + backend pytest (4 cross-tenant 404 assertions). REQUIREMENTS.md JCAL-01 wording relaxed per D-06 with `*(D-06)*` provenance marker. D-07 zero-regression contract held across 12 critical Seva files.

- **Phase 15 (Juno Weekly Viral Sweeper Tab 3, shipped 2026-05-21):** Largest v3.1 phase — 7 plans across 3 waves. New `scheduler/agents/juno_weekly_sweeper.py` orchestrator (588 LOC + 17 unit tests) + new `JUNO_SWEEPER_SYSTEM_PROMPT` (Janes/CSIS voice + verbatim anti-tactical clause from Phase 10 + "3 content angles" task framing) + new `JUNO_SWEEPER_X_QUERY` constant (11 corrected handles + 2 hashtags; defence-prime cashtags excluded per anti-feature) + cron registration at lock 1021 Sunday 08:00 PT America/Los_Angeles env-gated by `JUNO_SWEEPER_CRON_ENABLED`. Phase 15 research caught critical D-03 substrate contradiction (Phase 10's `raw_sources_jsonb` stored diagnostic counts only); Plan 15-01 extended Phase 10 writers to persist story-URL arrays (Juno-only; Seva untouched per D-10). Research also surfaced 4 X-handle spelling corrections + 2 Tier-2 Canadian handle additions. Operator voice UAT APPROVED 2026-05-21 (interpretation b: code+test correctness basis; voice_calibration_uat.md ledger reserved for post-D-03b-backfill actual smoke fire).

- **Phase 16 (v3.1 Audit Cleanup Bundle, shipped 2026-05-21):** 5 single-task plans (mirrors Phase 11's pattern for v3.0 audit cleanup), all parallel-safe Wave 1. Closed all pre-existing tech-debt items surfaced by initial v3.1 audit: CLEAN-01 frontend ESLint (15 → 0 errors), CLEAN-02 backend ruff UP017 + E501 (17 → 0), CLEAN-03 scheduler ruff F401 (6 → 0), CLEAN-04 scheduler test RuntimeWarnings (4 → 0; `AsyncMock` → `MagicMock` for sync `AsyncSession.add()`), CLEAN-05 stale Phase-9-era "Coming in Phase 10" empty-state copy → tenant-aware rewrite. Zero regression deltas across all 3 test suites; D-10 byte-identical Seva contract held. v3.1 audit re-ran post-Phase-16 → verdict flipped from `tech_debt` to `passed`.

- **Production rollout completed within milestone:** `JUNO_CRON_ENABLED=true` flipped in Railway 2026-05-20 (first real Juno production brief at 08:05 PT 2026-05-21). 5 operator activation gates remain pending post-v3.1-archive (Phase 12 per-tenant API keys + STRICT flip + CI integration; Phase 14 3 visual spot-checks; Phase 15 `JUNO_SWEEPER_CRON_ENABLED` flip) — documented in audit as activation work for already-shipped code, NOT tech debt.

- **Notable parallel-execution lesson:** Phase 16's 5-agent Wave 1 surfaced a shared `.git/index` staging race when multiple executors committed with `--no-verify` concurrently. 16-04 + 16-05 frontend code bundled into single commit `5fc45f0` under 16-04's attribution; 16-05 SUMMARY landed in `49ad7c7` alongside 16-01's docs. Zero functional impact (all artifacts in HEAD, all gates pass); minor commit-attribution discrepancy in 2 of 12 commits. Filed for future GSD tooling consideration: per-executor commit locking would prevent.

---

## v3.0.1 v3.0 Audit Cleanup Bundle (Shipped: 2026-05-20)

**Phases completed:** 1 phase (11), 5 plans

**Audit:** Phase verifier 5/5 PASS — `.planning/phases/11-audit-cleanup-bundle/11-VERIFICATION.md`. All preserved invariants confirmed: fail-closed contract, backwards-compat signature, SerpAPI cap headroom, worker.py lazy import resolution, exactly-one `run_juno_daily_summary` definition.

**Key accomplishments:**

- **Phase 11 (Audit Cleanup Bundle):** 5 non-blocking v3.0 audit follow-ups closed atomically in 2 waves. Wave 1 (3 parallel, file-disjoint): CLEANUP-01 removed morning-only SerpAPI cost gate so both daily Juno fires execute 7 Canadian-procurement queries (budget $5.25→$8-9/mo inside $50/mo cap); CLEANUP-02 refreshed `milestones/v3.0-REQUIREMENTS.md` DEF-01..07 traceability rows from "Scaffolded" → "Complete" matching DEF-08..10 format; CLEANUP-04 flipped `nyquist_compliant: true` + `wave_0_complete: true` in both `09-VALIDATION.md` + `10-VALIDATION.md` frontmatters. Wave 2 (2 parallel after 11-01, both touching `daily_summary.py` in disjoint line ranges): CLEANUP-03 removed stale Phase 9 stub section-divider comment block (Phase 10 had already replaced stub body inline — planner correctly scoped to comment, not function); CLEANUP-05 wired Haiku 4.5 `pydantic.ValidationError` observability via caller-owned `validation_errors: list[dict] | None = None` keyword-only accumulator in `juno_relevance.py::classify_story` + plumbed through to `agent_runs.notes['haiku_validation_errors']` with `{input_excerpt, error_type, error_msg}` shape — fail-closed contract preserved verbatim; 3 new RED→GREEN tests; backwards-compat verified via `inspect.signature`.
- **Tests at milestone close:** backend 184 pass (no change vs v3.0 baseline) / scheduler 331 pass (+3 from CLEANUP-05's new ValidationError observability tests) / frontend 168 pass (no change). Zero regressions across all suites.
- **Production action completed:** `JUNO_CRON_ENABLED=true` flipped in Railway env-vars on 2026-05-20 immediately post-merge. Scheduler service successfully redeployed; APScheduler logged `juno_daily_summary cron ENABLED via JUNO_CRON_ENABLED=true env var` on boot. First real Juno production brief expected 2026-05-21 08:05 PT America/Los_Angeles.
- **GSD CLI hang workaround:** `phase complete 11` hung in TUI spinner loop emitting only ANSI escape sequences with no progress. Killed process and applied artifact updates manually (REQUIREMENTS.md / ROADMAP.md / STATE.md) — same edits the CLI would have made. Worth filing upstream if recurrence pattern emerges.

---

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
