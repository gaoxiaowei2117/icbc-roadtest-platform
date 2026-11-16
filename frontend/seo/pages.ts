/**
 * Static, crawlable landing pages for the route site (built by `vite build --mode routes`).
 *
 *   /zh/  /en/                          hub: every test centre
 *   /zh/<slug>/  /en/<slug>/            one centre: intro, routes, FAQ, price
 *   /zh/<slug>/route-N/  (and /en/)     one route: video, key points, chapters, map
 *
 * The SPA renders everything in the browser, so search engines and AI crawlers that
 * don't run JS saw an empty page. These pages are plain HTML with JSON-LD
 * (BreadcrumbList, Product, FAQPage, VideoObject). They hold only public content
 * (no navigation links) and send visitors to the app (/?centre=<slug>) to try or buy.
 *
 * Inputs: the public catalog (backend/app/data/route_packs.json: names, price, previews,
 * YouTube ids, free flags) and seo/route-pages.json (hand-written text, FAQ, chapters).
 */

import { captureFirstTouch } from '../src/attribution'

export const SITE_ORIGIN = 'https://roadtestgo.com'

/** Same first-touch capture as the app, so a visitor landing here from YouTube/Google is credited at sign-up. */
const FIRST_TOUCH_SCRIPT = `<script>(${captureFirstTouch.toString()})()</script>`

type Lang = 'zh' | 'en'
type Bi = { zh: string; en: string }

interface CatalogRoute {
  title: string
  free?: boolean
  preview?: string | null
  preview_en?: string | null
  youtube_zh?: string | null
  youtube_en?: string | null
}
interface CatalogPack {
  slug: string
  name: string
  name_zh?: string
  city: string
  city_zh?: string
  centre: string
  price_cents: number
  currency: string
  routes: CatalogRoute[]
}
interface VideoMeta {
  title: string
  upload_date: string
  duration: string
  chapters: [string, string][]
}
interface RouteContent {
  km: number
  minutes: number
  filmed: boolean
  summary_zh: string
  summary_en: string
  highlights_zh: string[]
  highlights_en: string[]
  video?: { zh: VideoMeta; en: VideoMeta }
}
interface PackContent {
  centre_zh: string
  centre_en: string
  short_zh: string
  short_en: string
  /** Short English place for titles, e.g. "4399 Wayburne Dr". */
  place_en: string
  intro_zh: string
  intro_en: string
  faq: [string, string, string, string][]
  routes: RouteContent[]
}
export interface SeoContent {
  updated: string
  packs: Record<string, PackContent>
}

type BiText = { zh: string; en: string }
interface GuideSection {
  h2: BiText
  ordered?: boolean
  /** Link the section to this centre's page. */
  pack?: string
  items: [BiText, BiText][]
}
export interface Guide {
  slug: string
  updated: string
  title: BiText
  description: BiText
  h1: BiText
  intro: BiText
  sections: GuideSection[]
  faq: [string, string, string, string][]
}

export interface SeoPage {
  /** Output file, e.g. "en/richmond-5300/route-1/index.html". */
  file: string
  /** Canonical URL path, e.g. "/en/richmond-5300/route-1/". */
  path: string
  /** Same page in the other language, for hreflang and the sitemap. */
  alternates: Record<Lang, string>
}

const esc = (s: string) =>
  s.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;')
const abs = (path: string) => `${SITE_ORIGIN}${path}`
const t = (lang: Lang, b: Bi) => b[lang]
/** JSON-LD inside <script>: escape "<" so "</script>" in text can't close the tag. */
const ld = (data: unknown) =>
  `<script type="application/ld+json">${JSON.stringify(data).replace(/</g, '\\u003c')}</script>`

const hubPath = (lang: Lang) => `/${lang}/`
const packPath = (lang: Lang, slug: string) => `/${lang}/${slug}/`
const routePath = (lang: Lang, slug: string, i: number) => `/${lang}/${slug}/route-${i + 1}/`
/** The app page for this centre, opened in the matching UI language. */
const appUrl = (lang: Lang, slug: string) => `/?centre=${slug}&lang=${lang}`

