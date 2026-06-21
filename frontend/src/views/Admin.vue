<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { api } from '@/api/client'
import type { Booking } from '@/api/bookings'
import { getPosList, type PosEntry } from '@/api/pos'
import type { User } from '@/stores/auth'
import { useI18n } from '@/i18n'

type AdminUser = User & { is_active: boolean; email_verified: boolean; has_secret: boolean }

const bookings = ref<Booking[]>([])
const users = ref<AdminUser[]>([])
const posList = ref<PosEntry[]>([])
const statusFilter = ref<string>('')
const error = ref('')
const deletingUserId = ref<number | null>(null)
const expandedUserId = ref<number | null>(null)
const { tr, apiError, dateLocale, locale } = useI18n()

async function refresh() {
  try {
    error.value = ''
    const params: Record<string, string> = { limit: '200' }
    if (statusFilter.value) params.status_filter = statusFilter.value
    const [bookingsResponse, usersResponse, positions] = await Promise.all([
      api.get('/api/admin/bookings', { params }),
      api.get('/api/admin/users', { params: { limit: 200 } }),
      getPosList(),
    ])
    bookings.value = bookingsResponse.data
    users.value = usersResponse.data
    posList.value = positions
  } catch (e: any) {
    error.value = apiError(e, '加载失败', 'Failed to load admin data')
  }
}

onMounted(refresh)

function formatDateTime(value: string | null) {
  return value ? new Date(value).toLocaleString(dateLocale.value) : '—'
}

function formatPositions(ids: number[] | null) {
  if (!ids?.length) return '—'
  return ids.map((id) => posList.value.find((pos) => pos.pos_id === id)?.name || `ID: ${id}`).join(locale.value.startsWith('zh') ? '、' : ', ')
}

function formatDays(days: number[] | null) {
  const labels = {
    zh: ['周一', '周二', '周三', '周四', '周五', '周六', '周日'],
    'zh-Hant': ['週一', '週二', '週三', '週四', '週五', '週六', '週日'],
    en: ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'],
    fr: ['Lun', 'Mar', 'Mer', 'Jeu', 'Ven', 'Sam', 'Dim'],
    es: ['Lun', 'Mar', 'Mié', 'Jue', 'Vie', 'Sáb', 'Dom'],
  }[locale.value]
  return days?.length ? days.map((day) => labels[day] || String(day)).join(locale.value.startsWith('zh') ? '、' : ', ') : '—'
}

function formatParts(parts: number[] | null) {
  const labels: Record<number, string> = {
    zh: { 0: '上午', 1: '下午' }, 'zh-Hant': { 0: '上午', 1: '下午' }, en: { 0: 'Morning', 1: 'Afternoon' },
    fr: { 0: 'Matin', 1: 'Après-midi' }, es: { 0: 'Mañana', 1: 'Tarde' },
  }[locale.value]
  return parts?.length ? parts.map((part) => labels[part] || String(part)).join(locale.value.startsWith('zh') ? '、' : ', ') : '—'
}

async function deleteUser(user: User) {
  if (!window.confirm(tr(
    `确定删除用户 ${user.email} 吗？该用户的任务和凭据也会被删除。`,
    `Delete ${user.email}? Their bookings and credentials will also be deleted.`,
    `Supprimer ${user.email}? Ses réservations et identifiants seront également supprimés.`,
    `¿Eliminar ${user.email}? Sus reservas y credenciales también se eliminarán.`,
    `確定刪除使用者 ${user.email} 嗎？該使用者的任務和憑證也會被刪除。`,
  ))) return
  deletingUserId.value = user.id
  error.value = ''
  try {
    await api.delete(`/api/admin/users/${user.id}`)
    await refresh()
  } catch (e: any) {
    error.value = apiError(e, '删除失败', 'Failed to delete user')
  } finally {
    deletingUserId.value = null
  }
}
</script>

