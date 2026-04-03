import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { describe, it, expect } from 'vitest'
import { SettingsPage } from './SettingsPage'

function createWrapper() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  })
  return function Wrapper({ children }: { children: React.ReactNode }) {
    return <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
  }
}

describe('SettingsPage', () => {
  it('renders all 6 tab triggers', () => {
    render(<SettingsPage />, { wrapper: createWrapper() })

    expect(screen.getByText('Watchlists')).toBeInTheDocument()
    expect(screen.getByText('Keywords')).toBeInTheDocument()
    expect(screen.getByText('Scoring')).toBeInTheDocument()
    expect(screen.getByText('Notifications')).toBeInTheDocument()
    expect(screen.getByText('Agent Runs')).toBeInTheDocument()
    expect(screen.getByText('Schedule')).toBeInTheDocument()
  })

  it('watchlists tab shows twitter entries by default', async () => {
    render(<SettingsPage />, { wrapper: createWrapper() })

    // Should default to watchlists tab
    await waitFor(() => {
      expect(screen.getByText('@goldwatcher')).toBeInTheDocument()
    })
  })

  it('watchlists tab platform toggle filters entries', async () => {
    render(<SettingsPage />, { wrapper: createWrapper() })

    // Default is twitter — should show @goldwatcher
    await waitFor(() => {
      expect(screen.getByText('@goldwatcher')).toBeInTheDocument()
    })

    // Switch to instagram
    fireEvent.click(screen.getByText('Instagram'))

    await waitFor(() => {
      expect(screen.getByText('@goldanalysis_ig')).toBeInTheDocument()
    })
  })

  it('watchlists tab add button opens form', async () => {
    render(<SettingsPage />, { wrapper: createWrapper() })

    // Wait for initial data to load
    await waitFor(() => {
      expect(screen.getByText('Add Account')).toBeInTheDocument()
    })

    fireEvent.click(screen.getByText('Add Account'))

    expect(screen.getByPlaceholderText('@handle')).toBeInTheDocument()
  })

  it('keywords tab shows entries with term column', async () => {
    render(<SettingsPage />, { wrapper: createWrapper() })

    // Click Keywords tab
    fireEvent.click(screen.getByText('Keywords'))

    await waitFor(() => {
      expect(screen.getByText('gold price')).toBeInTheDocument()
      expect(screen.getByText('central bank')).toBeInTheDocument()
    })
  })

  it('keywords tab shows term column header', async () => {
    render(<SettingsPage />, { wrapper: createWrapper() })

    fireEvent.click(screen.getByText('Keywords'))

    await waitFor(() => {
      expect(screen.getByText('Term')).toBeInTheDocument()
    })
  })

  it('keywords tab delete button opens confirmation dialog', async () => {
    render(<SettingsPage />, { wrapper: createWrapper() })

    fireEvent.click(screen.getByText('Keywords'))

    await waitFor(() => {
      expect(screen.getByText('gold price')).toBeInTheDocument()
    })

    // Click Delete on the first keyword row
    const deleteButtons = screen.getAllByText('Delete')
    fireEvent.click(deleteButtons[0])

    await waitFor(() => {
      expect(screen.getByText('Remove Keyword')).toBeInTheDocument()
      expect(screen.getByText('Keep Keyword')).toBeInTheDocument()
    })
  })

  it('scoring tab loads config and shows save button', async () => {
    render(<SettingsPage />, { wrapper: createWrapper() })

    fireEvent.click(screen.getByText('Scoring'))

    await waitFor(() => {
      expect(screen.getByText('Save Scoring Settings')).toBeInTheDocument()
    })

    // Should show content scoring section heading
    expect(screen.getByText('Content Agent Scoring')).toBeInTheDocument()
  })

  it('notifications tab renders', async () => {
    render(<SettingsPage />, { wrapper: createWrapper() })

    fireEvent.click(screen.getByText('Notifications'))

    // No notification keys in mock — should show empty state
    await waitFor(() => {
      const emptyOrSave = screen.queryByText('Save Notification Settings') ??
        screen.queryByText('No notification config keys found.')
      expect(emptyOrSave).toBeInTheDocument()
    })
  })

  it('agent runs tab shows run entries with filter dropdown', async () => {
    render(<SettingsPage />, { wrapper: createWrapper() })

    fireEvent.click(screen.getByText('Agent Runs'))

    await waitFor(() => {
      expect(screen.getByText('twitter_agent')).toBeInTheDocument()
    })

    // Filter dropdown should be present
    const filterSelect = screen.getByRole('combobox')
    expect(filterSelect).toBeInTheDocument()
  })

  it('agent runs tab shows quota bar', async () => {
    render(<SettingsPage />, { wrapper: createWrapper() })

    fireEvent.click(screen.getByText('Agent Runs'))

    await waitFor(() => {
      expect(screen.getByText('X API Monthly Quota')).toBeInTheDocument()
    })
  })

  it('schedule tab shows interval inputs and restart note', async () => {
    render(<SettingsPage />, { wrapper: createWrapper() })

    fireEvent.click(screen.getByText('Schedule'))

    await waitFor(() => {
      expect(screen.getByText(/next worker restart/i)).toBeInTheDocument()
    })
  })
})
