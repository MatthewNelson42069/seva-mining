import { render, screen, fireEvent } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { ApprovalCard } from './ApprovalCard'
import { useAppStore } from '@/stores/index'
import type { DraftItemResponse } from '@/api/types'

// Mock sonner toast to avoid side effects
vi.mock('sonner', () => ({
  toast: {
    success: vi.fn(),
    dismiss: vi.fn(),
  },
}))

const mockItem: DraftItemResponse = {
  id: 'test-card-id',
  platform: 'twitter',
  status: 'pending',
  source_url: 'https://x.com/goldwatcher/status/123',
  source_text: 'Gold breaks $2,400 resistance — watch for continuation above 2,420.',
  source_account: '@goldwatcher',
  follower_count: 45200,
  score: 8.2,
  quality_score: 7.8,
  alternatives: [
    {
      text: 'The 2,400 break matters because it clears the March 2024 high.',
      type: 'reply',
      label: 'Draft A',
    },
    {
      text: 'Central bank accumulation is doing the heavy lifting here.',
      type: 'reply',
      label: 'Draft B',
    },
  ],
  rationale: 'High engagement tweet from credible technical account.',
  urgency: 'high',
  created_at: new Date(Date.now() - 3600000).toISOString(),
}

function createWrapper() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  })
  return function Wrapper({ children }: { children: React.ReactNode }) {
    return <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
  }
}

beforeEach(() => {
  vi.clearAllMocks()
  // Mock navigator.clipboard
  Object.assign(navigator, {
    clipboard: { writeText: vi.fn().mockResolvedValue(undefined) },
  })
  // Reset Zustand store to prevent state leaking between tests
  useAppStore.setState({
    editingCardId: null,
    rejectionPanelCardId: null,
    activeDraftTab: {},
    fadingCardIds: new Set(),
    pendingTimeouts: new Map(),
  })
})

describe('ApprovalCard', () => {
  it('renders platform badge, source account, score, source text, and action buttons', () => {
    render(<ApprovalCard item={mockItem} platform="twitter" />, {
      wrapper: createWrapper(),
    })

    // Platform badge
    expect(screen.getByText('Twitter')).toBeInTheDocument()
    // Source account
    expect(screen.getByText('@goldwatcher')).toBeInTheDocument()
    // Score badge: 8.2/10
    expect(screen.getByText('8.2/10')).toBeInTheDocument()
    // Source text
    expect(screen.getByText(/Gold breaks \$2,400/)).toBeInTheDocument()
    // Draft text (first alternative)
    expect(screen.getByText(/The 2,400 break matters/)).toBeInTheDocument()
    // Action buttons
    expect(screen.getByRole('button', { name: /Approve/ })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /Reject/ })).toBeInTheDocument()
  })

  it('renders draft tabs for multiple alternatives', () => {
    render(<ApprovalCard item={mockItem} platform="twitter" />, {
      wrapper: createWrapper(),
    })

    // Tab buttons are rendered (shadcn Tabs only mounts the active panel;
    // query by role='tab' which is always present in the tablist)
    const tabs = screen.getAllByRole('tab')
    expect(tabs.length).toBeGreaterThanOrEqual(2)
  })

  it('clicking "Why this post?" reveals the rationale text', () => {
    render(<ApprovalCard item={mockItem} platform="twitter" />, {
      wrapper: createWrapper(),
    })

    // Rationale is hidden initially
    expect(screen.queryByText(/High engagement tweet/)).not.toBeInTheDocument()

    // Click toggle
    fireEvent.click(screen.getByText(/Why this post\?/))

    // Rationale is now visible
    expect(screen.getByText(/High engagement tweet from credible technical account/)).toBeInTheDocument()
  })

  it('source URL link has target="_blank" and rel="noopener noreferrer"', () => {
    render(<ApprovalCard item={mockItem} platform="twitter" />, {
      wrapper: createWrapper(),
    })

    const link = screen.getByRole('link', { name: /View source/ })
    expect(link).toHaveAttribute('target', '_blank')
    expect(link).toHaveAttribute('rel', 'noopener noreferrer')
    expect(link).toHaveAttribute('href', 'https://x.com/goldwatcher/status/123')
  })

  it('clicking Reject opens the reject panel with all 5 categories', () => {
    render(<ApprovalCard item={mockItem} platform="twitter" />, {
      wrapper: createWrapper(),
    })

    // Panel not visible initially
    expect(screen.queryByText('Off-topic')).not.toBeInTheDocument()

    // Click Reject
    fireEvent.click(screen.getByRole('button', { name: /Reject/ }))

    // All 5 rejection categories shown
    expect(screen.getByText('Off-topic')).toBeInTheDocument()
    expect(screen.getByText('Low quality')).toBeInTheDocument()
    expect(screen.getByText('Bad timing')).toBeInTheDocument()
    expect(screen.getByText('Tone wrong')).toBeInTheDocument()
    expect(screen.getByText('Duplicate')).toBeInTheDocument()
  })

  it('clicking on draft text enters inline edit mode showing a textarea', () => {
    render(<ApprovalCard item={mockItem} platform="twitter" />, {
      wrapper: createWrapper(),
    })

    // Click on draft text to enter edit mode
    const draftText = screen.getByText(/The 2,400 break matters/)
    fireEvent.click(draftText)

    // Should show a textarea in edit mode
    expect(screen.getByRole('textbox')).toBeInTheDocument()
  })

  it('follower count is formatted correctly', () => {
    render(<ApprovalCard item={mockItem} platform="twitter" />, {
      wrapper: createWrapper(),
    })

    expect(screen.getByText('45.2K followers')).toBeInTheDocument()
  })
})
