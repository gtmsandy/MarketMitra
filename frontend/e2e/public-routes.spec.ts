import { test, expect } from '@playwright/test'

import { assertAccessibleSurface, diagnostics, publicRoutes } from './support.js'

test.describe('public route smoke coverage', () => {
  for (const route of publicRoutes) {
    test(`${route.path} renders its public surface`, async ({ page }) => {
      const observed = diagnostics(page)
      await page.goto(route.path, { waitUntil: 'networkidle' })
      await expect(page.getByRole('heading', { name: route.heading, exact: true })).toBeVisible()
      await assertAccessibleSurface(page)
      observed.assertClean()
    })
  }
})

test('dashboard navigates through stock search and browser history', async ({ page }) => {
  const observed = diagnostics(page)
  await page.goto('/', { waitUntil: 'networkidle' })
  const search = page.getByRole('combobox', { name: 'Search stocks by symbol or company name' })
  await search.fill('SYNBANKA')
  await expect(page.getByRole('option', { name: /SYNBANKA/ })).toBeVisible()
  await search.press('ArrowDown')
  await search.press('Enter')
  await expect(page).toHaveURL(/\/stocks\/SYNBANKA$/)
  await expect(page.getByRole('heading', { name: 'SYNBANKA', exact: true })).toBeVisible()
  await page.goBack()
  await expect(page).toHaveURL(/\/$/)
  await page.goForward()
  await expect(page).toHaveURL(/\/stocks\/SYNBANKA$/)
  observed.assertClean()
})

test('screener filters and resets without writing data', async ({ page }) => {
  const observed = diagnostics(page)
  await page.goto('/screener', { waitUntil: 'networkidle' })
  await expect(page.getByRole('heading', { name: 'Stock screener' })).toBeVisible()
  const query = page.getByRole('textbox', { name: 'Symbol or company', exact: true })
  await query.fill('SYNBANKA')
  await expect(page.getByRole('link', { name: /SYNBANKA/ })).toBeVisible()
  await page.getByRole('button', { name: 'Reset' }).click()
  await expect(query).toHaveValue('')
  await expect(page.getByRole('link', { name: /SYNBANKA/ })).toBeVisible()
  observed.assertClean()
})

test('public analytics controls filter and sort deterministically', async ({ page }) => {
  const observed = diagnostics(page)
  await page.goto('/market/heatmap', { waitUntil: 'networkidle' })
  const sector = page.getByLabel('Filter by sector')
  const sectorCount = await sector.locator('option').count()
  expect(sectorCount).toBeGreaterThan(1)
  const allTiles = page.getByRole('region', { name: 'Stock heatmap grid' }).getByRole('link')
  const allTileCount = await allTiles.count()
  await sector.selectOption({ index: 1 })
  await expect(sector).toHaveValue(/.+/)
  const filteredTileCount = await page.getByRole('region', { name: 'Stock heatmap grid' }).getByRole('link').count()
  expect(filteredTileCount).toBeGreaterThan(0)
  expect(filteredTileCount).toBeLessThanOrEqual(allTileCount)
  await page.getByRole('region', { name: 'Stock heatmap grid' }).getByRole('link').first().click()
  await expect(page).toHaveURL(/\/stocks\/[A-Z0-9]+$/)

  await page.goto('/screener', { waitUntil: 'networkidle' })
  const priceSort = page.getByRole('button', { name: /^Price/ })
  await priceSort.click()
  await expect(page).toHaveURL(/sort_by=price.*sort_order=asc/)
  await priceSort.click()
  await expect(page).toHaveURL(/sort_by=price.*sort_order=desc/)
  observed.assertClean()
})

test('SYNBANKA exposes populated technical-analysis controls and provenance', async ({ page }) => {
  const observed = diagnostics(page)
  await page.goto('/stocks/SYNBANKA', { waitUntil: 'networkidle' })
  await expect(page.getByRole('heading', { name: 'SYNBANKA' })).toBeVisible()
  await expect(page.getByText(/synthetic\/historical/i).first()).toBeVisible()
  await expect(page.getByRole('group', { name: 'Chart timeframe' })).toBeVisible()

  await expect(page.locator('.price-chart__container')).toBeVisible()
  await expect(page.getByLabel('Show volume')).toBeChecked()
  await page.getByLabel('Show candlesticks').check()
  await expect(page.getByLabel('Show candlesticks')).toBeChecked()

  for (const label of ['Show SMA', 'Show EMA', 'Show Bollinger Bands', 'Show RSI', 'Show MACD']) {
    await page.getByLabel(label).check()
  }
  for (const message of ['SMA has enough valid observations.', 'EMA has enough valid observations.', 'Bollinger Bands has enough valid observations.', 'RSI has enough valid observations.', 'MACD has enough valid observations.']) {
    await expect(page.getByText(message)).toBeVisible()
  }
  await expect(page.locator('section[aria-label="RSI"]')).toBeVisible()
  await expect(page.locator('section[aria-label="MACD"]')).toBeVisible()

  for (const timeframe of ['1Y', '1M', '1W', '1D', 'ALL']) {
    await page.getByRole('button', { name: timeframe, exact: true }).click()
    await expect(page.getByRole('group', { name: 'Chart timeframe' })).toBeVisible()
  }
  await page.getByRole('button', { name: '1D', exact: true }).click()
  await expect(page.getByText(/No intraday trading records available/)).toBeVisible()
  observed.assertClean()
})

test('unknown public routes render a safe not-found page', async ({ page }) => {
  const observed = diagnostics(page)
  await page.goto('/not-a-real-marketmitra-route', { waitUntil: 'networkidle' })
  await expect(page.getByRole('heading', { name: 'Page not found' })).toBeVisible()
  await expect(page.getByRole('link', { name: /Return to dashboard/ })).toBeVisible()
  observed.assertClean()
})
