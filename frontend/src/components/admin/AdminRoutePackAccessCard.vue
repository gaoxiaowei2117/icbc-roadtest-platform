<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { api } from '@/api/client'
import { listRoutePacks, type RoutePack } from '@/api/routePacks'
import { useI18n } from '@/i18n'

/** Admin card: grant a route pack by email, and list / revoke / re-grant purchases. */
const emit = defineEmits<{ changed: [] }>()

type RoutePackPurchase = {
  id: number
  user_email: string | null
  pack_slug: string
  status: 'active' | 'revoked'
  source: 'stripe' | 'manual'
  created_at: string
  revoked_at: string | null
}

const routePacks = ref<RoutePack[]>([])
const purchases = ref<RoutePackPurchase[]>([])
const grantSlug = ref('')
const grantEmail = ref('')
const granting = ref(false)
const error = ref('')
const { tr, apiError, dateLocale } = useI18n()

async function refresh() {
  try {
    error.value = ''
    const [packs, purchasesResponse] = await Promise.all([
      listRoutePacks(),
      api.get('/api/admin/route-packs/purchases', { params: { limit: 200 } }),
    ])
    routePacks.value = packs
    purchases.value = purchasesResponse.data
    if (!grantSlug.value && packs.length) grantSlug.value = packs[0].slug
  } catch (e: any) {
    error.value = apiError(e, '加载路线包授权失败', 'Failed to load route pack access')
  }
}

async function change(action: 'grant' | 'revoke', slug = grantSlug.value, email = grantEmail.value.trim()) {
  if (!slug || !email) return
  if (action === 'revoke' && !window.confirm(tr(`收回 ${email} 的路线包 ${slug}？`, `Revoke ${slug} from ${email}?`))) return
  granting.value = true
  error.value = ''
  try {
    await api.post(`/api/admin/route-packs/${encodeURIComponent(slug)}/${action}`, { email })
    if (action === 'grant') grantEmail.value = ''
    await refresh()
    emit('changed')
  } catch (e: any) {
    error.value = apiError(e, '路线包操作失败', 'Route pack update failed')
  } finally {
    granting.value = false
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
    <h2 class="text-lg font-semibold mb-4">{{ tr('路线包授权', 'Route Pack Access') }}</h2>
    <p v-if="error" class="text-sm text-red-600 mb-3">{{ error }}</p>
    <form class="flex flex-wrap gap-2 mb-4" @submit.prevent="change('grant')">
      <select v-model="grantSlug" class="input w-auto">
        <option v-for="pack in routePacks" :key="pack.slug" :value="pack.slug">{{ pack.slug }}</option>
      </select>
      <input v-model="grantEmail" type="email" required class="input w-64 max-w-full" :placeholder="tr('用户邮箱', 'User email')" />
      <button type="submit" class="btn-primary" :disabled="granting || !grantSlug">{{ tr('手动开通', 'Grant') }}</button>
    </form>
    <div v-if="!purchases.length" class="text-sm text-slate-500 text-center py-4">{{ tr('暂无', 'None') }}</div>
    <table v-else class="w-full text-sm">
      <thead class="text-left text-slate-500 border-b">
        <tr>
          <th class="py-2 pr-3">{{ tr('邮箱', 'Email') }}</th>
          <th class="pr-3">{{ tr('路线包', 'Pack') }}</th>
          <th class="pr-3">{{ tr('状态', 'Status') }}</th>
          <th class="pr-3">{{ tr('来源', 'Source') }}</th>
          <th class="pr-3">{{ tr('创建时间', 'Created') }}</th>
          <th>{{ tr('操作', 'Actions') }}</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="p in purchases" :key="p.id" class="border-b last:border-0">
          <td class="py-2 pr-3">{{ p.user_email || '—' }}</td>
          <td class="pr-3">{{ p.pack_slug }}</td>
          <td class="pr-3">
            <span :class="p.status === 'active' ? 'badge-done' : 'badge-cancelled'">
              {{ p.status === 'active' ? tr('有效', 'Active') : tr('已收回', 'Revoked') }}
            </span>
          </td>
          <td class="pr-3">{{ p.source === 'stripe' ? 'Stripe' : tr('手动', 'Manual') }}</td>
          <td class="pr-3 whitespace-nowrap">{{ formatDateTime(p.created_at) }}</td>
          <td>
            <button
              v-if="p.status === 'active' && p.user_email"
              class="btn-secondary text-xs"
              :disabled="granting"
              @click="change('revoke', p.pack_slug, p.user_email)"
            >{{ tr('收回', 'Revoke') }}</button>
            <button
              v-else-if="p.user_email"
              class="btn-secondary text-xs"
              :disabled="granting"
              @click="change('grant', p.pack_slug, p.user_email)"
            >{{ tr('重新开通', 'Re-grant') }}</button>
          </td>
        </tr>
      </tbody>
    </table>
  </div>
</template>
