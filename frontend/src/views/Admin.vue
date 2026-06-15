<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { api } from '@/api/client'
import type { Booking } from '@/api/bookings'

const bookings = ref<Booking[]>([])
const statusFilter = ref<string>('')
const error = ref('')

async function refresh() {
  try {
    const params: Record<string, string> = { limit: '200' }
    if (statusFilter.value) params.status_filter = statusFilter.value
    const r = await api.get('/api/admin/bookings', { params })
    bookings.value = r.data
  } catch (e: any) {
    error.value = e.response?.data?.detail || '加载失败'
  }
}

onMounted(refresh)
</script>

<template>
  <div class="space-y-6">
    <h1 class="text-2xl font-bold">Admin · 全部任务</h1>
    <div class="card">
      <div class="flex items-center gap-3 mb-4">
        <label class="text-sm">状态筛选：</label>
        <select v-model="statusFilter" class="input max-w-xs" @change="refresh">
          <option value="">全部</option>
          <option value="pending">pending</option>
          <option value="running">running</option>
          <option value="done">done</option>
          <option value="failed">failed</option>
          <option value="cancelled">cancelled</option>
        </select>
      </div>
      <p v-if="error" class="text-sm text-red-600">{{ error }}</p>
      <div v-if="!bookings.length" class="text-sm text-slate-500 text-center py-8">暂无</div>
      <table v-else class="w-full text-sm">
        <thead class="text-left text-slate-500 border-b">
          <tr>
            <th class="py-2">#</th>
            <th>user</th>
            <th>状态</th>
            <th>尝试</th>
            <th>最后错误</th>
            <th>创建</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="b in bookings" :key="b.id" class="border-b last:border-0">
            <td class="py-2">{{ b.id }}</td>
            <td>{{ b.user_id }}</td>
            <td>{{ b.status }}</td>
            <td>{{ b.attempt_count }}</td>
            <td class="text-red-600 text-xs truncate max-w-xs">{{ b.last_error || '—' }}</td>
            <td>{{ new Date(b.created_at).toLocaleString() }}</td>
          </tr>
        </tbody>
      </table>
    </div>
  </div>
</template>
