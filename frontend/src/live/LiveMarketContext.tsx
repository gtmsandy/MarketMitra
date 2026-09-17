import { createContext, useEffect, useMemo, useRef, useState, type ReactNode } from 'react'

export type LiveConnectionState = 'CONNECTING' | 'CONNECTED' | 'RECONNECTING' | 'DISCONNECTED'
export type LiveState = { provider: string; market_status: string; data_freshness: string; index?: number | null; quotes: Record<string, { ltp?: number|null; change_percent?: number|null; change?: number|null; open?: number|null; high?: number|null; low?: number|null; volume?: number|null; turnover?: number|null; provider_timestamp?: string|null }> }
const LiveContext = createContext<{state: LiveState|null; connection: LiveConnectionState}>({state:null, connection:'DISCONNECTED'})

export function LiveMarketProvider({children}:{children:ReactNode}) {
  const [state,setState]=useState<LiveState|null>(null); const [connection,setConnection]=useState<LiveConnectionState>('DISCONNECTED'); const retry=useRef(500); const socket=useRef<WebSocket|null>(null); const stopped=useRef(false)
  useEffect(()=>{ stopped.current=false; let timer:number|undefined
    const connect=()=>{ if(stopped.current) return; setConnection(retry.current===500?'CONNECTING':'RECONNECTING'); const proto=location.protocol==='https:'?'wss':'ws'; const apiUrl=import.meta.env.VITE_API_BASE_URL ?? `${location.protocol}//${location.host}`; const parsed=new URL(apiUrl); const ws=new WebSocket(`${proto}://${parsed.host}/api/v1/ws/market`); socket.current=ws
      ws.onopen=()=>{setConnection('CONNECTED');retry.current=500}; ws.onmessage=(e)=>{try{const m=JSON.parse(e.data);if(m.type==='snapshot')setState(m.data); if(m.type==='quote_update')setState(prev=>prev?({...prev,quotes:{...prev.quotes,[m.data.symbol]:m.data}}):prev)}catch{}}; ws.onclose=()=>{if(!stopped.current){setConnection('RECONNECTING');timer=window.setTimeout(connect,retry.current);retry.current=Math.min(retry.current*2,10000)}}; ws.onerror=()=>ws.close()
    }; connect(); return()=>{stopped.current=true;if(timer)clearTimeout(timer);socket.current?.close();setConnection('DISCONNECTED')}
  },[])
  const value=useMemo(()=>({state,connection}),[state,connection]); return <LiveContext.Provider value={value}>{children}</LiveContext.Provider>
}
export { LiveContext }
