import { cleanup, render } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'

import PriceChart from '../src/components/PriceChart'
import { calculateTechnicalIndicators } from '../src/technical/indicators'
import type { PriceHistoryPoint } from '../src/types/market'

class TestResizeObserver {
  observe() {}
  disconnect() {}
}

vi.stubGlobal('ResizeObserver', TestResizeObserver)

const chartMocks = vi.hoisted(() => {
  const setDataCalls: unknown[][] = []
  const addSeries = vi.fn((type: unknown) => ({
    setData: vi.fn((data: unknown[]) => setDataCalls.push(data)),
    priceScale: vi.fn(() => ({ applyOptions: vi.fn() })),
    type,
  }))
  const chart = {
    addSeries,
    timeScale: vi.fn(() => ({ fitContent: vi.fn() })),
    subscribeCrosshairMove: vi.fn(),
    remove: vi.fn(),
    resize: vi.fn(),
  }
  return { addSeries, chart, setDataCalls, HistogramSeries: 'histogram' }
})

vi.mock('lightweight-charts', () => ({
  CandlestickSeries: 'candlestick',
  HistogramSeries: chartMocks.HistogramSeries,
  LineSeries: 'line',
  createChart: vi.fn(() => chartMocks.chart),
}))

afterEach(() => cleanup())

function history(): PriceHistoryPoint[] {
  return Array.from({ length: 40 }, (_, index) => ({
    date: new Date(Date.UTC(2026, 0, index + 1)).toISOString().slice(0, 10),
    open: 100 + index,
    high: 102 + index,
    low: 99 + index,
    close: 101 + index,
    volume: 1_000 + index,
  }))
}

describe('PriceChart', () => {
  it('renders the populated MACD histogram as a histogram series', () => {
    const data = history()
    const indicators = calculateTechnicalIndicators(data)
    render(<PriceChart data={data} indicators={indicators} options={{
      candleMode: false,
      showVolume: true,
      showSma: false,
      showEma: false,
      showBollinger: false,
      showRsi: false,
      showMacd: true,
    }} />)

    const histogramCalls = chartMocks.addSeries.mock.calls.filter(([type]) => type === chartMocks.HistogramSeries)
    expect(histogramCalls).toHaveLength(2)
    expect(chartMocks.setDataCalls.some((data) => data.length === indicators.macd.filter((point) => point.histogram !== null).length)).toBe(true)
  })
})
