import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'

import { describe, expect, it } from 'vitest'

import { calculateTechnicalIndicators } from '../src/technical/indicators'

type Fixture = {
  prices: Array<{ symbol: string; date: string; close: number }>
}

const fixture = JSON.parse(
  readFileSync(resolve(process.cwd(), '../provenance/fixtures/marketmitra-synthetic-technical-analysis-v1.json'), 'utf8'),
) as Fixture

const rows = fixture.prices
  .filter((row) => row.symbol === 'SYNBANKA')
  .map(({ date, close }) => ({ date, close }))

describe('technical-analysis fixture', () => {
  it('provides a complete deterministic history for every conventional indicator', () => {
    const result = calculateTechnicalIndicators(rows)
    const firstSmaWindow = rows.slice(0, 20).reduce((sum, point) => sum + point.close, 0) / 20

    expect(rows).toHaveLength(120)
    expect(result.sma.filter((point) => point.value !== null)).toHaveLength(101)
    expect(result.ema.filter((point) => point.value !== null)).toHaveLength(101)
    expect(result.rsi.filter((point) => point.value !== null)).toHaveLength(106)
    expect(result.macd.filter((point) => point.macd !== null)).toHaveLength(95)
    expect(result.macd.filter((point) => point.signal !== null)).toHaveLength(87)
    expect(result.bollinger.filter((point) => point.middle !== null)).toHaveLength(101)
    expect(result.sma[19].value).toBeCloseTo(firstSmaWindow)
    expect(result.ema[19].value).toBeCloseTo(firstSmaWindow)
    expect(result.availability.macd.available).toBe(true)
  })

  it('does not let a later close change earlier indicator values', () => {
    const baseline = calculateTechnicalIndicators(rows)
    const changed = calculateTechnicalIndicators(
      rows.map((point, index) => (index === rows.length - 1 ? { ...point, close: point.close + 100 } : point)),
    )

    expect(changed.sma[rows.length - 2].value).toBe(baseline.sma[rows.length - 2].value)
    expect(changed.ema[rows.length - 2].value).toBe(baseline.ema[rows.length - 2].value)
    expect(changed.rsi[rows.length - 2].value).toBe(baseline.rsi[rows.length - 2].value)
    expect(changed.macd[rows.length - 2].macd).toBe(baseline.macd[rows.length - 2].macd)
  })
})
