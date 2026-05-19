import { type ReactNode } from 'react'

interface XHandlePillProps {
  href: string
  children?: ReactNode
}

/**
 * Phase 8 — UI-05 reframe (D-01..D-04).
 *
 * Renders @handle as a monospace pill linked to https://x.com/{handle}.
 *
 * Visual contract (D-01 / UI-SPEC §Interaction States):
 *   - font-mono text-xs bg-zinc-800/60 px-2 py-0.5 rounded
 *   - border border-transparent so hover state doesn't cause 1px reflow
 *   - text-zinc-300 (WCAG AA contrast on zinc-800/60 over zinc-900 ≈ 7.2:1)
 *
 * Hover (D-03):
 *   - hover:border-amber-500/40 hover:text-amber-300 transition-colors
 *
 * Behavior (D-03):
 *   - target="_blank" rel="noopener noreferrer" — opens new tab safely
 */
export function XHandlePill({ href, children }: XHandlePillProps) {
  return (
    <a
      href={href}
      target="_blank"
      rel="noopener noreferrer"
      className="font-mono text-xs bg-zinc-800/60 text-zinc-300 px-2 py-0.5 rounded
                 border border-transparent transition-colors
                 hover:border-amber-500/40 hover:text-amber-300
                 focus:outline-none focus-visible:ring-2 focus-visible:ring-amber-500/40
                 focus-visible:ring-offset-1 focus-visible:ring-offset-zinc-900"
    >
      {children}
    </a>
  )
}
