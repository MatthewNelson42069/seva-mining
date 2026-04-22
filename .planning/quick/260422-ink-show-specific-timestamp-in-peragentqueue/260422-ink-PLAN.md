---
phase: quick-260422-ink
plan: 01
type: execute
wave: 1
depends_on: []
files_modified:
  - frontend/src/pages/PerAgentQueuePage.tsx
autonomous: true
requirements:
  - INK-01  # Widen agent_runs fetch window from 7 to 30 days
  - INK-02  # Replace bare "(earlier)" fallback with specific timestamp from newest item in no-run bucket

must_haves:
  truths:
    - "Threads tab never renders the bare string '(earlier)' in the RunHeader."
    - "When a draft group has no matching agent_run, the RunHeader shows 'Pulled from agent run at {h:mm a} · {MMM d}' using the newest item's created_at in that bucket."
    - "Matched-run groups render exactly as before (no visual regression)."
    - "Agent runs query fetches 30 days of runs instead of 7."
    - "Frontend lint, tsc, test, and build all pass clean."
  artifacts:
    - path: "frontend/src/pages/PerAgentQueuePage.tsx"
      provides: "PerAgentQueuePage with widened fetch window and specific-timestamp RunHeader fallback"
      contains: "getAgentRuns(tab.agentName, 30)"
  key_links:
    - from: "PerAgentQueueBody useQuery"
      to: "getAgentRuns"
      via: "days=30 argument (was 7)"
      pattern: "getAgentRuns\\(tab\\.agentName,\\s*30\\)"
    - from: "RunHeader"
      to: "newest item.created_at in no-run bucket"
      via: "fallbackTime prop OR resolved displayTime string passed by caller"
      pattern: "Pulled from agent run at"
---

<objective>
Fix the Threads tab RunHeader rendering `Pulled from agent run (earlier)` by (a) widening the `getAgentRuns` fetch window from 7 to 30 days so more drafts match real runs, and (b) replacing the bare `(earlier)` fallback with a specific timestamp derived from the newest item's `created_at` in the no-run bucket. Result: every RunHeader shows a real time + date, matching the Breaking News tab's format.

Purpose: Operators currently see inconsistent, low-signal headers on tabs with older drafts (Threads has pre-eoe-split drafts from before 2026-04-21). This replaces the confusing fallback with a specific, scannable timestamp.

Output: One modified file (`frontend/src/pages/PerAgentQueuePage.tsx`), one atomic commit on branch `quick/260422-ink-run-header-fallback-time`, all frontend gates green.
</objective>

<execution_context>
@$HOME/.claude/get-shit-done/workflows/execute-plan.md
@$HOME/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/STATE.md
@frontend/src/pages/PerAgentQueuePage.tsx
@frontend/src/pages/PerAgentQueuePage.test.tsx

<interfaces>
<!-- Key contracts extracted from codebase. Executor should use these directly. -->

From frontend/src/api/settings.ts (L53-58):
```typescript
export async function getAgentRuns(
  agentName?: string,
  days?: number,  // <-- SECOND PARAM IS DAYS, NOT ROW COUNT
): Promise<AgentRunResponse[]>
```

From frontend/src/pages/PerAgentQueuePage.tsx (current state):
```typescript
// groupByRun return type:
Array<{ run: AgentRunResponse | null; items: DraftItemResponse[] }>

// NO_RUN_KEY sentinel: '__no_run__' — group where run === null
// Items in each bucket are ordered DESC by created_at (inherited from queue sort),
// so items[0].created_at is the NEWEST item in the bucket.

// RunHeader current signature:
function RunHeader({ run }: { run: AgentRunResponse | null }): JSX.Element
// Renders: "Pulled from agent run at {h:mm a} · {MMM d}" when run is non-null,
//          "Pulled from agent run (earlier)" when run is null.  <-- THIS IS THE BUG.
```

Existing tests (frontend/src/pages/PerAgentQueuePage.test.tsx):
- Uses `vi.mock('@/api/settings', () => ({ getAgentRuns: vi.fn().mockResolvedValue([]) }))`.
- Mock returns empty array → current tests exercise the `showRunGroups === false` branch, NOT the RunHeader fallback path. No existing test will break. Adding a new test for the fallback is OPTIONAL but encouraged (see Task 1 action).
</interfaces>
</context>

<tasks>

