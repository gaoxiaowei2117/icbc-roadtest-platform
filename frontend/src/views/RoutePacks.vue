<script setup lang="ts">
import { onMounted, onUnmounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { createRoutePackCheckout, getRoutePackLinks, listRoutePacks, type RoutePack } from '@/api/routePacks'
import { useAuthStore } from '@/stores/auth'
import { SUPPORT_EMAIL } from '@/config/support'
import { useI18n } from '@/i18n'

const auth = useAuthStore()
const route = useRoute()
const router = useRouter()
const { tr, apiError, dateLocale, locale } = useI18n()

const packs = ref<RoutePack[]>([])
const loading = ref(true)
const error = ref('')
const message = ref('')
const buying = ref<string | null>(null)
const opening = ref<string | null>(null)
let pollTimer: number | undefined

async function load() {
  try {
    packs.value = await listRoutePacks()
  } catch (e: any) {
    // An expired session is logged out by the auth interceptor; show the public view instead.
    if (!auth.token) packs.value = await listRoutePacks()
    else throw e
  }
}

async function refresh() {
  error.value = ''
  try {
    await load()
  } catch (e: any) {
    error.value = apiError(e, '加载失败', 'Failed to load route packs')
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
  await refresh()
  const slug = typeof route.query.pack === 'string' ? route.query.pack : ''
  if (route.query.checkout === 'success' && slug) {
    const pack = packs.value.find((p) => p.slug === slug)
    if (pack?.purchased) {
      message.value = tr('付款成功，路线已解锁。', 'Payment received. Your routes are unlocked.')
    } else {
      message.value = tr('付款完成，正在解锁路线…', 'Payment complete. Unlocking your routes…')
      waitForPurchase(slug)
    }
  } else if (route.query.checkout === 'cancelled') {
    message.value = tr('已取消付款，未扣款。', 'Checkout cancelled. You have not been charged.')
  }
  if (route.query.checkout) {
    // Drop the Stripe return parameters so a refresh doesn't repeat the message.
    router.replace({ name: 'routes' })
  }
})

onUnmounted(() => {
  if (pollTimer) window.clearInterval(pollTimer)
})

function packName(pack: RoutePack) {
  return locale.value.startsWith('zh') && pack.name_zh ? pack.name_zh : pack.name
}

function formatPrice(pack: RoutePack) {
  return new Intl.NumberFormat(dateLocale.value, {
    style: 'currency',
    currency: pack.currency.toUpperCase(),
    currencyDisplay: 'code',
  }).format(pack.price_cents / 100)
}

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

function segmentLabels(pack: RoutePack, routeIndex: number) {
  const count = pack.routes[routeIndex].segment_count
  if (count === 1) return [segmentLabel('全程')]
  return Array.from({ length: count }, (_, i) => segmentLabel(`第 ${i + 1} 段`))
}

async function onBuy(pack: RoutePack) {
  if (!auth.token) {
    router.push({ name: 'login', query: { redirect: '/routes' } })
    return
  }
  buying.value = pack.slug
  error.value = ''
  try {
    const checkout = await createRoutePackCheckout(pack.slug)
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
    // Fetched on demand so the links never sit in the page or its URL.
    const links = await getRoutePackLinks(pack.slug)
    const url = links.routes[routeIndex]?.segments[segmentIndex]?.url
    if (!url) throw new Error('missing link')
    // Same tab: on phones this hands off to the Google Maps app.
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
  <div class="max-w-3xl mx-auto space-y-6">
    <h1 class="text-2xl font-bold">{{ tr('路考练习路线', 'Road Test Practice Routes') }}</h1>
    <p v-if="message" class="text-sm rounded-md bg-blue-50 text-blue-800 px-4 py-3">{{ message }}</p>
    <p v-if="error" class="text-sm text-red-600">{{ error }}</p>
    <div v-if="loading" class="text-sm text-slate-500">{{ tr('加载中…', 'Loading…') }}</div>
    <div v-else-if="!packs.length && !error" class="text-sm text-slate-500">{{ tr('暂无路线包', 'No route packs yet') }}</div>

    <div v-for="pack in packs" :key="pack.slug" class="card space-y-5">
      <div>
        <h2 class="text-xl font-semibold">{{ packName(pack) }}</h2>
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
        <li>✓ {{ tr('手机一键打开 Google 地图导航', 'Opens in the Google Maps app on your phone', 'S’ouvre dans l’application Google Maps', 'Se abre en la app de Google Maps', '手機一鍵開啟 Google 地圖導航') }}</li>
        <li>✓ {{ tr('一次付款，永久查看', 'One-time payment, no subscription', 'Paiement unique, sans abonnement', 'Pago único, sin suscripción', '一次付款，永久查看') }}</li>
      </ul>

      <!-- Purchased: one big button per segment; the link is fetched on tap. -->
      <div v-if="pack.purchased" class="space-y-4">
        <div v-for="(r, ri) in pack.routes" :key="ri" class="border border-slate-200 rounded-lg p-4">
          <h3 class="font-semibold mb-3">{{ routeTitle(r.title) }}</h3>
          <div class="grid gap-3 sm:grid-cols-3">
            <button
              v-for="(label, si) in segmentLabels(pack, ri)"
              :key="si"
              class="btn-primary w-full py-4 text-base"
              :disabled="opening !== null"
              @click="onOpenSegment(pack, ri, si)"
            >
              {{ opening === `${pack.slug}:${ri}:${si}` ? tr('打开中…', 'Opening…') : `${label} ↗` }}
            </button>
          </div>
        </div>
        <p class="text-xs text-slate-500">{{ tr(
          '长路线因 Google 地图途经点数量限制被分成几段，请按顺序依次打开。',
          'Long routes are split into parts because Google Maps limits the number of stops. Open them in order.',
        ) }}</p>
      </div>

      <!-- Not purchased: preview + buy -->
      <div v-else class="space-y-4">
        <ul class="text-sm text-slate-600 grid gap-1 sm:grid-cols-2">
          <li v-for="(r, ri) in pack.routes" :key="ri">🔒 {{ routeTitle(r.title) }} · {{ tr(
            `${r.segment_count} 段`,
            `${r.segment_count} part${r.segment_count === 1 ? '' : 's'}`,
            `${r.segment_count} partie(s)`,
            `${r.segment_count} parte(s)`,
            `${r.segment_count} 段`,
          ) }}</li>
        </ul>
        <div class="flex flex-wrap items-center gap-4">
          <span class="text-2xl font-bold">{{ formatPrice(pack) }}</span>
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
      </div>
    </div>

    <div class="rounded-lg border border-amber-200 bg-amber-50 p-4 text-sm text-amber-900 space-y-1">
      <p class="font-semibold">{{ tr('免责声明', 'Disclaimer') }}</p>
      <p>{{ tr(
        '路线根据公开信息整理，并非 ICBC 官方路线；考官可能随时更改考试路线。',
        'Routes are compiled from public information and are not official ICBC routes. Examiners may change routes at any time.',
      ) }}</p>
      <p>{{ tr(
        '仅供考前熟悉路况和练习使用，不保证通过考试。练习时请遵守交通规则，注意安全。',
        'For preview and practice only; not a guarantee of passing. Always drive safely and follow the rules of the road.',
      ) }}</p>
    </div>
  </div>
</template>
