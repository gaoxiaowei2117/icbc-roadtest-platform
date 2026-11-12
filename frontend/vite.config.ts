import { defineConfig, type Plugin } from 'vite'
import vue from '@vitejs/plugin-vue'
import { fileURLToPath, URL } from 'node:url'

// Two sites from one codebase:
//   default mode  → booking service, base /booking/, dist/
//   --mode routes → route-pack site, base /,         dist-routes/
export default defineConfig(({ mode }) => {
  const routes = mode === 'routes'
  const title = routes ? '路考练习路线 · roadtestgo — Road Test Practice Routes' : 'ICBC Road Test Booking'

  const siteTitle: Plugin = {
    name: 'site-title',
    transformIndexHtml: (html) => html.replace(/<title>.*<\/title>/, `<title>${title}</title>`),
  }

  return {
    plugins: [vue(), siteTitle],
    base: routes ? '/' : '/booking/',
    build: {
      outDir: routes ? 'dist-routes' : 'dist',
      emptyOutDir: true,
    },
    server: {
      port: routes ? 5174 : 5173,
      proxy: {
        '/api': 'http://127.0.0.1:8000',
      },
    },
    resolve: {
      alias: {
        '@site': fileURLToPath(new URL(routes ? './src/sites/routes.ts' : './src/sites/booking.ts', import.meta.url)),
        '@': fileURLToPath(new URL('./src', import.meta.url)),
      },
    },
  }
})