function price(pack: CatalogPack) {
  return `CA$${(pack.price_cents / 100).toFixed(2)}`
}

/** "路线 4 · 上高速线" → "路线 4 · 上高速线" / "Route 4 · Highway route". */
function routeName(lang: Lang, r: CatalogRoute, i: number) {
  const hw = /上高速/.test(r.title)
  if (lang === 'zh') return r.title
  return `Route ${i + 1}${hw ? ' · Highway route' : ''}`
}

function previewUrl(lang: Lang, r: CatalogRoute) {
  const p = lang === 'zh' ? r.preview || r.preview_en : r.preview_en || r.preview
  return p ? `/${p}` : ''
}

function videoId(lang: Lang, r: CatalogRoute) {
  return (lang === 'zh' ? r.youtube_zh || r.youtube_en : r.youtube_en || r.youtube_zh) || ''
}

/** "12:37" / "1:02:03" → seconds. */
function seconds(ts: string) {
  return ts.split(':').reduce((acc, n) => acc * 60 + Number(n), 0)
}
/** "PT12M37S" → seconds. */
function isoSeconds(d: string) {
  const m = d.match(/PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?/)
  return m ? Number(m[1] || 0) * 3600 + Number(m[2] || 0) * 60 + Number(m[3] || 0) : 0
}

const STYLE = `
:root{color-scheme:light;--ink:#0f172a;--muted:#475569;--line:#e2e8f0;--blue:#2563eb;--bg:#f8fafc;--green:#15803d}
*{box-sizing:border-box}body{margin:0;font:16px/1.65 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,"PingFang SC","Hiragino Sans GB","Microsoft YaHei",sans-serif;color:var(--ink);background:var(--bg)}
a{color:var(--blue)}header,main,footer{max-width:860px;margin:0 auto;padding:0 16px}
header{display:flex;align-items:center;justify-content:space-between;gap:12px;padding-top:16px;padding-bottom:8px}
.brand{display:flex;align-items:center;gap:8px;font-weight:700;color:var(--ink);text-decoration:none}.brand img{width:28px;height:28px}
nav.crumbs{font-size:14px;color:var(--muted);margin:8px 0 4px}nav.crumbs a{color:var(--muted)}
h1{font-size:28px;line-height:1.3;margin:8px 0 12px}h2{font-size:21px;margin:32px 0 12px}h3{font-size:17px;margin:20px 0 6px}
.lead{color:var(--muted)}.meta{color:var(--muted);font-size:15px}
.cta{background:#fff;border:1px solid var(--line);border-radius:12px;padding:16px;margin:20px 0;display:flex;flex-wrap:wrap;align-items:center;gap:12px 20px}
.cta strong{font-size:22px}.btn{display:inline-block;background:var(--blue);color:#fff;text-decoration:none;font-weight:600;padding:12px 20px;border-radius:8px}
.free{color:var(--green);font-weight:600}
.cards{display:grid;gap:16px;grid-template-columns:repeat(auto-fill,minmax(250px,1fr))}
.card{background:#fff;border:1px solid var(--line);border-radius:12px;padding:14px;display:flex;flex-direction:column;gap:8px}
.card img{width:100%;height:auto;border-radius:8px;border:1px solid var(--line)}.card h3{margin:0}.card p{margin:0;font-size:15px;color:var(--muted)}
.video{position:relative;aspect-ratio:16/9;background:#000;border-radius:12px;overflow:hidden;margin:16px 0}.video iframe{position:absolute;inset:0;width:100%;height:100%;border:0}
.map{max-width:420px;width:100%;height:auto;border-radius:12px;border:1px solid var(--line)}
ul.points li{margin:4px 0}ol.chapters{padding-left:0;list-style:none;columns:2;column-gap:24px;font-size:15px}ol.chapters li{break-inside:avoid;margin:2px 0}
ol.chapters a{font-variant-numeric:tabular-nums;margin-right:8px}
.faq h3{margin-top:18px}.faq p{margin:4px 0 0}
.note{font-size:14px;color:var(--muted);background:#fff;border:1px solid var(--line);border-radius:8px;padding:10px 12px}
footer{color:var(--muted);font-size:14px;padding-top:32px;padding-bottom:32px}
@media (max-width:560px){h1{font-size:23px}ol.chapters{columns:1}}
`

