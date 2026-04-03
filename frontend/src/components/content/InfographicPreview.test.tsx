import { render, screen, fireEvent } from '@testing-library/react'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { InfographicPreview } from './InfographicPreview'

const mockDraft = {
  format: 'infographic' as const,
  headline: 'Central Bank Gold Reserves Hit All-Time High',
  key_stats: [
    { stat: '1,037 tonnes purchased in 2023', source: 'WGC Gold Demand Trends', source_url: 'https://www.gold.org/goldhub/research' },
    { stat: '24% of annual mine supply', source: 'World Gold Council', source_url: 'https://www.gold.org' },
  ],
  visual_structure: 'bar chart',
  caption_text: 'Central banks are reshaping gold demand. 1,037 tonnes in 2023 represents structural buying, not tactical hedging.',
}

describe('InfographicPreview', () => {
  beforeEach(() => {
    Object.assign(navigator, {
      clipboard: { writeText: vi.fn().mockResolvedValue(undefined) },
    })
  })

  it('renders headline text', () => {
    render(<InfographicPreview draft={mockDraft} />)
    expect(screen.getByText('Central Bank Gold Reserves Hit All-Time High')).toBeInTheDocument()
  })

  it('renders INFOGRAPHIC BRIEF label', () => {
    render(<InfographicPreview draft={mockDraft} />)
    expect(screen.getByText(/INFOGRAPHIC BRIEF/i)).toBeInTheDocument()
  })

  it('renders visual_structure as a Badge', () => {
    render(<InfographicPreview draft={mockDraft} />)
    expect(screen.getByText('bar chart')).toBeInTheDocument()
  })

  it('renders each key_stat with bold stat text', () => {
    render(<InfographicPreview draft={mockDraft} />)
    expect(screen.getByText('1,037 tonnes purchased in 2023')).toBeInTheDocument()
    expect(screen.getByText('24% of annual mine supply')).toBeInTheDocument()
  })

  it('renders each key_stat with source link', () => {
    render(<InfographicPreview draft={mockDraft} />)
    const links = screen.getAllByRole('link')
    expect(links.some(l => l.getAttribute('href') === 'https://www.gold.org/goldhub/research')).toBe(true)
    expect(links.some(l => l.getAttribute('href') === 'https://www.gold.org')).toBe(true)
  })

  it('renders caption_text', () => {
    render(<InfographicPreview draft={mockDraft} />)
    expect(screen.getByText(/Central banks are reshaping gold demand/)).toBeInTheDocument()
  })

  it('Copy Caption button copies caption_text to clipboard', async () => {
    render(<InfographicPreview draft={mockDraft} />)
    const btn = screen.getByRole('button', { name: /copy caption/i })
    fireEvent.click(btn)
    expect(navigator.clipboard.writeText).toHaveBeenCalledWith(mockDraft.caption_text)
  })
})
