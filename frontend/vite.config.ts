import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    // 127.0.0.1, not "localhost": on Node 17+ (Windows) localhost can resolve to ::1
    // while uvicorn listens on IPv4, which gives ECONNREFUSED.
    proxy: { '/api': 'http://127.0.0.1:8000' },
  },
})