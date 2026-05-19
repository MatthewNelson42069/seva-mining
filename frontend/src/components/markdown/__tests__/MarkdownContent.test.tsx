// REDLINE: switch describe.skip -> describe in Wave 2 once MarkdownContent.tsx exists.
// Phase 8 — Plan 08-01 (Wave 0) RED-tests-first scaffolding for UI-05 pipeline.
//
// These tests describe the end-to-end markdown rendering pipeline:
//   1. [@handle](https://x.com/...) markdown links render as XHandlePill (D-04).
//   2. Bare @handle text inside paragraphs is wrapped into a pill by the rehype
//      plugin which synthesizes the x.com/{handle} href (D-02).
//   3. Non-X external links render as default <a>, NOT pills, and do NOT open
//      in a new tab (D-03: only x.com/twitter.com get new-tab treatment).
//   4. rehype-sanitize still runs first in the rehypePlugins chain and strips
//      dangerous tags like <script> (Research §Pattern 3 ordering guarantee).
//   5. @handle inside a code fence (`` `@jpow` ``) stays plain text — the
//      rehype plugin must skip text nodes whose parent is <code>.
//
// IMPORT STRATEGY: see XHandlePill.test.tsx — Vite resolves static imports at
// transform time, so we use dynamic `await import('../MarkdownContent')` inside
// each `it` body. Under `describe.skip` the `it` bodies never execute and the
// dynamic import never runs. Wave 2's redline: flip `describe.skip` -> `describe`
// AND ship `frontend/src/components/markdown/MarkdownContent.tsx`.
import { describe, it, expect } from 'vitest'
import { render } from '@testing-library/react'

// eslint-disable-next-line @typescript-eslint/no-explicit-any
type MarkdownContentModule = { MarkdownContent: (props: { content: string }) => any }

// Variable-path indirection defeats Vite's static import analysis. The plugin
// only inspects literal string arguments to `import()`; a variable forces
// runtime resolution. Under `describe.skip` the `it` bodies never execute, so
// this resolution never runs at collection time.
const MARKDOWN_CONTENT_MODULE_PATH = '../MarkdownContent'

describe.skip('MarkdownContent', () => {
  it('renders [@handle](https://x.com/jpow) as an XHandlePill', async () => {
    const { MarkdownContent } = (await import(/* @vite-ignore */ MARKDOWN_CONTENT_MODULE_PATH)) as MarkdownContentModule
    const md = 'Hat tip to [@jpow](https://x.com/jpow) for the call.'
    const { container } = render(<MarkdownContent content={md} />)
    const anchor = container.querySelector('a')
    expect(anchor).not.toBeNull()
    expect(anchor?.getAttribute('href')).toBe('https://x.com/jpow')
    expect(anchor?.className).toContain('font-mono')
  })

  it('wraps bare @handle text in a pill via rehypeHandleMentions', async () => {
    const { MarkdownContent } = (await import(/* @vite-ignore */ MARKDOWN_CONTENT_MODULE_PATH)) as MarkdownContentModule
    const md = 'Hat tip @jpow on the call.'
    const { container } = render(<MarkdownContent content={md} />)
    const anchors = container.querySelectorAll('a')
    expect(anchors.length).toBe(1)
    expect(anchors[0].getAttribute('href')).toBe('https://x.com/jpow')
    expect(anchors[0].className).toContain('font-mono')
  })

  it('renders non-X external link as a default anchor (NOT a pill)', async () => {
    const { MarkdownContent } = (await import(/* @vite-ignore */ MARKDOWN_CONTENT_MODULE_PATH)) as MarkdownContentModule
    const md = 'See [Bloomberg](https://bloomberg.com/x) for context.'
    const { container } = render(<MarkdownContent content={md} />)
    const anchor = container.querySelector('a')
    expect(anchor).not.toBeNull()
    expect(anchor?.getAttribute('href')).toBe('https://bloomberg.com/x')
    expect(anchor?.className ?? '').not.toContain('font-mono')
    // D-03: only x.com / twitter.com get new-tab treatment; other links stay in-tab.
    const target = anchor?.getAttribute('target')
    expect(target == null || target !== '_blank').toBe(true)
  })

  it('rehype-sanitize still strips dangerous tags', async () => {
    const { MarkdownContent } = (await import(/* @vite-ignore */ MARKDOWN_CONTENT_MODULE_PATH)) as MarkdownContentModule
    const md = '<script>alert(1)</script>safe text'
    const { container } = render(<MarkdownContent content={md} />)
    expect(container.innerHTML).not.toContain('<script>')
    expect(container.textContent ?? '').toContain('safe text')
  })

  it('does NOT wrap @handle inside code fences', async () => {
    const { MarkdownContent } = (await import(/* @vite-ignore */ MARKDOWN_CONTENT_MODULE_PATH)) as MarkdownContentModule
    const md = 'Here is `@jpow` in code.'
    const { container } = render(<MarkdownContent content={md} />)
    const code = container.querySelector('code')
    expect(code).not.toBeNull()
    // @jpow inside <code> must be plain text, not an anchor.
    expect(code?.textContent).toContain('@jpow')
    expect(code?.querySelector('a')).toBeNull()
  })
})
