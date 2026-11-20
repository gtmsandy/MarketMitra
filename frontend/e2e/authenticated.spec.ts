import { randomUUID } from 'node:crypto'

import { expect, test, type Page } from '@playwright/test'

import { apiBaseURL, assertAccessibleSurface, assertNoHorizontalOverflow, diagnostics } from './support.js'

const authEnabled = process.env.PLAYWRIGHT_AUTH_E2E === 'true'
const databaseName = process.env.PLAYWRIGHT_E2E_DATABASE_NAME ?? ''
const databaseRole = process.env.PLAYWRIGHT_E2E_DATABASE_ROLE ?? ''
const databaseConfirmation = process.env.PLAYWRIGHT_E2E_DATABASE_CONFIRMATION ?? ''
const databaseVerified = databaseName === 'marketmitra_e2e_ci' && databaseRole === 'marketmitra_e2e_ci_user' && databaseConfirmation === 'marketmitra_e2e_ci/marketmitra_e2e_ci_user'
const password = process.env.PLAYWRIGHT_E2E_USER_PASSWORD ?? ''
const adminEmail = process.env.PLAYWRIGHT_E2E_ADMIN_EMAIL ?? ''
const adminPassword = process.env.PLAYWRIGHT_E2E_ADMIN_PASSWORD ?? ''
const tradeDate = process.env.PLAYWRIGHT_E2E_TRADE_DATE ?? new Date(Date.now() - 86_400_000).toISOString().slice(0, 10)

test.use({ trace: 'off', screenshot: 'off', video: 'off' })

