import { defineConfig } from 'vite'

export default defineConfig({
  server: {
    host: '0.0.0.0',
    proxy: {
      '/api': { target: process.env.API_PROXY_TARGET || 'http://localhost:8000', rewrite: path => path.replace(/^\/api/, '') },
      '/ai': { target: process.env.AI_PROXY_TARGET || 'http://localhost:8001', rewrite: path => path.replace(/^\/ai/, '') },
    },
  },
})