import { defineConfig, type Plugin } from 'vite'
import vue from '@vitejs/plugin-vue'
import { fileURLToPath, URL } from 'node:url'
import { readFileSync } from 'node:fs'

const SITE_ORIGIN = 'https://roadtestgo.com'
const SITE_DESC =
  'ICBC 路考考场路线导航包：考官常用路线，手机一键打开 Google 地图导航，路线 1 免费试用。' +
  ' ICBC road test practice routes for BC test centres (Burnaby, Richmond) — open each route in Google Maps; route 1 is free.'

/** Pack slugs from the public (placeholder-link) catalog, for sitemap.xml. */
function packSlugs(): string[] {
  const file = fileURLToPath(new URL('../backend/app/data/route_packs.json', import.meta.url))
  const data = JSON.parse(readFileSync(file, 'utf8'))
  const packs: { slug: string }[] = Array.isArray(data) ? data : data.packs
  return packs.map((p) => p.slug)
}

/** Route site only: search/share meta tags, favicon, robots.txt and sitemap.xml. */
function routeSiteSeo(): Plugin {
  const og = `${SITE_ORIGIN}/og/roadtestgo-og.jpg`
  const head = [
    `<link rel="icon" type="image/svg+xml" href="/favicon.svg" />`,
    `<meta name="description" content="${SITE_DESC}" />`,
    `<meta property="og:type" content="website" />`,
    `<meta property="og:site_name" content="roadtestgo" />`,
    `<meta property="og:url" content="${SITE_ORIGIN}/" />`,
    `<meta property="og:title" content="ICBC 路考考场路线导航包 · Road Test Practice Routes" />`,
    `<meta property="og:description" content="${SITE_DESC}" />`,
    `<meta property="og:image" content="${og}" />`,
    `<meta property="og:image:width" content="1200" />`,
    `<meta property="og:image:height" content="630" />`,
    `<meta name="twitter:card" content="summary_large_image" />`,
    `<meta name="twitter:image" content="${og}" />`,
  ].join('\n    ')
  return {
    name: 'route-site-seo',
    transformIndexHtml: (html) => html.replace(/<link rel="icon" href="data:," \/>/, head),
    generateBundle() {
      this.emitFile({
        type: 'asset',
        fileName: 'robots.txt',
        source: `User-agent: *\nDisallow: /api/\nDisallow: /booking/\n\nSitemap: ${SITE_ORIGIN}/sitemap.xml\n`,
      })
      const urls = [`${SITE_ORIGIN}/`, ...packSlugs().map((s) => `${SITE_ORIGIN}/?centre=${s}`)]
      this.emitFile({
        type: 'asset',
        fileName: 'sitemap.xml',
        source:
          '<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n' +
          urls.map((u) => `  <url><loc>${u.replace(/&/g, '&amp;')}</loc></url>`).join('\n') +
          '\n</urlset>\n',
      })
    },
  }
}

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
    plugins: routes ? [vue(), siteTitle, routeSiteSeo()] : [vue(), siteTitle],
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
