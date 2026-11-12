<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { api } from '@/api/client'
import { useI18n } from '@/i18n'

/** Admin card: the most recent "Open navigation" taps across all users. */
type RoutePackOpen = {
  id: number
  user_email: string | null
  pack_slug: string
  route_title: string | null
  route_index: number
  ip: string | null
  user_agent: string | null
  created_at: string
  redirected_at: string | null
}

const opens = ref<RoutePackOpen[]>([])
const error = ref('')
const { tr, apiError, dateLocale } = useI18n()

async function refresh() {
  try {
    error.value = ''
    opens.value = (await api.get('/api/admin/route-packs/opens', { params: { limit: 100 } })).data
  } catch (e: any) {
    error.value = apiError(e, '加载导航打开记录失败', 'Failed to load route opens')
  }
}

onMounted(refresh)
defineExpose({ refresh })

function formatDateTime(value: string | null) {
  return value ? new Date(value).toLocaleString(dateLocale.value) : '—'
}
</script>

<template>
  <div class="card overflow-x-auto">
    <h2 class="text-lg font-semibold mb-1">{{ tr('最近打开导航', 'Recent Route Opens') }}</h2>
    <p class="text-xs text-slate-500 mb-4">
      {{ tr('买家每点一次"打开导航"记一条。跳转后 Google 地图里的链接仍可被复制，这里只用来看使用情况和发现共享账号。',
            'One row per "Open navigation" tap. After the redirect the Google Maps link can still be copied; this is for usage and spotting shared accounts.') }}
    </p>
    <p v-if="error" class="text-sm text-red-600 mb-3">{{ error }}</p>
    <div v-if="!opens.length" class="text-sm text-slate-500 text-center py-4">{{ tr('暂无', 'None') }}</div>
    <table v-else class="w-full text-sm">
      <thead class="text-left text-slate-500 border-b">
        <tr>
          <th class="py-2 pr-3">{{ tr('时间', 'Time') }}</th>
          <th class="pr-3">{{ tr('邮箱', 'Email') }}</th>
          <th class="pr-3">{{ tr('路线', 'Route') }}</th>
          <th class="pr-3">IP</th>
          <th class="pr-3">{{ tr('已跳转', 'Redirected') }}</th>
          <th>{{ tr('设备', 'Device') }}</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="o in opens" :key="o.id" class="border-b last:border-0">
          <td class="py-2 pr-3 whitespace-nowrap">{{ formatDateTime(o.created_at) }}</td>
          <td class="pr-3">{{ o.user_email || '—' }}</td>
          <td class="pr-3">{{ o.pack_slug }} · {{ o.route_title || `#${o.route_index + 1}` }}</td>
          <td class="pr-3 text-xs">{{ o.ip || '—' }}</td>
          <td class="pr-3">{{ o.redirected_at ? tr('是', 'Yes') : tr('否', 'No') }}</td>
          <td class="text-xs text-slate-500 max-w-xs truncate" :title="o.user_agent || ''">{{ o.user_agent || '—' }}</td>
        </tr>
      </tbody>
    </table>
  </div>
</template>
