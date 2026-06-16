<script setup lang="ts">
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'

const email = ref('')
const password = ref('')
const error = ref('')
const loading = ref(false)
const auth = useAuthStore()
const router = useRouter()

async function onSubmit() {
  error.value = ''
  loading.value = true
  try {
    await auth.login(email.value, password.value)
    router.push('/dashboard')
  } catch (e: any) {
    if (e.response?.status === 403) {
      if (confirm('邮箱未验证，是否前往验证？')) {
        router.push({ name: 'verify', query: { email: email.value } })
      }
    } else {
      error.value = e.response?.data?.detail || '登录失败'
    }
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <div class="max-w-md mx-auto mt-20">
    <div class="card">
      <h1 class="text-2xl font-bold mb-6 text-center">登录</h1>
      <form @submit.prevent="onSubmit" class="space-y-4">
        <div>
          <label class="label">邮箱</label>
          <input v-model="email" type="email" required class="input" autocomplete="email" />
        </div>
        <div>
          <label class="label">密码</label>
          <input v-model="password" type="password" required class="input" autocomplete="current-password" />
        </div>
        <p v-if="error" class="text-sm text-red-600">{{ error }}</p>
        <button type="submit" class="btn-primary w-full" :disabled="loading">
          {{ loading ? '登录中…' : '登录' }}
        </button>
        <p class="text-sm text-center text-slate-600">
          还没有账号？<RouterLink to="/register" class="text-blue-600 hover:underline">注册</RouterLink>
        </p>
      </form>
    </div>
  </div>
</template>
