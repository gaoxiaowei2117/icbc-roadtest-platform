<script setup lang="ts">
// One test centre's pack: overview images, segments, buy / open buttons.
import { onMounted, onUnmounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { createRoutePackCheckout, getRoutePack, openRoute, type RoutePack, type RouteSummary } from '@/api/routePacks'
import { SITE } from '@/site'
import { useAuthStore } from '@/stores/auth'
import { SUPPORT_EMAIL } from '@/config/support'
import { useI18n } from '@/i18n'
import { useRoutePackText } from '@/routePackText'

const props = defineProps<{
  slug: string
  /** Stripe return status for this pack, if the page was opened from Checkout. */
  checkout?: 'success' | 'cancelled' | null
}>()

const auth = useAuthStore()
const route = useRoute()
const router = useRouter()
const { tr, apiError, locale } = useI18n()
const { packName, formatPrice, cityName, regionName } = useRoutePackText()
const notFound = ref(false)

const packs = ref<RoutePack[]>([])
const loading = ref(true)
const error = ref('')
const message = ref('')
const buying = ref<string | null>(null)
const opening = ref<string | null>(null)
const enlarged = ref<{ src: string; alt: string } | null>(null)
let pollTimer: number | undefined

async function load() {
  try {
    packs.value = [await getRoutePack(props.slug)]
  } catch (e: any) {
    // An expired session is logged out by the auth interceptor; show the public view instead.
    if (e.response?.status !== 404 && !auth.token) packs.value = [await getRoutePack(props.slug)]
    else throw e
  }
}

async function refresh() {
  error.value = ''
  notFound.value = false
  try {
    await load()
  } catch (e: any) {
    packs.value = []
    if (e.response?.status === 404) notFound.value = true
    else error.value = apiError(e, '加载失败', 'Failed to load route packs')
  } finally {
    loading.value = false
  }
}

/** Stripe redirects back before the webhook may have landed; poll briefly until it unlocks. */
function waitForPurchase(slug: string) {
  let tries = 0
  pollTimer = window.setInterval(async () => {
    tries += 1
    try {
      await load()
    } catch {
      /* keep polling */
    }
    const pack = packs.value.find((p) => p.slug === slug)
    if (pack?.purchased) {
      window.clearInterval(pollTimer)
      pollTimer = undefined
      message.value = tr('付款成功，路线已解锁。', 'Payment received. Your routes are unlocked.')
    } else if (tries >= 15) {
      window.clearInterval(pollTimer)
      pollTimer = undefined
      message.value = tr(
        '付款已提交，正在确认中。请稍后刷新页面；如长时间未解锁请联系客服。',
        'Payment submitted and still being confirmed. Refresh in a moment, or contact support if it does not unlock.',
      )
    }
  }, 2000)
}

onMounted(async () => {
  window.addEventListener('keydown', onKeydown)
  await refresh()
  const slug = props.slug
  if (props.checkout === 'success') {
    const pack = packs.value.find((p) => p.slug === slug)
    if (pack?.purchased) {
      message.value = tr('付款成功，路线已解锁。', 'Payment received. Your routes are unlocked.')
    } else {
      message.value = tr('付款完成，正在解锁路线…', 'Payment complete. Unlocking your routes…')
      waitForPurchase(slug)
    }
  } else if (props.checkout === 'cancelled') {
    message.value = tr('已取消付款，未扣款。', 'Checkout cancelled. You have not been charged.')
  }
})

watch(() => props.slug, () => {
  message.value = ''
  if (pollTimer) window.clearInterval(pollTimer)
  pollTimer = undefined
  refresh()
})

onUnmounted(() => {
  window.removeEventListener('keydown', onKeydown)
  if (pollTimer) window.clearInterval(pollTimer)
})

/** Data titles are Chinese ("路线 1", "第 1 段", "全程"); show them in the UI language. */
function routeTitle(title: string) {
  const m = /^路线\s*(\d+)(?:\s*·\s*(.+))?$/.exec(title)
  if (!m) return title
  const n = m[1]
  const hw = m[2] === '上高速线'
  const sfx = (zh: string, en: string) => (m[2] ? (hw ? tr(` · ${zh}`, ` · ${en}`) : ` · ${m[2]}`) : '')
  return tr(`路线 ${n}`, `Route ${n}`, `Itinéraire ${n}`, `Ruta ${n}`, `路線 ${n}`) + sfx('上高速线', 'Highway route')
}

function segmentLabel(label: string) {
  const m = /^第\s*(\d+)\s*段$/.exec(label)
  if (m) return tr(`第 ${m[1]} 段`, `Part ${m[1]}`, `Partie ${m[1]}`, `Parte ${m[1]}`, `第 ${m[1]} 段`)
  if (label === '全程') return tr('全程', 'Full route', 'Itinéraire complet', 'Ruta completa', '全程')
  return label
}

/** "centre" is the test centre; other places are English street names shown as-is. */
function place(name: string) {
  return name === 'centre' ? tr('考场', 'Test centre', 'Centre d’examen', 'Centro de examen', '考場') : name
}

/** "第 1 段：考场 → Smith Ave" / "Part 1: Test centre → Smith Ave". */
function segmentText(seg: RouteSummary['segments'][number]) {
  const label = segmentLabel(seg.label)
  if (!seg.from || !seg.to) return label
  return `${label}${tr('：', ': ', ' : ', ': ', '：')}${place(seg.from)} → ${place(seg.to)}`
}

/** Footnote under the routes: the "open parts in order" hint only when some route is split. */
function routeHint(pack: RoutePack) {
  const hints: string[] = []
  if (pack.routes.some((r) => r.segments.length > 1)) {
    hints.push(tr('分成几段的路线请按顺序依次打开。', 'Routes split into parts should be opened in order.'))
  }
  if (pack.routes.some((r) => r.preview)) {
    hints.push(tr('点击概览图可放大。', 'Tap an overview map to enlarge it.'))
  }
  return hints.join(tr('', ' '))
}

function routeNote(r: RouteSummary) {
  return (locale.value.startsWith('zh') ? r.note_zh || r.note : r.note || r.note_zh) || ''
}

function previewSrc(r: RouteSummary) {
  // Chinese map labels for zh / zh-Hant, the English-labelled image for every other UI language.
  const p = locale.value.startsWith('zh') ? r.preview || r.preview_en : r.preview_en || r.preview
  return p ? `${import.meta.env.BASE_URL}${p}` : ''
}

/** Purchased packs open every route; a free trial route opens for anyone logged in. */
function canOpen(pack: RoutePack, r: RouteSummary) {
  return !!pack.purchased || (!!r.free && !!auth.token)
}

/** Free trial routes ("路线 1、路线 2" / "Route 1, Route 2"), for the bullet list. */
function freeRouteTitles(pack: RoutePack) {
  return pack.routes.filter((r) => r.free).map((r) => routeTitle(r.title)).join(tr('、', ', '))
}

function lockedCount(pack: RoutePack) {
  return pack.routes.filter((r) => !r.free).length
}

function goLogin() {
  router.push({ name: 'login', query: { redirect: route.fullPath } })
}

function onKeydown(e: KeyboardEvent) {
  if (e.key === 'Escape') enlarged.value = null
}

async function onBuy(pack: RoutePack) {
  if (!auth.token) {
    // Come back to this centre after logging in.
    goLogin()
    return
  }
  buying.value = pack.slug
  error.value = ''
  try {
    const checkout = await createRoutePackCheckout(pack.slug, SITE)
    window.location.assign(checkout.url)
  } catch (e: any) {
    if (e.response?.status === 409) await refresh()
    else error.value = apiError(e, '付款页面创建失败', 'Failed to start checkout')
    buying.value = null
  }
}

async function onOpenSegment(pack: RoutePack, routeIndex: number, segmentIndex: number) {
  const key = `${pack.slug}:${routeIndex}:${segmentIndex}`
  opening.value = key
  error.value = ''
  try {
    // The server checks the purchase, logs the click and returns a few-minutes redirect URL
    // (/api/route-packs/go/<token>) that forwards to Google Maps; the link never sits in the page.
    const { url } = await openRoute(pack.slug, routeIndex, segmentIndex)
    // Same tab: on phones the redirect hands off to the Google Maps app.
    window.location.assign(url)
  } catch (e: any) {
    error.value = apiError(e, '打开导航失败', 'Could not open navigation')
  } finally {
    opening.value = null
  }
}

function contactMailto(pack: RoutePack) {
  return `mailto:${SUPPORT_EMAIL}?subject=${encodeURIComponent(`Route pack: ${pack.name}`)}`
}
</script>

<template>
  <div class="space-y-6">
    <p v-if="message" class="text-sm rounded-md bg-blue-50 text-blue-800 px-4 py-3">{{ message }}</p>
    <p v-if="error" class="text-sm text-red-600">{{ error }}</p>
    <div v-if="loading" class="text-sm text-slate-500">{{ tr('加载中…', 'Loading…') }}</div>
    <div v-else-if="notFound" class="card text-sm text-slate-600">{{ tr('没有找到这个考场的路线包。', 'This test centre was not found.') }}</div>

    <div v-for="pack in packs" :key="pack.slug" class="card space-y-5">
      <div>
        <h2 class="text-xl font-semibold">{{ packName(pack) }}</h2>
        <p class="text-sm text-slate-500">{{ cityName(pack) }}{{ tr('，', ', ') }}{{ regionName(pack.country, pack.region) }}</p>
        <p class="text-sm text-slate-500">{{ pack.centre }}</p>
      </div>

      <ul class="text-sm text-slate-700 space-y-1">
        <li>✓ {{ tr(
          `${pack.route_count} 条练习路线，覆盖考场周边常见考试路段`,
          `${pack.route_count} practice routes around the test centre`,
          `${pack.route_count} itinéraires d’entraînement autour du centre`,
          `${pack.route_count} rutas de práctica alrededor del centro`,
          `${pack.route_count} 條練習路線，涵蓋考場周邊常見考試路段`,
        ) }}</li>
        <li v-if="!pack.purchased && freeRouteTitles(pack)" class="text-green-700 font-medium">✓ {{ tr(
          `${freeRouteTitles(pack)} 免费试用，登录即可打开`,
          `${freeRouteTitles(pack)}: free trial, just log in`,
          `${freeRouteTitles(pack)} : essai gratuit, connectez-vous`,
          `${freeRouteTitles(pack)}: prueba gratis, solo inicia sesión`,
          `${freeRouteTitles(pack)} 免費試用，登入即可開啟`,
        ) }}</li>
        <li>✓ {{ tr('手机一键打开 Google 地图导航', 'Opens in the Google Maps app on your phone', 'S’ouvre dans l’application Google Maps', 'Se abre en la app de Google Maps', '手機一鍵開啟 Google 地圖導航') }}</li>
        <li>✓ {{ tr('一次付款，永久查看', 'One-time payment, no subscription', 'Paiement unique, sans abonnement', 'Pago único, sin suscripción', '一次付款，永久查看') }}</li>
      </ul>

      <!-- Not purchased: price + buy first, so phones don't scroll past the previews. -->
      <div v-if="!pack.purchased" class="flex flex-wrap items-center gap-4 border-y border-slate-100 py-4">
        <div>
          <span class="text-2xl font-bold">{{ formatPrice(pack) }}</span>
          <p v-if="lockedCount(pack) < pack.route_count" class="text-sm text-slate-500">{{ tr(
            `还有 ${lockedCount(pack)} 条路线 · 解锁全部`,
            `${lockedCount(pack)} more route${lockedCount(pack) === 1 ? '' : 's'} · unlock all`,
            `${lockedCount(pack)} itinéraire(s) de plus · tout débloquer`,
            `${lockedCount(pack)} ruta(s) más · desbloquear todo`,
            `還有 ${lockedCount(pack)} 條路線 · 解鎖全部`,
          ) }}</p>
        </div>
        <template v-if="pack.checkout_enabled">
          <button class="btn-primary px-6 py-3 text-base" :disabled="buying !== null" @click="onBuy(pack)">
            {{ buying === pack.slug ? tr('正在跳转付款…', 'Redirecting to checkout…') : tr('购买', 'Buy now') }}
          </button>
          <span v-if="!auth.token" class="text-sm text-slate-500">{{ tr('购买前需要先登录或注册', 'You will be asked to log in or register first') }}</span>
        </template>
        <span v-else class="text-sm text-slate-600">
          {{ tr('在线购买即将开放，如需现在购买请', 'Online purchase is coming soon. To buy now, ') }}<a
            :href="contactMailto(pack)" class="text-blue-600 hover:underline"
          >{{ tr('联系我们', 'contact us') }}</a>{{ tr('。', '.') }}
        </span>
      </div>

      <!-- Routes: overview image + segments. Locked: text only; purchased (or a free trial
           route while logged in): one big button per segment, whose link is fetched from the API on tap. -->
      <div class="grid gap-4" :class="pack.purchased ? '' : 'sm:grid-cols-2'">
        <div v-for="(r, ri) in pack.routes" :key="ri" class="border border-slate-200 rounded-lg p-4 space-y-3 min-w-0">
          <h3 class="font-semibold">
            <span v-if="!pack.purchased && !r.free" aria-hidden="true">🔒 </span>{{ routeTitle(r.title) }}
            <span
              v-if="!pack.purchased && r.free"
              class="ml-1 align-middle rounded-full bg-green-50 text-green-700 text-xs font-medium px-2 py-0.5"
            >{{ tr('免费试用', 'Free trial', 'Essai gratuit', 'Prueba gratis', '免費試用') }}</span>
          </h3>
          <div :class="pack.purchased ? 'sm:flex sm:gap-4 space-y-3 sm:space-y-0' : 'space-y-3'">
            <button
              v-if="r.preview"
              type="button"
              class="block w-full overflow-hidden rounded-md border border-slate-200 bg-slate-100"
              :class="pack.purchased ? 'sm:w-56 sm:shrink-0' : ''"
              :aria-label="tr('放大路线概览图', 'Enlarge route overview')"
              @click="enlarged = { src: previewSrc(r), alt: routeTitle(r.title) }"
            >
              <img
                :src="previewSrc(r)"
                :alt="tr(`${routeTitle(r.title)} 路线概览图`, `${routeTitle(r.title)} overview map`)"
                width="740"
                height="720"
                loading="lazy"
                decoding="async"
                class="w-full h-auto"
              />
            </button>
            <div class="space-y-2 min-w-0 flex-1">
              <template v-if="canOpen(pack, r)">
                <button
                  v-for="(seg, si) in r.segments"
                  :key="si"
                  class="btn-primary w-full py-4 text-base text-left flex items-center justify-between gap-2"
                  :disabled="opening !== null"
                  @click="onOpenSegment(pack, ri, si)"
                >
                  <span class="min-w-0">{{ opening === `${pack.slug}:${ri}:${si}` ? tr('打开中…', 'Opening…') : segmentText(seg) }}</span>
                  <span aria-hidden="true" class="shrink-0">↗</span>
                </button>
              </template>
              <button
                v-else-if="r.free"
                class="btn-primary w-full py-4 text-base"
                @click="goLogin"
              >{{ tr('登录后免费打开导航', 'Log in to open it free', 'Connectez-vous pour l’ouvrir gratuitement', 'Inicia sesión para abrirla gratis', '登入後免費開啟導航') }}</button>
              <ul v-else class="text-sm text-slate-600 space-y-1">
                <li v-for="(seg, si) in r.segments" :key="si">{{ segmentText(seg) }}</li>
              </ul>
              <p v-if="routeNote(r)" class="text-xs rounded-md bg-amber-50 text-amber-900 px-3 py-2">{{ routeNote(r) }}</p>
            </div>
          </div>
        </div>
      </div>
      <p v-if="routeHint(pack)" class="text-xs text-slate-500">{{ routeHint(pack) }}</p>
    </div>

    <div
      v-if="enlarged"
      class="fixed inset-0 z-50 bg-black/80 flex items-center justify-center p-4"
      role="dialog"
      aria-modal="true"
      @click="enlarged = null"
    >
      <img :src="enlarged.src" :alt="enlarged.alt" class="max-w-full max-h-full rounded-md bg-white" />
      <button
        class="absolute top-3 right-3 btn-secondary px-3"
        :aria-label="tr('关闭', 'Close')"
        @click.stop="enlarged = null"
      >✕</button>
    </div>

  </div>
</template>