function layout(o: {
  lang: Lang
  title: string
  description: string
  path: string
  alternates: Record<Lang, string>
  image?: string
  jsonld: unknown[]
  body: string
  updated: string
}) {
  const other: Lang = o.lang === 'zh' ? 'en' : 'zh'
  const image = o.image ? abs(o.image) : abs('/og/roadtestgo-og.jpg')
  return `<!DOCTYPE html>
<html lang="${o.lang === 'zh' ? 'zh-CN' : 'en'}">
<head>
<meta charset="UTF-8" />
<meta name="viewport" content="width=device-width, initial-scale=1.0" />
<title>${esc(o.title)}</title>
<meta name="description" content="${esc(o.description)}" />
<link rel="canonical" href="${abs(o.path)}" />
<link rel="alternate" hreflang="zh" href="${abs(o.alternates.zh)}" />
<link rel="alternate" hreflang="en" href="${abs(o.alternates.en)}" />
<link rel="alternate" hreflang="x-default" href="${abs(o.alternates.en)}" />
<link rel="icon" type="image/svg+xml" href="/favicon.svg" />
<meta property="og:type" content="website" />
<meta property="og:site_name" content="roadtestgo" />
<meta property="og:url" content="${abs(o.path)}" />
<meta property="og:title" content="${esc(o.title)}" />
<meta property="og:description" content="${esc(o.description)}" />
<meta property="og:image" content="${image}" />
<meta name="twitter:card" content="summary_large_image" />
<style>${STYLE.trim()}</style>
${o.jsonld.map(ld).join('\n')}
${FIRST_TOUCH_SCRIPT}
</head>
<body>
<header>
<a class="brand" href="${hubPath(o.lang)}"><img src="/favicon.svg" alt="" width="28" height="28" />roadtestgo</a>
<a href="${o.alternates[other]}" hreflang="${other}" lang="${other === 'zh' ? 'zh-CN' : 'en'}">${other === 'zh' ? '中文' : 'English'}</a>
</header>
<main>
${o.body}
</main>
<footer>
${o.lang === 'zh'
    ? `最后更新：${o.updated}。roadtestgo.com 是独立开发的小工具，与 ICBC 无任何关联。路线根据驾校教练分享的路线图和公开视频整理，不是 ICBC 官方路线，考官可能随时调整。`
    : `Last updated: ${o.updated}. roadtestgo.com is an independent tool, not affiliated with ICBC. Routes are compiled from route maps shared by driving instructors and from public videos; they are not official ICBC routes and examiners may change them at any time.`}
</footer>
</body>
</html>
`
}

function crumbs(lang: Lang, items: [string, string][]) {
  const html = items
    .map(([name, path], i) => (i === items.length - 1 ? esc(name) : `<a href="${path}">${esc(name)}</a>`))
    .join(' › ')
  const data = {
    '@context': 'https://schema.org',
    '@type': 'BreadcrumbList',
    itemListElement: items.map(([name, path], i) => ({ '@type': 'ListItem', position: i + 1, name, item: abs(path) })),
  }
  return { html: `<nav class="crumbs" aria-label="${lang === 'zh' ? '导航' : 'Breadcrumb'}">${html}</nav>`, data }
}

const HUB_NAME: Bi = { zh: 'ICBC 路考练习路线', en: 'ICBC road test routes' }

