import { describe, expect, it } from 'vitest'
import { render, screen } from '@testing-library/react'

import { SectionBlock } from '../SectionBlock'

describe('SectionBlock', () => {
  it('renders the title in an h3', () => {
    render(<SectionBlock title="Gold News" content={null} emptyFallback="No data." />)
    const h3 = screen.getByRole('heading', { level: 3 })
    expect(h3.textContent).toBe('Gold News')
  })

  it('renders markdown content (h2 + ul + li)', () => {
    const md = '## Hello\n\n* one\n* two\n'
    const { container } = render(
      <SectionBlock title="Gold News" content={md} emptyFallback="No data." />
    )
    expect(container.querySelector('h2')?.textContent).toBe('Hello')
    const lis = container.querySelectorAll('li')
    expect(lis.length).toBe(2)
    expect(lis[0].textContent).toBe('one')
    expect(lis[1].textContent).toBe('two')
  })

  it('renders the emptyFallback when content is null', () => {
    render(<SectionBlock title="Ontario Law" content={null} emptyFallback="No new laws today." />)
    expect(screen.getByText('No new laws today.')).toBeInTheDocument()
  })

  it('renders the emptyFallback when content is an empty string', () => {
    render(<SectionBlock title="Ontario Stats" content="" emptyFallback="No new stats." />)
    expect(screen.getByText('No new stats.')).toBeInTheDocument()
  })

  it('strips <script> tags via rehype-sanitize (XSS defence)', () => {
    const evil = "Hello <script>alert('xss')</script> world"
    const { container } = render(
      <SectionBlock title="Gold News" content={evil} emptyFallback="No data." />
    )
    expect(container.querySelector('script')).toBeNull()
    expect(container.textContent).toContain('Hello')
    expect(container.textContent).toContain('world')
  })

  it('strips <iframe> tags via rehype-sanitize', () => {
    // react-markdown v10 default drops raw HTML blocks entirely (allowDangerousHtml: false).
    // Content containing only raw HTML (iframe) is fully stripped — MORE conservative than
    // rehype-sanitize alone. The key security assertion: no iframe element in DOM.
    const evil = "safe prefix\n\n<iframe src='https://evil.example/'></iframe>"
    const { container } = render(
      <SectionBlock title="Gold News" content={evil} emptyFallback="No data." />
    )
    expect(container.querySelector('iframe')).toBeNull()
    // "safe prefix" is a markdown paragraph — it renders through and remains
    expect(container.textContent).toContain('safe prefix')
  })

  it('strips javascript: URLs from links', () => {
    const evil = "[click](javascript:alert(1))"
    const { container } = render(
      <SectionBlock title="Gold News" content={evil} emptyFallback="No data." />
    )
    const link = container.querySelector('a')
    // rehype-sanitize default schema removes the href attribute when it's a
    // disallowed protocol; the anchor element may remain but href must be safe.
    if (link) {
      const href = link.getAttribute('href') ?? ''
      expect(href.toLowerCase().startsWith('javascript:')).toBe(false)
    }
  })
})
