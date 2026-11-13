<script setup lang="ts">
// Browse test centres: country → region dropdowns, search, cards grouped by region.
// All filter state lives in the query string (?country=CA&region=BC&q=...), so
// links are shareable and back/forward work.
import { computed, onUnmounted, ref, watch } from 'vue'
import { useRoute, useRouter, type LocationQueryRaw } from 'vue-router'
import { listRoutePacks, type RoutePack, type RoutePackFacets } from '@/api/routePacks'
import { useAuthStore } from '@/stores/auth'
import { useI18n } from '@/i18n'
import { useRoutePackText } from '@/routePackText'

const props = defineProps<{ facets: RoutePackFacets }>()

const auth = useAuthStore()
const route = useRoute()
const router = useRouter()
const { tr, apiError } = useI18n()
const { packName, placeLine, formatPrice, countryName, regionName } = useRoutePackText()

const str = (v: unknown) => (typeof v === 'string' ? v : '')
const country = computed(() => str(route.query.country).toUpperCase())
const region = computed(() => str(route.query.region).toUpperCase())
const q = computed(() => str(route.query.q))

const packs = ref<RoutePack[]>([])
const loading = ref(true)
const error = ref('')
const searchText = ref(q.value)

const multiCountry = computed(() => props.facets.countries.length > 1)
// With a single country there is nothing to choose; its regions are offered directly.
const effectiveCountry = computed(() => country.value || (multiCountry.value ? '' : props.facets.countries[0]?.code || ''))
const regionOptions = computed(
  () => props.facets.countries.find((c) => c.code === effectiveCountry.value)?.regions ?? [],
)
const hasFilters = computed(() => !!(country.value || region.value || q.value))

function updateQuery(patch: Record<string, string | undefined>, replace = false) {
  const query: LocationQueryRaw = { ...route.query, ...patch }
  for (const key of Object.keys(query)) if (!query[key]) delete query[key]
  return replace ? router.replace({ query }) : router.push({ query })
}

function onCountry(e: Event) {
  updateQuery({ country: (e.target as HTMLSelectElement).value || undefined, region: undefined })
}

function onRegion(e: Event) {
  updateQuery({ region: (e.target as HTMLSelectElement).value || undefined })
}

function clearFilters() {
  searchText.value = ''
  router.push({ query: {} })
}

// Debounced search; replace (not push) so typing doesn't flood the history.
let searchTimer: number | undefined
watch(searchText, (value) => {
  window.clearTimeout(searchTimer)
  searchTimer = window.setTimeout(() => {
    if (value.trim() !== q.value) updateQuery({ q: value.trim() || undefined }, true)
  }, 300)
})
watch(q, (value) => {
  if (value !== searchText.value.trim()) searchText.value = value
})
onUnmounted(() => window.clearTimeout(searchTimer))

let requestId = 0
async function load() {
  const id = ++requestId
  loading.value = true
  error.value = ''
  const filters = { country: country.value, region: region.value, q: q.value }
  try {
    let result: RoutePack[]
    try {
      result = await listRoutePacks(filters)
    } catch (e: any) {
      // Expired session: the interceptor logged out; retry as anonymous.
      if (auth.token) throw e
      result = await listRoutePacks(filters)
    }
    if (id === requestId) packs.value = result
  } catch (e: any) {
    if (id === requestId) error.value = apiError(e, '加载失败', 'Failed to load route packs')
  } finally {
    if (id === requestId) loading.value = false
  }
}
watch([country, region, q], load, { immediate: true })

const groups = computed(() => {
  const byKey = new Map<string, { country: string; region: string; packs: RoutePack[] }>()
  for (const p of packs.value) {
    const key = `${p.country}-${p.region}`
    if (!byKey.has(key)) byKey.set(key, { country: p.country, region: p.region, packs: [] })
    byKey.get(key)!.packs.push(p)
  }
  return [...byKey.values()]
    .sort((a, b) => a.country.localeCompare(b.country) || regionName(a.country, a.region).localeCompare(regionName(b.country, b.region)))
    .map((g) => ({ ...g, packs: [...g.packs].sort((a, b) => a.city.localeCompare(b.city) || a.name.localeCompare(b.name)) }))
})

