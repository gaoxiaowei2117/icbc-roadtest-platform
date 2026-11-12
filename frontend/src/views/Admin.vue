<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { api } from '@/api/client'
import type { Booking } from '@/api/bookings'
import AdminUsersCard from '@/components/admin/AdminUsersCard.vue'
import AdminRoutePackAccessCard from '@/components/admin/AdminRoutePackAccessCard.vue'
import AdminRouteOpensCard from '@/components/admin/AdminRouteOpensCard.vue'
import { useI18n } from '@/i18n'
import { translateActivity } from '@/activity'

// Users, route-pack access and route opens live in their own cards (shared with
// the route-pack site's admin tab); this view owns the bookings table.
const bookings = ref<Booking[]>([])
const statusFilter = ref<string>('')
const error = ref('')
const reviewingBookingId = ref<number | null>(null)
const usersCard = ref<InstanceType<typeof AdminUsersCard> | null>(null)
const accessCard = ref<InstanceType<typeof AdminRoutePackAccessCard> | null>(null)
const { tr, apiError, dateLocale } = useI18n()

async function refresh() {
  try {
    error.value = ''
    const params: Record<string, string> = { limit: '200' }
    if (statusFilter.value) params.status_filter = statusFilter.value
    bookings.value = (await api.get('/api/admin/bookings', { params })).data
  } catch (e: any) {
    error.value = apiError(e, '加载失败', 'Failed to load admin data')
  }
}

/** A deleted user takes their bookings and purchases with them. */
function onUsersChanged() {
  refresh()
  accessCard.value?.refresh()
}

/** Approving a payment can grant an execution pass, shown in the user list. */
async function refreshAfterReview() {
  await refresh()
  usersCard.value?.refresh()
}

onMounted(refresh)

function formatDateTime(value: string | null) {
  return value ? new Date(value).toLocaleString(dateLocale.value) : '—'
}

async function approvePayment(booking: Booking) {
  if (!window.confirm(tr(
    booking.status === 'cancelled'
      ? `确认已收到任务 #${booking.id} 的付款，并给用户发放一次可用次数？原任务将保持取消状态。`
      : `确认已收到任务 #${booking.id} 的付款并发放一次执行权限？`,
    booking.status === 'cancelled'
      ? `Confirm payment for cancelled booking #${booking.id} and grant one available execution pass?`
      : `Confirm payment for booking #${booking.id} and grant one execution pass?`,
  ))) return
  reviewingBookingId.value = booking.id
  try {
    await api.post(`/api/admin/bookings/${booking.id}/approve-payment`)
    await refreshAfterReview()
  } catch (e: any) {
    error.value = apiError(e, '审核通过失败', 'Failed to approve payment')
  } finally {
    reviewingBookingId.value = null
  }
}

async function rejectPayment(booking: Booking) {
  const reason = window.prompt(tr('请输入拒绝原因（可选）：', 'Reason for rejection (optional):'))
  if (reason === null) return
  reviewingBookingId.value = booking.id
  try {
    await api.post(`/api/admin/bookings/${booking.id}/reject-payment`, { reason })
    await refreshAfterReview()
  } catch (e: any) {
    error.value = apiError(e, '拒绝付款失败', 'Failed to reject payment')
  } finally {
    reviewingBookingId.value = null
  }
}
</script>

<template>
  <div class="space-y-6">
    <h1 class="text-2xl font-bold">{{ tr('管理员控制台', 'Admin Console') }}</h1>
    <p v-if="error" class="text-sm text-red-600">{{ error }}</p>
    <AdminUsersCard ref="usersCard" @changed="onUsersChanged" />
    <AdminRoutePackAccessCard ref="accessCard" @changed="usersCard?.refresh()" />
    <AdminRouteOpensCard />

    <div class="card">
      <h2 class="text-lg font-semibold mb-4">{{ tr('全部任务', 'All Bookings') }}</h2>
      <div class="flex items-center gap-3 mb-4">
        <label class="text-sm">{{ tr('状态筛选：', 'Status filter:') }}</label>
        <select v-model="statusFilter" class="input max-w-xs" @change="refresh">
          <option value="">{{ tr('全部', 'All') }}</option>
          <option value="pending">pending</option>
          <option value="awaiting_payment">awaiting_payment</option>
          <option value="awaiting_review">awaiting_review</option>
          <option value="payment_rejected">payment_rejected</option>
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
            <th>{{ tr('付款', 'Payment') }}</th>
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
            <td>
              <div>{{ b.payment_status }}</div>
              <div v-if="b.payment_reference" class="text-xs text-slate-500">{{ b.payment_reference }}</div>
              <div v-if="b.review_reason" class="text-xs text-red-600">{{ b.review_reason }}</div>
              <div v-if="b.payment_status === 'awaiting_review'" class="flex gap-2 mt-1">
                <button
                  class="text-green-700 hover:underline disabled:opacity-50"
                  :disabled="reviewingBookingId === b.id"
                  @click="approvePayment(b)"
                >{{ b.status === 'cancelled' ? tr('通过并发放次数', 'Approve and grant pass') : tr('通过', 'Approve') }}</button>
                <button
                  class="text-red-700 hover:underline disabled:opacity-50"
                  :disabled="reviewingBookingId === b.id"
                  @click="rejectPayment(b)"
                >{{ tr('拒绝', 'Reject') }}</button>
              </div>
            </td>
            <td>{{ b.attempt_count }}</td>
            <td>{{ b.progress_rounds }}</td>
            <td class="text-xs truncate max-w-xs">
              <span v-if="b.last_error" class="text-red-600">{{ translateActivity(b.last_error, tr) }}</span>
              <span v-else class="text-slate-600">{{ translateActivity(b.last_progress, tr) || '—' }}</span>
            </td>
            <td class="text-xs text-slate-500">{{ formatDateTime(b.last_progress_at || b.updated_at) }}</td>
            <td>{{ new Date(b.created_at).toLocaleString(dateLocale) }}</td>
          </tr>
        </tbody>
      </table>
    </div>
  </div>
</template>