<task type="auto" tdd="false">
  <name>Task 1: Widen runs window to 30 days and replace bare "(earlier)" fallback with specific newest-item timestamp</name>
  <files>frontend/src/pages/PerAgentQueuePage.tsx</files>

  <behavior>
    - On /agents/threads with drafts older than any run in the 30-day window, RunHeader renders "Pulled from agent run at {h:mm a} · {MMM d}" where the time is formatted from the newest item's created_at in the no-run bucket (NOT the string "(earlier)").
    - On /agents/breaking-news with matched runs, RunHeader renders exactly as before (no visual regression).
    - useQuery calls getAgentRuns(tab.agentName, 30) — second argument is 30, not 7.
    - Multiple groups on a page with matched runs sort by run.started_at DESC as before; the no-run group (if present) still renders last.
  </behavior>

  <action>
    Make the following changes in `frontend/src/pages/PerAgentQueuePage.tsx`. Do NOT touch any other file.

    **Change 1 — Widen fetch window (L101):**
    - Replace `getAgentRuns(tab.agentName, 7)` with `getAgentRuns(tab.agentName, 30)`.
    - Rationale: sub-agents produce at most a few dozen runs/month — trivial query cost, covers pre-eoe-split historical drafts (addresses INK-01).

    **Change 2 — Replace bare "(earlier)" fallback with specific timestamp (L56-70 `RunHeader` + L135-137 call site):**

    Pick the CLEANER of these two approaches (both acceptable):

    *Approach A — caller resolves displayTime (preferred for simplicity):*
    1. Change `RunHeader` signature to accept a resolved time string:
       ```typescript
       function RunHeader({
         displayTime,
         itemsQueued,
       }: {
         displayTime: string          // already formatted "h:mm a · MMM d"
         itemsQueued?: number | null  // optional queued count (only known for matched runs)
       }) {
         return (
           <div className="flex items-center gap-3 py-1">
             <span className="text-xs font-medium text-muted-foreground whitespace-nowrap">
               Pulled from agent run at {displayTime}
             </span>
             <div className="flex-1 border-t border-border" />
             {itemsQueued != null && (
               <span className="text-xs text-muted-foreground shrink-0">
                 {itemsQueued} queued
               </span>
             )}
           </div>
         )
       }
       ```
    2. At the call site (currently `<RunHeader run={group.run} />`), resolve the timestamp inline:
       ```typescript
       {groupByRun(items, runs).map((group, gi) => {
         const sourceDate = group.run
           ? new Date(group.run.started_at)
           : new Date(group.items[0].created_at)  // newest item in no-run bucket
         const displayTime = `${format(sourceDate, 'h:mm a')} · ${format(sourceDate, 'MMM d')}`
         return (
           <div key={gi} className="space-y-3">
             <RunHeader displayTime={displayTime} itemsQueued={group.run?.items_queued} />
             {group.items.map((item) => (
               <ContentSummaryCard key={item.id} item={item} />
             ))}
           </div>
         )
       })}
       ```
    3. Note: `group.items[0]` is the newest item because `items` arrive sorted DESC by `created_at` from `useQueue` (verify by reading `frontend/src/hooks/useQueue.ts` if uncertain — a 30-second read confirms). If for any reason `group.items` could be empty, guard with `group.items[0]?.created_at ?? new Date().toISOString()` — but `groupByRun` only creates a bucket when it pushes an item, so `items.length >= 1` is invariant and a guard is NOT required. Adding a defensive `?? new Date().toISOString()` is acceptable if it makes the executor more comfortable.

    *Approach B — optional fallbackTime prop:*
    - Add `fallbackTime?: string` prop to `RunHeader`. When `run` is null, render using `fallbackTime`. Caller computes `fallbackTime` from `group.items[0].created_at` the same way. Either works — prefer A (less branching inside the component).

    **String requirement (both approaches):** The emitted string MUST be `Pulled from agent run at {h:mm a} · {MMM d}` with NO conditional "(earlier)" branch anywhere. Grep `(earlier)` in the file after editing → must return zero hits. Grep `Pulled from agent run at` → must match unconditionally (not inside a ternary branching on `run`). This addresses INK-02.

    **Change 3 — Test coverage (RECOMMENDED, not strictly required):**
    Add one test case to `frontend/src/pages/PerAgentQueuePage.test.tsx` that:
    - Renders `/agents/threads` with `mockGetQueue` returning 1 draft whose `created_at` is `2026-04-01T17:30:00Z` (pre-window).
    - `getAgentRuns` mock returns `[]` (no runs in window).
    - Asserts the rendered header text matches `/Pulled from agent run at .* · .*/` and does NOT contain the substring `(earlier)`.
    - If adding the test would widen scope beyond a single file, SKIP it — the grep assertions in <verify> are sufficient to prove the fix.

    **What NOT to do:**
    - Do NOT modify `frontend/src/api/settings.ts` — the `days` parameter already flows through correctly.
    - Do NOT modify the backend `/agent-runs` endpoint or any DB query.
    - Do NOT change `groupByRun`'s bucketing logic or sort order (matched groups still lead, no-run group still trails).
    - Do NOT add new dependencies.
    - Do NOT change `ContentSummaryCard`, `EmptyState`, or any other imported component.
    - Do NOT touch other pages.
  </action>

  <verify>
    <automated>cd /Users/matthewnelson/seva-mining &amp;&amp; grep -n "getAgentRuns(tab.agentName, 30)" frontend/src/pages/PerAgentQueuePage.tsx &amp;&amp; ! grep -n "(earlier)" frontend/src/pages/PerAgentQueuePage.tsx &amp;&amp; grep -n "Pulled from agent run at" frontend/src/pages/PerAgentQueuePage.tsx &amp;&amp; pnpm -C frontend lint &amp;&amp; pnpm -C frontend tsc --noEmit &amp;&amp; pnpm -C frontend test --run &amp;&amp; pnpm -C frontend build</automated>
  </verify>

  <done>
    - `frontend/src/pages/PerAgentQueuePage.tsx` contains `getAgentRuns(tab.agentName, 30)`.
    - `frontend/src/pages/PerAgentQueuePage.tsx` contains zero occurrences of the literal string `(earlier)`.
    - `frontend/src/pages/PerAgentQueuePage.tsx` emits `Pulled from agent run at` unconditionally (not inside a `run ? ... : ...` ternary).
    - `pnpm -C frontend lint` exits 0 with no new warnings.
    - `pnpm -C frontend tsc --noEmit` exits 0.
    - `pnpm -C frontend test --run` exits 0 (all existing tests still pass; new test optional).
    - `pnpm -C frontend build` exits 0.
    - Single atomic commit on branch `quick/260422-ink-run-header-fallback-time` with message like `fix(frontend): show specific timestamp in PerAgentQueuePage RunHeader fallback`.
    - Branch NOT pushed (orchestrator FF-merges + pushes after user review).
  </done>
