<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref } from 'vue'
import { cancelBooking, createBooking, listBookings, submitPayment, type Booking } from '@/api/bookings'
import { api } from '@/api/client'
import { SUPPORT_EMAIL } from '@/config/support'
import { useI18n } from '@/i18n'

const bookings = ref<Booking[]>([])
const error = ref('')
const message = ref('')
const loading = ref(false)
const paymentSubmitting = ref(false)
const availableCredits = ref(0)
let refreshTimer: number | undefined
const { tr, apiError, dateLocale } = useI18n()

const WECHAT_QR = `${import.meta.env.BASE_URL}donate/wechat.png`
const ALIPAY_QR = `${import.meta.env.BASE_URL}donate/alipay.png`
const paymentReference = ref('')
const paymentReferenceValid = computed(() => paymentReference.value.trim().length > 0)

const hasActiveBooking = computed(() =>
  bookings.value.some((b) => ['awaiting_payment', 'awaiting_review', 'pending', 'running'].includes(b.status)),
)
const paymentBooking = computed(() => bookings.value.find((b) => b.status === 'awaiting_payment'))

async function refresh() {
  if (!refreshTimer) loading.value = true
  try {
    const [bookingList, credits] = await Promise.all([
      listBookings(),
      api.get<{ available: number }>('/api/users/me/credits'),
    ])
    bookings.value = bookingList
    availableCredits.value = credits.data.available
    syncAutoRefresh()
  } catch (e: any) {
    error.value = apiError(e, '加载失败', 'Failed to load bookings')
  } finally {
    loading.value = false
  }
}

async function onCreate() {
  try {
    const booking = await createBooking()
    if (booking.status === 'awaiting_payment') {
      message.value = tr(
        '任务已创建，请按管理员提供的方式付款，然后在下方提交付款审核。',
        'Booking created. Pay using the administrator-provided method, then submit payment for review below.',
      )
    } else {
      alert(tr('任务已创建，等待 worker 执行', 'Booking created and waiting for a worker'))
    }
    await refresh()
  } catch (e: any) {
    alert(tr('创建失败：', 'Create failed: ') + apiError(e, '未知错误', 'Unknown error'))
  }
}

async function onSubmitPayment(b: Booking) {
  paymentSubmitting.value = true
  try {
    await submitPayment(b.id, paymentReference.value.trim())
    paymentReference.value = ''
    message.value = tr('付款已提交，等待超级管理员审核。', 'Payment submitted. Waiting for super-admin review.')
    await refresh()
  } catch (e: any) {
    error.value = apiError(e, '提交付款失败', 'Failed to submit payment')
  } finally {
    paymentSubmitting.value = false
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

function supportMailto(bookingId?: number) {
  const subject = bookingId
    ? `Road Test booking #${bookingId} payment support`
    : 'Road Test booking support'
  return `mailto:${SUPPORT_EMAIL}?subject=${encodeURIComponent(subject)}`
}

function badgeClass(s: Booking['status']) {
  return {
    pending: 'badge-pending',
    running: 'badge-running',
    done: 'badge-done',
    failed: 'badge-failed',
    cancelled: 'badge-cancelled',
    awaiting_payment: 'badge-pending',
    awaiting_review: 'badge-pending',
    payment_rejected: 'badge-failed',
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
      <p class="text-sm font-medium text-blue-700">
        {{ tr(`可用执行次数：${availableCredits}`, `Available execution passes: ${availableCredits}`) }}
      </p>
      <p class="text-sm text-slate-600">
        {{ tr('抢号参数来自「设置」页的档案（考点 / 日期 / 时间 / 偏好）。请先在设置页填好档案与 keyword，再创建任务。', 'Booking parameters come from Settings (location, dates, times, and preferences). Complete your profile and keyword before creating a booking.') }}
      </p>
      <button class="btn-primary" @click="onCreate">{{ tr('创建任务', 'Create booking') }}</button>
    </div>

    <div v-if="paymentBooking" class="card border-amber-200 bg-amber-50 space-y-3">
      <h2 class="text-lg font-semibold text-amber-900">{{ tr('付款后提交审核', 'Payment required') }}</h2>
      <p class="text-sm text-amber-800">
        {{ tr('请使用下方任一种方式完成任务付款。付款完成后提交付款凭证，管理员确认后会发放一次可执行权限。', 'Pay for this execution using one of the methods below. Submit your payment reference afterward; approval grants one execution pass.') }}
      </p>
      <p class="text-sm text-amber-800">
        {{ tr('付款或审核遇到问题？请联系', 'Questions about payment or review? Contact') }}
        <a class="font-semibold underline" :href="supportMailto(paymentBooking.id)">{{ SUPPORT_EMAIL }}</a>
        {{ tr(`，并注明注册邮箱和任务编号 #${paymentBooking.id}。`, ` and include your registered email and booking #${paymentBooking.id}.`) }}
      </p>
      <div class="grid gap-4 sm:grid-cols-2">
        <div class="flex flex-col items-center gap-2 rounded-lg bg-white p-3">
          <img :src="WECHAT_QR" alt="WeChat Pay" class="w-full max-w-xs rounded-lg border border-slate-200" />
          <span class="text-sm text-slate-600">{{ tr('微信付款', 'WeChat Pay') }}</span>
        </div>
        <div class="flex flex-col items-center gap-2 rounded-lg bg-white p-3">
          <img :src="ALIPAY_QR" alt="Alipay" class="w-full max-w-xs rounded-lg border border-slate-200" />
          <span class="text-sm text-slate-600">{{ tr('支付宝付款', 'Alipay') }}</span>
        </div>
      </div>
      <input
        v-model="paymentReference"
        class="input"
        required
        :placeholder="tr('付款凭证号或备注（必填）', 'Payment reference or note (required)')"
      />
      <button class="btn-primary" :disabled="paymentSubmitting || !paymentReferenceValid" @click="onSubmitPayment(paymentBooking)">
        {{ paymentSubmitting ? tr('提交中…', 'Submitting…') : tr('我已付款，提交审核', 'I have paid — submit for review') }}
      </button>
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
                v-if="b.status === 'awaiting_payment'"
                class="text-blue-600 hover:underline mr-3"
                @click="onSubmitPayment(b)"
              >
                {{ tr('我已付款', 'I have paid') }}
              </button>
              <span v-if="b.status === 'awaiting_review'" class="text-amber-700 mr-3">
                {{ tr('待管理员审核，审核完成后可取消', 'Awaiting admin review; cancellation is available after review') }}
              </span>
              <span v-if="b.status === 'payment_rejected'" class="text-red-600 mr-3" :title="b.review_reason || ''">
                {{ b.review_reason || tr('付款被拒绝', 'Payment rejected') }}
              </span>
              <button
                v-if="['awaiting_payment', 'pending', 'running', 'payment_rejected'].includes(b.status)"
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
