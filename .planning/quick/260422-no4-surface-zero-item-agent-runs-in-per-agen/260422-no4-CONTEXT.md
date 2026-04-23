# Quick Task 260422-no4: Surface zero-item agent runs in per-agent queue UI - Context

**Gathered:** 2026-04-23
**Status:** Ready for planning
**Discuss mode:** Orchestrator pre-surfaced 6 gray areas with recommendations; user responded "yeah push it" — interpreted as "All clear / proceed with recommendations". Decisions below are locked.

<domain>
## Task Boundary

Surface zero-item agent runs in the per-agent queue UI so cron ticks are visibly distinguishable from "agent hasn't fired / is broken." Triggered by the user's ask:

> "Even if some of the agents runs dont find anything, for examples the quotes or gold media one, I still want it to say 'no content found' so I know it is working tomorrow"

Tomorrow = the 12:00 PT cron verification after the gmb fix + mfg rename + Railway deploy. Every cron tick must be visible in the UI — whether or not items were produced — so the user can distinguish "agent fired, passed 0 items" from "agent is broken / didn't fire."

**In scope:**
- `frontend/src/pages/PerAgentQueuePage.tsx` (and its test file)
- Render-logic only: `groupByRun` emits groups for ALL runs (even 0-items); the `items.length === 0` branch falls back to run-history when runs exist; keep `<EmptyState />` only for the genuine "agent never ran + queue empty" case.
- Uniform across all 7 sub-agents (breaking_news, threads, long_form, quotes, infographics, gold_media, gold_history).

**Out of scope:**
- Backend changes (API already returns `items_found` / `items_queued` / `notes` — no schema or endpoint work needed).
- No DB migrations.
- No new dependencies.
- No changes to `RunHeader` props API — extend it, don't break ink's timestamp fix or mfg's rename.
- Not fixing `notes` telemetry for the other 6 agents (gmb added it for sub_gold_media only; other agents may have null `notes` — UI tolerates this).

</domain>

<decisions>
## Implementation Decisions

### D-01 — Wording for the zero-items state
**Decision:** "No content found" (Recommended: A)

Rationale: User used this exact phrase verbatim in their ask. Matches their mental model. "No qualifying content this run" was more technically precise but the user's wording is clearer. "0 items queued" is bland and already shown on the non-zero RunHeader's right side — reusing that wording for zero would be confusing.

### D-02 — Telemetry surfacing for runs with structured `notes`
**Decision:** Inline muted subtitle under RunHeader (Recommended: A)

