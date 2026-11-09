import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// /api/* -> FastAPI on :8000. Same origin in dev = no CORS, and httpOnly cookies just work later.
export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      '/api': { target: 'http://localhost:8000', rewrite: (p) => p.replace(/^\/api/, '') },
    },
  },
})
