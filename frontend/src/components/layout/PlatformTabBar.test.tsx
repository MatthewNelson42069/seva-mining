import { describe, it, expect, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { PlatformTabBar } from './PlatformTabBar'
import type { Platform } from '@/api/types'

const defaultCounts: Record<Platform, number> = {
  twitter: 0,
  content: 0,
}

describe('PlatformTabBar', () => {
  it('renders two tabs: Twitter, Content', () => {
    render(
      <PlatformTabBar
        activeTab="twitter"
        onTabChange={() => {}}
        counts={defaultCounts}
      />
    )
    expect(screen.getByText('Twitter')).toBeInTheDocument()
    expect(screen.getByText('Content')).toBeInTheDocument()
  })

  it('shows badge counts when count > 0', () => {
    const counts: Record<Platform, number> = {
      twitter: 5,
      content: 0,
    }
    render(
      <PlatformTabBar
        activeTab="twitter"
        onTabChange={() => {}}
        counts={counts}
      />
    )
    expect(screen.getByText('5')).toBeInTheDocument()
    // content has 0 — badge should not appear
    expect(screen.queryByText('0')).not.toBeInTheDocument()
  })

  it('calls onTabChange with correct platform when tab is clicked', async () => {
    const user = userEvent.setup()
    const onTabChange = vi.fn()

    render(
      <PlatformTabBar
        activeTab="twitter"
        onTabChange={onTabChange}
        counts={defaultCounts}
      />
    )

    await user.click(screen.getByText('Content'))
    expect(onTabChange).toHaveBeenCalledWith('content')
  })

  it('active tab reflects the activeTab prop', () => {
    const { rerender } = render(
      <PlatformTabBar
        activeTab="twitter"
        onTabChange={() => {}}
        counts={defaultCounts}
      />
    )

    // Rerender with a different active tab
    rerender(
      <PlatformTabBar
        activeTab="content"
        onTabChange={() => {}}
        counts={defaultCounts}
      />
    )

    // The Content tab trigger should have data-active attribute
    const contentTab = screen.getByText('Content').closest('[data-slot="tabs-trigger"]')
    expect(contentTab).toHaveAttribute('data-active')
  })
})
