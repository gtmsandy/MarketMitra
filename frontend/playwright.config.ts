import { defineConfig, devices } from '@playwright/test'

const baseURL = process.env.PLAYWRIGHT_BASE_URL ?? 'http://127.0.0.1:5173'
const apiBaseURL = process.env.PLAYWRIGHT_API_BASE_URL ?? 'http://127.0.0.1:8000'

function requireLocalUrl(value: string, name: string): string {
  let parsed: URL
  try {
    parsed = new URL(value)
  } catch {
    throw new Error(`${name} must be an absolute localhost URL`)
  }
  if (parsed.protocol !== 'http:' || !['127.0.0.1', 'localhost'].includes(parsed.hostname)) {
    throw new Error(`${name} must target http://127.0.0.1 or http://localhost`)
  }
  return parsed.origin
}

const browserBaseURL = requireLocalUrl(baseURL, 'PLAYWRIGHT_BASE_URL')
requireLocalUrl(apiBaseURL, 'PLAYWRIGHT_API_BASE_URL')

export default defineConfig({
  testDir: './e2e',
  globalSetup: './e2e/global-setup.ts',
  fullyParallel: true,
  forbidOnly: Boolean(process.env.CI),
  retries: process.env.CI ? 2 : 0,
  timeout: 30_000,
  expect: { timeout: 8_000 },
  reporter: [['list'], ['html', { outputFolder: 'playwright-report', open: 'never' }]],
  outputDir: 'test-results',
  use: {
    baseURL: browserBaseURL,
    trace: 'retain-on-failure',
    screenshot: 'only-on-failure',
    // Keep failure evidence portable; video needs a separate ffmpeg download.
    video: 'off',
    serviceWorkers: 'block',
    colorScheme: 'light',
  },
  projects: [{
    name: 'chromium',
    use: {
      ...devices['Desktop Chrome'],
      channel: process.env.PLAYWRIGHT_CHANNEL ?? 'chrome',
    },
  }],
})
