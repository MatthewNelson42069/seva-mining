# Phase 9: Multi-Tenant Foundation - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-05-19
**Phase:** 09-multi-tenant-foundation
**Areas discussed:** Scheduler topology, AppHeader freeze treatment, `companies` DB table vs hardcoded list, URL + redirect + switcher UX bundle

---

## Gray Area Selection

User selected all 4 candidate gray areas for discussion.

| Gray Area | Description | Selected |
|-----------|-------------|----------|
| Scheduler topology | 3 distinct proposals from research wave — affects daily_summary cron shape + lock ID inventory + failure isolation | ✓ |
| AppHeader freeze treatment | Path A (lift freeze) vs Path B (sibling CompanyBar) + brand mark per-tenant behavior in v3.0 | ✓ |
| `companies` DB table vs hardcoded list | Migration scope vs source-of-truth for valid tenant IDs | ✓ |
| URL + redirect + switcher UX bundle | Tenant slugs, bare `/` redirect target, v2.x bookmark grace redirects, CompanySwitcher visual style | ✓ |

---

## Area 1: Scheduler Topology

### Q1 — Which scheduler topology for Phase 9?

| Option | Description | Selected |
|--------|-------------|----------|
| A. Single-cron-fanout | Zero new lock IDs. Daily_summary agent loops `for c in ACTIVE_COMPANIES` with per-company try/except. Simplest. Trade-off: tangled failure modes inside one job; one slow company blocks the next. | |
| B. Per-company jobs | Lock IDs 1020/1021 for Juno. Separate APScheduler jobs per company. True failure isolation. Trade-off: lock-ID inventory grows linearly. | ✓ |
| C. Per-tenant 100-ID blocks | Heaviest convention; scales to N>>2; CONVENTIONS.md rule + assertion sub-check. Trade-off: over-engineered for N=2. | |

**User's choice:** B. Per-company jobs (Recommended)
**Notes:** True APScheduler-level isolation; cleanest Railway logs; lock IDs scale linearly but fine for v3.0's N=2.

### Q2 — Stagger between Seva and Juno scheduler fires?

| Option | Description | Selected |
|--------|-------------|----------|
| 5-min stagger | Seva 07:00 PT (existing), Juno 07:05 PT. Spreads Anthropic API rate-limit pressure. | ✓ |
| No stagger (parallel) | Both at 07:00 PT. Simultaneous Sonnet calls — doubled rate-limit pressure. | |
| 10-min stagger | More conservative; Juno surfaces 10 min later. | |

**User's choice:** 5-min stagger (Recommended)
**Notes:** PITFALLS.md §3 mitigation; matches existing v2.0 + v2.1 cron stagger discipline.

### Q3 — Lock-ID allocation: reserve juno_weekly_sweeper slot now or later?

| Option | Description | Selected |
|--------|-------------|----------|
| Reserve both 1020 + 1021 in Phase 9 | Add both to JOB_LOCK_IDS; 1021 is slot-only (not registered). Saves future surgical edit. | ✓ |
| Only 1020 now; 1021 in v3.1+ | Phase 9 adds 1020 only; v3.1+ adds 1021 when Juno Sweeper lands. | |

**User's choice:** Reserve both 1020 + 1021 in Phase 9 (Recommended)
**Notes:** OPS-02 inventory cleaner; less future churn on worker.py.

---

## Area 2: AppHeader Freeze Treatment

### Q1 — AppHeader freeze treatment for Phase 9?

| Option | Description | Selected |
|--------|-------------|----------|
| Path A — Lift freeze, edit AppHeader | Document v3.0 milestone rationale; surgical 5-line insert between brand mark and Logout. v3.0 becomes new frozen baseline. | ✓ |
| Path B — Preserve freeze, sibling CompanyBar | AppHeader untouched; new CompanyBar.tsx rendered below AppHeader in its own sub-bar. | |

**User's choice:** Path A — Lift freeze, edit AppHeader (Recommended)
**Notes:** AppHeader becomes canonical home for switcher (Linear/Notion/Slack/Vercel convention). v3.0 baseline re-baselined at Phase 9 verification.

### Q2 — Brand mark + wordmark behavior in v3.0?

| Option | Description | Selected |
|--------|-------------|----------|
| Keep "Seva Mining" wordmark on both tenants in v3.0 | "S" amber square + "Seva Mining" wordmark stays on /juno/ pages. Per-company branding deferred to v3.1+ per REQUIREMENTS.md TENANT-BRAND-v31. | ✓ |
| Switch to neutral product name ("Dashboard") | Replace "Seva Mining" with neutral name. Less branded; conflicts with no-AppHeader-edit if Path B chosen. | |
| Per-company brand mark in v3.0 | Pull TENANT-BRAND-v31 into v3.0 scope. ~1-2 days extra work; needs Juno logo/color decisions. | |

**User's choice:** Keep "Seva Mining" wordmark on both tenants in v3.0 (Recommended)
**Notes:** Accepted v3.0 tech debt for speed. Awkward (seeing Seva wordmark on Juno page) but ships fast. Fix in v3.1.

---

## Area 3: `companies` DB Table vs Hardcoded List

