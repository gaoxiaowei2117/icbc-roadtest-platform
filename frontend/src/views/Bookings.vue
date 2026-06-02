<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { cancelBooking, createBooking, listBookings, type Booking } from '@/api/bookings'

const bookings = ref<Booking[]>([])
const error = ref('')
const message = ref('')
const loading = ref(false)

const form = ref({
  target_date: '',
  pos_code: '',
  morning: true,
  afternoon: true,
  evening: false,
})

async function refresh() {
  loading.value = true
  try {
    bookings.value = await listBookings()
  } catch (e: any) {
    error.value = e.response?.data?.detail || '加载失败'
  } finally {
    loading.value = false
  }
}

async function onCreate() {
  error.value = ''
  message.value = ''
  try {
    const payload: any = {}
    if (form.value.target_date) payload.target_date = form.value.target_date
    if (form.value.pos_code) payload.pos_code = form.value.pos_code
    payload.time_window = {
      morning: form.value.morning,
      afternoon: form.value.afternoon,
      evening: form.value.evening,
    }
    await createBooking(payload)
    message.value = '任务已创建，等待 worker 执行'
    await refresh()
  } catch (e: any) {
    error.value = e.response?.data?.detail || '创建失败'
  }
}

async function onCancel(b: Booking) {
  if (!confirm(`确定取消任务 #${b.id}？`)) return
  try {
    await cancelBooking(b.id)
    await refresh()
  } catch (e: any) {
    error.value = e.response?.data?.detail || '取消失败'
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

onMounted(refresh)
</script>

<template>
  <div class="space-y-6">
    <h1 class="text-2xl font-bold">抢约任务</h1>

    <div class="card space-y-4">
      <h2 class="text-lg font-semibold">新建任务</h2>
      <div class="grid grid-cols-3 gap-4">
        <div>
          <label class="label">期望日期（可空）</label>
          <input v-model="form.target_date" type="date" class="input" />
        </div>
        <div>
          <label class="label">考点代码（可空，用首选）</label>
          <input v-model="form.pos_code" class="input" />
        </div>
        <div>
          <label class="label">时间段</label>
          <div class="flex gap-3 text-sm pt-2">
            <label class="flex items-center gap-1">
              <input type="checkbox" v-model="form.morning" />上午
            </label>
            <label class="flex items-center gap-1">
              <input type="checkbox" v-model="form.afternoon" />下午
            </label>
            <label class="flex items-center gap-1">
              <input type="checkbox" v-model="form.evening" />傍晚
            </label>
          </div>
        </div>
      </div>
      <button class="btn-primary" @click="onCreate">创建任务</button>
    </div>

    <p v-if="message" class="text-sm text-green-600">{{ message }}</p>
    <p v-if="error" class="text-sm text-red-600">{{ error }}</p>

    <div class="card">
      <div class="flex items-center justify-between mb-4">
        <h2 class="text-lg font-semibold">我的任务</h2>
        <button class="btn-secondary" @click="refresh" :disabled="loading">刷新</button>
      </div>
      <div v-if="!bookings.length" class="text-sm text-slate-500 text-center py-8">暂无任务</div>
      <table v-else class="w-full text-sm">
        <thead class="text-left text-slate-500 border-b">
          <tr>
            <th class="py-2">#</th>
            <th>状态</th>
            <th>目标日期</th>
            <th>考点</th>
            <th>尝试</th>
            <th>最后错误</th>
            <th>创建</th>
            <th></th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="b in bookings" :key="b.id" class="border-b last:border-0">
            <td class="py-2">{{ b.id }}</td>
            <td><span :class="badgeClass(b.status)">{{ b.status }}</span></td>
            <td>{{ b.target_date || '任意' }}</td>
            <td>{{ b.pos_code || '首选' }}</td>
            <td>{{ b.attempt_count }}</td>
            <td class="text-red-600 text-xs truncate max-w-xs">{{ b.last_error || '—' }}</td>
            <td>{{ new Date(b.created_at).toLocaleString() }}</td>
            <td>
              <button
                v-if="b.status === 'pending' || b.status === 'running'"
                class="text-red-600 hover:underline"
                @click="onCancel(b)"
              >
                取消
              </button>
            </td>
          </tr>
        </tbody>
      </table>
    </div>
  </div>
</template>
