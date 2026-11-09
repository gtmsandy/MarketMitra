import { describe, expect, it } from 'vitest'

import { calculateTechnicalIndicators } from '../src/technical/indicators'

const points = (closes: Array<number | null>) => closes.map((close, index) => ({ date: `2026-01-${String(index + 1).padStart(2, '0')}`, close }))

describe('technical indicators', () => {
  it('calculates SMA and population Bollinger bands without look-ahead', () => {
    const result = calculateTechnicalIndicators(points([1, 2, 3, 4]), { sma: 2, ema: 2, rsi: 2, macdFast: 2, macdSlow: 3, macdSignal: 2, bollinger: 2, bollingerStdDev: 2 })
    expect(result.sma.map((point) => point.value)).toEqual([null, 1.5, 2.5, 3.5])
    expect(result.bollinger[1].middle).toBe(1.5)
    expect(result.bollinger[1].upper).toBeCloseTo(2.5)
    expect(result.bollinger[1].lower).toBeCloseTo(0.5)
  })

  it('seeds EMA with the first SMA window', () => {
    const result = calculateTechnicalIndicators(points([2, 4, 6, 8]), { sma: 2, ema: 3, rsi: 2, macdFast: 2, macdSlow: 3, macdSignal: 2, bollinger: 2, bollingerStdDev: 2 })
    expect(result.ema.map((point) => point.value)).toEqual([null, null, 4, 6])
  })

  it('uses Wilder RSI smoothing and treats a flat series as neutral', () => {
    const flat = calculateTechnicalIndicators(points([10, 10, 10, 10]), { sma: 2, ema: 2, rsi: 2, macdFast: 2, macdSlow: 3, macdSignal: 2, bollinger: 2, bollingerStdDev: 2 })
    expect(flat.rsi.map((point) => point.value)).toEqual([null, null, 50, 50])
    const rising = calculateTechnicalIndicators(points([1, 2, 3, 4]), { sma: 2, ema: 2, rsi: 2, macdFast: 2, macdSlow: 3, macdSignal: 2, bollinger: 2, bollingerStdDev: 2 })
    expect(rising.rsi[2].value).toBe(100)
  })

  it('calculates MACD line, signal and histogram after warm-up', () => {
    const result = calculateTechnicalIndicators(points([1, 2, 3, 4, 5, 6]), { sma: 2, ema: 2, rsi: 2, macdFast: 2, macdSlow: 3, macdSignal: 2, bollinger: 2, bollingerStdDev: 2 })
    expect(result.macd[2].macd).toBeCloseTo(0.5)
    expect(result.macd[3].signal).toBeCloseTo(0.5)
    expect(result.macd[3].histogram).toBeCloseTo(0)
    expect(result.macd[2].signal).toBeNull()
  })

  it('resets warm-up windows across missing observations and reports insufficiency', () => {
    const result = calculateTechnicalIndicators(points([1, 2, null, 4]), { sma: 3, ema: 3, rsi: 2, macdFast: 2, macdSlow: 3, macdSignal: 2, bollinger: 3, bollingerStdDev: 2 })
    expect(result.sma.map((point) => point.value)).toEqual([null, null, null, null])
    expect(result.availability.sma.available).toBe(false)
    expect(result.availability.sma.message).toContain('only 2')
  })

  it('rejects invalid period relationships', () => {
    expect(() => calculateTechnicalIndicators(points([1, 2, 3]), { sma: 2, ema: 2, rsi: 2, macdFast: 3, macdSlow: 2, macdSignal: 2, bollinger: 2, bollingerStdDev: 2 })).toThrow(/fast period/)
  })
})
