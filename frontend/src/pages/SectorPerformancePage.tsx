import { useEffect, useState } from 'react'
import { getSectorAnalytics } from '../api/market'
import ErrorState from '../components/ErrorState'
import LoadingState from '../components/LoadingState'
import SectorPerformanceSection from '../components/SectorPerformanceSection'
import type { SectorPerformance } from '../types/market'
export default function SectorPerformancePage() { const [data, setData] = useState<SectorPerformance[] | null>(null); const [error,setError]=useState(false); const load=()=>{setError(false);void getSectorAnalytics().then(setData).catch(()=>setError(true))}; useEffect(()=>{const timer=window.setTimeout(load,0); return()=>window.clearTimeout(timer)},[]); if(!data&&!error)return <LoadingState/>; if(error||!data)return <ErrorState onRetry={load}/>; return <main className="analytics-page"><div className="section-heading"><div><p className="section-heading__eyebrow">Market Analytics</p><h1>Sector Performance</h1></div><p>Common equity session aggregation</p></div>{data.length ? <SectorPerformanceSection sectors={data}/> : <p className="empty-state">No sector data is available.</p>}</main> }