function groupTitle(g: { country: string; region: string }) {
  const name = regionName(g.country, g.region)
  return multiCountry.value ? `${name} · ${countryName(g.country)}` : name
}
</script>

<template>
  <div class="space-y-4">
    <div class="card space-y-3 p-4 sm:p-6">
      <label class="block">
        <span class="sr-only">{{ tr('搜索考场', 'Search test centres') }}</span>
        <input
          v-model="searchText"
          type="search"
          class="input"
          :placeholder="tr('搜索考场、城市或地址', 'Search centre, city or address')"
          enterkeyhint="search"
        />
      </label>
      <div class="grid grid-cols-2 gap-3">
        <select class="input" :value="country" :aria-label="tr('国家', 'Country')" @change="onCountry">
          <option value="">{{ tr('全部国家', 'All countries') }}</option>
          <option v-for="c in facets.countries" :key="c.code" :value="c.code">{{ countryName(c.code) }} ({{ c.count }})</option>
        </select>
        <select
          class="input"
          :value="region"
          :disabled="!effectiveCountry"
          :aria-label="tr('省 / 州', 'Province / state')"
          @change="onRegion"
        >
          <option value="">{{ effectiveCountry ? tr('全部省 / 州', 'All provinces / states') : tr('省 / 州', 'Province / state') }}</option>
          <option v-for="r in regionOptions" :key="r.code" :value="r.code">{{ regionName(effectiveCountry, r.code) }} ({{ r.count }})</option>
        </select>
      </div>
      <div class="flex items-center justify-between gap-3 text-sm text-slate-600">
        <span>{{ loading ? tr('搜索中…', 'Searching…') : tr(`共 ${packs.length} 个考场`, `${packs.length} test centre${packs.length === 1 ? '' : 's'}`) }}</span>
        <button v-if="hasFilters" type="button" class="text-blue-600 hover:underline" @click="clearFilters">{{ tr('清除筛选', 'Clear filters') }}</button>
      </div>
    </div>

    <p v-if="error" class="text-sm text-red-600">{{ error }}</p>

    <div v-if="!loading && !error && !packs.length" class="card text-center space-y-2">
      <p class="font-medium">{{ tr('没有符合条件的考场', 'No test centres match') }}</p>
      <p class="text-sm text-slate-500">{{ tr('换个关键词，或清除筛选查看全部考场。', 'Try another search, or clear the filters to see all centres.') }}</p>
      <button v-if="hasFilters" type="button" class="btn-secondary mt-2" @click="clearFilters">{{ tr('清除筛选', 'Clear filters') }}</button>
    </div>

    <section v-for="g in groups" :key="`${g.country}-${g.region}`" class="space-y-2">
      <h2 class="text-sm font-semibold text-slate-500 uppercase tracking-wide">{{ groupTitle(g) }}</h2>
      <div class="grid gap-3 sm:grid-cols-2">
        <RouterLink
          v-for="p in g.packs"
          :key="p.slug"
          :to="{ query: { ...route.query, centre: p.slug } }"
          class="card p-4 block hover:ring-2 hover:ring-blue-200 transition min-w-0"
        >
          <div class="flex items-start justify-between gap-2">
            <h3 class="font-semibold leading-snug min-w-0">{{ packName(p) }}</h3>
            <span v-if="p.purchased" class="badge-done shrink-0">{{ tr('已购买', 'Purchased') }}</span>
            <span
              v-else-if="p.routes.some((r) => r.free)"
              class="shrink-0 rounded-full bg-green-50 text-green-700 text-xs font-medium px-2 py-0.5"
            >{{ tr('可免费试用', 'Free trial', 'Essai gratuit', 'Prueba gratis', '可免費試用') }}</span>
          </div>
          <p class="text-sm text-slate-500 mt-1">{{ placeLine(p) }}</p>
          <div class="flex items-center justify-between gap-2 mt-3 text-sm">
            <span class="text-slate-600">{{ tr(`${p.route_count} 条路线`, `${p.route_count} route${p.route_count === 1 ? '' : 's'}`) }}</span>
            <span class="font-semibold">{{ formatPrice(p) }}</span>
          </div>
        </RouterLink>
      </div>
    </section>
  </div>
</template>