### Q1 — Where lives the source of truth for valid tenant IDs?

| Option | Description | Selected |
|--------|-------------|----------|
| A. Hardcoded CHECK constraint + Python Literal | Alembic 0014 adds `CHECK company_id IN ('seva','juno')` + `ACTIVE_COMPANIES: Literal["seva","juno"]` in Python. DB-level safety + type-level safety; no extra table. Close in v3.2+. | ✓ |
| B. `companies` DB table now | Alembic 0014 creates `companies(id, display_name, created_at)` + FK from multi-tenant tables. Cleanest for future N. Heavier 0014 scope. | |
| C. Python-only config, no DB constraint | No CHECK, no companies table. Validation only in FastAPI dependency. Lightest weight; less safe. | |

**User's choice:** A. Hardcoded CHECK constraint + Python Literal (Recommended)
**Notes:** Best balance for v3.0's N=2 scope. Tech debt closed by v3.2+ when scaling beyond 2 tenants requires the `companies` table.

---

## Area 4: URL + Redirect + Switcher UX Bundle

### Q1 — Tenant URL slug + default landing for bare `/`?

| Option | Description | Selected |
|--------|-------------|----------|
| Short slugs + hardcoded /seva default | `/seva/` and `/juno/`. Bare `/` → `/seva/`. Simplest. | ✓ |
| Short slugs + last-visited default | `/seva/` and `/juno/`. Bare `/` reads `lastVisitedCompany` from Zustand persist. Linear/Notion pattern. | |
| Long slugs + hardcoded /seva default | `/seva-mining/` and `/juno-industries/`. More descriptive; longer URLs. | |

**User's choice:** Short slugs + hardcoded /seva default (Recommended)
**Notes:** Linear/Notion use short slugs. Last-visited deferred to v3.1+ (Zustand `lastVisitedCompany` still populated as switch-action byproduct).

### Q2 — v2.x bookmark grace redirects + CompanySwitcher visual style?

| Option | Description | Selected |
|--------|-------------|----------|
| Auto-redirect to /seva/* + segmented control | All unprefixed legacy URLs auto-redirect to /seva/*; CompanySwitcher is 2-button segmented control with active state amber-tinted. | ✓ |
| Auto-redirect to /seva/* + dropdown menu | Same redirects; dropdown menu instead of segmented (needs new shadcn primitive). | |
| 404 unprefixed legacy URLs + segmented control | No auto-redirect; force operator to update bookmarks. Stricter; breaks existing flow. | |
| Auto-redirect to /seva/* + Cmd+K palette | Same redirects; Cmd+K palette (no inline button). Power-user pattern; needs palette dep. | |

**User's choice:** Auto-redirect to /seva/* + segmented control (Recommended)
**Notes:** Smooth migration + visual clarity at N=2. No new shadcn primitives needed. Segmented control uses semantic CSS tokens from v2.1 Phase 8 (`--color-brand-accent[-hover/-subtle]`).

---

## Wrap-Up

| Option | Description | Selected |
|--------|-------------|----------|
| Ready — write CONTEXT.md | All 4 areas resolved; planner has enough to plan against. | ✓ |
| Explore one more area | Surface additional gray areas (login post-auth redirect, tab state across switch, etc.) | |

**User's choice:** Ready — write CONTEXT.md (Recommended)
**Notes:** Items left to Claude's discretion in CONTEXT.md: login post-auth redirect, tab state preservation across switch, scheduler/companies/juno/ skeleton in Phase 9, CI grep gate implementation, Zustand persist key naming.

---

## Claude's Discretion (captured for planner)

Items the discussion did NOT lock; planner picks:

1. **Login post-auth redirect target** — hardcoded `/seva/` (matches D-05) OR last-visited if `intended URL` was tenant-scoped (matches existing `<ProtectedRoute>` pattern). Recommended: existing pattern.
2. **Tab state preservation across company switch** — D-07 says preserve sub-path on switch; planner picks edge-case behavior when target sub-path doesn't exist for the new tenant.
3. **`scheduler/companies/juno/` module skeleton in Phase 9 OR write-to-DB-directly** — recommended: minimal skeleton (~30 lines) so Phase 10 is purely "fill the lists."
4. **CI grep gate implementation** — recommended: shell script `scripts/verify-tenant-isolation.sh` mirroring v2.1 grep scripts. Wired into Wave 0.
5. **Zustand `persist` middleware key naming** — `lastVisitedCompany` in the existing app-store key.

## Deferred Ideas (captured for v3.1+ phases)

- Per-company branding (logos, colors, wordmark) — TENANT-BRAND-v31
- `companies` DB table — TENANT-N-v32
- Last-visited tenant for bare `/` redirect — v3.1+
- Per-tenant Anthropic API key — defer per PITFALLS §5
- Cmd+K command palette for tenant switching — v3.1+
- Per-company RBAC — TENANT-RBAC-v32
- Real Juno content (Defence News + Canadian Procurement + World Events) — Phase 10 (DEF-01..10)
- Juno Calendar (Tab 2) + Juno Weekly Viral Sweeper (Tab 3) — JUNO-CAL-v31 + JUNO-SWEEP-v31
