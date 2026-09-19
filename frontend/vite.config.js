import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// During `npm run dev`, /api and /health are proxied to the FastAPI container/service.
export default defineConfig({
  plugins: [react()],
  server: {
    host: true,
    port: 5173,
    proxy: {
      '/api': { target: process.env.VITE_API_TARGET || 'http://localhost:8000', changeOrigin: true },
      '/health': { target: process.env.VITE_API_TARGET || 'http://localhost:8000', changeOrigin: true },
    },
  },
})