function ctaBox(lang: Lang, pack: CatalogPack, opts: { freeRoute?: boolean } = {}) {
  const url = appUrl(lang, pack.slug)
  if (opts.freeRoute) {
    return `<div class="cta"><div><span class="free">${t(lang, { zh: '免费试用', en: 'Free trial' })}</span><br />${t(lang, {
      zh: '登录后一键在手机上打开 Google 地图导航，跟着这条路线开。',
      en: 'Log in and open turn-by-turn Google Maps navigation for this route on your phone.',
    })}</div><a class="btn" href="${esc(url)}">${t(lang, { zh: '免费打开导航', en: 'Open it free' })}</a></div>`
  }
  return `<div class="cta"><div><strong>${price(pack)}</strong> · ${t(lang, {
    zh: `${pack.routes.length} 条路线，一次付款，永久查看`,
    en: `${pack.routes.length} routes, one-time payment`,
  })}<br /><span class="free">${t(lang, { zh: '路线 1 免费试用', en: 'Route 1 is free to try' })}</span></div><a class="btn" href="${esc(url)}">${t(lang, {
    zh: '查看路线包',
    en: 'Get the route pack',
  })}</a></div>`
}

function hubPage(lang: Lang, packs: CatalogPack[], content: SeoContent, guides: Guide[]) {
  const path = hubPath(lang)
  const alternates = { zh: hubPath('zh'), en: hubPath('en') }
  const cards = packs
    .map((p) => {
      const c = content.packs[p.slug]
      return `<a class="card" href="${packPath(lang, p.slug)}" style="text-decoration:none;color:inherit">
<h3>${esc(lang === 'zh' ? c.centre_zh : c.centre_en)}</h3>
<p>${esc(t(lang, { zh: `${p.routes.length} 条练习路线 · ${price(p)}`, en: `${p.routes.length} practice routes · ${price(p)}` }))}</p>
<p>${esc(lang === 'zh' ? c.intro_zh : c.intro_en)}</p></a>`
    })
    .join('\n')
  const body = `<h1>${t(lang, { zh: 'ICBC 路考考场练习路线（BC 省）', en: 'ICBC road test practice routes (BC)' })}</h1>
<p class="lead">${t(lang, {
    zh: '按考场整理的 ICBC 路考练习路线：每条路线有讲解视频、重点路口和概览图，手机上可以一键打开 Google 地图导航跟着开，考前熟悉路况。',
    en: 'ICBC road test practice routes by test centre. Each route has a narrated video, its key intersections and an overview map, and opens as turn-by-turn Google Maps navigation on your phone so you can drive it before your test.',
  })}</p>
<div class="cards">${cards}</div>
${guideLinks(lang, guides)}`
  return {
    page: { file: `${lang}/index.html`, path, alternates },
    html: layout({
      lang, path, alternates, body, updated: content.updated, jsonld: [],
      title: t(lang, { zh: 'ICBC 路考练习路线 · 本拿比、列治文考场 | roadtestgo', en: 'ICBC Road Test Practice Routes – Burnaby & Richmond | roadtestgo' }),
      description: t(lang, {
        zh: 'BC 省 ICBC 路考考场练习路线：本拿比 4399 考场、列治文 Lansdowne 考场，每条路线有视频、重点路口和 Google 地图导航。',
        en: 'ICBC road test practice routes for BC test centres – Burnaby 4399 Wayburne Dr and Richmond Lansdowne Centre – with videos, key intersections and Google Maps navigation.',
      }),
    }),
  }
}

