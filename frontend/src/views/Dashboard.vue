<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useAuthStore } from '@/stores/auth'
import { getSecretStatus } from '@/api/users'

const auth = useAuthStore()
const hasSecret = ref(false)
const secretUpdatedAt = ref<string | null>(null)

onMounted(async () => {
  try {
    const s = await getSecretStatus()
    hasSecret.value = s.has_secret
    secretUpdatedAt.value = s.updated_at
  } catch (e) {
    /* ignore */
  }
})
</script>

<template>
  <div class="space-y-6">
    <h1 class="text-2xl font-bold">我的资料</h1>
    <div class="card">
      <h2 class="text-lg font-semibold mb-4">账号信息</h2>
      <dl class="grid grid-cols-2 gap-3 text-sm">
        <dt class="text-slate-500">邮箱</dt><dd>{{ auth.user?.email }}</dd>
        <dt class="text-slate-500">角色</dt>
        <dd>
          <span v-if="auth.user?.is_admin" class="badge bg-purple-100 text-purple-800">admin</span>
          <span v-else class="badge bg-slate-100 text-slate-800">普通用户</span>
        </dd>
        <dt class="text-slate-500">注册时间</dt>
        <dd>{{ auth.user?.created_at ? new Date(auth.user.created_at).toLocaleString() : '—' }}</dd>
      </dl>
    </div>

    <div class="card">
      <h2 class="text-lg font-semibold mb-4">ICBC 资料</h2>
      <dl class="grid grid-cols-2 gap-3 text-sm">
        <dt class="text-slate-500">驾照号</dt>
        <dd>{{ auth.user?.icbc_license_no || '— 未填写' }}</dd>
        <dt class="text-slate-500">姓氏</dt>
        <dd>{{ auth.user?.icbc_last_name || '— 未填写' }}</dd>
        <dt class="text-slate-500">首选考点</dt>
        <dd>
          <span v-if="auth.user?.preferred_pos?.length">{{ auth.user.preferred_pos.join('、') }}</span>
          <span v-else>— 未设置</span>
        </dd>
        <dt class="text-slate-500">可接受等待天数</dt>
        <dd>{{ auth.user?.max_wait_days }} 天</dd>
      </dl>
      <RouterLink to="/settings" class="btn-primary inline-block mt-4">编辑资料 / 修改凭据</RouterLink>
    </div>

    <div class="card">
      <h2 class="text-lg font-semibold mb-4">ICBC 登录凭据</h2>
      <p v-if="hasSecret" class="text-sm text-green-700">
        ✓ 已配置
        <span v-if="secretUpdatedAt" class="text-slate-500">
          （更新于 {{ new Date(secretUpdatedAt).toLocaleString() }}）
        </span>
      </p>
      <p v-else class="text-sm text-red-600">✗ 未配置，无法启动抢约</p>
      <RouterLink to="/settings" class="btn-secondary inline-block mt-4">管理凭据</RouterLink>
    </div>
  </div>
</template>