</task>

</tasks>

<verification>
Run the same command chain from <verify> above. All seven checks must pass:
1. `getAgentRuns(tab.agentName, 30)` present.
2. Literal `(earlier)` absent.
3. `Pulled from agent run at` present (and unconditional).
4. `pnpm -C frontend lint` clean.
5. `pnpm -C frontend tsc --noEmit` clean.
6. `pnpm -C frontend test --run` green.
7. `pnpm -C frontend build` succeeds.

Manual smoke (optional, operator already saw the bug — re-verify only if uncertain):
- `pnpm -C frontend dev`, load `/agents/threads`, confirm no `(earlier)` string appears and the Threads tab header format matches Breaking News.
</verification>

<success_criteria>
- All seven verification checks pass.
- Threads tab's RunHeader fallback now shows `Pulled from agent run at {h:mm a} · {MMM d}` using the newest item's `created_at` in the no-run bucket.
- Matched-run groups (Breaking News and most Threads runs within 30 days) render identically to before.
- No backend, API, or DB changes. No changes to any file other than `frontend/src/pages/PerAgentQueuePage.tsx` (and optionally the existing test file if a new test was added).
- Single atomic commit on `quick/260422-ink-run-header-fallback-time`. Branch not pushed.
</success_criteria>

<output>
After completion, create `.planning/quick/260422-ink-show-specific-timestamp-in-peragentqueue/260422-ink-SUMMARY.md` summarizing:
- What changed (bullet list of diffs in `PerAgentQueuePage.tsx`).
- Chosen approach (A vs B from Task 1 action).
- Verification gate results (all 7 green).
- Commit SHA.
- Whether a test was added (and which describe/it block).
</output>
