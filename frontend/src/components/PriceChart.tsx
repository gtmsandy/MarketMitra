import { useEffect, useRef, useState } from 'react'
import {
  CandlestickSeries,
  createChart,
  HistogramSeries,
  LineSeries,
  type ISeriesApi,
  type Time,
} from 'lightweight-charts'

import type { PriceHistoryPoint } from '../types/market'
import type { IndicatorValue, MacdValue, TechnicalIndicators } from '../technical/indicators'

export type ChartDisplayOptions = {
  candleMode: boolean
  showVolume: boolean
  showSma: boolean
  showEma: boolean
  showBollinger: boolean
  showRsi: boolean
  showMacd: boolean
}

type PriceChartProps = {
  data: PriceHistoryPoint[]
  indicators?: TechnicalIndicators
  options?: ChartDisplayOptions
}

const defaultOptions: ChartDisplayOptions = {
  candleMode: false,
  showVolume: true,
  showSma: false,
  showEma: false,
  showBollinger: false,
  showRsi: false,
  showMacd: false,
}

const chartOptions = {
  layout: {
    background: { color: '#ffffff' },
    textColor: '#5e6b78',
    fontFamily: 'Inter, "Segoe UI", system-ui, sans-serif',
    fontSize: 11,
  },
  grid: {
    vertLines: { color: '#f0f2f4' },
    horzLines: { color: '#f0f2f4' },
  },
  rightPriceScale: { borderColor: '#d9e0e6' },
  timeScale: { borderColor: '#d9e0e6', fixLeftEdge: true, fixRightEdge: true },
  crosshair: {
    vertLine: { color: '#d9e0e6', width: 1, style: 3 },
    horzLine: { color: '#d9e0e6', width: 1, style: 3 },
  },
  handleScale: false,
  handleScroll: false,
} as const

function toChartTime(value: string): Time {
  if (!value.includes('T')) return value as Time
  return Math.floor(new Date(value).getTime() / 1000) as Time
}

function lineData(data: IndicatorValue[]) {
  return data.flatMap((point) => point.value === null ? [] : [{ time: toChartTime(point.date), value: point.value }])
}

function IndicatorPanel({ title, lines }: { title: string; lines: Array<{ data: IndicatorValue[]; color: string }> }) {
  const containerRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (!containerRef.current) return
    const chart = createChart(containerRef.current, { ...chartOptions, height: 180 })
    lines.forEach((line) => {
      const series = chart.addSeries(LineSeries, { color: line.color, lineWidth: 1 })
      series.setData(lineData(line.data))
    })
    chart.timeScale().fitContent()
    const resizeObserver = new ResizeObserver((entries) => {
      for (const entry of entries) chart.resize(entry.contentRect.width, 180)
    })
    resizeObserver.observe(containerRef.current)
    return () => {
      resizeObserver.disconnect()
      chart.remove()
    }
  }, [lines])

  return <section className="technical-chart-panel" aria-label={title}><h3>{title}</h3><div className="technical-chart-panel__container" ref={containerRef} /></section>
}

function PriceChart({ data, indicators, options = defaultOptions }: PriceChartProps) {
  const containerRef = useRef<HTMLDivElement>(null)
  const [hoverLabel, setHoverLabel] = useState('')

  useEffect(() => {
    if (!containerRef.current || data.length === 0) return
    const chart = createChart(containerRef.current, { ...chartOptions, height: 320 })
    let hoverSeries: ISeriesApi<'Line'> | null = null
    if (options.candleMode) {
      const series = chart.addSeries(CandlestickSeries, {
        upColor: '#18794e', downColor: '#c33c54', borderVisible: false,
        wickUpColor: '#18794e', wickDownColor: '#c33c54',
      })
      series.setData(data.map((point) => ({ time: toChartTime(point.date), open: point.open, high: point.high, low: point.low, close: point.close })))
    } else {
      hoverSeries = chart.addSeries(LineSeries, {
        color: '#1e4e79', lineWidth: 2, crosshairMarkerRadius: 4,
        crosshairMarkerBorderColor: '#1e4e79', crosshairMarkerBackgroundColor: '#ffffff',
        priceFormat: { type: 'price', precision: 2, minMove: 0.01 },
      })
      hoverSeries.setData(data.map((point) => ({ time: toChartTime(point.date), value: point.close })))
    }
    if (options.showVolume) {
      const volume = chart.addSeries(HistogramSeries, {
        color: '#9bb7cb', priceFormat: { type: 'volume' }, priceScaleId: 'volume',
      })
      volume.priceScale().applyOptions({ scaleMargins: { top: 0.82, bottom: 0 } })
      volume.setData(data.map((point) => ({ time: toChartTime(point.date), value: point.volume })))
    }
    const addOverlay = (seriesData: IndicatorValue[], color: string) => {
      const series = chart.addSeries(LineSeries, { color, lineWidth: 1 })
      series.setData(lineData(seriesData))
    }
    if (indicators && options.showSma) addOverlay(indicators.sma, '#2563eb')
    if (indicators && options.showEma) addOverlay(indicators.ema, '#d97706')
    if (indicators && options.showBollinger) {
      addOverlay(indicators.bollinger.map((point) => ({ date: point.date, value: point.upper })), '#7c3aed')
      addOverlay(indicators.bollinger.map((point) => ({ date: point.date, value: point.middle })), '#a78bfa')
      addOverlay(indicators.bollinger.map((point) => ({ date: point.date, value: point.lower })), '#7c3aed')
    }
    chart.subscribeCrosshairMove((param) => {
      if (!param.time) {
        setHoverLabel('')
        return
      }
      const value = hoverSeries ? param.seriesData.get(hoverSeries) : undefined
      const price = value && 'value' in value ? value.value : undefined
      setHoverLabel(`${String(param.time)}${typeof price === 'number' ? ` · NPR ${price.toFixed(2)}` : ''}`)
    })
    chart.timeScale().fitContent()
    const resizeObserver = new ResizeObserver((entries) => {
      for (const entry of entries) chart.resize(entry.contentRect.width, 320)
    })
    resizeObserver.observe(containerRef.current)
    return () => {
      resizeObserver.disconnect()
      chart.remove()
    }
  }, [data, indicators, options])

  const macdLines: Array<{ data: IndicatorValue[]; color: string }> = indicators ? [
    { data: indicators.macd.map((point: MacdValue) => ({ date: point.date, value: point.macd })), color: '#1e4e79' },
    { data: indicators.macd.map((point: MacdValue) => ({ date: point.date, value: point.signal })), color: '#d97706' },
  ] : []
  return <div className="price-chart">
    {hoverLabel && <p className="price-chart__hover" role="status">{hoverLabel}</p>}
    <div className="price-chart__container" ref={containerRef} />
    {indicators && options.showRsi && indicators.availability.rsi.available && <IndicatorPanel title="RSI" lines={[{ data: indicators.rsi, color: '#7c3aed' }]} />}
    {indicators && options.showMacd && indicators.availability.macd.available && <IndicatorPanel title="MACD" lines={macdLines} />}
  </div>
}

export default PriceChart