function packPage(lang: Lang, pack: CatalogPack, c: PackContent, updated: string, guides: Guide[]) {
  const path = packPath(lang, pack.slug)
  const alternates = { zh: packPath('zh', pack.slug), en: packPath('en', pack.slug) }
  const centre = lang === 'zh' ? c.centre_zh : c.centre_en
  const short = lang === 'zh' ? c.short_zh : c.short_en
  const bc = crumbs(lang, [[t(lang, HUB_NAME), hubPath(lang)], [short, path]])
  const cards = pack.routes
    .map((r, i) => {
      const rc = c.routes[i]
      const img = previewUrl(lang, r)
      return `<a class="card" href="${routePath(lang, pack.slug, i)}" style="text-decoration:none;color:inherit">
${img ? `<img src="${img}" alt="${esc(`${routeName(lang, r, i)} ${t(lang, { zh: '路线概览图', en: 'overview map' })}`)}" width="740" height="720" loading="lazy" />` : ''}
<h3>${esc(routeName(lang, r, i))}${r.free ? ` <span class="free">· ${t(lang, { zh: '免费试用', en: 'free' })}</span>` : ''}</h3>
<p>${esc(t(lang, { zh: `约 ${rc.km} 公里 · 约 ${rc.minutes} 分钟`, en: `About ${rc.km} km · about ${rc.minutes} min` }))}${videoId(lang, r) ? esc(t(lang, { zh: ' · 有视频', en: ' · video' })) : ''}</p>
<p>${esc(lang === 'zh' ? rc.summary_zh : rc.summary_en)}</p></a>`
    })
    .join('\n')
  const faq = c.faq.map(([qz, az, qe, ae]) => (lang === 'zh' ? [qz, az] : [qe, ae]))
  const body = `${bc.html}
<h1>${esc(t(lang, { zh: `${centre} 路考路线`, en: `${centre}: road test routes` }))}</h1>
<p class="lead">${esc(lang === 'zh' ? c.intro_zh : c.intro_en)}</p>
<p class="meta">${esc(t(lang, { zh: `考场地址：${pack.centre}`, en: `Test centre address: ${pack.centre}` }))}</p>
${ctaBox(lang, pack)}
<h2>${t(lang, { zh: `${pack.routes.length} 条练习路线`, en: `${pack.routes.length} practice routes` })}</h2>
<div class="cards">${cards}</div>
<h2>${t(lang, { zh: '常见问题', en: 'FAQ' })}</h2>
<div class="faq">${faq.map(([q, a]) => `<h3>${esc(q)}</h3><p>${esc(a)}</p>`).join('\n')}</div>
${guideLinks(lang, guides)}`
  const product = {
    '@context': 'https://schema.org',
    '@type': 'Product',
    name: t(lang, { zh: `${centre} 路考路线导航包`, en: `${centre} road test route pack` }),
    description: lang === 'zh' ? c.intro_zh : c.intro_en,
    image: abs(previewUrl(lang, pack.routes[0]) || '/og/roadtestgo-og.jpg'),
    brand: { '@type': 'Brand', name: 'roadtestgo' },
    offers: {
      '@type': 'Offer',
      price: (pack.price_cents / 100).toFixed(2),
      priceCurrency: pack.currency.toUpperCase(),
      availability: 'https://schema.org/InStock',
      url: abs(path),
    },
  }
  const faqLd = {
    '@context': 'https://schema.org',
    '@type': 'FAQPage',
    mainEntity: faq.map(([q, a]) => ({ '@type': 'Question', name: q, acceptedAnswer: { '@type': 'Answer', text: a } })),
  }
  return {
    page: { file: `${lang}/${pack.slug}/index.html`, path, alternates },
    html: layout({
      lang, path, alternates, body, updated, image: previewUrl(lang, pack.routes[0]) || undefined,
      jsonld: [bc.data, product, faqLd],
      title: t(lang, {
        zh: `${pack.city_zh || pack.city} ICBC 路考路线 · ${c.short_zh}（${pack.centre.split(',')[0]}）| roadtestgo`,
        en: `ICBC ${pack.city} Road Test Routes – ${c.place_en} | roadtestgo`,
      }),
      description: t(lang, {
        zh: `${centre}的 ${pack.routes.length} 条 ICBC 路考练习路线：讲解视频、重点路口、概览图，手机一键打开 Google 地图导航。路线 1 免费试用。`,
        en: `${pack.routes.length} ICBC road test practice routes from the ${centre}: narrated videos, key intersections, overview maps and one-tap Google Maps navigation. Route 1 is free.`,
      }),
    }),
  }
}

