import { useContext } from 'react'
import { LiveContext } from './LiveMarketContext'
export const useLiveMarket = () => useContext(LiveContext)
