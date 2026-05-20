# Roadmap: Seva Mining

## Milestones

- ✅ **v1.0.1 — Approval Dashboard (deprecated by v2.0 pivot)** — Phases 1-11, shipped 2026-04-25 → archive: [`milestones/v1.0.1/ROADMAP.md`](milestones/v1.0.1/ROADMAP.md)
- ✅ **v2.0 — Daily Summary Feed** — Phases 1-4 (reset numbering), shipped 2026-05-06 → archive: [`milestones/v2.0-ROADMAP.md`](milestones/v2.0-ROADMAP.md)
- ✅ **v2.1 — Three-Tab Content Engine + UI Polish** — Phases 5-8 (project-wide counter continues), shipped 2026-05-19 → archive in [`milestones/v3.0-ROADMAP.md`](milestones/v3.0-ROADMAP.md) (snapshot at v3.0 close includes v2.1 phase details — v2.1 was never archived separately before v3.0 started)
- ✅ **v3.0 — Multi-Tenant Dashboards (Juno Industries Onboarding)** — Phases 9-10, shipped 2026-05-19 → archive: [`milestones/v3.0-ROADMAP.md`](milestones/v3.0-ROADMAP.md) (audit: [`milestones/v3.0-MILESTONE-AUDIT.md`](milestones/v3.0-MILESTONE-AUDIT.md))

## Phases

<details>
<summary>✅ v2.0 Daily Summary Feed (Phases 1-4) — SHIPPED 2026-05-06</summary>

- [x] Phase 1: Gold News Card + Web Feed (6/6 plans) — completed 2026-05-06
- [x] Phase 2: Ontario Law Ingestion (1/1 plan) — completed 2026-05-06
- [x] Phase 3: Ontario Stats Ingestion (1/1 plan) — completed 2026-05-06
- [x] Phase 4: Prune Cron + Operations Hardening (1/1 plan, 4 tasks) — completed 2026-05-06

Phase artifacts archived to `milestones/v2.0-phases/`. Full roadmap detail: `milestones/v2.0-ROADMAP.md`.

</details>

<details>
<summary>✅ v1.0.1 Approval Dashboard (Phases 1-11) — DEPRECATED by v2.0 pivot</summary>

11 phases shipped between 2026-03-30 and 2026-04-25 covering FastAPI backend, React approval dashboard, Twitter Agent (later deprecated), Senior Agent (later deprecated), Instagram Agent (later deprecated), Content Agent + 6 sub-agents, dashboard views + WhatsApp digest, agent execution polish, and content preview / rendered images. Source files retained as dead code per v2.0 retirement intent. Full archive: `milestones/v1.0.1/ROADMAP.md`.

</details>

<details>
<summary>✅ v2.1 Three-Tab Content Engine + UI Polish (Phases 5-8) — SHIPPED 2026-05-19</summary>

- [x] Phase 5: Foundation — Tabs + DB + Backend Stubs (5/5 plans) — completed 2026-05-19
- [x] Phase 6: Content Calendar (5/5 plans) — completed 2026-05-19
- [x] Phase 7: Weekly Viral Sweeper (6/6 plans) — completed 2026-05-19 (X-API pivot from Reddit per 07-CONTEXT.md D-03)
- [x] Phase 8: UI Polish + Dead-Code Strip (4/4 plans) — completed 2026-05-19

Full roadmap detail snapshot in `milestones/v3.0-ROADMAP.md` (v2.1 phases were never archived separately — captured in the v3.0 close snapshot).

</details>

<details>
<summary>✅ v3.0 Multi-Tenant Dashboards — Juno Industries Onboarding (Phases 9-10) — SHIPPED 2026-05-19</summary>

- [x] Phase 9: Multi-Tenant Foundation (5/5 plans, verifier 10/10 PASS) — completed 2026-05-19
- [x] Phase 10: Juno Defence News Funnel (5/5 plans, verifier 10/10 PASS, voice UAT + visual QA APPROVED) — completed 2026-05-19

Full roadmap detail: `milestones/v3.0-ROADMAP.md`. Audit verdict `tech_debt` (20/20 reqs satisfied; 8 non-blocking follow-ups for v3.0.1/v3.1+).

</details>

---

## Progress

| Phase | Milestone | Plans | Status | Completed |
|-------|-----------|-------|--------|-----------|
| 1. Gold News Card + Web Feed | v2.0 | 6/6 | Complete | 2026-05-06 |
| 2. Ontario Law Ingestion | v2.0 | 1/1 | Complete | 2026-05-06 |
| 3. Ontario Stats Ingestion | v2.0 | 1/1 | Complete | 2026-05-06 |
| 4. Prune Cron + Ops Hardening | v2.0 | 1/1 | Complete | 2026-05-06 |
| 5. Foundation — Tabs + DB + Backend Stubs | v2.1 | 5/5 | Complete | 2026-05-19 |
| 6. Content Calendar | v2.1 | 5/5 | Complete | 2026-05-19 |
| 7. Weekly Viral Sweeper | v2.1 | 6/6 | Complete | 2026-05-19 |
| 8. UI Polish + Dead-Code Strip | v2.1 | 4/4 | Complete | 2026-05-19 |
| 9. Multi-Tenant Foundation | v3.0 | 5/5 | Complete | 2026-05-19 |
| 10. Juno Defence News Funnel | v3.0 | 5/5 | Complete | 2026-05-19 |

---

## Next Milestone

Not yet scoped. Run `/gsd:new-milestone` to start the next milestone cycle (questioning → research → requirements → roadmap).

Candidate v3.0.1 cleanup items (filed by v3.0 audit, see [`milestones/v3.0-MILESTONE-AUDIT.md`](milestones/v3.0-MILESTONE-AUDIT.md)):

- REQUIREMENTS.md DEF-01..07 traceability table refresh (Scaffolded → Complete) — DONE in cleanup
- 12:05 PT Canadian Procurement UX decision (operator preference: both daily fires produce a brief; +$1/mo SerpAPI)
- `run_juno_daily_summary` double-definition cleanup (`daily_summary.py:762` shadowed by `:1150`)
- VALIDATION.md frontmatter flag updates (`nyquist_compliant: true` for Phase 9 + Phase 10)
- Skydio Pydantic ValidationError logging + Haiku temperature tuning

Candidate v3.1+ features:

- Juno Content Calendar (Tab 2) — JUNO-CAL-v31
- Juno Weekly Viral Sweeper (Tab 3) — JUNO-SWEEP-v31; lock slot `juno_weekly_sweeper=1021` already reserved
- Per-company branding — TENANT-BRAND-v31 (Juno currently shows "Seva Mining" wordmark)
- Last-visited tenant for bare `/` redirect — Zustand `lastVisitedCompany` already populated as switch-action byproduct
- Per-tenant Anthropic API key
- Tier-2 defence RSS feeds — if Tier-1 signal insufficient after 2-4 weeks production

Candidate v3.2+ (scaling beyond N=2 tenants):

- `companies` DB table — TENANT-N-v32
