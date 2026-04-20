import { render, screen, fireEvent } from '@testing-library/react'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { InfographicPreview } from './InfographicPreview'

// ---------------------------------------------------------------------------
// Stub clipboard and toast
// ---------------------------------------------------------------------------

vi.mock('sonner', () => ({
  toast: { success: vi.fn() },
}))

const mockWriteText = vi.fn().mockResolvedValue(undefined)

beforeEach(() => {
  Object.defineProperty(navigator, 'clipboard', {
    value: { writeText: mockWriteText },
    configurable: true,
  })
  mockWriteText.mockReset()
})

// ---------------------------------------------------------------------------
// Test A: new-shape draft renders three labeled sections + three Copy buttons
// ---------------------------------------------------------------------------

describe('InfographicPreview — new mfy shape', () => {
  const newDraft = {
    format: 'infographic' as const,
    twitter_caption: 'Central banks bought 1,136t of gold in Q1 2026.',
    suggested_headline: 'Central Banks Set Q1 Gold Buying Record',
    data_facts: ['1,136 tonnes purchased Q1 2026', 'Highest quarterly total since 1971'],
    image_prompt: 'You are building a Seva Mining editorial social asset...\n\nHEADLINE FOR THIS VISUAL:\nCentral Banks Set Q1 Gold Buying Record',
  }

  it('renders "Suggested Headline" section label', () => {
    render(<InfographicPreview draft={newDraft} />)
    expect(screen.getByText(/Suggested Headline/i)).toBeInTheDocument()
  })

  it('renders "Key Facts" section label', () => {
    render(<InfographicPreview draft={newDraft} />)
    expect(screen.getByText(/Key Facts/i)).toBeInTheDocument()
  })

  it('renders "Image Prompt" section label', () => {
    render(<InfographicPreview draft={newDraft} />)
    expect(screen.getByText(/Image Prompt/i)).toBeInTheDocument()
  })

  it('renders three Copy buttons', () => {
    render(<InfographicPreview draft={newDraft} />)
    const copyBtns = screen.getAllByRole('button', { name: /Copy/i })
    expect(copyBtns.length).toBe(3)
  })

  it('Copy for Suggested Headline writes headline to clipboard', () => {
    render(<InfographicPreview draft={newDraft} />)
    // The first Copy button is the headline Copy
    const copyBtns = screen.getAllByRole('button', { name: /Copy/i })
    fireEvent.click(copyBtns[0])
    expect(mockWriteText).toHaveBeenCalledWith(newDraft.suggested_headline)
  })

  it('Copy for Key Facts writes joined facts to clipboard', () => {
    render(<InfographicPreview draft={newDraft} />)
    const copyBtns = screen.getAllByRole('button', { name: /Copy/i })
    fireEvent.click(copyBtns[1])
    const expected = newDraft.data_facts.map(f => `- ${f}`).join('\n')
    expect(mockWriteText).toHaveBeenCalledWith(expected)
  })

  it('Copy for Image Prompt writes full image_prompt to clipboard', () => {
    render(<InfographicPreview draft={newDraft} />)
    const copyBtns = screen.getAllByRole('button', { name: /Copy/i })
    fireEvent.click(copyBtns[2])
    expect(mockWriteText).toHaveBeenCalledWith(newDraft.image_prompt)
  })
})

// ---------------------------------------------------------------------------
// Test B: legacy shape (no image_prompt) renders placeholder, no crash
// ---------------------------------------------------------------------------

describe('InfographicPreview — legacy shape (no image_prompt)', () => {
  it('renders legacy placeholder text and no Copy buttons', () => {
    render(<InfographicPreview draft={{ format: 'infographic' }} />)
    expect(screen.getByText(/Legacy format/i)).toBeInTheDocument()
    const copyBtns = screen.queryAllByRole('button', { name: /Copy/i })
    expect(copyBtns.length).toBe(0)
  })

  it('renders legacy placeholder when draft is completely empty object', () => {
    render(<InfographicPreview draft={{}} />)
    expect(screen.getByText(/Legacy format/i)).toBeInTheDocument()
  })

  it('does not crash when draft is null', () => {
    render(<InfographicPreview draft={null} />)
    expect(screen.getByText(/Legacy format/i)).toBeInTheDocument()
  })
})

// ---------------------------------------------------------------------------
// Test D: no <img> tags rendered for infographic
// ---------------------------------------------------------------------------

describe('InfographicPreview — no images', () => {
  it('does not render any <img> elements', () => {
    const newDraft = {
      format: 'infographic' as const,
      suggested_headline: 'Headline',
      data_facts: ['fact 1'],
      image_prompt: 'BRAND_PREAMBLE...',
    }
    const { container } = render(<InfographicPreview draft={newDraft} />)
    expect(container.querySelector('img')).toBeNull()
  })
})
