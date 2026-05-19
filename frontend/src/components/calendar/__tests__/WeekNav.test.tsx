import { describe, it, expect, vi } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import { WeekNav } from '../WeekNav'

describe('WeekNav', () => {
  // Wednesday May 20 2026 -> ISO week is Mon May 18 -> Sun May 24
  const WED = new Date(2026, 4, 20)

  it('fires onPrev when prev button clicked', () => {
    const onPrev = vi.fn()
    render(
      <WeekNav
        weekAnchor={WED}
        onPrev={onPrev}
        onNext={vi.fn()}
        onToday={vi.fn()}
      />,
    )
    fireEvent.click(screen.getByLabelText('Previous week'))
    expect(onPrev).toHaveBeenCalledTimes(1)
  })

  it('fires onNext when next button clicked', () => {
    const onNext = vi.fn()
    render(
      <WeekNav
        weekAnchor={WED}
        onPrev={vi.fn()}
        onNext={onNext}
        onToday={vi.fn()}
      />,
    )
    fireEvent.click(screen.getByLabelText('Next week'))
    expect(onNext).toHaveBeenCalledTimes(1)
  })

  it('fires onToday when Today button clicked', () => {
    const onToday = vi.fn()
    render(
      <WeekNav
        weekAnchor={WED}
        onPrev={vi.fn()}
        onNext={vi.fn()}
        onToday={onToday}
      />,
    )
    fireEvent.click(screen.getByLabelText('Jump to today'))
    expect(onToday).toHaveBeenCalledTimes(1)
  })

  it('renders the week range label "May 18 – May 24, 2026"', () => {
    render(
      <WeekNav
        weekAnchor={WED}
        onPrev={vi.fn()}
        onNext={vi.fn()}
        onToday={vi.fn()}
      />,
    )
    const label = screen.getByTestId('week-range-label')
    expect(label.textContent).toMatch(/May 18.*May 24.*2026/)
  })
})
