# Phase 6: Content Calendar - Context

**Gathered:** 2026-05-18
**Status:** Ready for planning

<domain>
## Phase Boundary

A clean, manual weekly-grid calendar where the operator types freeform plain-text notes directly into each day cell. **One text blob per date, max.** Auto-save on blur. No tags, no dialogs, no chip rendering, no AI helpers, no scheduling logic. This is a paper-planner replacement, not a content-management system.

Out of scope (deferred — see `<deferred>`): tag color coding, multi-item per day, click-to-edit dialogs, markdown rendering, "+ Add" hover buttons, "+N more" overflow handling, drag-and-drop reschedule, date-dropdown reschedule.

</domain>

<decisions>
## Implementation Decisions

### Editing Model
- **D-01:** Each day cell IS a textarea — direct in-cell editing. No dialog, no popover, no slide-over.
- **D-02:** **One row per date, maximum.** The DB allows many rows per date but the app enforces single-row-per-date semantics. If the user already typed for Tuesday and types again, it's a PATCH to the existing row, not a new POST.
- **D-03:** **Auto-save on blur** (when textarea loses focus). No Save button. No save-on-Enter. Save is silent on success; a sonner error toast surfaces only on failure.
- **D-04:** **Plain text only.** Line breaks preserved (`whitespace-pre-wrap`). No markdown rendering, no react-markdown, no preview toggle.
- **D-05:** **Clearing all text deletes the row.** If the user blurs out with an empty textarea (`text.trim() === ""`) and a row exists for that date, fire DELETE. Prevents accumulation of empty rows.

### Schema Reconciliation (planner decides exact mechanism)
- **D-06:** The Phase 5 `calendar_items` schema is reused as-is, with the user's text body stored in `notes_md` (already nullable TEXT, no size limit). The `tag` column stays null forever. The `title` column needs reconciliation — planner picks ONE of:
  - **Option A (cleanest):** Migration 0013 makes `title` nullable AND adds `UNIQUE(date)` constraint. Single-row-per-date enforced at DB level.
  - **Option B (no migration):** App writes a synthetic `title` value (e.g. first 80 chars of body) on every save; uniqueness enforced at app layer via "find row by date → PATCH or POST" logic.
  - Recommendation: **Option A**. The migration is trivial (2 ALTER statements), enforces the invariant at DB level, and makes the API contract simpler (upsert-by-date is a natural primary-key-ish flow).

### Grid & Navigation (standard calendar UX, no surprises)
- **D-07:** 7-column **Mon–Sun ISO week** grid (matches FEATURES.md recommendation).
- **D-08:** Prev/next-week arrow navigation + a "Today" jump button. Default view is the current week (LA local time, consistent with the rest of the system).
- **D-09:** Today's cell highlighted with `ring-2 ring-amber-500 bg-amber-500/5` (matches v2.1 amber-500 design system).

### Data Layer
- **D-10:** TanStack Query with **optimistic mutations** + `onMutate` snapshot / `onError` rollback / `onSettled` invalidation — required to make auto-save feel instant.
- **D-11:** `staleTime: 0`, `refetchOnWindowFocus: false` on `useCalendar()` (calendar is user-mutated; no stale tolerance, but no auto-refetch on tab switching either).
- **D-12:** `GET /calendar?start=&end=` returns items in `date ASC` order; `start`/`end` are `datetime.date` Pydantic fields parsed from `"YYYY-MM-DD"` strings (NEVER `datetime` — TZ off-by-one risk on Railway UTC). Same constraint applies to all date round-tripping.

### Claude's Discretion
- **Save indicator UX:** Silent-success / error-toast-only is the default. If the planner wants to add a subtle "Saving..." → "Saved ✓" inline indicator that fades after 1s, that's fine but not required.
- **Empty-state placeholder:** Per-cell faint placeholder text (e.g. "—" or empty) is fine; planner picks.
- **Day-cell height behavior:** Planner picks between auto-expand (uneven grid) vs fixed-height-with-internal-scroll. Recommended: fixed `min-h-32` with auto-grow up to a cap (e.g. `max-h-64`) and internal `overflow-y-auto` past the cap, so the grid stays visually balanced but doesn't truncate.
- **Validation rule for "delete on clear":** The exact debounce/blur logic is planner-decided. Simplest correct behavior: on blur, if textarea is non-empty → POST or PATCH; if empty AND a row exists → DELETE; if empty AND no row exists → no-op.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Domain & Architecture
- `.planning/research/ARCHITECTURE.md` — "Database Layer" (`calendar_items` DDL — locked in Phase 5 migration 0011), "Backend / API Layer" (calendar router + Pydantic schemas — adapt for simplified scope), "Dual-Model Parity" (model files already created in Phase 5)
- `.planning/research/FEATURES.md` §"CONTENT CALENDAR UX — Detailed Findings" — week-start convention, today-highlight pattern, drag-and-drop deferral rationale. **NOTE:** Tag color map and chip overflow guidance in this doc are NOW OUT OF SCOPE per user decision — ignore those subsections.
- `.planning/research/PITFALLS.md` — TZ off-by-one risks (DATE vs DateTime), optimistic-rollback gotchas. P1, P2, P3, P4, P5 from the Phase 6 ROADMAP entry are still load-bearing.

### Phase Inputs
- `.planning/phases/05-foundation-tabs-db-backend-stubs/05-04-SUMMARY.md` — Phase 5 stub router that this phase replaces
- `.planning/phases/05-foundation-tabs-db-backend-stubs/05-05-SUMMARY.md` — frontend tab shell `/calendar` page that this phase fills in
- `backend/alembic/versions/0011_add_calendar_items.py` — locked DDL the planner must work around
- `backend/app/models/calendar_item.py` + `scheduler/models/calendar_item.py` — existing SQLAlchemy models
- `frontend/src/pages/ContentCalendarPage.tsx` — current "Coming soon" stub that gets replaced

