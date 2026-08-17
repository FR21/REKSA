import dns from 'node:dns'
dns.setDefaultResultOrder('ipv4first')

import react from '@vitejs/plugin-react'
import { defineConfig } from 'vitest/config'
import { loadEnv } from 'vite'

export default defineConfig(({ mode }) => {
  // Load env file vars and process.env vars
  const env = loadEnv(mode, process.cwd(), '')
  const backendUrl = env.BACKEND_URL || 'http://localhost:8000'
  const wsUrl = backendUrl.replace(/^http/, 'ws')

  console.log("VITE PROXY TARGET IS:", backendUrl)

  return {
    plugins: [react()],
    test: {
      environment: 'jsdom',
      setupFiles: './tests/setup.ts',
      globals: true,
    },
    server: {
      port: 5173,
      proxy: {
        '/api': { target: backendUrl, changeOrigin: true },
        '/ws': { target: wsUrl, ws: true, changeOrigin: true },
      },
    },
  }
})
