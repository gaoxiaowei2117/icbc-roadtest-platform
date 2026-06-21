<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import { useI18n } from '@/i18n'

const route = useRoute()
const router = useRouter()
const auth = useAuthStore()
const { tr, apiError } = useI18n()

const email = ref((route.query.email as string) || '')
const code = ref('')
const cooldown = ref(0)
let timer: number | undefined

async function onVerify() {
  if (!/^[0-9]{6}$/.test(code.value)) {
    alert(tr('请输入 6 位验证码', 'Enter the 6-digit verification code'))
    return
  }
  try {
    await auth.verifyEmail(email.value, code.value)
    alert(tr('验证成功', 'Email verified'))
    router.push('/dashboard')
  } catch (e: any) {
    alert(tr('验证失败：', 'Verification failed: ') + apiError(e, '未知错误', 'Unknown error'))
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
    alert(tr('验证码已重新发送', 'Verification code resent'))
    startCooldown()
  } catch (e: any) {
    alert(tr('发送失败：', 'Send failed: ') + apiError(e, '未知错误', 'Unknown error'))
  }
}

onMounted(() => { if (email.value) startCooldown() })
</script>

<template>
  <div class="max-w-md mx-auto mt-20">
    <div class="card space-y-4">
      <h1 class="text-2xl font-bold text-center">{{ tr('验证邮箱', 'Verify email') }}</h1>
      <p class="text-sm text-slate-600 text-center">{{ tr(
        `验证码已发送到 ${email}，10 分钟内有效。`,
        `A verification code was sent to ${email}. It is valid for 10 minutes.`,
        `Un code de vérification a été envoyé à ${email}. Il est valide pendant 10 minutes.`,
        `Se envió un código de verificación a ${email}. Es válido durante 10 minutos.`,
        `驗證碼已發送到 ${email}，10 分鐘內有效。`,
      ) }}</p>
      <div>
        <label class="label">{{ tr('邮箱', 'Email') }}</label>
        <input v-model="email" type="email" class="input" />
      </div>
      <div>
        <label class="label">{{ tr('6 位验证码', '6-digit verification code') }}</label>
        <input v-model="code" maxlength="6" class="input" />
      </div>
      <button class="btn-primary w-full" @click="onVerify">{{ tr('验证', 'Verify') }}</button>
      <button class="btn-secondary w-full" :disabled="cooldown > 0" @click="onResend">
        {{ cooldown > 0 ? tr(`重发（${cooldown}s）`, `Resend (${cooldown}s)`, `Renvoyer (${cooldown}s)`, `Reenviar (${cooldown}s)`, `重新發送（${cooldown}s）`) : tr('重发验证码', 'Resend code') }}
      </button>
      <p class="text-sm text-center text-slate-600">
        <RouterLink to="/login" class="text-blue-600 hover:underline">{{ tr('返回登录', 'Back to login') }}</RouterLink>
      </p>
    </div>
  </div>
</template>
