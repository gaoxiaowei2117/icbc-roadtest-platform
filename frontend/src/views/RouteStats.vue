<script setup lang="ts">
// Admin-only "Stats" tab of the route-pack site: sign-ups, free-route trials and
// sales by Vancouver day. Admins and accounts marked as test accounts are left out
// (marked on the Users tab). Visitor counts live in Cloudflare Web Analytics.
import { computed, onMounted, ref, watch } from 'vue'
import { HEARD_FROM, SOURCE_NAMES } from '@/sources'
import { getStats, type Stats } from '@/api/stats'
import { useI18n } from '@/i18n'

const RANGES = [7, 30, 90] as const
const CLOUDFLARE_WEB_ANALYTICS = 'https://dash.cloudflare.com/?to=/:account/web-analytics'

const { tr, apiError, dateLocale } = useI18n()
const days = ref<number>(30)
const stats = ref<Stats | null>(null)
const loading = ref(true)
const error = ref('')

async function load() {
  loading.value = true
  error.value = ''
  try {
    stats.value = await getStats(days.value)
  } catch (e: any) {
    error.value = apiError(e, '加载统计失败', 'Failed to load stats')
  } finally {
    loading.value = false
  }
}

onMounted(load)
watch(days, load)

function money(cents: number) {
  return new Intl.NumberFormat(dateLocale.value, {
    style: 'currency',
    currency: (stats.value?.currency || 'cad').toUpperCase(),
    currencyDisplay: 'code',
  }).format(cents / 100)
}

function pct(part: number, whole: number) {
  return whole ? `${Math.round((part / whole) * 100)}%` : '—'
}

/** "11月14日 周五" / "Fri, Nov 14": the date is a plain YYYY-MM-DD in Vancouver time. */
function dayLabel(iso: string) {
  const [y, m, d] = iso.split('-').map(Number)
  return new Date(y, m - 1, d).toLocaleDateString(dateLocale.value, { month: 'short', day: 'numeric', weekday: 'short' })
}

const tiles = computed(() => {
  const t = stats.value?.totals
  if (!t) return []
  return [
    { label: tr('新注册', 'Sign-ups'), value: String(t.signups), sub: tr(`${t.verified} 人已验证邮箱`, `${t.verified} verified`) },
    { label: tr('试用免费路线', 'Tried free route'), value: String(t.trial_users), sub: tr(`共打开导航 ${t.route_opens} 次`, `${t.route_opens} navigation opens`) },
    { label: tr('发起付款', 'Started checkout'), value: String(t.checkouts), sub: tr('打开了付款页面的人数', 'People who opened checkout') },
    { label: tr('购买', 'Purchases'), value: String(t.purchases), sub: tr('Stripe 付款成功，不含手动授权', 'Paid via Stripe, excludes manual grants') },
    { label: tr('收入', 'Revenue'), value: money(t.revenue_cents), sub: tr('付款成功的金额（未扣手续费）', 'Paid amount, before fees') },
  ]
})

/** Each step of the sign-up cohort, as a share of everyone who signed up in the range. */
const funnel = computed(() => {
  const f = stats.value?.funnel
  if (!f) return []
  return [
    { label: tr('注册', 'Signed up'), value: f.signed_up },
    { label: tr('验证邮箱', 'Verified email'), value: f.verified },
    { label: tr('打开免费路线', 'Opened free route'), value: f.tried_free_route },
    { label: tr('发起付款', 'Started checkout'), value: f.started_checkout },
    { label: tr('购买', 'Purchased'), value: f.purchased },
  ].map((step, i, all) => ({
    ...step,
    width: f.signed_up ? (step.value / f.signed_up) * 100 : 0,
    ofTotal: pct(step.value, f.signed_up),
    ofPrev: i === 0 ? '' : pct(step.value, all[i - 1].value),
  }))
})

