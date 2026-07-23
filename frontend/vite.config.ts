import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'
import { VitePWA } from 'vite-plugin-pwa'

const API_TARGET = 'http://localhost:8000'

export default defineConfig({
  plugins: [
    react(),
    tailwindcss(),
    VitePWA({
      registerType: 'autoUpdate',
      includeAssets: ['favicon.svg'],
      manifest: {
        name: 'TODOSCARE',
        short_name: 'TODOSCARE',
        description: 'Tu salud, en un solo lugar.',
        theme_color: '#0E7C6B',
        background_color: '#F4F7F6',
        display: 'standalone',
        start_url: '/',
        icons: [
          { src: '/icon-192.png', sizes: '192x192', type: 'image/png' },
          { src: '/icon-512.png', sizes: '512x512', type: 'image/png' },
          { src: '/icon-512-maskable.png', sizes: '512x512', type: 'image/png', purpose: 'maskable' },
        ],
      },
    }),
  ],
  server: {
    // El cliente llama a /api/*; en dev lo proxyamos al backend quitando el
    // prefijo. En producción lo hace nginx (ver frontend/docker/nginx.conf).
    proxy: {
      '/api': { target: API_TARGET, changeOrigin: true, rewrite: (p) => p.replace(/^\/api/, '') },
      '/files': { target: API_TARGET, changeOrigin: true },
    },
  },
})
