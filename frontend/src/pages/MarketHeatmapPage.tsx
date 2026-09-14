import { useEffect, useState } from 'react'
import { getMarketHeatmap } from '../api/market'
import ErrorState from '../components/ErrorState'
import LoadingState from '../components/LoadingState'
import MarketHeatmapSection from '../components/MarketHeatmapSection'
import type { HeatmapItem } from '../types/market'
export default function MarketHeatmapPage() { const [data,setData]=useState<HeatmapItem[]|null>(null); const [error,setError]=useState(false); const load=()=>{setError(false);void getMarketHeatmap().then(setData).catch(()=>setError(true))}; useEffect(()=>{const timer=window.setTimeout(load,0); return()=>window.clearTimeout(timer)},[]); if(!data&&!error)return <LoadingState/>; if(error||!data)return <ErrorState onRetry={load}/>; return <main className="analytics-page"><div className="section-heading"><div><p className="section-heading__eyebrow">Market Analytics</p><h1>Market Heatmap</h1></div><p>Common equity performance by symbol</p></div>{data.length ? <MarketHeatmapSection items={data}/> : <p className="empty-state">No heatmap data is available.</p>}</main> }
