import { test, expect } from '@playwright/test'

import { assertNoHorizontalOverflow, diagnostics } from './support.js'

const viewports = [
  [320, 700], [360, 800], [375, 812], [390, 844], [430, 932],
  [768, 1024], [1024, 768], [1280, 800], [1440, 900], [1920, 1080],
] as const

const routes = [
  { path: '/', heading: 'NEPSE Market Summary' },
  { path: '/screener', heading: 'Stock screener' },
  { path: '/stocks/SYNBANKA', heading: 'SYNBANKA' },
] as const

for (const route of routes) {
  for (const [width, height] of viewports) {
    test(`${route.path} remains usable at ${width}x${height}`, async ({ page }, testInfo) => {
      await page.setViewportSize({ width, height })
      const observed = diagnostics(page)
      await page.goto(route.path, { waitUntil: 'networkidle' })
      await expect(page.getByRole('heading', { name: route.heading, exact: true })).toBeVisible()
      await assertNoHorizontalOverflow(page)
      await expect(page.getByRole('combobox', { name: 'Search stocks by symbol or company name' })).toBeVisible()
      if (route.path === '/stocks/SYNBANKA') {
        await expect(page.getByRole('group', { name: 'Chart timeframe' })).toBeVisible()
        await expect(page.getByLabel('SMA period')).toBeVisible()
        await expect(page.getByLabel('RSI period')).toBeVisible()
      }
      await page.screenshot({ path: testInfo.outputPath('responsive.png'), fullPage: true })
      observed.assertClean()
    })
  }
}

test('mobile navigation remains keyboard and touch usable', async ({ page }) => {
  await page.setViewportSize({ width: 320, height: 700 })
  const observed = diagnostics(page)
  await page.goto('/', { waitUntil: 'networkidle' })
  const menu = page.locator('.app-header__mobile-nav')
  await expect(menu).toBeVisible()
  await menu.locator('summary').click()
  await expect(menu.getByRole('link', { name: 'Screener' })).toBeVisible()
  await menu.getByRole('link', { name: 'Screener' }).click()
  await expect(page).toHaveURL(/\/screener$/)
  observed.assertClean()
})
