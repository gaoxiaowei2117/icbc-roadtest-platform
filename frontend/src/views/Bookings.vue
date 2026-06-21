<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref } from 'vue'
import { cancelBooking, createBooking, listBookings, type Booking } from '@/api/bookings'
import { useI18n } from '@/i18n'

const bookings = ref<Booking[]>([])
const error = ref('')
const message = ref('')
const loading = ref(false)
let refreshTimer: number | undefined
const { tr, apiError, dateLocale } = useI18n()

const hasActiveBooking = computed(() =>
  bookings.value.some((b) => b.status === 'pending' || b.status === 'running'),
)

async function refresh() {
  if (!refreshTimer) loading.value = true
  try {
    bookings.value = await listBookings()
    syncAutoRefresh()
  } catch (e: any) {
    error.value = apiError(e, '加载失败', 'Failed to load bookings')
  } finally {
    loading.value = false
  }
}

async function onCreate() {
  try {
    await createBooking()
    alert(tr('任务已创建，等待 worker 执行', 'Booking created and waiting for a worker'))
    await refresh()
  } catch (e: any) {
    alert(tr('创建失败：', 'Create failed: ') + apiError(e, '未知错误', 'Unknown error'))
  }
}

async function onCancel(b: Booking) {
  if (!confirm(tr(`确定取消任务 #${b.id}？`, `Cancel booking #${b.id}?`, `Annuler la réservation no ${b.id}?`, `¿Cancelar la reserva n.º ${b.id}?`, `確定取消任務 #${b.id}？`))) return
  try {
    await cancelBooking(b.id)
    await refresh()
  } catch (e: any) {
    error.value = apiError(e, '取消失败', 'Cancellation failed')
  }
}

function badgeClass(s: Booking['status']) {
  return {
    pending: 'badge-pending',
    running: 'badge-running',
    done: 'badge-done',
    failed: 'badge-failed',
    cancelled: 'badge-cancelled',
  }[s]
}

function formatDateTime(value: string | null) {
  return value ? new Date(value).toLocaleString(dateLocale.value) : '—'
}

function syncAutoRefresh() {
  if (hasActiveBooking.value && !refreshTimer) {
    refreshTimer = window.setInterval(refresh, 5000)
  } else if (!hasActiveBooking.value && refreshTimer) {
    window.clearInterval(refreshTimer)
    refreshTimer = undefined
  }
}

onMounted(refresh)
onUnmounted(() => {
  if (refreshTimer) window.clearInterval(refreshTimer)
})
</script>

<template>
  <div class="space-y-6">
    <h1 class="text-2xl font-bold">{{ tr('抢约任务', 'Road Test Bookings') }}</h1>

    <div class="card space-y-4">
      <h2 class="text-lg font-semibold">{{ tr('新建任务', 'New Booking') }}</h2>
      <p class="text-sm text-slate-600">
        {{ tr('抢号参数来自「设置」页的档案（考点 / 日期 / 时间 / 偏好）。请先在设置页填好档案与 keyword，再创建任务。', 'Booking parameters come from Settings (location, dates, times, and preferences). Complete your profile and keyword before creating a booking.') }}
      </p>
      <button class="btn-primary" @click="onCreate">{{ tr('创建任务', 'Create booking') }}</button>
    </div>

    <p v-if="message" class="text-sm text-green-600">{{ message }}</p>
    <p v-if="error" class="text-sm text-red-600">{{ error }}</p>

    <div class="card">
      <div class="flex items-center justify-between mb-4">
        <h2 class="text-lg font-semibold">{{ tr('我的任务', 'My Bookings') }}</h2>
        <button class="btn-secondary" @click="refresh" :disabled="loading">{{ tr('刷新', 'Refresh') }}</button>
      </div>
      <div v-if="!bookings.length" class="text-sm text-slate-500 text-center py-8">{{ tr('暂无任务', 'No bookings') }}</div>
      <table v-else class="w-full text-sm">
        <thead class="text-left text-slate-500 border-b">
          <tr>
            <th class="py-2">#</th>
            <th>{{ tr('状态', 'Status') }}</th>
            <th>{{ tr('尝试', 'Attempts') }}</th>
            <th>{{ tr('查询轮次', 'Search rounds') }}</th>
            <th>{{ tr('最近动态', 'Latest activity') }}</th>
            <th>{{ tr('更新时间', 'Updated') }}</th>
            <th>{{ tr('创建', 'Created') }}</th>
            <th></th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="b in bookings" :key="b.id" class="border-b last:border-0">
            <td class="py-2">{{ b.id }}</td>
            <td><span :class="badgeClass(b.status)">{{ b.status }}</span></td>
            <td>{{ b.attempt_count }}</td>
            <td>{{ b.progress_rounds }}</td>
            <td class="text-xs max-w-sm">
              <span v-if="b.last_error" class="text-red-600">{{ b.last_error }}</span>
              <span v-else class="text-slate-600">{{ b.last_progress || '—' }}</span>
            </td>
            <td class="text-xs text-slate-500">{{ formatDateTime(b.last_progress_at || b.updated_at) }}</td>
            <td>{{ new Date(b.created_at).toLocaleString(dateLocale) }}</td>
            <td>
              <button
                v-if="b.status === 'pending' || b.status === 'running'"
                class="text-red-600 hover:underline"
                @click="onCancel(b)"
              >
                {{ tr('取消', 'Cancel') }}
              </button>
            </td>
          </tr>
        </tbody>
      </table>
    </div>
  </div>
</template>