test.describe.serial('authenticated disposable-database journeys', () => {
  test.skip(!authEnabled || !databaseVerified || !password, 'Set the explicit disposable-database identity confirmation and runtime credentials')

  const runId = randomUUID().slice(0, 8)
  const primaryEmail = `e2e-investor-${runId}@marketmitra.test`
  const secondEmail = `e2e-owner-${runId}@marketmitra.test`
  const displayName = 'E2E Investor'
  const watchlistName = `e2e-watchlist-${runId}`
  const portfolioName = `E2E Portfolio ${runId}`

  function attachDiagnostics(page: Page) {
    const report = diagnostics(page)
    return report
  }

  async function register(page: Page, email: string) {
    await page.goto('/register')
    await page.getByLabel('Display name').fill(displayName)
    await page.getByLabel('Email').fill(email)
    await page.getByLabel('Password').fill(password)
    await page.getByLabel('Confirm password').fill(password)
    await page.getByRole('button', { name: 'Create account' }).click()
    await expect(page).toHaveURL(/\/profile$/)
  }

  async function login(page: Page, email: string, secret = password) {
    await page.goto('/login')
    await page.getByLabel('Email').fill(email)
    await page.getByLabel('Password').fill(secret)
    await page.getByRole('button', { name: 'Sign in' }).click()
    await expect(page).toHaveURL(/\/profile$/)
  }

  test('registers with validation, authenticates, and persists after refresh', async ({ page }) => {
    const report = attachDiagnostics(page)
    await page.goto('/register')
    await page.getByLabel('Display name').fill(displayName)
    await page.getByLabel('Email').fill(primaryEmail)
    await page.getByLabel('Password').fill(password)
    await page.getByLabel('Confirm password').fill(`${password}-mismatch`)
    await page.getByRole('button', { name: 'Create account' }).click()
    await expect(page.getByRole('alert')).toHaveText('Passwords do not match')

    await page.getByLabel('Confirm password').fill(password)
    await page.getByRole('button', { name: 'Create account' }).click()
    await expect(page).toHaveURL(/\/profile$/)
    await expect(page.getByRole('heading', { name: 'Your profile' })).toBeVisible()
    await page.reload()
    await expect(page.getByText(primaryEmail)).toBeVisible()
    report.assertClean()
  })

  test('logs out, rejects bad credentials, and protects authenticated routes', async ({ page }) => {
    const report = diagnostics(page, { allowedStatuses: [403] })
    await login(page, primaryEmail)
    await page.getByRole('button', { name: 'Sign out' }).click()
    await expect(page).toHaveURL(/\/login$/)

    await page.getByLabel('Email').fill(primaryEmail)
    await page.getByLabel('Password').fill(`${password}-wrong`)
    await page.getByRole('button', { name: 'Sign in' }).click()
    await expect(page.getByRole('alert')).toHaveText('Email or password is incorrect')

    await page.goto('/profile')
    await expect(page).toHaveURL(/\/login$/)
    await login(page, primaryEmail)
    await page.goto('/admin')
    await expect(page.getByRole('heading', { name: 'Administrator access required' })).toBeVisible()

    await page.context().clearCookies()
    await page.goto('/profile')
    await expect(page).toHaveURL(/\/login$/)
    report.assertClean()
  })

  test('creates, edits, persists, and removes a watchlist with CSRF protection', async ({ page }) => {
    const report = diagnostics(page, { allowedStatuses: [403] })
    await login(page, primaryEmail)
    await page.goto('/watchlists')
    await page.getByLabel('Watchlist name').fill(watchlistName)
    const createResponse = page.waitForResponse((response) => response.url().endsWith('/api/v1/watchlists') && response.request().method() === 'POST')
    await page.getByRole('button', { name: 'Create' }).click()
    expect((await (await createResponse).json()).id).toBeTruthy()
    await expect(page.getByRole('button', { name: watchlistName.toLowerCase() })).toBeVisible()

    await page.getByLabel('Search stocks to add').fill('SYNBANKA')
    const results = page.locator('.watchlist-search-results')
    await expect(results.getByText('SYNBANKA')).toBeVisible()
    await results.getByRole('button', { name: 'Add' }).click()
    await expect(page.getByText('SYNBANKA')).toBeVisible()

    const csrfStatus = await page.evaluate(async ({ api, name }) => {
      const response = await fetch(`${api}/api/v1/watchlists`, { method: 'POST', credentials: 'include', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ name }) })
      return response.status
    }, { api: apiBaseURL, name: `${watchlistName}-csrf` })
    expect(csrfStatus).toBe(403)

    await page.reload()
    await expect(page.getByText('SYNBANKA')).toBeVisible()
    await page.getByRole('button', { name: 'Remove' }).click()
    await expect(page.getByText('No instruments in this watchlist.')).toBeVisible()
    report.assertClean()
  })

  test('creates a portfolio, records financial transactions, and rejects overselling', async ({ page }) => {
    const report = attachDiagnostics(page)
    await login(page, primaryEmail)
    await page.goto('/portfolio')
    await page.getByLabel('Portfolio name').fill(portfolioName)
    const createResponse = page.waitForResponse((response) => response.url().endsWith('/api/v1/portfolios') && response.request().method() === 'POST')
    await page.getByRole('button', { name: 'Create' }).click()
    expect((await (await createResponse).json()).id).toBeTruthy()
    await expect(page.getByRole('button', { name: portfolioName })).toBeVisible()

    await page.getByLabel('Transaction symbol').fill('SYNBANKA')
    await page.getByLabel('Trade date').fill(tradeDate)
    await page.getByLabel('Quantity').fill('10')
    await page.getByLabel('Unit price').fill('100')
    await page.getByLabel('Fees').fill('10')
    await page.getByRole('button', { name: 'Record transaction' }).click()
    await expect(page.getByText('NPR 101.00')).toBeVisible()

    await page.getByLabel('Side').selectOption('SELL')
    await page.getByLabel('Quantity').fill('4')
    await page.getByLabel('Unit price').fill('120')
    await page.getByLabel('Fees').fill('2')
    await page.getByRole('button', { name: 'Record transaction' }).click()
    await expect(page.getByText('NPR 74.00')).toBeVisible()
    await expect(page.getByText('NPR 606.00')).toBeVisible()

    await page.getByLabel('Quantity').fill('100')
    await page.getByRole('button', { name: 'Record transaction' }).click()
    await expect(page.getByRole('alert')).toContainText(/holding|sell/i)
    report.assertClean()
  })

  test('keeps user data isolated and remains usable across navigation and mobile layout', async ({ page }) => {
    const report = attachDiagnostics(page)
    await login(page, primaryEmail)
    await page.getByRole('button', { name: 'Sign out' }).click()
    await expect(page).toHaveURL(/\/login$/)
    await register(page, secondEmail)

    await page.goto('/watchlists')
    await expect(page.getByText('No watchlists yet.')).toBeVisible()
    await page.goto('/portfolio')
    await expect(page.getByText('Create a portfolio to begin.')).toBeVisible()

    await login(page, primaryEmail)
    await page.goto('/watchlists')
    await expect(page.getByRole('button', { name: watchlistName.toLowerCase() })).toBeVisible()
    await page.goto('/portfolio')
    await expect(page.getByRole('button', { name: portfolioName })).toBeVisible()
    await page.goBack()
    await page.goForward()

    await page.setViewportSize({ width: 390, height: 844 })
    await assertNoHorizontalOverflow(page)
    await assertAccessibleSurface(page)
    report.assertClean()
  })

  test('verifies the pre-provisioned admin journey when credentials are supplied', async ({ page }) => {
    test.skip(!adminEmail || !adminPassword, 'Admin credentials are intentionally supplied only at runtime')
    const report = attachDiagnostics(page)
    await login(page, primaryEmail)
    await page.getByRole('button', { name: 'Sign out' }).click()
    await login(page, adminEmail, adminPassword)
    await page.goto('/admin')
    await expect(page.getByRole('heading', { name: 'MarketMitra administration' })).toBeVisible()
    report.assertClean()
  })

  test('does not expose secrets in the page surface', async ({ page }) => {
    await login(page, primaryEmail)
    const visibleText = await page.locator('body').innerText()
    expect(visibleText).not.toContain(password)
    if (adminPassword) expect(visibleText).not.toContain(adminPassword)
  })

})
