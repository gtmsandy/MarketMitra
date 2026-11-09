import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './index.css'
import App from './App.tsx'
import { LiveMarketProvider } from './live/LiveMarketContext'
import { AuthProvider } from './auth/AuthContext'

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <AuthProvider><LiveMarketProvider><App /></LiveMarketProvider></AuthProvider>
  </StrictMode>,
)
