# Roadmap: Seva Mining

## Milestones

- ✅ **v1.0.1 — Approval Dashboard (deprecated by v2.0 pivot)** — Phases 1-11, shipped 2026-04-25 → archive: [`milestones/v1.0.1/ROADMAP.md`](milestones/v1.0.1/ROADMAP.md)
- ✅ **v2.0 — Daily Summary Feed** — Phases 1-4 (reset numbering), shipped 2026-05-06 → archive: [`milestones/v2.0-ROADMAP.md`](milestones/v2.0-ROADMAP.md)
- ✅ **v2.1 — Three-Tab Content Engine + UI Polish** — Phases 5-8 (project-wide counter continues), shipped 2026-05-19 → archive in [`milestones/v3.0-ROADMAP.md`](milestones/v3.0-ROADMAP.md) (snapshot at v3.0 close includes v2.1 phase details — v2.1 was never archived separately before v3.0 started)
- ✅ **v3.0 — Multi-Tenant Dashboards (Juno Industries Onboarding)** — Phases 9-10, shipped 2026-05-19 → archive: [`milestones/v3.0-ROADMAP.md`](milestones/v3.0-ROADMAP.md) (audit: [`milestones/v3.0-MILESTONE-AUDIT.md`](milestones/v3.0-MILESTONE-AUDIT.md))
- ✅ **v3.0.1 — v3.0 Audit Cleanup Bundle** — Phase 11, shipped 2026-05-20 (verifier 5/5 PASS)
- ✅ **v3.1 — Juno Feature Parity + Branding** — Phases 12-16, shipped 2026-05-21 → archive: [`milestones/v3.1-ROADMAP.md`](milestones/v3.1-ROADMAP.md) (audit: [`milestones/v3.1-MILESTONE-AUDIT.md`](milestones/v3.1-MILESTONE-AUDIT.md))

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

<details>
<summary>✅ v3.0.1 v3.0 Audit Cleanup Bundle (Phase 11) — SHIPPED 2026-05-20</summary>

- [x] Phase 11: Audit Cleanup Bundle (5/5 plans, verifier 5/5 PASS; `JUNO_CRON_ENABLED=true` flipped in Railway 2026-05-20) — completed 2026-05-20

Full roadmap detail snapshot in this file under "v3.0.1" section (the v3.0.1 roadmap was inlined rather than archived to a separate file since it was a single-phase milestone). Milestone audit recap in `MILESTONES.md`.

</details>

---

<details>
<summary>✅ v3.1 Juno Feature Parity + Branding (Phases 12-16) — SHIPPED 2026-05-21</summary>

- [x] Phase 12: Per-tenant Anthropic API Key (3/3 plans) — completed 2026-05-20
- [x] Phase 13: Per-company Branding (3/3 plans, operator visual QA 10/10 PASS) — completed 2026-05-20
- [x] Phase 14: Juno Content Calendar — Tab 2 (1/1 plan) — completed 2026-05-20
- [x] Phase 15: Juno Weekly Viral Sweeper — Tab 3 (7/7 plans, operator voice UAT APPROVED) — completed 2026-05-21
- [x] Phase 16: v3.1 Audit Cleanup Bundle (5/5 plans, verifier PASS) — completed 2026-05-21

Full roadmap detail: `milestones/v3.1-ROADMAP.md`. Audit verdict: `passed` (25/25 reqs, 7/7 E2E flows WIRED, 0 v3.1-introduced tech debt) → `milestones/v3.1-MILESTONE-AUDIT.md`.

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
| 11. v3.0 Audit Cleanup Bundle | v3.0.1 | 5/5 | Complete | 2026-05-20 |
| 12. Per-tenant Anthropic API Key | v3.1 | 3/3 | Complete   | 2026-05-20 |
| 13. Per-company Branding | v3.1 | 3/3 | Complete   | 2026-05-20 |
| 14. Juno Content Calendar (Tab 2) | v3.1 | 1/1 | Complete   | 2026-05-20 |
| 15. Juno Weekly Viral Sweeper (Tab 3) | v3.1 | 7/7 | Complete   | 2026-05-21 |
| 16. v3.1 Audit Cleanup Bundle | v3.1 | 5/5 | Complete   | 2026-05-21 |

---

## Next Milestone

v3.2+ scope candidates (deferred from v3.1 planning or surfaced during v3.1 execution):

- **TENANT-N-v32** — `companies` DB table replacing hardcoded `CHECK company_id IN ('seva','juno')` constraint; scales beyond N=2 tenants
- **DEF-TIER2-v3X** — Tier-2 defence RSS feeds (Defense Daily, Inside Defense, National Defense Magazine, Defense Industry Daily, Shephard, Defense One); decision deferred pending 2-4 weeks of Tier-1 production signal data
- **TENANT-VISITED-v31-redux** — Last-visited tenant for bare `/` redirect; Zustand `lastVisitedCompany` already populated as switch-action byproduct in Phase 9; may opportunistically land in v3.1 Phase 13 if budget allows
- **OPS-DASH-v3X** — Per-tenant cost dashboard (read Anthropic + SerpAPI usage by tenant via the per-tenant key separation from Phase 12); useful operator tooling but not a v3.1 deliverable
- **Sweeper system-prompt iteration** — if v3.1 Phase 15 voice UAT or production-data refusal rate surfaces issues with `DEFENCE_SWEEPER_SYSTEM_PROMPT`, iterate in v3.2
