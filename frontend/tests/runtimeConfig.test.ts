import { describe, expect, it } from 'vitest'

import { resolveApiBaseUrl, toWebSocketUrl } from '../src/config/runtime'

describe('resolveApiBaseUrl', () => {
  it('preserves the localhost fallback during development', () => {
    expect(resolveApiBaseUrl({ mode: 'development' })).toBe(
      'http://127.0.0.1:8000',
    )
  })

  it('requires an explicit API URL for production', () => {
    expect(() => resolveApiBaseUrl({ mode: 'production' })).toThrow(
      'VITE_API_BASE_URL is required',
    )
  })

  it('requires HTTPS for the production API URL', () => {
    expect(() =>
      resolveApiBaseUrl({
        mode: 'production',
        configuredUrl: 'http://api.example.com',
      }),
    ).toThrow('must use HTTPS')
  })

  it('rejects credentials, query strings, and fragments', () => {
    for (const configuredUrl of [
      'https://user:secret@api.example.com',
      'https://api.example.com?token=secret',
      'https://api.example.com/#fragment',
    ]) {
      expect(() =>
        resolveApiBaseUrl({ mode: 'production', configuredUrl }),
      ).toThrow('valid API origin')
    }
  })

  it('normalizes an explicit API origin', () => {
    expect(
      resolveApiBaseUrl({
        mode: 'production',
        configuredUrl: 'https://api.example.com/',
      }),
    ).toBe('https://api.example.com')
  })
})

describe('toWebSocketUrl', () => {
  it('maps HTTPS to WSS', () => {
    expect(toWebSocketUrl('https://api.example.com')).toBe(
      'wss://api.example.com/api/v1/ws/market',
    )
  })

  it('maps development HTTP to WS', () => {
    expect(toWebSocketUrl('http://127.0.0.1:8000')).toBe(
      'ws://127.0.0.1:8000/api/v1/ws/market',
    )
  })
})
