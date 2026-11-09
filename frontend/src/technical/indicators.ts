export type IndicatorInput = { date: string; close: number | null }
export type IndicatorValue = { date: string; value: number | null }
export type BollingerValue = { date: string; middle: number | null; upper: number | null; lower: number | null }
export type MacdValue = { date: string; macd: number | null; signal: number | null; histogram: number | null }

export type IndicatorPeriods = {
  sma: number
  ema: number
  rsi: number
  macdFast: number
  macdSlow: number
  macdSignal: number
  bollinger: number
  bollingerStdDev: number
}

export type IndicatorAvailability = {
  required: number
  available: boolean
  message: string
}

export type TechnicalIndicators = {
  dates: string[]
  sma: IndicatorValue[]
  ema: IndicatorValue[]
  rsi: IndicatorValue[]
  macd: MacdValue[]
  bollinger: BollingerValue[]
  availability: {
    sma: IndicatorAvailability
    ema: IndicatorAvailability
    rsi: IndicatorAvailability
    macd: IndicatorAvailability
    bollinger: IndicatorAvailability
  }
}

export const DEFAULT_INDICATOR_PERIODS: IndicatorPeriods = {
  sma: 20,
  ema: 20,
  rsi: 14,
  macdFast: 12,
  macdSlow: 26,
  macdSignal: 9,
  bollinger: 20,
  bollingerStdDev: 2,
}

const MIN_PERIOD = 2
const MAX_PERIOD = 200

function validatePeriod(name: string, period: number): number {
  if (!Number.isInteger(period) || period < MIN_PERIOD || period > MAX_PERIOD) {
    throw new RangeError(`${name} must be an integer between ${MIN_PERIOD} and ${MAX_PERIOD}`)
  }
  return period
}

function validClose(value: number | null): value is number {
  return value !== null && Number.isFinite(value)
}

function mean(values: number[]): number {
  return values.reduce((sum, value) => sum + value, 0) / values.length
}

function populationStandardDeviation(values: number[], average: number): number {
  return Math.sqrt(mean(values.map((value) => (value - average) ** 2)))
}

function sortedInputs(data: IndicatorInput[]): IndicatorInput[] {
  return [...data].sort((left, right) => left.date.localeCompare(right.date))
}

function availability(name: string, required: number, data: IndicatorInput[]): IndicatorAvailability {
  let longestRun = 0
  let run = 0
  for (const point of data) {
    if (validClose(point.close)) {
      run += 1
      longestRun = Math.max(longestRun, run)
    } else run = 0
  }
  return {
    required,
    available: longestRun >= required,
    message: longestRun >= required
      ? `${name} has enough valid observations.`
      : `${name} requires ${required} consecutive valid observations; only ${longestRun} are available.`,
  }
}

function rollingAverage(data: IndicatorInput[], period: number): IndicatorValue[] {
  const values: IndicatorValue[] = []
  let window: number[] = []
  for (const point of data) {
    if (!validClose(point.close)) {
      window = []
      values.push({ date: point.date, value: null })
      continue
    }
    window = [...window, point.close].slice(-period)
    values.push({ date: point.date, value: window.length === period ? mean(window) : null })
  }
  return values
}

type EmaState = { seed: number[]; value: number | null }

function newEmaState(): EmaState {
  return { seed: [], value: null }
}

function updateEma(state: EmaState, value: number, period: number): number | null {
  if (state.value === null) {
    state.seed.push(value)
    if (state.seed.length < period) return null
    state.value = mean(state.seed)
    return state.value
  }
  state.value = (value - state.value) * (2 / (period + 1)) + state.value
  return state.value
}

function exponentialAverage(data: IndicatorInput[], period: number): IndicatorValue[] {
  const values: IndicatorValue[] = []
  let state = newEmaState()
  for (const point of data) {
    if (!validClose(point.close)) {
      state = newEmaState()
      values.push({ date: point.date, value: null })
      continue
    }
    values.push({ date: point.date, value: updateEma(state, point.close, period) })
  }
  return values
}

