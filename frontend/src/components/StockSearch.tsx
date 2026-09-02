import { useCallback, useEffect, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'

import { searchStocks } from '../api/market'
import type { StockQuote } from '../types/market'
import { useDebounce } from '../hooks/useDebounce'

function StockSearch() {
  const [query, setQuery] = useState('')
  const [results, setResults] = useState<StockQuote[]>([])
  const [isOpen, setIsOpen] = useState(false)
  const debouncedQuery = useDebounce(query, 300)
  const navigate = useNavigate()
  const containerRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (!debouncedQuery.trim()) {
      setResults([])
      setIsOpen(false)
      return
    }

    let cancelled = false
    searchStocks(debouncedQuery).then((data) => {
      if (!cancelled) {
        setResults(data)
        setIsOpen(data.length > 0)
      }
    }).catch(() => {
      if (!cancelled) {
        setResults([])
        setIsOpen(false)
      }
    })

    return () => { cancelled = true }
  }, [debouncedQuery])

  const handleSelect = useCallback((symbol: string) => {
    setQuery('')
    setResults([])
    setIsOpen(false)
    navigate(`/stocks/${symbol}`)
  }, [navigate])

  useEffect(() => {
    function handleClickOutside(e: MouseEvent) {
      if (containerRef.current && !containerRef.current.contains(e.target as Node)) {
        setIsOpen(false)
      }
    }
    document.addEventListener('mousedown', handleClickOutside)
    return () => document.removeEventListener('mousedown', handleClickOutside)
  }, [])

  function handleKeyDown(e: React.KeyboardEvent) {
    if (e.key === 'Escape') {
      setIsOpen(false)
      setQuery('')
    }
  }

  return (
    <div className="stock-search" ref={containerRef}>
      <input
        className="stock-search__input"
        type="text"
        placeholder="Search stocks…"
        value={query}
        onChange={(e) => setQuery(e.target.value)}
        onKeyDown={handleKeyDown}
        aria-label="Search stocks by symbol or company name"
      />
      {isOpen && results.length > 0 && (
        <ul className="stock-search__results" role="listbox">
          {results.map((stock) => (
            <li key={stock.symbol} role="option">
              <button
                className="stock-search__result"
                type="button"
                onClick={() => handleSelect(stock.symbol)}
              >
                <span className="stock-search__symbol">{stock.symbol}</span>
                <span className="stock-search__name">{stock.company_name}</span>
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}

export default StockSearch
