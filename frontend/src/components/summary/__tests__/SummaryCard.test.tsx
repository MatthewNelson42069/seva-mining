import { describe, expect, it } from 'vitest'
import { render, screen } from '@testing-library/react'

import type { SummaryCard as SummaryCardData } from '@/api/summaries'
import { SummaryCard } from '../SummaryCard'

function makeSummary(overrides: Partial<SummaryCardData> = {}): SummaryCardData {
  return {
    id: 'abc-123',
    generated_at: '2026-04-27T15:00:00Z',
    period_label: '08:00 PT',
    gold_news_md: null,
    ontario_law_md: null,
    ontario_stats_md: null,
    status: 'completed',
    error_text: null,
    ...overrides,
  }
}

describe('SummaryCard', () => {
  it('renders the title "Summary as of {period_label} — {Month Day}"', () => {
    render(<SummaryCard summary={makeSummary({ period_label: '08:00 PT' })} />)
    // date-fns "MMMM d" of 2026-04-27 (UTC parsed) is "April 27" in most TZs.
    // We assert the prefix and the period label; the date portion uses the
    // actual local-rendered output to avoid TZ flakiness in CI.
    const heading = screen.getByRole('heading', { level: 2 })
    expect(heading.textContent).toMatch(/^Summary as of 08:00 PT — /)
    expect(heading.textContent).toMatch(/April \d{1,2}$/)
  })

  it('hides the status badge when status === "completed"', () => {
    const { container } = render(<SummaryCard summary={makeSummary({ status: 'completed' })} />)
    // No "Partial" or "Failed" text anywhere
    expect(screen.queryByText('Partial')).toBeNull()
    expect(screen.queryByText('Failed')).toBeNull()
    // No element with amber or destructive classes within the title row
    expect(container.querySelector('[class*="amber"]')).toBeNull()
  })

  it('shows an amber-pill "Partial" badge when status === "partial"', () => {
    const { container } = render(<SummaryCard summary={makeSummary({ status: 'partial' })} />)
    const badge = screen.getByText('Partial')
    expect(badge).toBeInTheDocument()
    // Amber tinting is conveyed via Tailwind classes on the badge or an ancestor
    expect(container.querySelector('[class*="amber"]')).not.toBeNull()
  })

  it('shows a red "Failed" badge when status === "failed"', () => {
    const { container } = render(<SummaryCard summary={makeSummary({ status: 'failed' })} />)
    expect(screen.getByText('Failed')).toBeInTheDocument()
    // shadcn Badge variant="destructive" applies bg-destructive / text-destructive classes
    const badgeMatch = container.querySelector('[class*="destructive"]')
    expect(badgeMatch).not.toBeNull()
  })

  it('renders three SectionBlocks (Gold News / Ontario Law / Ontario Stats)', () => {
    render(<SummaryCard summary={makeSummary()} />)
    expect(screen.getByRole('heading', { level: 3, name: 'Gold News' })).toBeInTheDocument()
    expect(screen.getByRole('heading', { level: 3, name: 'Ontario Law' })).toBeInTheDocument()
    expect(screen.getByRole('heading', { level: 3, name: 'Ontario Stats' })).toBeInTheDocument()
  })

  it('renders empty-state fallbacks when all *_md fields are null', () => {
    render(<SummaryCard summary={makeSummary()} />)
    expect(screen.getByText(/No major moves in gold/i)).toBeInTheDocument()
    expect(screen.getByText(/No new Ontario mining-related laws/i)).toBeInTheDocument()
    expect(screen.getByText(/No new production statistics released/i)).toBeInTheDocument()
  })

  it('passes gold_news_md through to react-markdown (h2 rendered)', () => {
    const { container } = render(
      <SummaryCard summary={makeSummary({ gold_news_md: '## Lead\n\n* one\n' })} />
    )
    // There are multiple h2s in the document (the card title + the markdown h2)
    // Find the one with text "Lead"
    const h2Elements = container.querySelectorAll('h2')
    const leadH2 = Array.from(h2Elements).find(el => el.textContent === 'Lead')
    expect(leadH2).toBeTruthy()
    expect(container.querySelector('li')?.textContent).toBe('one')
  })
})
