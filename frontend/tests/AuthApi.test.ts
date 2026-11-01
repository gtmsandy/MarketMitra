import { afterEach, describe, expect, it, vi } from 'vitest'

import { getSession, logoutIdentity } from '../src/api/auth'

afterEach(() => {
  vi.unstubAllGlobals()
})

describe('identity API client', () => {
  it('bootstraps with the HttpOnly cookie credential mode', async () => {
    const fetchMock = vi.fn().mockResolvedValue(new Response(JSON.stringify({ user: {}, csrf_token: 'csrf', expires_at: 'later' }), { status: 200 }))
    vi.stubGlobal('fetch', fetchMock)

    await getSession()

    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringMatching(/\/api\/v1\/auth\/session$/),
      expect.objectContaining({ credentials: 'include' }),
    )
  })

  it('sends CSRF only in the mutation header', async () => {
    const fetchMock = vi.fn().mockResolvedValue(new Response(null, { status: 204 }))
    vi.stubGlobal('fetch', fetchMock)

    await logoutIdentity('csrf-only-in-memory')

    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringMatching(/\/api\/v1\/auth\/logout$/),
      expect.objectContaining({
        method: 'POST',
        credentials: 'include',
        headers: { 'X-CSRF-Token': 'csrf-only-in-memory' },
      }),
    )
  })
})
