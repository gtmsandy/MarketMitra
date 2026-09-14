import { useEffect, useState } from 'react'
import { getMostActiveStocks, getTopGainers, getTopLosers } from '../api/market'
import ErrorState from '../components/ErrorState'
import LoadingState from '../components/LoadingState'
import MarketMoversTable from '../components/MarketMoversTable'
import MostActiveTable from '../components/MostActiveTable'
import type { MarketMover, MostActiveStock } from '../types/market'
export default function MarketMoversPage() {
  const [data, setData] = useState<{gainers: MarketMover[]; losers: MarketMover[]; active: MostActiveStock[]} | null>(null)
  const [error, setError] = useState(false)
  const load = () => { setError(false); void Promise.all([getTopGainers(), getTopLosers(), getMostActiveStocks()]).then(([gainers, losers, active]) => setData({gainers, losers, active})).catch(() => setError(true)) }
  useEffect(() => { const timer = window.setTimeout(load, 0); return () => window.clearTimeout(timer) }, [])
  if (!data && !error) return <LoadingState />
  if (error || !data) return <ErrorState onRetry={load} />
  const date = data.gainers[0]?.observation_date ?? data.losers[0]?.observation_date ?? data.active[0]?.observation_date
  return <main className="analytics-page"><div className="section-heading"><div><p className="section-heading__eyebrow">Market Analytics</p><h1>Market Movers</h1></div><p>{date ? `Equity session: ${date}` : 'Latest available equity rankings'}</p></div><section className="market-tables" aria-label="Market movers"><MarketMoversTable title="Top Equity Gainers" rows={data.gainers} limit={10} /><MarketMoversTable title="Top Equity Losers" rows={data.losers} limit={10} /><MostActiveTable title="Most Active Equities" rows={data.active} limit={15} /></section></main>
}
