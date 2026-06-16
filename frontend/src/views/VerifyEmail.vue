<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'

const route = useRoute()
const router = useRouter()
const auth = useAuthStore()

const email = ref((route.query.email as string) || '')
const code = ref('')
const cooldown = ref(0)
let timer: number | undefined

async function onVerify() {
  if (!/^[0-9]{6}$/.test(code.value)) {
    alert('请输入 6 位验证码')
    return
  }
  try {
    await auth.verifyEmail(email.value, code.value)
    alert('验证成功')
    router.push('/dashboard')
  } catch (e: any) {
    alert('验证失败：' + (e.response?.data?.detail || '未知错误'))
  }
}

function startCooldown() {
  cooldown.value = 60
  timer = window.setInterval(() => {
    cooldown.value -= 1
    if (cooldown.value <= 0 && timer) window.clearInterval(timer)
  }, 1000)
}

async function onResend() {
  try {
    await auth.resendCode(email.value)
    alert('验证码已重新发送')
    startCooldown()
  } catch (e: any) {
    alert('发送失败：' + (e.response?.data?.detail || '未知错误'))
  }
}

onMounted(() => { if (email.value) startCooldown() })
</script>

<template>
  <div class="max-w-md mx-auto mt-20">
    <div class="card space-y-4">
      <h1 class="text-2xl font-bold text-center">验证邮箱</h1>
      <p class="text-sm text-slate-600 text-center">验证码已发送到 {{ email }}，10 分钟内有效。</p>
      <div>
        <label class="label">邮箱</label>
        <input v-model="email" type="email" class="input" />
      </div>
      <div>
        <label class="label">6 位验证码</label>
        <input v-model="code" maxlength="6" class="input" />
      </div>
      <button class="btn-primary w-full" @click="onVerify">验证</button>
      <button class="btn-secondary w-full" :disabled="cooldown > 0" @click="onResend">
        {{ cooldown > 0 ? `重发（${cooldown}s）` : '重发验证码' }}
      </button>
      <p class="text-sm text-center text-slate-600">
        <RouterLink to="/login" class="text-blue-600 hover:underline">返回登录</RouterLink>
      </p>
    </div>
  </div>
</template>
