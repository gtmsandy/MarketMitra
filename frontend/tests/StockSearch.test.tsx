import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { MemoryRouter, useLocation } from 'react-router-dom'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { searchStocks } from '../src/api/market'
import StockSearch from '../src/components/StockSearch'

vi.mock('../src/api/market', () => ({
  searchStocks: vi.fn(),
}))

afterEach(() => {
  cleanup()
  vi.mocked(searchStocks).mockReset()
})

function LocationProbe() {
  return <output aria-label="Current route">{useLocation().pathname}</output>
}

describe('StockSearch keyboard interaction', () => {
  it('exposes combobox state and selects a result with ArrowDown and Enter', async () => {
    vi.mocked(searchStocks).mockResolvedValue([
      {
        symbol: 'NABIL',
        company_name: 'Nabil Bank Limited',
        ltp: 515,
        change: 13,
        change_percent: 2.59,
        open: 504,
        high: 520,
        low: 502,
        previous_close: 502,
        volume: 182_450,
        last_updated: '2026-09-03T11:30:00+05:45',
      },
    ])

    render(
      <MemoryRouter>
        <StockSearch />
        <LocationProbe />
      </MemoryRouter>,
    )

    const input = screen.getByRole('combobox', {
      name: 'Search stocks by symbol or company name',
    })
    expect(input.getAttribute('aria-expanded')).toBe('false')

    fireEvent.change(input, { target: { value: 'nabil' } })
    const option = await screen.findByRole('option', { name: /NABIL.*Nabil Bank Limited/ })
    expect(input.getAttribute('aria-expanded')).toBe('true')

    fireEvent.keyDown(input, { key: 'ArrowDown' })
    expect(input.getAttribute('aria-activedescendant')).toBe(option.id)
    expect(option.getAttribute('aria-selected')).toBe('true')

    fireEvent.keyDown(input, { key: 'Enter' })
    expect(screen.getByLabelText('Current route').textContent).toBe('/stocks/NABIL')
    expect(input.getAttribute('aria-expanded')).toBe('false')
  })
})