Rationale: Single-user internal tool — no mobile/hover concerns. The whole point of this fix is diagnostic visibility; burying telemetry in hover defeats the purpose. Format: `{x_candidates} candidates · {llm_accepted} accepted · {queued} queued` when notes are populated. When `notes` is null (i.e., the other 6 sub-agents that haven't been instrumented with gmb-style counters yet), skip the subtitle silently — don't render empty parens or placeholders.

**Field mapping (from gmb-added schema on sub_gold_media):**
- `x_candidates` → "candidates"
- `llm_accepted` → "accepted" (shortened from "accepted by LLM" for single-line readability)
- `compliance_blocked` → "blocked" (only show if > 0; skip in the common 0-case to keep the line short)
- `queued` → "queued"

**Graceful degradation:** if `notes` is JSON but missing some fields, show only the present ones joined with `·`. If `notes` is malformed JSON, treat as null.

### D-03 — Where zero-item runs render in the list
**Decision:** Inline with item-producing runs in chronological order (Recommended: A)

Rationale: Uniform timeline — user sees cron cadence at a glance. A sequence like "5 items, 0 items, 2 items across 3 runs" renders as 3 groups in chronological order, with the middle group showing "No content found" under its RunHeader. No special-case render modes. No collapsible sections.

### D-04 — When `items.length === 0` AND `runs.length === 0`
**Decision:** Keep `<EmptyState />` as-is (Recommended, no change)

Rationale: This genuinely represents "agent has never run" or "agent queue table is empty." Nothing to show. Leave the existing fallback untouched.

### D-05 — Top-of-page subtitle ("N pending") when items.length === 0
**Decision:** Leave as "0 pending" (Recommended, no change)

Rationale: The timeline below will show all the detail. Don't double-surface. Keep the page header minimal and stable.

### D-06 — Uniform across all 7 sub-agents vs. gated by agent type
**Decision:** Uniform across all 7 sub-agents (Recommended: A)

Rationale: Pure render-logic change, zero runtime cost, uniform UX across tabs. Agent-specific gating would introduce conditional logic and a confusing UX where some tabs show zero-run history and others don't.

### Claude's Discretion
- **Exact Tailwind classes / spacing** for the "No content found" line beneath RunHeader — implementer picks matching utility classes consistent with existing RunHeader style (`text-xs text-muted-foreground`). Keep vertical rhythm tight: likely one line, `py-1` or similar.
- **Component structure** — planner/executor decides whether to extend `RunHeader` with an optional `status` prop, or introduce a separate `EmptyRunRow` component and render it inline. Either is fine; prefer whichever yields the smaller diff.
- **Icon/glyph** — optional muted dot or dash to visually differentiate zero-item groups from item-producing ones. Implementer picks; skipping is also fine.
- **Test depth** — prioritize: (a) zero-item run renders with "No content found" label, (b) timeline interleaves zero and non-zero runs correctly, (c) `notes` telemetry subtitle renders when present and is omitted when null/malformed, (d) `items.length === 0` AND `runs.length > 0` case shows run history (not `<EmptyState />`).

</decisions>

<specifics>
## Specific Ideas

**Data contract (already live, no changes needed):**
- `AgentRunResponse` fields already returned by `getAgentRuns()`: `id`, `started_at`, `status`, `items_found`, `items_queued`, `notes` (string | null, JSON-encoded structured data for gold_media; null for others until retrofitted).
- `notes` schema for sub_gold_media (from debug-260422-gmb): `{"x_candidates": N, "llm_accepted": N, "compliance_blocked": N, "queued": N}`. Parse as JSON on frontend; if parse fails, treat as null.

**Existing styles to match (from `RunHeader` in PerAgentQueuePage.tsx lines 56-76):**
- Wrapper: `flex items-center gap-3 py-1`
- Text: `text-xs font-medium text-muted-foreground whitespace-nowrap` (the "Pulled from agent run at" label)
- Divider: `flex-1 border-t border-border`
- Right-side count: `text-xs text-muted-foreground shrink-0`

**Recent adjacent work to respect:**
- **quick-260422-ink:** Fixed RunHeader's timestamp fallback. Preserve the specific-timestamp behavior.
- **quick-260422-mfg:** `PerAgentQueuePage.test.tsx` modified — no `video_clip` strings allowed in new tests. Use `sub_gold_media` / `gold_media` / `GoldMediaPreview`.
- **debug-260422-gmb:** Added `notes` telemetry structure. This task consumes that data.

**Test harness:** `PerAgentQueuePage.test.tsx` uses vitest + @testing-library/react (existing patterns). Mock `useQueue` and `useQuery(['agent-runs', ...])` the same way existing tests do.

</specifics>

<canonical_refs>
## Canonical References

- `frontend/src/pages/PerAgentQueuePage.tsx` — the file being modified
- `frontend/src/pages/PerAgentQueuePage.test.tsx` — test file to extend
- `frontend/src/api/types.ts` — `AgentRunResponse` type definition
- `frontend/src/api/settings.ts` — `getAgentRuns()` function
- `frontend/src/components/shared/EmptyState.tsx` — existing empty-state component (leave untouched, still used for `items.length === 0` AND `runs.length === 0`)
- `.planning/debug/resolved/260422-gmb.md` — source of the `notes` structured schema (consumer contract)
- `.planning/quick/260422-ink-*/` — prior RunHeader timestamp fix (do not regress)
- `.planning/quick/260422-mfg-*/` — prior rename (zero-grep hygiene)

</canonical_refs>
