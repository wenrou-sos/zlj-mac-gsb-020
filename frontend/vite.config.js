import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// During `npm run dev`, forward API calls to the FastAPI container/service.
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      '/health': 'http://localhost:8000',
      '/stats': 'http://localhost:8000',
      '/network': 'http://localhost:8000',
      '/incidents': 'http://localhost:8000',
      '/work-orders': 'http://localhost:8000',
      '/teams': 'http://localhost:8000',
      '/materials': 'http://localhost:8000',
      '/road-closures': 'http://localhost:8000',
      '/shortages': 'http://localhost:8000',
      '/notifications': 'http://localhost:8000'
    }
  }
})
