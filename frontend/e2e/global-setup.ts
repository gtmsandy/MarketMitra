import { request, type FullConfig } from '@playwright/test'

import { verifyLocalApi } from './support.js'

export default async function globalSetup(_config: FullConfig) {
  const context = await request.newContext()
  try {
    await verifyLocalApi(context)
  } finally {
    await context.dispose()
  }
}
