import { test, expect } from '@playwright/test'

import { diagnostics } from './support.js'

test('records bounded public navigation, history and indicator timings', async ({ page }, testInfo) => {
  const observed = diagnostics(page)
  const navigationStarted = Date.now()
  const historyResponsePromise = page.waitForResponse((response) => response.url().includes('/api/v1/stocks/SYNBANKA/history') && response.status() === 200)

  await page.goto('/stocks/SYNBANKA', { waitUntil: 'networkidle' })
  const historyResponse = await historyResponsePromise
  const history = await historyResponse.json() as unknown[]
  const navigationMs = Date.now() - navigationStarted
  const requestTiming = historyResponse.request().timing()
  const apiMs = requestTiming.responseEnd >= 0
    ? requestTiming.responseEnd > requestTiming.startTime
      ? requestTiming.responseEnd - requestTiming.startTime
      : requestTiming.responseEnd
    : null

  await expect(page.getByRole('heading', { name: 'SYNBANKA', exact: true })).toBeVisible()
  await expect(page.locator('.price-chart__container')).toBeVisible()
  const indicatorStarted = Date.now()
  await page.getByLabel('Show SMA').check()
  await expect(page.getByText('SMA has enough valid observations.')).toBeVisible()
  const indicatorToggleMs = Date.now() - indicatorStarted

  const measurement = {
    navigationMs,
    historyObservationCount: history.length,
    historyApiMs: apiMs,
    indicatorToggleMs,
  }
  console.log(`PERFORMANCE_SMOKE ${JSON.stringify(measurement)}`)
  await testInfo.attach('performance.json', {
    body: JSON.stringify(measurement, null, 2),
    contentType: 'application/json',
  })
  observed.assertClean()
})
