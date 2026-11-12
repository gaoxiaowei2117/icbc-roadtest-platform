<script setup lang="ts">
// Route packs page (root site "/" and /booking/routes).
//   ?centre=<slug>                 → that centre's detail (shareable)
//   ?country=&region=&q=           → browse view filters
//   ?pack=<slug>&checkout=success  → Stripe return; rewritten to ?centre=<slug>
// Without ?centre the browse view (search + country/region filters) is always shown, even with one pack.
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter, type LocationQueryRaw } from 'vue-router'
import { getRoutePackFacets, listRoutePacks, type RoutePackFacets } from '@/api/routePacks'
import RoutePackBrowse from '@/components/RoutePackBrowse.vue'
import RoutePackDetail from '@/components/RoutePackDetail.vue'
import { IS_ROUTE_SITE } from '@/site'
import { useI18n } from '@/i18n'

const route = useRoute()
const router = useRouter()
const { tr, apiError } = useI18n()

const str = (v: unknown) => (typeof v === 'string' ? v : '')
const facets = ref<RoutePackFacets | null>(null)
const onlySlug = ref('')
const error = ref('')
const checkout = ref<{ slug: string; status: 'success' | 'cancelled' } | null>(null)

const centre = computed(() => str(route.query.centre))
const hasFilters = computed(() => !!(route.query.country || route.query.region || route.query.q))
const detailSlug = computed(() => centre.value)
const canBrowse = computed(() => true)

function backToList() {
  const query: LocationQueryRaw = { ...route.query }
  delete query.centre
  router.push({ query })
}

onMounted(async () => {
  const pack = str(route.query.pack)
  const status = str(route.query.checkout)
  if (pack && (status === 'success' || status === 'cancelled')) {
    checkout.value = { slug: pack, status }
    // Drop the Stripe parameters so a refresh doesn't repeat the message.
    await router.replace({ query: { centre: pack } })
  }
  try {
    facets.value = await getRoutePackFacets()
    if (facets.value.total === 1) onlySlug.value = (await listRoutePacks())[0]?.slug ?? ''
  } catch (e: any) {
    error.value = apiError(e, '加载失败', 'Failed to load route packs')
  }
})

// The Stripe message belongs to that one centre only.
watch(centre, (slug) => {
  if (checkout.value && slug !== checkout.value.slug) checkout.value = null
})
</script>

<template>
  <div class="max-w-3xl mx-auto space-y-6">
    <!-- The route site's header already carries this title. -->
    <h1 v-if="!IS_ROUTE_SITE" class="text-2xl font-bold">{{ tr('路考练习路线', 'Road Test Practice Routes') }}</h1>
    <p v-if="error" class="text-sm text-red-600">{{ error }}</p>

    <template v-if="detailSlug">
      <button v-if="canBrowse" type="button" class="text-sm text-blue-600 hover:underline" @click="backToList">
        ← {{ tr('全部考场', 'All test centres') }}
      </button>
      <RoutePackDetail
        :key="detailSlug"
        :slug="detailSlug"
        :checkout="checkout && checkout.slug === detailSlug ? checkout.status : null"
      />
    </template>
    <RoutePackBrowse v-else-if="facets" :facets="facets" />
    <div v-else-if="!error" class="text-sm text-slate-500">{{ tr('加载中…', 'Loading…') }}</div>

    <div class="rounded-lg border border-amber-200 bg-amber-50 p-4 text-sm text-amber-900 space-y-1">
      <p class="font-semibold">{{ tr('免责声明', 'Disclaimer') }}</p>
      <p>{{ tr(
        '路线根据公开信息整理，并非 ICBC 或其他考试机构的官方路线；考官可能随时更改考试路线。',
        'Routes are compiled from public information and are not official routes of ICBC or any other licensing authority. Examiners may change routes at any time.',
      ) }}</p>
      <p>{{ tr(
        '仅供考前熟悉路况和练习使用，不保证通过考试。练习时请遵守交通规则，注意安全。',
        'For preview and practice only; not a guarantee of passing. Always drive safely and follow the rules of the road.',
      ) }}</p>
    </div>
  </div>
</template>
