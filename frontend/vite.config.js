import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import { VitePWA } from 'vite-plugin-pwa'

export default defineConfig({
  plugins: [
    react(),
    VitePWA({
      registerType: 'autoUpdate',
      // Service worker is generated into dist/ at build time
      includeAssets: ['favicon.ico', 'icons/apple-touch-icon.png'],
      manifest: {
        name: 'FaceChan',
        short_name: 'FaceChan',
        description: 'Anonymous-first imageboard and community platform',
        theme_color: '#1a1a2e',
        background_color: '#1a1a2e',
        display: 'standalone',
        orientation: 'portrait-primary',
        scope: '/',
        start_url: '/',
        icons: [
          {
            src: '/icons/icon-192.png',
            sizes: '192x192',
            type: 'image/png',
          },
          {
            src: '/icons/icon-512.png',
            sizes: '512x512',
            type: 'image/png',
          },
          {
            src: '/icons/icon-512.png',
            sizes: '512x512',
            type: 'image/png',
            purpose: 'maskable',
          },
        ],
      },
      workbox: {
        // Only precache the shell — not all JS/CSS
        globPatterns: ['**/*.{ico,png,svg,woff2}'],
        // Skip waiting so new SW activates immediately on deploy
        skipWaiting: true,
        clientsClaim: true,
        runtimeCaching: [
          {
            // App JS/CSS — NetworkFirst so deploys show immediately
            urlPattern: /\/assets\/.*/i,
            handler: 'NetworkFirst',
            options: {
              cacheName: 'assets-cache',
              expiration: {
                maxEntries: 50,
                maxAgeSeconds: 60 * 60 * 24, // 1 day max
              },
            },
          },
          {
            // Never cache API calls, admin, or Django static files
            urlPattern: /^https?:\/\/.*\/(api|admin|static)\/.*/i,
            handler: 'NetworkOnly',
          },
          {
            urlPattern: /^https?:\/\/.*\/media\/.*/i,
            handler: 'CacheFirst',
            options: {
              cacheName: 'media-cache',
              expiration: {
                maxEntries: 100,
                maxAgeSeconds: 60 * 60 * 24 * 7, // 7 days
              },
            },
          },
        ],
      },
    }),
  ],
  server: {
    port: 5173,
    host: '0.0.0.0',   // required so Docker can expose the port
    allowedHosts: 'all',
  },
})