/** Newest first, and only days where something happened. */
const activeDays = computed(() =>
  (stats.value?.daily ?? [])
    .filter((d) => d.signups || d.trial_users || d.route_opens || d.checkouts || d.purchases || d.revenue_cents)
    .slice()
    .reverse(),
)

/** "youtube" → "YouTube"; other sites show their host. */
function heardLabel(answer: string) {
  const opt = HEARD_FROM.find((o) => o.value === answer)
  return opt ? tr(opt.zh, opt.en, undefined, undefined, opt.zhHant) : answer
}

function sourceLabel(source: string) {
  if (source === 'direct') return tr('直接访问 / 未知', 'Direct / unknown')
  if (source === 'unknown') return tr('未记录（统计上线前注册）', 'Not recorded (signed up before tracking)')
  return SOURCE_NAMES[source] || source
}
</script>

<template>
  <div class="space-y-6">
    <div class="flex flex-wrap items-end justify-between gap-3">
      <div>
        <h1 class="text-2xl font-bold">{{ tr('统计', 'Stats') }}</h1>
        <p v-if="stats" class="text-sm text-slate-500">
          {{ dayLabel(stats.start) }} – {{ dayLabel(stats.end) }} · {{ tr('温哥华时间', 'Vancouver time') }}
        </p>
      </div>
      <div class="inline-flex rounded-md border border-slate-300 bg-white p-0.5 text-sm" role="group" :aria-label="tr('时间范围', 'Time range')">
        <button
          v-for="n in RANGES"
          :key="n"
          type="button"
          class="px-3 py-1.5 rounded"
          :class="days === n ? 'bg-blue-600 text-white' : 'text-slate-700 hover:bg-slate-100'"
          :aria-pressed="days === n"
          @click="days = n"
        >{{ tr(`近 ${n} 天`, `${n} days`) }}</button>
      </div>
    </div>

    <p class="text-xs text-slate-500">
      {{ tr(
        `管理员和标记为测试的账号不计入（目前 ${stats?.excluded_accounts ?? '…'} 个，在「用户」标签里标记）。访客数请看 `,
        `Admins and accounts marked as test accounts are left out (${stats?.excluded_accounts ?? '…'} now; mark them on the Users tab). For visitor counts, see `,
      ) }}<a :href="CLOUDFLARE_WEB_ANALYTICS" target="_blank" rel="noopener" class="text-blue-600 hover:underline">Cloudflare Web Analytics</a>{{ tr('。', '.') }}
    </p>

    <p v-if="error" class="text-sm text-red-600">{{ error }}</p>
    <div v-if="loading && !stats" class="text-sm text-slate-500">{{ tr('加载中…', 'Loading…') }}</div>

    <template v-if="stats">
      <!-- Headline numbers for the range -->
      <div class="grid gap-3 grid-cols-2 lg:grid-cols-5" :class="loading ? 'opacity-60' : ''">
        <div v-for="tile in tiles" :key="tile.label" class="card p-4">
          <p class="text-sm text-slate-500">{{ tile.label }}</p>
          <p class="text-2xl font-bold mt-1 tabular-nums">{{ tile.value }}</p>
          <p class="text-xs text-slate-500 mt-1">{{ tile.sub }}</p>
        </div>
      </div>

      <!-- Sign-up cohort funnel: one hue, bars share one scale (everyone who signed up) -->
      <div class="card space-y-4">
        <div>
          <h2 class="text-lg font-semibold">{{ tr('转化漏斗', 'Funnel') }}</h2>
          <p class="text-sm text-slate-500">{{ tr(
            `这段时间注册的 ${stats.funnel.signed_up} 人，到目前为止各走到了哪一步`,
            `How far the ${stats.funnel.signed_up} people who signed up in this range have got so far`,
          ) }}</p>
        </div>
        <div v-if="!stats.funnel.signed_up" class="text-sm text-slate-500">{{ tr('这段时间还没有人注册。', 'No sign-ups in this range yet.') }}</div>
        <ol v-else class="space-y-3">
          <li
            v-for="step in funnel"
            :key="step.label"
            class="grid grid-cols-[7.5rem_1fr_auto] sm:grid-cols-[9rem_1fr_7rem] items-center gap-3 text-sm"
            :title="step.ofPrev
              ? tr(`${step.label}：${step.value} 人，占注册 ${step.ofTotal}，占上一步 ${step.ofPrev}`, `${step.label}: ${step.value}, ${step.ofTotal} of sign-ups, ${step.ofPrev} of the previous step`)
              : tr(`${step.label}：${step.value} 人`, `${step.label}: ${step.value}`)"
          >
            <span class="text-slate-700">{{ step.label }}</span>
            <div class="h-6 rounded bg-slate-100 overflow-hidden">
              <div class="h-full rounded bg-blue-600 transition-[width]" :style="{ width: `${Math.max(step.width, step.value ? 2 : 0)}%` }"></div>
            </div>
            <span class="text-right tabular-nums">
              <span class="font-semibold">{{ step.value }}</span>
              <span class="text-slate-500"> · {{ step.ofTotal }}</span>
            </span>
          </li>
        </ol>
        <p class="text-sm text-slate-700 border-t border-slate-100 pt-3">
          {{ tr(
            `累计 ${stats.trial_users_all_time} 人试用过免费路线，其中 ${stats.trial_then_purchased_all_time} 人之后购买了路线包（${pct(stats.trial_then_purchased_all_time, stats.trial_users_all_time)}）。`,
            `All time: ${stats.trial_users_all_time} people tried the free route; ${stats.trial_then_purchased_all_time} of them bought the pack afterwards (${pct(stats.trial_then_purchased_all_time, stats.trial_users_all_time)}).`,
          ) }}
        </p>
      </div>

      <!-- Sign-ups by where they first came from (first touch, see src/attribution.ts) -->
      <div class="card overflow-x-auto">
        <h2 class="text-lg font-semibold">{{ tr('注册来源', 'Sign-ups by source') }}</h2>
        <p class="text-sm text-slate-500 mb-3">{{ tr(
          '按用户第一次从哪里来到网站统计（30 天内），以及各自走到了哪一步。',
          'Where each person first came from (within 30 days before signing up), and how far they got.',
        ) }}</p>
        <div v-if="!stats.by_source.length" class="text-sm text-slate-500 py-6 text-center">{{ tr('这段时间还没有人注册。', 'No sign-ups in this range yet.') }}</div>
        <table v-else class="w-full text-sm">
          <thead class="text-left text-slate-500 border-b">
            <tr>
              <th class="py-2 pr-3 font-medium">{{ tr('来源', 'Source') }}</th>
              <th class="py-2 px-3 font-medium text-right">{{ tr('注册', 'Sign-ups') }}</th>
              <th class="py-2 px-3 font-medium text-right">{{ tr('已验证', 'Verified') }}</th>
              <th class="py-2 px-3 font-medium text-right">{{ tr('试用', 'Tried free') }}</th>
              <th class="py-2 px-3 font-medium text-right">{{ tr('结账', 'Checkout') }}</th>
              <th class="py-2 pl-3 font-medium text-right">{{ tr('购买', 'Bought') }}</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="row in stats.by_source" :key="row.source" class="border-b border-slate-100 last:border-0">
              <td class="py-2 pr-3">{{ sourceLabel(row.source) }}</td>
              <td class="py-2 px-3 text-right tabular-nums font-semibold">{{ row.signups }}</td>
              <td class="py-2 px-3 text-right tabular-nums">{{ row.verified }}</td>
              <td class="py-2 px-3 text-right tabular-nums">{{ row.tried_free_route }}</td>
              <td class="py-2 px-3 text-right tabular-nums">{{ row.started_checkout }}</td>
              <td class="py-2 pl-3 text-right tabular-nums">{{ row.purchased }}</td>
            </tr>
          </tbody>
        </table>
      </div>

      <!-- Post-purchase survey: "how did you hear about us?" (components/HeardFromSurvey.vue) -->
      <div class="card overflow-x-auto">
        <h2 class="text-lg font-semibold">{{ tr('购买后问卷：从哪里知道我们', 'Post-purchase survey: how they heard about us') }}</h2>
        <p class="text-sm text-slate-500 mb-3">{{ tr(
          '付款成功后请用户选一项（可跳过）。累计全部时间，不受上面日期范围影响。',
          'Asked right after a successful payment (skippable). All time, not limited to the range above.',
        ) }}</p>
        <div v-if="!stats.heard_from.length" class="text-sm text-slate-500 py-6 text-center">{{ tr('还没有人回答。', 'No answers yet.') }}</div>
        <table v-else class="w-full text-sm">
          <thead class="text-left text-slate-500 border-b">
            <tr>
              <th class="py-2 pr-3 font-medium">{{ tr('回答', 'Answer') }}</th>
              <th class="py-2 px-3 font-medium text-right">{{ tr('人数', 'People') }}</th>
              <th class="py-2 pl-3 font-medium text-right">{{ tr('其中已购买', 'Of whom bought') }}</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="row in stats.heard_from" :key="row.answer" class="border-b border-slate-100 last:border-0">
              <td class="py-2 pr-3">{{ heardLabel(row.answer) }}</td>
              <td class="py-2 px-3 text-right tabular-nums font-semibold">{{ row.users }}</td>
              <td class="py-2 pl-3 text-right tabular-nums">{{ row.purchased }}</td>
            </tr>
          </tbody>
        </table>
      </div>

      <!-- Day by day (table view of everything above) -->
      <div class="card overflow-x-auto">
        <h2 class="text-lg font-semibold">{{ tr('每日明细', 'By day') }}</h2>
        <p class="text-sm text-slate-500 mb-3">{{ tr('只列出有数据的日期。', 'Only days with activity are listed.') }}</p>
        <div v-if="!activeDays.length" class="text-sm text-slate-500 py-6 text-center">{{ tr('这段时间没有数据。', 'Nothing in this range.') }}</div>
        <table v-else class="w-full text-sm">
          <thead class="text-left text-slate-500 border-b">
            <tr>
              <th class="py-2 pr-3">{{ tr('日期', 'Date') }}</th>
              <th class="pr-3 text-right">{{ tr('注册', 'Sign-ups') }}</th>
              <th class="pr-3 text-right">{{ tr('已验证', 'Verified') }}</th>
              <th class="pr-3 text-right">{{ tr('试用', 'Trials') }}</th>
              <th class="pr-3 text-right">{{ tr('打开导航', 'Opens') }}</th>
              <th class="pr-3 text-right">{{ tr('发起付款', 'Checkouts') }}</th>
              <th class="pr-3 text-right">{{ tr('购买', 'Purchases') }}</th>
              <th class="text-right">{{ tr('收入', 'Revenue') }}</th>
            </tr>
          </thead>
          <tbody class="tabular-nums">
            <tr v-for="d in activeDays" :key="d.date" class="border-b last:border-0">
              <td class="py-2 pr-3 whitespace-nowrap">{{ dayLabel(d.date) }}</td>
              <td class="pr-3 text-right">{{ d.signups || '—' }}</td>
              <td class="pr-3 text-right">{{ d.signups ? d.verified : '—' }}</td>
              <td class="pr-3 text-right">{{ d.trial_users || '—' }}</td>
              <td class="pr-3 text-right">{{ d.route_opens || '—' }}</td>
              <td class="pr-3 text-right">{{ d.checkouts || '—' }}</td>
              <td class="pr-3 text-right">{{ d.purchases || '—' }}</td>
              <td class="text-right whitespace-nowrap">{{ d.revenue_cents ? money(d.revenue_cents) : '—' }}</td>
            </tr>
          </tbody>
        </table>
      </div>
    </template>
  </div>
</template>
