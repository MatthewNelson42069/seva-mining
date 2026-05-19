// REDLINE: switch describe.skip -> describe in Wave 2 once rehypeHandleMentions.ts exists.
// Phase 8 — Plan 08-01 (Wave 0) RED-tests-first scaffolding for the rehype plugin.
//
// These tests drive the plugin against synthetic hast trees directly, NOT
// through react-markdown. This isolates the AST transformation contract from
// react-markdown's component renderer (which is exercised in MarkdownContent.test.tsx).
//
// Contracts captured here (08-RESEARCH §Pattern 3):
//   1. A bare @handle text node inside <p> is split into [text(prefix), <a>@handle</a>, text(suffix)].
//   2. @handle already inside an <a> is NOT double-wrapped.
//   3. @handle inside <code> is NOT wrapped (handles in code blocks stay literal).
//   4. Multiple @handles in one text node are all wrapped and surrounding text is preserved.
//
// IMPORT STRATEGY: see XHandlePill.test.tsx — Vite resolves static imports at
// transform time, so we use dynamic `await import('../rehypeHandleMentions')`
// inside each `it` body. Under `describe.skip` the `it` bodies never execute and
// the dynamic import never runs. Wave 2's redline: flip `describe.skip` -> `describe`
// AND ship `frontend/src/components/markdown/rehypeHandleMentions.ts`.
import { describe, it, expect } from 'vitest'
import type { Root } from 'hast'

type RehypeTransformer = (tree: Root) => Root | void | undefined
type RehypeHandleMentionsModule = { rehypeHandleMentions: () => RehypeTransformer }

// Variable-path indirection defeats Vite's static import analysis. The plugin
// only inspects literal string arguments to `import()`; a variable forces
// runtime resolution. Under `describe.skip` the `it` bodies never execute,
// so this resolution never runs at collection time.
const REHYPE_MODULE_PATH = '../rehypeHandleMentions'

async function run(tree: Root): Promise<Root> {
  const mod = (await import(/* @vite-ignore */ REHYPE_MODULE_PATH)) as RehypeHandleMentionsModule
  const transformer = mod.rehypeHandleMentions()
  const result = transformer(tree)
  return (result as Root | undefined) ?? tree
}

describe.skip('rehypeHandleMentions', () => {
  it('wraps a bare @handle text node into an <a href="https://x.com/{handle}">', async () => {
    const tree: Root = {
      type: 'root',
      children: [
        {
          type: 'element',
          tagName: 'p',
          properties: {},
          children: [{ type: 'text', value: 'See @jpow' }],
        },
      ],
    }
    const out = await run(tree)
    const p = (out.children[0] as { children: unknown[] }).children as Array<
      { type: string; value?: string; tagName?: string; properties?: { href?: string }; children?: unknown[] }
    >
    expect(p.length).toBe(2)
    expect(p[0]).toEqual({ type: 'text', value: 'See ' })
    expect(p[1].type).toBe('element')
    expect(p[1].tagName).toBe('a')
    expect(p[1].properties?.href).toBe('https://x.com/jpow')
    expect(p[1].children).toEqual([{ type: 'text', value: '@jpow' }])
  })

  it('does NOT double-wrap @handle that is already inside an <a>', async () => {
    const tree: Root = {
      type: 'root',
      children: [
        {
          type: 'element',
          tagName: 'p',
          properties: {},
          children: [
            {
              type: 'element',
              tagName: 'a',
              properties: { href: 'https://x.com/jpow' },
              children: [{ type: 'text', value: '@jpow' }],
            },
          ],
        },
      ],
    }
    const out = await run(tree)
    const p = out.children[0] as { children: unknown[] }
    expect(p.children.length).toBe(1)
    const a = p.children[0] as { tagName: string; children: unknown[] }
    expect(a.tagName).toBe('a')
    expect(a.children).toEqual([{ type: 'text', value: '@jpow' }])
  })

  it('does NOT wrap @handle inside <code>', async () => {
    const tree: Root = {
      type: 'root',
      children: [
        {
          type: 'element',
          tagName: 'p',
          properties: {},
          children: [
            {
              type: 'element',
              tagName: 'code',
              properties: {},
              children: [{ type: 'text', value: '@jpow' }],
            },
          ],
        },
      ],
    }
    const out = await run(tree)
    const code = ((out.children[0] as { children: unknown[] }).children[0]) as {
      tagName: string
      children: Array<{ type: string; value: string }>
    }
    expect(code.tagName).toBe('code')
    expect(code.children).toEqual([{ type: 'text', value: '@jpow' }])
  })

  it('handles multiple @handles in one text node and preserves surrounding text', async () => {
    const tree: Root = {
      type: 'root',
      children: [
        {
          type: 'element',
          tagName: 'p',
          properties: {},
          children: [{ type: 'text', value: 'hat tip @alice and @bob' }],
        },
      ],
    }
    const out = await run(tree)
    const p = out.children[0] as { children: Array<{ type: string; value?: string; tagName?: string; properties?: { href?: string } }> }
    expect(p.children.length).toBe(4)
    expect(p.children[0]).toEqual({ type: 'text', value: 'hat tip ' })
    expect(p.children[1].tagName).toBe('a')
    expect(p.children[1].properties?.href).toBe('https://x.com/alice')
    expect(p.children[2]).toEqual({ type: 'text', value: ' and ' })
    expect(p.children[3].tagName).toBe('a')
    expect(p.children[3].properties?.href).toBe('https://x.com/bob')
  })
})
