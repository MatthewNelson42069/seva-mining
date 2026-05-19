import ReactMarkdown from 'react-markdown'
import rehypeRaw from 'rehype-raw'
import rehypeSanitize from 'rehype-sanitize'

import { XHandlePill } from './XHandlePill'
import { rehypeHandleMentions } from './rehypeHandleMentions'

/**
 * Phase 8 — UI-05 reframe (D-02 / D-04).
 *
 * Shared markdown wrapper that bundles the security-first sanitize plugin with
 * the X-handle mention plugin, then routes every X/Twitter anchor through the
 * pill component. Used by `SweeperCard` (3 sections) and `SectionBlock` (1).
 *
 * Plugin pipeline order is `[rehypeRaw, rehypeSanitize, rehypeHandleMentions]`:
 *   1. `rehypeRaw` promotes raw-HTML nodes into hast so the sanitizer can see
 *      them as proper elements (without it, react-markdown silently drops raw
 *      HTML blocks AND any trailing text inside the same block — including
 *      benign content, which makes sanitization untestable).
 *   2. `rehypeSanitize` is the security boundary and runs immediately after
 *      `rehypeRaw` (RESEARCH key finding #3) — dangerous tags like <script>,
 *      <iframe>, and inline event handlers are stripped at the AST level.
 *   3. `rehypeHandleMentions` runs LAST on the already-sanitized tree so any
 *      synthetic <a> elements it inserts carry only safe `https://x.com/…`
 *      hrefs.
 *
 * components.a override:
 *   - href matches X_HOST_RE → render XHandlePill (new-tab, amber-hover pill)
 *   - otherwise → default <a> rendering with the original href + children
 */

const X_HOST_RE = /^https?:\/\/(www\.)?(x|twitter)\.com\//i

interface MarkdownContentProps {
  content: string
}

export function MarkdownContent({ content }: MarkdownContentProps) {
  return (
    <ReactMarkdown
      rehypePlugins={[rehypeRaw, rehypeSanitize, rehypeHandleMentions]}
      components={{
        a({ href, children, ...rest }) {
          if (href && X_HOST_RE.test(href)) {
            return <XHandlePill href={href}>{children}</XHandlePill>
          }
          return (
            <a href={href} {...rest}>
              {children}
            </a>
          )
        },
      }}
    >
      {content}
    </ReactMarkdown>
  )
}