function routePage(lang: Lang, pack: CatalogPack, c: PackContent, i: number, updated: string) {
  const r = pack.routes[i]
  const rc = c.routes[i]
  const path = routePath(lang, pack.slug, i)
  const alternates = { zh: routePath('zh', pack.slug, i), en: routePath('en', pack.slug, i) }
  const name = routeName(lang, r, i)
  const short = lang === 'zh' ? c.short_zh : c.short_en
  const bc = crumbs(lang, [[t(lang, HUB_NAME), hubPath(lang)], [short, packPath(lang, pack.slug)], [name, path]])
  const vid = videoId(lang, r)
  // Metadata follows the video actually shown (it may be the other language's).
  const shownLang: Lang = vid && vid === r.youtube_zh ? 'zh' : 'en'
  const vm = rc.video?.[shownLang]
  const img = previewUrl(lang, r)
  const summary = lang === 'zh' ? rc.summary_zh : rc.summary_en
  const highlights = lang === 'zh' ? rc.highlights_zh : rc.highlights_en
  const watch = (s?: number) => `https://www.youtube.com/watch?v=${vid}${s ? `&t=${s}s` : ''}`
  const kind = rc.filmed
    ? t(lang, { zh: '驾校教练实拍讲解', en: 'filmed with a driving instructor' })
    : t(lang, { zh: '航拍 + 地图动画讲解', en: 'aerial view + map animation' })
  const others = pack.routes
    .map((o, j) => (j === i ? '' : `<li><a href="${routePath(lang, pack.slug, j)}">${esc(routeName(lang, o, j))}</a> · ${esc(t(lang, { zh: `约 ${c.routes[j].km} 公里`, en: `about ${c.routes[j].km} km` }))}</li>`))
    .join('')
  const body = `${bc.html}
<h1>${esc(t(lang, {
    zh: `${c.short_zh} ${name}（${pack.city_zh || pack.city} ICBC 路考）`,
    en: `${pack.city} ICBC road test ${name} – ${c.place_en}`,
  }))}</h1>
<p class="meta">${esc(t(lang, { zh: `全程约 ${rc.km} 公里 · 约 ${rc.minutes} 分钟 · 从考场出发，回到考场`, en: `About ${rc.km} km · about ${rc.minutes} minutes · starts and ends at the test centre` }))}</p>
<p class="lead">${esc(summary)}</p>
${vid && vm ? `<div class="video"><iframe src="https://www.youtube-nocookie.com/embed/${vid}?rel=0" title="${esc(vm.title)}" loading="lazy" allow="encrypted-media; picture-in-picture; fullscreen" allowfullscreen></iframe></div>
<p class="meta">${esc(t(lang, { zh: `视频：${kind}。`, en: `Video: ${kind}. ` }))}<a href="${esc(watch())}" rel="noopener">${t(lang, { zh: '在 YouTube 上观看', en: 'Watch on YouTube' })}</a></p>` : ''}
${ctaBox(lang, pack, { freeRoute: !!r.free })}
<h2>${t(lang, { zh: '这条路线的重点', en: 'Key points on this route' })}</h2>
<ul class="points">${highlights.map((h) => `<li>${esc(h)}</li>`).join('')}</ul>
${img ? `<h2>${t(lang, { zh: '路线概览图', en: 'Overview map' })}</h2><img class="map" src="${img}" alt="${esc(`${name} ${t(lang, { zh: '路线概览图', en: 'overview map' })}`)}" width="740" height="720" loading="lazy" />` : ''}
${vid && vm?.chapters.length ? `<h2>${t(lang, { zh: '视频章节', en: 'Video chapters' })}</h2>
<ol class="chapters">${vm.chapters.map(([ts, label]) => `<li><a href="${esc(watch(seconds(ts)))}" rel="noopener">${ts}</a>${esc(label)}</li>`).join('')}</ol>` : ''}
<h2>${t(lang, { zh: `${c.short_zh}的其他路线`, en: `Other routes from ${c.short_en}` })}</h2>
<ul>${others}</ul>
<p class="note">${t(lang, {
    zh: '路线根据驾校教练分享的路线图和公开视频整理，不是 ICBC 官方路线；考官可能随时调整，仅供考前熟悉路况。',
    en: 'Compiled from route maps shared by driving instructors and from public videos. Not an official ICBC route; examiners may change routes at any time. Use it to get to know the roads before your test.',
  })}</p>`
  const jsonld: unknown[] = [bc.data]
  if (vid && vm) {
    const total = isoSeconds(vm.duration)
    const starts = vm.chapters.map(([ts]) => seconds(ts))
    jsonld.push({
      '@context': 'https://schema.org',
      '@type': 'VideoObject',
      name: vm.title,
      description: summary,
      thumbnailUrl: [`https://i.ytimg.com/vi/${vid}/hqdefault.jpg`, `https://i.ytimg.com/vi/${vid}/maxresdefault.jpg`],
      uploadDate: vm.upload_date,
      duration: vm.duration,
      embedUrl: `https://www.youtube.com/embed/${vid}`,
      url: watch(),
      inLanguage: shownLang === 'zh' ? 'zh-CN' : 'en',
      hasPart: vm.chapters.map(([, label], k) => ({
        '@type': 'Clip',
        name: label,
        startOffset: starts[k],
        endOffset: k + 1 < starts.length ? starts[k + 1] : total,
        url: watch(starts[k]),
      })),
    })
  }
  return {
    page: { file: `${lang}/${pack.slug}/route-${i + 1}/index.html`, path, alternates },
    html: layout({
      lang, path, alternates, body, updated, image: img || undefined, jsonld,
      title: t(lang, {
        zh: `${pack.city_zh || pack.city} ICBC 路考${name}（${c.short_zh}）· 约 ${rc.km} 公里${vid ? ' · 视频' : ''} | roadtestgo`,
        en: `${pack.city} ICBC Road Test ${name} (${c.place_en}) – ${rc.km} km${vid ? ', video' : ''} & map | roadtestgo`,
      }),
      description: `${summary} ${highlights.slice(0, 3).join(lang === 'zh' ? '、' : '; ')}${lang === 'zh' ? '。' : '.'}`,
    }),
  }
}

