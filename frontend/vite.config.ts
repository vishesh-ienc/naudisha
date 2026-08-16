import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'
import path from 'node:path'
import type { ProxyOptions } from 'vite'

// Backend base URL. The Vite dev proxy keeps the browser on a single origin,
// so no CORS configuration is ever needed on the backend during development.
const BACKEND = process.env.VITE_BACKEND_URL ?? 'http://127.0.0.1:8000'

/**
 * A missing backend is the *expected* state while the frontend is developed
 * ahead of it. Vite's default proxy logging turns that into an ECONNREFUSED
 * stack trace on every poll, which buries real errors in the terminal.
 *
 * This handler answers the request with a 503 the app can interpret, and prints
 * one short line the first time rather than a trace every few seconds. The
 * frontend already reports backend availability far better in its own console.
 */
let offlineNoticeShown = false

function quietProxy(extra: Partial<ProxyOptions> = {}): ProxyOptions {
  return {
    target: BACKEND,
    changeOrigin: true,
    ...extra,
    configure(proxy) {
      proxy.on('error', (err, _req, res) => {
        const code = (err as NodeJS.ErrnoException).code
        if (code === 'ECONNREFUSED' && !offlineNoticeShown) {
          offlineNoticeShown = true
          console.log(
            `\n  ⓘ  Backend not running at ${BACKEND} — the app is serving demo data.` +
              `\n     Start it with:  .venv/bin/python -m uvicorn naudisha.api.main:app --port 8000\n`,
          )
        }

        // `res` is a ServerResponse for HTTP and a Socket for websocket upgrades.
        if ('writeHead' in res && !res.headersSent) {
          res.writeHead(503, { 'Content-Type': 'application/json' })
          res.end(JSON.stringify({ error: { code: 'BACKEND_OFFLINE', message: 'Backend not running' } }))
        } else if ('destroy' in res) {
          res.destroy()
        }
      })

      // A reachable backend means any later outage is worth announcing again.
      proxy.on('proxyRes', () => {
        offlineNoticeShown = false
      })
    },
  }
}

export default defineConfig({
  plugins: [react(), tailwindcss()],
  resolve: {
    alias: { '@': path.resolve(__dirname, './src') },
  },
  server: {
    port: 5173,
    proxy: {
      '/api': quietProxy(),
      '/health': quietProxy(),
      '/ready': quietProxy(),
      '/ws': quietProxy({ ws: true }),
    },
  },
})
