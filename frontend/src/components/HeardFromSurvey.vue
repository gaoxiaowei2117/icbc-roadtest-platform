<script setup lang="ts">
// One-tap "how did you hear about us?" shown after a successful purchase. Asked once per
// account (the answer is stored on the user); "skip" hides it in this browser.
import { computed, ref } from 'vue'
import { setHeardFrom } from '@/api/users'
import { useAuthStore } from '@/stores/auth'
import { useI18n } from '@/i18n'
import { HEARD_FROM, type HeardFrom } from '@/sources'

const SKIP_KEY = 'rtg.heard_from_skipped'
const auth = useAuthStore()
const { tr, apiError } = useI18n()

const skipped = ref(readSkipped())
const thanks = ref(false)
const saving = ref(false)
const error = ref('')
const otherOpen = ref(false)
const otherText = ref('')

const visible = computed(() => thanks.value || (!!auth.user && !auth.user.heard_from && !skipped.value))

function readSkipped(): boolean {
  try { return localStorage.getItem(SKIP_KEY) === '1' } catch { return false }
}

function skip() {
  skipped.value = true
  try { localStorage.setItem(SKIP_KEY, '1') } catch { /* storage blocked */ }
}

async function answer(value: HeardFrom, detail?: string) {
  saving.value = true
  error.value = ''
  try {
    auth.user = await setHeardFrom(value, detail)
    thanks.value = true
  } catch (e: any) {
    error.value = apiError(e, '提交失败，请再试一次', 'Could not save. Please try again.')
  } finally {
    saving.value = false
  }
}

function choose(value: HeardFrom) {
  if (value === 'other') otherOpen.value = true
  else answer(value)
}
</script>

<template>
  <div v-if="visible" class="rounded-md border border-slate-200 bg-white px-4 py-3">
    <p v-if="thanks" class="text-sm text-slate-700">{{ tr('谢谢你的反馈！', 'Thanks for telling us!', 'Merci !', '¡Gracias!', '謝謝你的回饋！') }}</p>
    <template v-else>
      <div class="flex items-start justify-between gap-3">
        <p class="text-sm font-medium text-slate-800">{{ tr(
          '最后一个小问题：你是从哪里知道我们的？',
          'One quick question: how did you hear about us?',
          'Une petite question : comment nous avez-vous connus ?',
          'Una pregunta rápida: ¿cómo nos conociste?',
          '最後一個小問題：你是從哪裡知道我們的？',
        ) }}</p>
        <button type="button" class="shrink-0 text-xs text-slate-500 hover:underline" @click="skip">{{ tr('跳过', 'Skip', 'Passer', 'Omitir', '略過') }}</button>
      </div>
      <div class="mt-2 flex flex-wrap gap-2">
        <button
          v-for="opt in HEARD_FROM" :key="opt.value" type="button" :disabled="saving"
          class="rounded-full border px-3 py-1.5 text-sm hover:bg-slate-50 disabled:opacity-50"
          :class="otherOpen && opt.value === 'other' ? 'border-blue-500 text-blue-700' : 'border-slate-300 text-slate-700'"
          @click="choose(opt.value)"
        >{{ tr(opt.zh, opt.en, undefined, undefined, opt.zhHant) }}</button>
      </div>
      <form v-if="otherOpen" class="mt-2 flex gap-2" @submit.prevent="answer('other', otherText)">
        <input v-model="otherText" maxlength="200" class="input flex-1"
               :placeholder="tr('比如：Facebook 群、驾校传单…', 'e.g. a Facebook group, a flyer…', undefined, undefined, '比如：Facebook 群、駕校傳單…')" />
        <button type="submit" class="btn-primary" :disabled="saving">{{ tr('提交', 'Send', 'Envoyer', 'Enviar', '送出') }}</button>
      </form>
      <p v-if="error" class="mt-2 text-sm text-red-600">{{ error }}</p>
    </template>
  </div>
</template>
