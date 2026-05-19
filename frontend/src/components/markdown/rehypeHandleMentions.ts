import type { Root, Text, Element, ElementContent } from 'hast'
import { visit } from 'unist-util-visit'

/**
 * Phase 8 — UI-05 reframe (D-02).
 *
 * Walks the hast tree and wraps bare `@handle` text occurrences into
 * `<a href="https://x.com/{handle}">@{handle}</a>` elements. The companion
 * `MarkdownContent` component's `components.a` override then renders each
 * synthetic anchor as an `XHandlePill` (because its href matches X_HOST_RE).
 *
 * Skips:
 *   - text already inside an `<a>` (avoid double-wrap; the link itself flows
 *     through the components.a pill renderer)
 *   - text inside `<code>` (handles in code fences should remain literal)
 *
 * Run AFTER `rehypeSanitize` in the rehypePlugins array — sanitize is the
 * security boundary and must see content first (RESEARCH key finding #3).
 */

// X username constraint: 1-15 chars [A-Za-z0-9_].
// Negative-character-class prefix prevents matching email-like sequences
// (e.g. "user@domain") and avoids re-matching inside URLs already containing @.
const MENTION_RE = /(^|[^A-Za-z0-9_/@])(@([A-Za-z0-9_]{1,15}))/g

export function rehypeHandleMentions() {
  return (tree: Root) => {
    visit(tree, 'text', (node: Text, index, parent) => {
      if (!parent || index === undefined) return
      if (parent.type === 'element' && (parent as Element).tagName === 'a') return
      if (parent.type === 'element' && (parent as Element).tagName === 'code') return

      const value = node.value
      MENTION_RE.lastIndex = 0
      if (!MENTION_RE.test(value)) return
      MENTION_RE.lastIndex = 0

      const newChildren: ElementContent[] = []
      let lastIndex = 0
      let match: RegExpExecArray | null
      while ((match = MENTION_RE.exec(value)) !== null) {
        const [, prefix, full, handle] = match
        const matchStart = match.index + prefix.length
        if (matchStart > lastIndex) {
          newChildren.push({ type: 'text', value: value.slice(lastIndex, matchStart) })
        }
        newChildren.push({
          type: 'element',
          tagName: 'a',
          properties: { href: `https://x.com/${handle}` },
          children: [{ type: 'text', value: full }],
        })
        lastIndex = matchStart + full.length
      }
      if (lastIndex < value.length) {
        newChildren.push({ type: 'text', value: value.slice(lastIndex) })
      }

      ;(parent as Element).children.splice(index, 1, ...newChildren)
      return index + newChildren.length
    })
  }
}
