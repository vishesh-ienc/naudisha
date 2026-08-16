import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'
import path from 'node:path'

// Backend base URL. The Vite dev proxy keeps the browser on a single origin,
// so no CORS configuration is ever needed on the backend during development.
const BACKEND = process.env.VITE_BACKEND_URL ?? 'http://localhost:8000'

export default defineConfig({
  plugins: [react(), tailwindcss()],
  resolve: {
    alias: { '@': path.resolve(__dirname, './src') },
  },
  server: {
    port: 5173,
    proxy: {
      // `secure`/`changeOrigin` left default: the backend is local in dev.
      // Errors are swallowed here so a dead backend surfaces as a failed
      // fetch in our own telemetry layer rather than a Vite overlay.
      '/api': { target: BACKEND, changeOrigin: true },
      '/health': { target: BACKEND, changeOrigin: true },
      '/ws': { target: BACKEND, changeOrigin: true, ws: true },
    },
  },
})
