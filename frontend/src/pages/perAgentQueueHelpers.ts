/** Helpers for PerAgentQueuePage (extracted to satisfy
 *  react-refresh/only-export-components — the rule requires page modules to
 *  export ONLY React components so Vite's HMR can fast-refresh them). Splitting
 *  the non-component export here keeps the page component file pure.
 *
 *  Imported by:
 *    - src/pages/PerAgentQueuePage.tsx
 *    - src/pages/PerAgentQueuePage.test.tsx
 */

/** Parse structured run telemetry added in debug-260422-gmb for sub_gold_media.
 *  Shape: {x_candidates, llm_accepted, compliance_blocked, queued}.
 *  Returns formatted subtitle string, or null if notes is absent/malformed/has no known fields.
 *  Format: "N candidates · N accepted · N queued" (blocked suppressed when 0 per D-02).
 */
export function parseRunNotes(notes: string | null | undefined): string | null {
  if (!notes) return null
  let parsed: unknown
  try {
    parsed = JSON.parse(notes)
  } catch {
    return null
  }
  if (!parsed || typeof parsed !== 'object') return null
  const n = parsed as Record<string, unknown>
  const parts: string[] = []
  if (typeof n.x_candidates === 'number') parts.push(`${n.x_candidates} candidates`)
  if (typeof n.llm_accepted === 'number') parts.push(`${n.llm_accepted} accepted`)
  if (typeof n.compliance_blocked === 'number' && n.compliance_blocked > 0) {
    parts.push(`${n.compliance_blocked} blocked`)
  }
  if (typeof n.queued === 'number') parts.push(`${n.queued} queued`)
  return parts.length > 0 ? parts.join(' · ') : null
}