const guidePath = (lang: Lang, slug: string) => `/${lang}/${slug}/`

function guidePage(lang: Lang, g: Guide, packs: CatalogPack[], content: SeoContent) {
  const path = guidePath(lang, g.slug)
  const alternates = { zh: guidePath('zh', g.slug), en: guidePath('en', g.slug) }
  const h1 = t(lang, g.h1)
  const bc = crumbs(lang, [[t(lang, HUB_NAME), hubPath(lang)], [h1, path]])
  const sections = g.sections
    .map((sec) => {
      const tag = sec.ordered ? 'ol' : 'ul'
      const pack = sec.pack ? packs.find((p) => p.slug === sec.pack) : undefined
      const link = pack
        ? `<p><a href="${packPath(lang, pack.slug)}">${esc(t(lang, {
            zh: `查看${content.packs[pack.slug]?.short_zh ?? pack.slug}的 ${pack.routes.length} 条练习路线和视频 →`,
            en: `See the ${pack.routes.length} practice routes and videos for ${content.packs[pack.slug]?.short_en ?? pack.slug} →`,
          }))}</a></p>`
        : ''
      return `<h2>${esc(t(lang, sec.h2))}</h2>
<${tag} class="points">${sec.items.map(([term, text]) => `<li><strong>${esc(t(lang, term))}</strong>${lang === 'zh' ? '：' : ': '}${esc(t(lang, text))}</li>`).join('')}</${tag}>
${link}`
    })
    .join('\n')
  const faq = g.faq.map(([qz, az, qe, ae]) => (lang === 'zh' ? [qz, az] : [qe, ae]))
  const body = `${bc.html}
<h1>${esc(h1)}</h1>
<p class="lead">${esc(t(lang, g.intro))}</p>
${sections}
<h2>${t(lang, { zh: '常见问题', en: 'FAQ' })}</h2>
<div class="faq">${faq.map(([q, a]) => `<h3>${esc(q)}</h3><p>${esc(a)}</p>`).join('\n')}</div>
<p class="note">${t(lang, {
    zh: '评分规则来自 ICBC 官方表格《Road Test — Skills Explainer》（MV2959，2023 年 7 月版）；考场具体位置的提醒来自驾校教练经验，不是官方规则。考试以考官指令为准。',
    en: 'Marking rules are from ICBC\'s "Road Test — Skills Explainer" (MV2959, July 2023); location tips are driving instructors\' experience, not official rules. Always follow the examiner\'s directions.',
  })}</p>`
  const article = {
    '@context': 'https://schema.org',
    '@type': 'Article',
    headline: h1,
    description: t(lang, g.description),
    inLanguage: lang === 'zh' ? 'zh-CN' : 'en',
    dateModified: g.updated,
    author: { '@type': 'Organization', name: 'roadtestgo', url: SITE_ORIGIN },
    publisher: { '@type': 'Organization', name: 'roadtestgo', url: SITE_ORIGIN },
    mainEntityOfPage: abs(path),
  }
  const faqLd = {
    '@context': 'https://schema.org',
    '@type': 'FAQPage',
    mainEntity: faq.map(([q, a]) => ({ '@type': 'Question', name: q, acceptedAnswer: { '@type': 'Answer', text: a } })),
  }
  return {
    page: { file: `${lang}/${g.slug}/index.html`, path, alternates },
    html: layout({
      lang, path, alternates, body, updated: g.updated, jsonld: [bc.data, article, faqLd],
      title: t(lang, g.title), description: t(lang, g.description),
    }),
  }
}

