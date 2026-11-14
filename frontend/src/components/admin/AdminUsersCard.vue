<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { api } from '@/api/client'
import { getPosList, type PosEntry } from '@/api/pos'
import { setStatsExclusion } from '@/api/stats'
import type { User } from '@/stores/auth'
import { useI18n } from '@/i18n'

/**
 * Admin user list, shared by the booking console and the route-pack site.
 * `routeOnly` keeps to what matters for route packs: no booking columns and
 * no ICBC profile. Delete is available in both; its confirmation says what goes with it.
 */
const props = defineProps<{ routeOnly?: boolean }>()
const emit = defineEmits<{ changed: [] }>()

type AdminUser = User & {
  is_active: boolean
  email_verified: boolean
  has_secret: boolean
  available_execution_passes: number
  route_packs?: string[]
  route_opens?: number
  route_opens_last_at?: string | null
  route_open_ips_24h?: number
  exclude_from_stats?: boolean
}

/** Distinct IPs in 24 h at or above this: the account may be shared (shown, not blocked). */
const SHARED_IP_WARN = 5

const users = ref<AdminUser[]>([])
const posList = ref<PosEntry[]>([])
const error = ref('')
const deletingUserId = ref<number | null>(null)
const expandedUserId = ref<number | null>(null)
const togglingStatsId = ref<number | null>(null)
const { tr, apiError, dateLocale, locale } = useI18n()

async function refresh() {
  try {
    error.value = ''
    const [usersResponse, positions] = await Promise.all([
      api.get('/api/admin/users', { params: { limit: 200 } }),
      props.routeOnly ? Promise.resolve<PosEntry[]>([]) : getPosList(),
    ])
    users.value = usersResponse.data
    posList.value = positions
  } catch (e: any) {
    error.value = apiError(e, '加载用户失败', 'Failed to load users')
  }
}

onMounted(refresh)
defineExpose({ refresh })

function formatDateTime(value: string | null) {
  return value ? new Date(value).toLocaleString(dateLocale.value) : '—'
}

function listSeparator() {
  return locale.value.startsWith('zh') ? '、' : ', '
}

function formatPositions(ids: number[] | null) {
  if (!ids?.length) return '—'
  return ids.map((id) => posList.value.find((pos) => pos.pos_id === id)?.name || `ID: ${id}`).join(listSeparator())
}

function formatDays(days: number[] | null) {
  const labels = {
    zh: ['周一', '周二', '周三', '周四', '周五', '周六', '周日'],
    'zh-Hant': ['週一', '週二', '週三', '週四', '週五', '週六', '週日'],
    en: ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'],
    fr: ['Lun', 'Mar', 'Mer', 'Jeu', 'Ven', 'Sam', 'Dim'],
    es: ['Lun', 'Mar', 'Mié', 'Jue', 'Vie', 'Sáb', 'Dom'],
  }[locale.value]
  return days?.length ? days.map((day) => labels[day] || String(day)).join(listSeparator()) : '—'
}

function formatParts(parts: number[] | null) {
  const labels: Record<number, string> = {
    zh: { 0: '上午', 1: '下午' }, 'zh-Hant': { 0: '上午', 1: '下午' }, en: { 0: 'Morning', 1: 'Afternoon' },
    fr: { 0: 'Matin', 1: 'Après-midi' }, es: { 0: 'Mañana', 1: 'Tarde' },
  }[locale.value]
  return parts?.length ? parts.map((part) => labels[part] || String(part)).join(listSeparator()) : '—'
}

/** Mark a test account so the Stats tab leaves it out (admins are always left out). */
async function toggleStats(user: AdminUser) {
  togglingStatsId.value = user.id
  error.value = ''
  try {
    const { excluded } = await setStatsExclusion(user.id, !user.exclude_from_stats)
    user.exclude_from_stats = excluded
  } catch (e: any) {
    error.value = apiError(e, '修改失败', 'Failed to update')
  } finally {
    togglingStatsId.value = null
  }
}