<template>
  <div class="space-y-6">
    <h1 class="text-2xl font-bold">{{ tr('管理员控制台', 'Admin Console') }}</h1>
    <p v-if="error" class="text-sm text-red-600">{{ error }}</p>
    <div class="card overflow-x-auto">
      <h2 class="text-lg font-semibold mb-4">{{ tr('全部用户', 'All Users') }}</h2>
      <div v-if="!users.length" class="text-sm text-slate-500 text-center py-8">{{ tr('暂无', 'None') }}</div>
      <table v-else class="w-full text-sm">
        <thead class="text-left text-slate-500 border-b">
          <tr>
            <th class="py-2">#</th>
            <th>{{ tr('邮箱', 'Email') }}</th>
            <th>{{ tr('角色', 'Role') }}</th>
            <th>{{ tr('邮箱验证', 'Email verification') }}</th>
            <th>{{ tr('状态', 'Status') }}</th>
            <th>{{ tr('注册时间', 'Registered') }}</th>
            <th class="text-right">{{ tr('操作', 'Actions') }}</th>
          </tr>
        </thead>
        <tbody>
          <template v-for="user in users" :key="user.id">
            <tr class="border-b">
              <td class="py-2">{{ user.id }}</td>
              <td>{{ user.email }}</td>
              <td>
                <span v-if="user.is_admin" class="badge bg-purple-100 text-purple-800">{{ tr('管理员', 'Admin') }}</span>
                <span v-else>{{ tr('普通用户', 'User') }}</span>
              </td>
              <td>{{ user.email_verified ? tr('已验证', 'Verified') : tr('未验证', 'Not verified') }}</td>
              <td>{{ user.is_active ? tr('启用', 'Active') : tr('停用', 'Disabled') }}</td>
              <td>{{ formatDateTime(user.created_at) }}</td>
              <td>
                <div class="flex justify-end gap-2">
                  <button
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
            <tr v-if="expandedUserId === user.id" class="border-b bg-slate-50">
              <td colspan="7" class="p-4">
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
    <div class="card">
      <h2 class="text-lg font-semibold mb-4">{{ tr('全部任务', 'All Bookings') }}</h2>
      <div class="flex items-center gap-3 mb-4">
        <label class="text-sm">{{ tr('状态筛选：', 'Status filter:') }}</label>
        <select v-model="statusFilter" class="input max-w-xs" @change="refresh">
          <option value="">{{ tr('全部', 'All') }}</option>
          <option value="pending">pending</option>
          <option value="running">running</option>
          <option value="done">done</option>
          <option value="failed">failed</option>
          <option value="cancelled">cancelled</option>
        </select>
      </div>
      <div v-if="!bookings.length" class="text-sm text-slate-500 text-center py-8">{{ tr('暂无', 'None') }}</div>
      <table v-else class="w-full text-sm">
        <thead class="text-left text-slate-500 border-b">
          <tr>
            <th class="py-2">#</th>
            <th>{{ tr('用户', 'User') }}</th>
            <th>{{ tr('状态', 'Status') }}</th>
            <th>{{ tr('尝试', 'Attempts') }}</th>
            <th>{{ tr('查询轮次', 'Search rounds') }}</th>
            <th>{{ tr('最近动态', 'Latest activity') }}</th>
            <th>{{ tr('更新时间', 'Updated') }}</th>
            <th>{{ tr('创建', 'Created') }}</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="b in bookings" :key="b.id" class="border-b last:border-0">
            <td class="py-2">{{ b.id }}</td>
            <td>
              <div>{{ b.user_email || tr('未知用户', 'Unknown user') }}</div>
              <div class="text-xs text-slate-400">ID: {{ b.user_id }}</div>
            </td>
            <td>{{ b.status }}</td>
            <td>{{ b.attempt_count }}</td>
            <td>{{ b.progress_rounds }}</td>
            <td class="text-xs truncate max-w-xs">
              <span v-if="b.last_error" class="text-red-600">{{ b.last_error }}</span>
              <span v-else class="text-slate-600">{{ b.last_progress || '—' }}</span>
            </td>
            <td class="text-xs text-slate-500">{{ formatDateTime(b.last_progress_at || b.updated_at) }}</td>
            <td>{{ new Date(b.created_at).toLocaleString(dateLocale) }}</td>
          </tr>
        </tbody>
      </table>
    </div>
  </div>
</template>