function relativeStrengthIndex(data: IndicatorInput[], period: number): IndicatorValue[] {
  const values: IndicatorValue[] = []
  let previous: number | null = null
  let gains: number[] = []
  let losses: number[] = []
  let averageGain: number | null = null
  let averageLoss: number | null = null

  for (const point of data) {
    if (!validClose(point.close)) {
      previous = null
      gains = []
      losses = []
      averageGain = null
      averageLoss = null
      values.push({ date: point.date, value: null })
      continue
    }
    if (previous === null) {
      previous = point.close
      values.push({ date: point.date, value: null })
      continue
    }
    const change = point.close - previous
    previous = point.close
    const gain = Math.max(change, 0)
    const loss = Math.max(-change, 0)
    if (averageGain === null || averageLoss === null) {
      gains = [...gains, gain].slice(-period)
      losses = [...losses, loss].slice(-period)
      if (gains.length < period) {
        values.push({ date: point.date, value: null })
        continue
      }
      averageGain = mean(gains)
      averageLoss = mean(losses)
    } else {
      averageGain = ((averageGain * (period - 1)) + gain) / period
      averageLoss = ((averageLoss * (period - 1)) + loss) / period
    }
    let rsi = 50
    if (averageLoss === 0 && averageGain > 0) rsi = 100
    else if (averageGain === 0 && averageLoss > 0) rsi = 0
    else if (averageGain !== 0 || averageLoss !== 0) {
      const relativeStrength = averageGain / averageLoss
      rsi = 100 - (100 / (1 + relativeStrength))
    }
    values.push({ date: point.date, value: rsi })
  }
  return values
}

function movingAverageConvergenceDivergence(
  data: IndicatorInput[],
  fastPeriod: number,
  slowPeriod: number,
  signalPeriod: number,
): MacdValue[] {
  const values: MacdValue[] = []
  let fast = newEmaState()
  let slow = newEmaState()
  let signal = newEmaState()
  for (const point of data) {
    if (!validClose(point.close)) {
      fast = newEmaState()
      slow = newEmaState()
      signal = newEmaState()
      values.push({ date: point.date, macd: null, signal: null, histogram: null })
      continue
    }
    const fastValue = updateEma(fast, point.close, fastPeriod)
    const slowValue = updateEma(slow, point.close, slowPeriod)
    if (fastValue === null || slowValue === null) {
      values.push({ date: point.date, macd: null, signal: null, histogram: null })
      continue
    }
    const macd = fastValue - slowValue
    const signalValue = updateEma(signal, macd, signalPeriod)
    values.push({
      date: point.date,
      macd,
      signal: signalValue,
      histogram: signalValue === null ? null : macd - signalValue,
    })
  }
  return values
}

function bollingerBands(data: IndicatorInput[], period: number, standardDeviations: number): BollingerValue[] {
  const values: BollingerValue[] = []
  let window: number[] = []
  for (const point of data) {
    if (!validClose(point.close)) {
      window = []
      values.push({ date: point.date, middle: null, upper: null, lower: null })
      continue
    }
    window = [...window, point.close].slice(-period)
    if (window.length < period) {
      values.push({ date: point.date, middle: null, upper: null, lower: null })
      continue
    }
    const middle = mean(window)
    const spread = populationStandardDeviation(window, middle) * standardDeviations
    values.push({ date: point.date, middle, upper: middle + spread, lower: middle - spread })
  }
  return values
}

export function calculateTechnicalIndicators(
  input: IndicatorInput[],
  periods: IndicatorPeriods = DEFAULT_INDICATOR_PERIODS,
): TechnicalIndicators {
  const validated = {
    sma: validatePeriod('SMA period', periods.sma),
    ema: validatePeriod('EMA period', periods.ema),
    rsi: validatePeriod('RSI period', periods.rsi),
    macdFast: validatePeriod('MACD fast period', periods.macdFast),
    macdSlow: validatePeriod('MACD slow period', periods.macdSlow),
    macdSignal: validatePeriod('MACD signal period', periods.macdSignal),
    bollinger: validatePeriod('Bollinger period', periods.bollinger),
    bollingerStdDev: periods.bollingerStdDev,
  }
  if (validated.macdFast >= validated.macdSlow) {
    throw new RangeError('MACD fast period must be less than slow period')
  }
  if (!Number.isFinite(validated.bollingerStdDev) || validated.bollingerStdDev <= 0 || validated.bollingerStdDev > 5) {
    throw new RangeError('Bollinger standard deviations must be greater than 0 and no more than 5')
  }
  const data = sortedInputs(input)
  return {
    dates: data.map((point) => point.date),
    sma: rollingAverage(data, validated.sma),
    ema: exponentialAverage(data, validated.ema),
    rsi: relativeStrengthIndex(data, validated.rsi),
    macd: movingAverageConvergenceDivergence(data, validated.macdFast, validated.macdSlow, validated.macdSignal),
    bollinger: bollingerBands(data, validated.bollinger, validated.bollingerStdDev),
    availability: {
      sma: availability('SMA', validated.sma, data),
      ema: availability('EMA', validated.ema, data),
      rsi: availability('RSI', validated.rsi + 1, data),
      macd: availability('MACD', validated.macdSlow + validated.macdSignal - 1, data),
      bollinger: availability('Bollinger Bands', validated.bollinger, data),
    },
  }
}