async function deleteUser(user: AdminUser) {
  const packs = user.route_packs?.length
    ? tr(
      `\n\n⚠ 该用户已购买路线包（${user.route_packs.join(', ')}），删除后购买和付款记录也会一起删除，无法恢复。`,
      `\n\n⚠ This user bought route packs (${user.route_packs.join(', ')}). Their purchase and payment records will be deleted too, permanently.`,
    )
    : ''
  if (!window.confirm(tr(
    `确定删除用户 ${user.email} 吗？该用户的抢号任务、凭据、路线包购买和导航打开记录也会被删除，无法恢复。`,
    `Delete ${user.email}? Their bookings, credentials, route-pack purchases and navigation opens will also be deleted, permanently.`,
    `Supprimer ${user.email}? Ses réservations, identifiants, achats d’itinéraires et ouvertures de navigation seront également supprimés définitivement.`,
    `¿Eliminar ${user.email}? Sus reservas, credenciales, compras de rutas y aperturas de navegación también se eliminarán de forma permanente.`,
    `確定刪除使用者 ${user.email} 嗎？該使用者的搶號任務、憑證、路線包購買和導航開啟記錄也會被刪除，無法恢復。`,
  ) + packs)) return
  deletingUserId.value = user.id
  error.value = ''
  try {
    await api.delete(`/api/admin/users/${user.id}`)
    await refresh()
    emit('changed')
  } catch (e: any) {
    error.value = apiError(e, '删除失败', 'Failed to delete user')
  } finally {
    deletingUserId.value = null
  }
}
</script>

