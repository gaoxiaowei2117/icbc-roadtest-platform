<script setup lang="ts">
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'

const email = ref('')
const password = ref('')
const confirm = ref('')
const error = ref('')
const loading = ref(false)
const auth = useAuthStore()
const router = useRouter()

async function onSubmit() {
  error.value = ''
  if (password.value !== confirm.value) {
    error.value = '两次密码不一致'
    return
  }
  if (password.value.length < 8) {
    error.value = '密码至少 8 位'
    return
  }
  loading.value = true
  try {
    await auth.register(email.value, password.value)
    router.push('/dashboard')
  } catch (e: any) {
    error.value = e.response?.data?.detail || '注册失败'
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <div class="max-w-md mx-auto mt-20">
    <div class="card">
      <h1 class="text-2xl font-bold mb-6 text-center">注册</h1>
      <form @submit.prevent="onSubmit" class="space-y-4">
        <div>
          <label class="label">邮箱</label>
          <input v-model="email" type="email" required class="input" />
        </div>
        <div>
          <label class="label">密码（至少 8 位）</label>
          <input v-model="password" type="password" required minlength="8" class="input" />
        </div>
        <div>
          <label class="label">确认密码</label>
          <input v-model="confirm" type="password" required minlength="8" class="input" />
        </div>
        <p v-if="error" class="text-sm text-red-600">{{ error }}</p>
        <button type="submit" class="btn-primary w-full" :disabled="loading">
          {{ loading ? '注册中…' : '注册' }}
        </button>
        <p class="text-sm text-center text-slate-600">
          已有账号？<RouterLink to="/login" class="text-blue-600 hover:underline">登录</RouterLink>
        </p>
      </form>
    </div>
  </div>
</template>
