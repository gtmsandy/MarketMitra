import { useCallback, useEffect, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'

import { searchStocks } from '../api/market'
import type { StockQuote } from '../types/market'
import { useDebounce } from '../hooks/useDebounce'

function StockSearch() {
  const [query, setQuery] = useState('')
  const [results, setResults] = useState<StockQuote[]>([])
  const [isOpen, setIsOpen] = useState(false)
  const [activeIndex, setActiveIndex] = useState(-1)
  const debouncedQuery = useDebounce(query, 300)
  const navigate = useNavigate()
  const containerRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (!debouncedQuery.trim()) {
      return
    }

    let cancelled = false
    searchStocks(debouncedQuery).then((data) => {
      if (!cancelled) {
        setResults(data)
        setIsOpen(true)
        setActiveIndex(-1)
      }
    }).catch(() => {
      if (!cancelled) {
        setResults([])
        setIsOpen(true)
      }
    })

    return () => { cancelled = true }
  }, [debouncedQuery])

  const handleSelect = useCallback((symbol: string) => {
    setQuery('')
    setResults([])
    setIsOpen(false)
    setActiveIndex(-1)
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
      setActiveIndex(-1)
      return
    }

    const visibleResults = results.slice(0, 10)
    if (!isOpen || visibleResults.length === 0) return

    if (e.key === 'ArrowDown') {
      e.preventDefault()
      setActiveIndex((current) => (current + 1) % visibleResults.length)
    } else if (e.key === 'ArrowUp') {
      e.preventDefault()
      setActiveIndex((current) =>
        current <= 0 ? visibleResults.length - 1 : current - 1,
      )
    } else if (e.key === 'Enter' && activeIndex >= 0) {
      e.preventDefault()
      handleSelect(visibleResults[activeIndex].symbol)
    }
  }

  const visibleResults = results.slice(0, 10)
  const activeOptionId = activeIndex >= 0
    ? `stock-search-option-${visibleResults[activeIndex]?.symbol}`
    : undefined

  return (
    <div className="stock-search" ref={containerRef}>
      <input
        className="stock-search__input"
        type="text"
        placeholder="Search stocks…"
        value={query}
        onChange={(e) => {
          const nextQuery = e.target.value
          setQuery(nextQuery)
          if (!nextQuery.trim()) {
            setResults([])
            setIsOpen(false)
            setActiveIndex(-1)
          }
        }}
        onFocus={() => {
          if (query.trim()) setIsOpen(true)
        }}
        onKeyDown={handleKeyDown}
        role="combobox"
        aria-autocomplete="list"
        aria-expanded={isOpen}
        aria-controls={isOpen ? 'stock-search-results' : undefined}
        aria-activedescendant={activeOptionId}
        aria-label="Search stocks by symbol or company name"
      />
      {isOpen && (
        <ul className="stock-search__results" id="stock-search-results" role="listbox">
          {visibleResults.length > 0 ? (
            visibleResults.map((stock, index) => (
              <li key={stock.symbol} role="none">
                <button
                  id={`stock-search-option-${stock.symbol}`}
                  className="stock-search__result"
                  type="button"
                  role="option"
                  aria-selected={activeIndex === index}
                  tabIndex={-1}
                  onMouseEnter={() => setActiveIndex(index)}
                  onClick={() => handleSelect(stock.symbol)}
                >
                  <span className="stock-search__symbol">{stock.symbol}</span>
                  <span className="stock-search__name">{stock.company_name}</span>
                </button>
              </li>
            ))
          ) : (
            <li className="stock-search__empty">No stocks matching &quot;{debouncedQuery}&quot;</li>
          )}
        </ul>
      )}
    </div>
  )
}

export default StockSearch
