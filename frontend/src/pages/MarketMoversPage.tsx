import { useEffect, useState } from 'react'
import { getMostActiveStocks, getTopGainers, getTopLosers } from '../api/market'
import ErrorState from '../components/ErrorState'
import LoadingState from '../components/LoadingState'
import MarketMoversTable from '../components/MarketMoversTable'
import MostActiveTable from '../components/MostActiveTable'
import type { MarketMover, MostActiveStock } from '../types/market'
import { useLiveMarket } from '../live/useLiveMarket'
export default function MarketMoversPage() {
  const live = useLiveMarket()
  const [data, setData] = useState<{gainers: MarketMover[]; losers: MarketMover[]; active: MostActiveStock[]} | null>(null)
  const [error, setError] = useState(false)
  const load = () => { setError(false); void Promise.all([getTopGainers(), getTopLosers(), getMostActiveStocks()]).then(([gainers, losers, active]) => setData({gainers, losers, active})).catch(() => setError(true)) }
  useEffect(() => { const timer = window.setTimeout(load, 0); return () => window.clearTimeout(timer) }, [])
  if (!data && !error) return <LoadingState />
  if (error || !data) return <ErrorState onRetry={load} />
  const liveRows = live.state ? Object.entries(live.state.quotes).map(([symbol,q])=>({symbol, ltp:q.ltp ?? 0, change_percent:q.change_percent ?? 0, volume:q.volume ?? 0, turnover:q.turnover ?? 0})) : []
  const gainers = liveRows.length ? liveRows.filter(x=>x.change_percent>0).sort((a,b)=>b.change_percent-a.change_percent).map(x=>({ ...x, company_name:x.symbol })) : data.gainers
  const losers = liveRows.length ? liveRows.filter(x=>x.change_percent<0).sort((a,b)=>a.change_percent-b.change_percent).map(x=>({ ...x, company_name:x.symbol })) : data.losers
  const active = liveRows.length ? liveRows.sort((a,b)=>b.volume-a.volume).map(x=>({ ...x, company_name:x.symbol })) : data.active
  const date = data.gainers[0]?.observation_date ?? data.losers[0]?.observation_date ?? data.active[0]?.observation_date
  return <main className="analytics-page"><div className="section-heading"><div><p className="section-heading__eyebrow">Market Analytics</p><h1>Market Movers</h1></div><p>{live.state?.provider === 'DEVELOPMENT_REPLAY' ? 'DEVELOPMENT REPLAY' : (date ? `Equity session: ${date}` : 'Latest available equity rankings')}</p></div><section className="market-tables" aria-label="Market movers"><MarketMoversTable title="Top Equity Gainers" rows={gainers} limit={10} /><MarketMoversTable title="Top Equity Losers" rows={losers} limit={10} /><MostActiveTable title="Most Active Equities" rows={active} limit={15} /></section></main>
}
