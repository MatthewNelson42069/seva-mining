# Phase 6: Content Calendar - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in `06-CONTEXT.md` — this log preserves the alternatives considered.

**Date:** 2026-05-18
**Phase:** 06-content-calendar
**Areas discussed:** Scope simplification (user-initiated), Day-content structure, Save trigger, Format

---

## Gray Area Selection (initial offer)

| Option | Description | Selected |
|--------|-------------|----------|
| Tag enum reconciliation (CRITICAL) | DB enum vs FEATURES.md color map mismatch (tweet/other vs image/article) | (made moot by simplification) |
| Reschedule date picker UX | HTML native / 7-day select / 28-day select / shadcn calendar | (made moot by simplification) |
| Delete confirmation + error feedback | No confirm vs confirm; success-toast vs error-only | (made moot by simplification) |
| Chip content density + markdown notes preview | Title-only vs title+tag; ellipsize/wrap; hover preview | (made moot by simplification) |

**User's response:** Bypassed all four options and stated: *"I dont need it to tag really anything. I just simply want a calendar layout that I can type into each day so I know my content schedule. Its as simple as that. I dont need the content calendar to schedule or create anything for me, I will do it myself. I just want a clean Ui calendar that I can type text as a box into for each day."*

**Effect:** All four pre-selected gray areas collapsed into "drop the elaborate spec and ship a paper-planner-like grid." Three follow-up questions issued to nail down the simplified scope.

---

## Day Content Structure

| Option | Description | Selected |
|--------|-------------|----------|
| One freeform text per day (Recommended) | Day cell IS a textarea; user types paragraphs / lists / whatever; 1 row per date | ✓ |
| Multiple items per day | Stack of separate items per cell; "+ Add" button; each item own DB row | |

**User's choice:** One freeform text per day.
**Notes:** Aligns with paper-planner mental model. Simplifies UI and API surface significantly — no chip rendering, no overflow handling, no item-level mutations.

---

## Save Trigger

| Option | Description | Selected |
|--------|-------------|----------|
| Auto-save on blur (Recommended) | Save silently on focus loss; error toast only on failure | ✓ |
| Explicit Save button per cell | Click Save to commit; predictable but cluttered | |
| Save on Enter / Cmd+S | Keyboard-triggered save; no button | |

**User's choice:** Auto-save on blur.
**Notes:** Matches Notion / Google Docs feel. Sonner toast already wired for error surface.

---

## Format

| Option | Description | Selected |
|--------|-------------|----------|
| Plain text only (Recommended) | What you type is what you see; line breaks preserved | ✓ |
| Markdown rendering | react-markdown render on blur; raw edit on focus | |

**User's choice:** Plain text only.
**Notes:** Matches "I just want to type text" framing. `whitespace-pre-wrap` for line break preservation. Drops `react-markdown` dependency for this phase even though it's already in `package.json` (still used elsewhere for `gold_news_md`, etc.).

---

## Wrap-up

| Option | Description | Selected |
|--------|-------------|----------|
| Looks good — write context (Recommended) | Sufficient signal; write CONTEXT.md and route to plan-phase | ✓ |
| Save indicator UX | Further discussion on Saving/Saved status indicator | |
| Empty-state placeholder text | Further discussion on day-cell placeholder | |
| Day-cell height behavior | Further discussion on cell overflow | |

**User's choice:** Looks good — write context.
**Notes:** Save indicator + placeholder + cell-height are left to Claude's discretion in CONTEXT.md with recommended defaults.

---

## Claude's Discretion

The following items were noted as planner-decided rather than user-decided:

- Save indicator UX (silent-success default vs subtle "Saving..." → "Saved ✓" inline indicator)
- Empty-state placeholder text per cell
- Day-cell height behavior (fixed min-h with auto-grow vs uneven grid)
- Exact delete-on-clear blur logic (debounce, trim handling)
- Schema reconciliation mechanism (migration 0013 vs synthetic-title app-layer workaround — recommendation: migration)

## Deferred Ideas

Pulled out of Phase 6 scope and parked in `<deferred>` section of CONTEXT.md:

- Tag enum + color-coded chips (CAL-TAGS-v22)
- Multi-item per day (CAL-MULTI-ITEM-v22)
- shadcn Dialog edit modal (CAL-DIALOG-v22)
- "+N more" overflow badge (CAL-OVERFLOW-v22)
- Markdown rendering (CAL-MARKDOWN-v22)
- Drag-and-drop reschedule (CAL-DnD-v22 — was already deferred to v2.2)
- WhatsApp morning ping (CAL-WHATSAPP-v22 — was already deferred to v2.2)