/** Link block to the guides, shown on the hub and centre pages. */
function guideLinks(lang: Lang, guides: Guide[]) {
  if (!guides.length) return ''
  return `<h2>${t(lang, { zh: '考前必读', en: 'Before your test' })}</h2>
<ul>${guides.map((g) => `<li><a href="${guidePath(lang, g.slug)}">${esc(t(lang, g.h1))}</a></li>`).join('')}</ul>`
}

/** Every static page for both languages. */
export function buildSeoPages(packs: CatalogPack[], content: SeoContent, guides: Guide[] = []) {
  const out: { page: SeoPage; html: string }[] = []
  for (const lang of ['zh', 'en'] as Lang[]) {
    out.push(hubPage(lang, packs.filter((p) => content.packs[p.slug]), content, guides))
    for (const g of guides) out.push(guidePage(lang, g, packs, content))
    for (const pack of packs) {
      const c = content.packs[pack.slug]
      if (!c) continue
      if (c.routes.length !== pack.routes.length) {
        throw new Error(`seo/route-pages.json: ${pack.slug} has ${c.routes.length} routes, catalog has ${pack.routes.length}`)
      }
      out.push(packPage(lang, pack, c, content.updated, guides))
      pack.routes.forEach((_, i) => out.push(routePage(lang, pack, c, i, content.updated)))
    }
  }
  return out
}

/** sitemap.xml with hreflang alternates for every static page, plus the app's home page. */
export function sitemapXml(pages: SeoPage[], lastmod: string) {
  const urls = pages
    .filter((p) => p.path.startsWith('/en/') || p.path.startsWith('/zh/'))
    .map(
      (p) => `  <url><loc>${abs(p.path)}</loc><lastmod>${lastmod}</lastmod>
    <xhtml:link rel="alternate" hreflang="zh" href="${abs(p.alternates.zh)}"/>
    <xhtml:link rel="alternate" hreflang="en" href="${abs(p.alternates.en)}"/>
    <xhtml:link rel="alternate" hreflang="x-default" href="${abs(p.alternates.en)}"/>
  </url>`,
    )
  return `<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9" xmlns:xhtml="http://www.w3.org/1999/xhtml">
  <url><loc>${SITE_ORIGIN}/</loc><lastmod>${lastmod}</lastmod></url>
${urls.join('\n')}
</urlset>
`
}
