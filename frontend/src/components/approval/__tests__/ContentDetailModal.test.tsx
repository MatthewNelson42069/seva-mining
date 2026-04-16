import { describe, it } from 'vitest'

// Wave 0 stub — skip until ContentDetailModal rewrite lands (Plan 06)
describe.skip('ContentDetailModal format-aware (Plan 11-06)', () => {
  it('renders InfographicPreview when bundle.content_type === "infographic"', () => {})
  it('renders ThreadPreview when bundle.content_type === "thread"', () => {})
  it('renders LongFormPreview when bundle.content_type === "long_form"', () => {})
  it('renders BreakingNewsPreview when bundle.content_type === "breaking_news"', () => {})
  it('renders QuotePreview when bundle.content_type === "quote"', () => {})
  it('renders VideoClipPreview when bundle.content_type === "video_clip"', () => {})
  it('falls back to flat DraftAlternative.text when bundle fetch fails (D-24)', () => {})
  it('shows skeleton placeholders + "rendering..." when rendered_images empty and bundle <10min old', () => {})
  it('hides image slots gracefully when bundle is >10min old and no rendered_images', () => {})
  it('Regenerate images button is disabled while rendering is in-flight (D-17)', () => {})
})
