<script setup lang="ts">
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import { useI18n } from '@/i18n'

const email = ref('')
const password = ref('')
const error = ref('')
const loading = ref(false)
const auth = useAuthStore()
const router = useRouter()
const { tr, apiError } = useI18n()

async function onSubmit() {
  error.value = ''
  loading.value = true
  try {
    await auth.login(email.value, password.value)
    router.push(auth.user?.is_admin ? '/admin' : '/dashboard')
  } catch (e: any) {
    if (e.response?.status === 403) {
      if (confirm(tr('邮箱未验证，是否前往验证？', 'Email is not verified. Go to verification?'))) {
        router.push({ name: 'verify', query: { email: email.value } })
      }
    } else {
      error.value = apiError(e, '登录失败', 'Login failed')
    }
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <div class="max-w-md mx-auto mt-20">
    <div class="card">
      <h1 class="text-2xl font-bold mb-6 text-center">{{ tr('登录', 'Log in') }}</h1>
      <form @submit.prevent="onSubmit" class="space-y-4">
        <div>
          <label class="label">{{ tr('邮箱', 'Email') }}</label>
          <input v-model="email" type="email" required class="input" autocomplete="email" />
        </div>
        <div>
          <label class="label">{{ tr('密码', 'Password') }}</label>
          <input v-model="password" type="password" required class="input" autocomplete="current-password" />
        </div>
        <p v-if="error" class="text-sm text-red-600">{{ error }}</p>
        <button type="submit" class="btn-primary w-full" :disabled="loading">
          {{ loading ? tr('登录中…', 'Logging in…') : tr('登录', 'Log in') }}
        </button>
        <p class="text-sm text-center text-slate-600">
          {{ tr('还没有账号？', "Don't have an account? ") }}<RouterLink to="/register" class="text-blue-600 hover:underline">{{ tr('注册', 'Register') }}</RouterLink>
        </p>
      </form>
    </div>
  </div>
</template>
