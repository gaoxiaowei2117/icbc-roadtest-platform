<script setup lang="ts">
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import { useI18n } from '@/i18n'

const email = ref('')
const password = ref('')
const confirm = ref('')
const error = ref('')
const loading = ref(false)
const auth = useAuthStore()
const router = useRouter()
const { tr, apiError } = useI18n()

async function onSubmit() {
  error.value = ''
  if (password.value !== confirm.value) {
    error.value = tr('两次密码不一致', 'Passwords do not match')
    return
  }
  if (password.value.length < 8) {
    error.value = tr('密码至少 8 位', 'Password must be at least 8 characters')
    return
  }
  loading.value = true
  try {
    await auth.register(email.value, password.value)
    router.push({ name: 'verify', query: { email: email.value } })
  } catch (e: any) {
    error.value = apiError(e, '注册失败', 'Registration failed')
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <div class="max-w-md mx-auto mt-20">
    <div class="card">
      <h1 class="text-2xl font-bold mb-6 text-center">{{ tr('注册', 'Register') }}</h1>
      <form @submit.prevent="onSubmit" class="space-y-4">
        <div>
          <label class="label">{{ tr('邮箱', 'Email') }}</label>
          <input v-model="email" type="email" required class="input" />
        </div>
        <div>
          <label class="label">{{ tr('密码（至少 8 位）', 'Password (at least 8 characters)') }}</label>
          <input v-model="password" type="password" required minlength="8" class="input" />
        </div>
        <div>
          <label class="label">{{ tr('确认密码', 'Confirm password') }}</label>
          <input v-model="confirm" type="password" required minlength="8" class="input" />
        </div>
        <p v-if="error" class="text-sm text-red-600">{{ error }}</p>
        <button type="submit" class="btn-primary w-full" :disabled="loading">
          {{ loading ? tr('注册中…', 'Registering…') : tr('注册', 'Register') }}
        </button>
        <p class="text-sm text-center text-slate-600">
          {{ tr('已有账号？', 'Already have an account? ') }}<RouterLink to="/login" class="text-blue-600 hover:underline">{{ tr('登录', 'Log in') }}</RouterLink>
        </p>
      </form>
    </div>
  </div>
</template>
