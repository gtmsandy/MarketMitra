import { useEffect, useRef } from 'react'
import { createChart, LineSeries, type IChartApi, type ISeriesApi, type LineData, type Time } from 'lightweight-charts'

import type { PriceHistoryPoint } from '../types/market'

type PriceChartProps = {
  data: PriceHistoryPoint[]
}

function PriceChart({ data }: PriceChartProps) {
  const containerRef = useRef<HTMLDivElement>(null)
  const chartRef = useRef<IChartApi | null>(null)
  const seriesRef = useRef<ISeriesApi<'Line'> | null>(null)

  useEffect(() => {
    if (!containerRef.current) return

    const chart = createChart(containerRef.current, {
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
      rightPriceScale: {
        borderColor: '#d9e0e6',
      },
      timeScale: {
        borderColor: '#d9e0e6',
        fixLeftEdge: true,
        fixRightEdge: true,
      },
      crosshair: {
        vertLine: { color: '#d9e0e6', width: 1, style: 3 },
        horzLine: { color: '#d9e0e6', width: 1, style: 3 },
      },
      handleScale: false,
      handleScroll: false,
    })

    const series = chart.addSeries(LineSeries, {
      color: '#1e4e79',
      lineWidth: 2,
      crosshairMarkerRadius: 4,
      crosshairMarkerBorderColor: '#1e4e79',
      crosshairMarkerBackgroundColor: '#ffffff',
      priceFormat: {
        type: 'price',
        precision: 2,
        minMove: 0.01,
      },
    })

    chartRef.current = chart
    seriesRef.current = series

    const resizeObserver = new ResizeObserver((entries) => {
      for (const entry of entries) {
        const { width } = entry.contentRect
        chart.resize(width, 320)
      }
    })
    resizeObserver.observe(containerRef.current)

    return () => {
      resizeObserver.disconnect()
      chart.remove()
      chartRef.current = null
      seriesRef.current = null
    }
  }, [])

  useEffect(() => {
    if (!seriesRef.current || data.length === 0) return

    const lineData: LineData<Time>[] = data.map((point) => ({
      time: point.date as Time,
      value: point.close,
    }))

    seriesRef.current.setData(lineData)
    chartRef.current?.timeScale().fitContent()
  }, [data])

  return (
    <div className="price-chart">
      <div className="price-chart__container" ref={containerRef} />
    </div>
  )
}

export default PriceChart
