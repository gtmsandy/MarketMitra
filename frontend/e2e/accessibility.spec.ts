import { test, expect } from '@playwright/test'

import { assertAccessibleSurface, diagnostics } from './support.js'

test('public dashboard has a logical keyboard surface and visible focus', async ({ page }) => {
  const observed = diagnostics(page)
  await page.goto('/', { waitUntil: 'networkidle' })
  await assertAccessibleSurface(page)

  const focusable = page.getByRole('navigation', { name: 'Primary navigation' }).getByRole('link', { name: 'Movers', exact: true })
  await focusable.focus()
  await expect(focusable).toBeFocused()
  const search = page.getByRole('combobox', { name: 'Search stocks by symbol or company name' })
  await search.focus()
  await expect(search).toBeFocused()
  await expect.poll(async () => search.evaluate((element) => getComputedStyle(element).boxShadow)).not.toBe('none')
  observed.assertClean()
})

test('public forms expose labels and errors through native semantics', async ({ page }) => {
  const observed = diagnostics(page)
  await page.goto('/register', { waitUntil: 'networkidle' })
  for (const label of ['Display name', 'Email', 'Password', 'Confirm password']) {
    await expect(page.getByLabel(label, { exact: true })).toBeVisible()
  }
  await expect(page.getByRole('button', { name: 'Create account' })).toBeVisible()
  await page.getByLabel('Display name', { exact: true }).fill('Browser Test')
  await page.getByLabel('Email', { exact: true }).fill('browser-test@example.invalid')
  await page.getByLabel('Password', { exact: true }).fill('not-the-same-password')
  await page.getByLabel('Confirm password', { exact: true }).fill('different-password')
  await page.getByRole('button', { name: 'Create account' }).click()
  await expect(page.locator('[role="alert"]')).toContainText('Passwords do not match')
  observed.assertClean()
})
