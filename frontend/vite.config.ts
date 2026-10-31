import react from '@vitejs/plugin-react'
import { defineConfig, loadEnv } from 'vite'

import { resolveApiBaseUrl } from './src/config/runtime.js'

// https://vite.dev/config/
export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), 'VITE_')
  resolveApiBaseUrl({
    mode,
    configuredUrl: env.VITE_API_BASE_URL,
  })

  return {
    plugins: [react()],
  }
})
