import { expect, type APIRequestContext, type Page } from '@playwright/test'

export const apiBaseURL = process.env.PLAYWRIGHT_API_BASE_URL ?? 'http://127.0.0.1:8000'

export async function verifyLocalApi(request: APIRequestContext) {
  const response = await request.get(`${apiBaseURL}/api/v1/health/live`)
  expect(response.ok(), `Backend health probe returned ${response.status()}`).toBeTruthy()
  await expect(response.json()).resolves.toMatchObject({ status: 'ok' })
}

export function diagnostics(page: Page) {
  const pageErrors: string[] = []
  const consoleErrors: string[] = []
  const failedRequests: string[] = []
  const badResponses: string[] = []

  page.on('pageerror', (error) => pageErrors.push(error.message))
  page.on('console', (message) => {
    if (message.type() === 'error' && !/401 \(Unauthorized\)|404 \(Not Found\)/i.test(message.text())) consoleErrors.push(message.text())
  })
  page.on('requestfailed', (request) => {
    const failure = request.failure()?.errorText ?? 'unknown failure'
    if (failure !== 'net::ERR_ABORTED') failedRequests.push(`${request.method()} ${request.url()} — ${failure}`)
  })
  page.on('response', (response) => {
    const status = response.status()
    // Anonymous public pages legitimately probe protected APIs and receive 401.
    const isBrowserFaviconProbe = status === 404 && new URL(response.url()).pathname === '/favicon.ico'
    if (status >= 500 || (status >= 400 && status !== 401 && !isBrowserFaviconProbe)) badResponses.push(`${status} ${response.request().method()} ${response.url()}`)
  })

  return {
    assertClean() {
      expect(pageErrors, 'uncaught page errors').toEqual([])
      expect(consoleErrors, 'console errors').toEqual([])
      expect(failedRequests, 'failed network requests').toEqual([])
      expect(badResponses, 'unexpected HTTP responses').toEqual([])
    },
  }
}

export async function assertNoHorizontalOverflow(page: Page) {
  const overflow = await page.evaluate(() => ({
    documentWidth: document.documentElement.scrollWidth,
    viewportWidth: window.innerWidth,
  }))
  expect(overflow.documentWidth, 'document has horizontal overflow').toBeLessThanOrEqual(overflow.viewportWidth + 1)
}

export async function assertAccessibleSurface(page: Page) {
  await expect(page.locator('main')).toHaveCount(1)
  await expect(page.locator('h1')).toHaveCount(1)
  await expect(page.getByRole('navigation', { name: 'Primary navigation' })).toBeVisible()

  const unnamedControls = await page.locator('button, input, select, textarea').evaluateAll((controls) => controls
    .filter((control) => {
      const element = control as HTMLElement
      const labelledBy = element.getAttribute('aria-labelledby')
      return !element.getAttribute('aria-label') && !labelledBy && !element.closest('label') && !element.textContent?.trim()
    })
    .map((control) => control.outerHTML.slice(0, 160)))
  expect(unnamedControls, 'interactive controls without accessible names').toEqual([])
}

export const publicRoutes = [
  { path: '/', heading: 'NEPSE Market Summary' },
  { path: '/market/movers', heading: 'Market Movers' },
  { path: '/market/sectors', heading: 'Sector Performance' },
  { path: '/market/heatmap', heading: 'Market Heatmap' },
  { path: '/screener', heading: 'Stock screener' },
  { path: '/login', heading: 'Sign in to MarketMitra' },
  { path: '/register', heading: 'Create your account' },
] as const
