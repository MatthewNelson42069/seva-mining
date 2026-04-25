import { render, screen, cleanup, fireEvent } from '@testing-library/react'
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { PostToXConfirmModal } from '../PostToXConfirmModal'

describe('PostToXConfirmModal (Phase B — quick-260424-l0d)', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  afterEach(() => {
    cleanup()
  })

  // Test 1 — renders breaking_news preview as a single text block
  it('renders breaking_news preview as a single text block', () => {
    render(
      <PostToXConfirmModal
        isOpen={true}
        onClose={() => {}}
        onConfirm={() => {}}
        isPending={false}
        contentType="breaking_news"
        preview="BREAKING: Gold surpasses $3,000/oz."
      />,
    )

    expect(screen.getByText('Post to X?')).toBeInTheDocument()
    expect(
      screen.getByText(/This will immediately post to your X account/i),
    ).toBeInTheDocument()
    expect(
      screen.getByText('BREAKING: Gold surpasses $3,000/oz.'),
    ).toBeInTheDocument()
    expect(screen.getByText(/A single tweet will be posted/i)).toBeInTheDocument()
  })

  // Test 2 — renders thread preview as a numbered list with all tweets
  it('renders thread preview as a numbered list with all tweets', () => {
    const tweets = [
      'Tweet one — opening hook.',
      'Tweet two — supporting data.',
      'Tweet three — closing call to action.',
    ]
    render(
      <PostToXConfirmModal
        isOpen={true}
        onClose={() => {}}
        onConfirm={() => {}}
        isPending={false}
        contentType="thread"
        preview={tweets}
      />,
    )

    for (const t of tweets) {
      expect(screen.getByText(t)).toBeInTheDocument()
    }
    expect(
      screen.getByText(/3-tweet thread will be posted as one chain/i),
    ).toBeInTheDocument()
  })

  // Test 3 — Cancel button calls onClose, Post to X button calls onConfirm
  it('Cancel triggers onClose and Post to X triggers onConfirm', () => {
    const onClose = vi.fn()
    const onConfirm = vi.fn()
    render(
      <PostToXConfirmModal
        isOpen={true}
        onClose={onClose}
        onConfirm={onConfirm}
        isPending={false}
        contentType="breaking_news"
        preview="Hello world."
      />,
    )

    fireEvent.click(screen.getByRole('button', { name: 'Cancel' }))
    expect(onClose).toHaveBeenCalledTimes(1)

    fireEvent.click(screen.getByRole('button', { name: 'Post to X' }))
    expect(onConfirm).toHaveBeenCalledTimes(1)
  })

  // Test 4 — pending state disables both buttons and changes button label
  it('disables both buttons and shows "Posting…" while pending', () => {
    render(
      <PostToXConfirmModal
        isOpen={true}
        onClose={() => {}}
        onConfirm={() => {}}
        isPending={true}
        contentType="breaking_news"
        preview="Hello world."
      />,
    )

    const cancelBtn = screen.getByRole('button', { name: 'Cancel' })
    const postBtn = screen.getByRole('button', { name: 'Posting…' })
    expect(cancelBtn).toBeDisabled()
    expect(postBtn).toBeDisabled()
    expect(screen.queryByRole('button', { name: 'Post to X' })).not.toBeInTheDocument()
  })

  // Test 5 — closed modal does not render any preview content
  it('renders nothing when isOpen is false', () => {
    render(
      <PostToXConfirmModal
        isOpen={false}
        onClose={() => {}}
        onConfirm={() => {}}
        isPending={false}
        contentType="breaking_news"
        preview="Should not appear."
      />,
    )

    expect(screen.queryByText('Should not appear.')).not.toBeInTheDocument()
    expect(screen.queryByText('Post to X?')).not.toBeInTheDocument()
  })
})