### Reusable Code Assets (from codebase scout)
- `frontend/src/components/ui/textarea.tsx` — shadcn Textarea primitive (the core of every day cell)
- `frontend/src/components/ui/button.tsx`, `dialog.tsx` (won't use Dialog given direct editing), `badge.tsx`, `sonner.tsx` (error toast)
- `frontend/src/components/settings/ScheduleTab.tsx` and `KeywordsTab.tsx` — established TanStack mutation pattern with optimistic updates to mirror
- `frontend/src/hooks/useApprove.ts` — `useMutation` shape to mirror for `useCreateCalendarItem` / `useUpdateCalendarItem` / `useDeleteCalendarItem`
- `frontend/src/api/queue.ts` and `summaries.ts` — `apiClient` usage pattern for new `calendar.ts` API module
- `date-fns` (already in package.json, used in `SummaryCard.tsx`, `DigestPage.tsx`) — for Mon-Sun week boundary computation, "today" detection, prev/next nav

### Requirements Rescoping (planner must update REQUIREMENTS.md)
The original CAL-01..CAL-10 requirements in `.planning/REQUIREMENTS.md` assume the elaborate spec (chips, tags, dialogs). Several need rewording to reflect the simplified scope:
- **KEEP unchanged:** CAL-01 (GET /calendar), CAL-04 (DELETE), CAL-05 (7-col Mon-Sun grid, prev/next, today jump), CAL-09 (optimistic mutations), CAL-10 (`staleTime: 0`, no auto-refetch)
- **REPHRASE:** CAL-02 (POST — drop `tag`, body is just `{date, body}`), CAL-03 (PATCH — drop `tag`, body is just `{body}`)
- **DROP/REPLACE:** CAL-06 (no tag color chips — replace with "render text body as `whitespace-pre-wrap` inside day cell"), CAL-07 (no "+ Add" hover button — replace with "clicking the cell focuses the textarea"), CAL-08 (no shadcn Dialog — replace with "in-cell textarea with auto-save on blur")

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `shadcn/textarea.tsx` — the core editing primitive for every day cell
- `sonner` (already wired in `main.tsx`) — error toast surface for failed auto-save
- `date-fns` — week boundary math, today detection, prev/next nav
- TanStack Query + apiClient pattern from `useApprove`, `useQueue`, settings tabs — direct precedent for `useCalendar()` hook and mutations
- `apiClient` in `frontend/src/api/client.ts` — JWT auth + Bearer header handling for the new `calendar.ts` module

### Established Patterns
- All settings tabs (ScheduleTab, KeywordsTab, ScoringTab, NotificationsTab) use `useMutation` with optimistic updates — planner should mirror this shape rather than invent a new one.
- Backend routers follow a consistent shape: `APIRouter(prefix=..., tags=..., dependencies=[Depends(get_current_user)])`. The Phase 5 stub `backend/app/routers/calendar.py` already has this skeleton — Phase 6 fleshes it out.
- Pydantic schemas live in `backend/app/schemas/` — `calendar.py` schema module needs to be created (does not yet exist).
- Frontend pages live in `frontend/src/pages/`. ContentCalendarPage.tsx exists as a stub and gets replaced.

### Integration Points
- `backend/app/main.py` already includes `calendar.router` (Phase 5 wiring) — no main.py changes needed.
- `frontend/src/App.tsx` already routes `/calendar` to `ContentCalendarPage` under `TabbedDashboard` (Phase 5) — no App.tsx changes needed.
- `frontend/src/components/layout/TabbedDashboard.tsx` provides the outer chrome — Phase 6 only fills in the page body.

</code_context>

<specifics>
## Specific Ideas

User's framing in their own words: "I dont need it to tag really anything. I just simply want a calendar layout that I can type into each day so I know my content schedule. Its as simple as that. I dont need the content calendar to schedule or create anything for me, I will do it myself. I just want a clean Ui calendar that I can type text as a box into for each day."

This phrasing should anchor every implementation decision. When in doubt, choose the simpler, more paper-planner-like option. The operator does NOT want this tool to be smart — they want it to get out of the way.

</specifics>

<deferred>
## Deferred Ideas

Originally in v2.1 Phase 6 spec, now dropped per user scope reduction. Captured here so they aren't lost:

- **CAL-TAGS-v22:** Tag enum + color-coded chip rendering (thread/video/podcast/tweet/idea/other). User explicitly does not want this. Revisit only if the user asks for visual differentiation later.
- **CAL-MULTI-ITEM-v22:** Multiple discrete items per day (each with its own title/tag). User chose single-text-blob model. Revisit only if the user reports the single-blob model feels cramped.
- **CAL-DIALOG-v22:** shadcn Dialog edit modal with title input + date dropdown + tag dropdown + markdown notes textarea. Replaced by direct in-cell textarea editing.
- **CAL-OVERFLOW-v22:** "+N more" overflow badge when a day has >3 items. Moot under single-text-blob model.
- **CAL-MARKDOWN-v22:** Markdown rendering of notes via `react-markdown`. User chose plain text. Revisit if the operator wants formatting for links/bold/lists.
- **CAL-DnD-v22:** Drag-and-drop calendar reschedule via `@dnd-kit/core`. Already deferred to v2.2 in ROADMAP. Stays deferred — and is now also moot since each day owns at most one text blob (there's nothing to "drag" between days; the operator can just cut/paste text).
- **CAL-WHATSAPP-v22:** Morning WhatsApp ping listing items planned for today. Already deferred to v2.2 in ROADMAP. Stays deferred.

</deferred>

---

*Phase: 06-content-calendar*
*Context gathered: 2026-05-18*