<template>
  <div class="card overflow-x-auto">
    <h2 class="text-lg font-semibold mb-4">
      {{ tr('全部用户', 'All Users') }}
      <span v-if="users.length" class="text-sm font-normal text-slate-500">· {{ users.length }}</span>
    </h2>
    <p v-if="error" class="text-sm text-red-600 mb-3">{{ error }}</p>
    <div v-if="!users.length" class="text-sm text-slate-500 text-center py-8">{{ tr('暂无', 'None') }}</div>
    <table v-else class="w-full text-sm">
      <thead class="text-left text-slate-500 border-b">
        <tr>
          <th class="py-2 pr-3">#</th>
          <th class="pr-3">{{ tr('邮箱', 'Email') }}</th>
          <th class="pr-3">{{ tr('角色', 'Role') }}</th>
          <th class="pr-3">{{ tr('邮箱验证', 'Email verification') }}</th>
          <th v-if="!routeOnly" class="pr-3">{{ tr('状态', 'Status') }}</th>
          <th v-if="!routeOnly" class="pr-3">{{ tr('可用次数', 'Available passes') }}</th>
          <th class="pr-3">{{ tr('已购路线包', 'Route packs') }}</th>
          <th class="pr-3">{{ tr('导航打开', 'Route opens') }}</th>
          <th class="pr-3">{{ tr('注册时间', 'Registered') }}</th>
          <th v-if="routeOnly" class="pr-3">{{ tr('计入统计', 'In stats') }}</th>
          <th class="text-right">{{ tr('操作', 'Actions') }}</th>
        </tr>
      </thead>
      <tbody>
        <template v-for="user in users" :key="user.id">
          <tr class="border-b">
            <td class="py-2 pr-3">{{ user.id }}</td>
            <td class="pr-3">{{ user.email }}</td>
            <td class="pr-3 whitespace-nowrap">
              <span v-if="user.is_admin" class="badge bg-purple-100 text-purple-800">{{ tr('管理员', 'Admin') }}</span>
              <span v-else>{{ tr('普通用户', 'User') }}</span>
            </td>
            <td class="pr-3 whitespace-nowrap">{{ user.email_verified ? tr('已验证', 'Verified') : tr('未验证', 'Not verified') }}</td>
            <td v-if="!routeOnly" class="pr-3">{{ user.is_active ? tr('启用', 'Active') : tr('停用', 'Disabled') }}</td>
            <td v-if="!routeOnly" class="pr-3">{{ user.available_execution_passes }}</td>
            <td class="pr-3 text-xs">
              <span v-if="user.is_admin" class="text-purple-700">{{ tr('全部（管理员）', 'All (admin)') }}</span>
              <span v-else-if="user.route_packs?.length">{{ user.route_packs.join(', ') }}</span>
              <span v-else class="text-slate-400">—</span>
            </td>
            <td class="pr-3 text-xs">
              <template v-if="user.route_opens">
                <span>{{ user.route_opens }}</span>
                <span class="text-slate-400"> · {{ formatDateTime(user.route_opens_last_at ?? null) }}</span>
                <span
                  v-if="(user.route_open_ips_24h ?? 0) >= SHARED_IP_WARN"
                  class="badge bg-red-100 text-red-700 ml-1"
                  :title="tr('24 小时内从很多不同 IP 打开，账号可能被共享', 'Opened from many IPs in 24 h: the account may be shared')"
                >{{ tr(`24h ${user.route_open_ips_24h} 个 IP`, `${user.route_open_ips_24h} IPs / 24h`) }}</span>
              </template>
              <span v-else class="text-slate-400">—</span>
            </td>
            <td class="pr-3 whitespace-nowrap">{{ formatDateTime(user.created_at) }}</td>
            <td v-if="routeOnly" class="pr-3 whitespace-nowrap text-xs">
              <span v-if="user.is_admin" class="text-slate-400">{{ tr('不计入（管理员）', 'No (admin)') }}</span>
              <template v-else>
                <span :class="user.exclude_from_stats ? 'text-slate-500' : 'text-slate-700'">
                  {{ user.exclude_from_stats ? tr('不计入（测试）', 'No (test)') : tr('计入', 'Yes') }}
                </span>
                <button
                  class="ml-2 text-blue-600 hover:underline disabled:opacity-50"
                  :disabled="togglingStatsId === user.id"
                  @click="toggleStats(user)"
                >{{ user.exclude_from_stats ? tr('恢复计入', 'Count again') : tr('标为测试账号', 'Mark as test') }}</button>
              </template>
            </td>
            <td>
              <div class="flex justify-end gap-2">
                <button
                  v-if="!routeOnly"
                  class="btn-secondary text-xs px-3 py-1"
                  @click="expandedUserId = expandedUserId === user.id ? null : user.id"
                >
                  {{ expandedUserId === user.id ? tr('收起配置', 'Hide configuration') : tr('查看配置', 'View configuration') }}
                </button>
                <button
                  v-if="!user.is_admin"
                  class="btn-danger text-xs px-3 py-1"
                  :disabled="deletingUserId === user.id"
                  @click="deleteUser(user)"
                >
                  {{ deletingUserId === user.id ? tr('删除中…', 'Deleting…') : tr('删除', 'Delete') }}
                </button>
                <span v-else class="self-center text-xs text-slate-400">{{ tr('受保护', 'Protected') }}</span>
              </div>
            </td>
          </tr>
          <tr v-if="!routeOnly && expandedUserId === user.id" class="border-b bg-slate-50">
            <td colspan="10" class="p-4">
              <div class="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
                <div>
                  <h3 class="font-medium mb-2">{{ tr('ICBC 资料', 'ICBC Profile') }}</h3>
                  <p>{{ tr('驾照号：', 'Licence number: ') }}{{ user.icbc_license_no || '—' }}</p>
                  <p>{{ tr('姓氏：', 'Last name: ') }}{{ user.icbc_last_name || '—' }}</p>
                  <p>keyword: {{ user.has_secret ? tr('已配置', 'Configured') : tr('未配置', 'Not configured') }}</p>
                </div>
                <div>
                  <h3 class="font-medium mb-2">{{ tr('预约范围', 'Booking Range') }}</h3>
                  <p>{{ tr('考试类型：', 'Exam class: ') }}{{ user.exam_class || '—' }}</p>
                  <p>{{ tr('考点：', 'Location: ') }}{{ formatPositions(user.pos_ids) }}</p>
                  <p>{{ tr('日期：', 'Dates: ') }}{{ user.expect_after_date || '—' }} {{ tr('至', 'to') }} {{ user.expect_before_date || '—' }}</p>
                </div>
                <div>
                  <h3 class="font-medium mb-2">{{ tr('时间偏好', 'Time Preferences') }}</h3>
                  <p>{{ tr('时间区间：', 'Time range: ') }}{{ user.expect_time_range || '—' }}</p>
                  <p>{{ tr('星期：', 'Days: ') }}{{ formatDays(user.pref_days_of_week) }}</p>
                  <p>{{ tr('时段：', 'Time of day: ') }}{{ formatParts(user.pref_parts_of_day) }}</p>
                </div>
              </div>
            </td>
          </tr>
        </template>
      </tbody>
    </table>
  </div>
</template>
