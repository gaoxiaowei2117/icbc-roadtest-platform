<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { useAuthStore } from '@/stores/auth'
import { deleteSecret, getSecretStatus, setSecret, updateMe } from '@/api/users'

const auth = useAuthStore()
const message = ref('')
const error = ref('')

const profile = reactive({
  icbc_license_no: '',
  icbc_last_name: '',
  preferred_pos: '',
  time_windows_morning: true,
  time_windows_afternoon: true,
  time_windows_evening: false,
  max_wait_days: 60,
})

const secret = reactive({
  icbc_username: '',
  icbc_password: '',
})
const hasSecret = ref(false)

onMounted(async () => {
  if (auth.user) {
    profile.icbc_license_no = auth.user.icbc_license_no || ''
    profile.icbc_last_name = auth.user.icbc_last_name || ''
    profile.preferred_pos = (auth.user.preferred_pos || []).join(',')
    profile.max_wait_days = auth.user.max_wait_days
    if (auth.user.time_windows) {
      profile.time_windows_morning = !!auth.user.time_windows.morning
      profile.time_windows_afternoon = !!auth.user.time_windows.afternoon
      profile.time_windows_evening = !!auth.user.time_windows.evening
    }
  }
  const s = await getSecretStatus()
  hasSecret.value = s.has_secret
})

async function saveProfile() {
  error.value = ''
  message.value = ''
  try {
    const pos = profile.preferred_pos
      .split(/[,,]/)
      .map((s) => s.trim())
      .filter(Boolean)
    const updated = await updateMe({
      icbc_license_no: profile.icbc_license_no || null,
      icbc_last_name: profile.icbc_last_name || null,
      preferred_pos: pos.length ? pos : null,
      time_windows: {
        morning: profile.time_windows_morning,
        afternoon: profile.time_windows_afternoon,
        evening: profile.time_windows_evening,
      },
      max_wait_days: profile.max_wait_days,
    })
    auth.user = updated
    message.value = '资料已保存'
  } catch (e: any) {
    error.value = e.response?.data?.detail || '保存失败'
  }
}

async function saveSecret() {
  error.value = ''
  message.value = ''
  try {
    await setSecret(secret)
    secret.icbc_password = ''
    hasSecret.value = true
    message.value = '凭据已加密保存'
  } catch (e: any) {
    error.value = e.response?.data?.detail || '保存失败'
  }
}

async function removeSecret() {
  if (!confirm('确定要删除 ICBC 凭据吗？删除后无法启动抢约。')) return
  await deleteSecret()
  hasSecret.value = false
  message.value = '凭据已删除'
}
</script>

<template>
  <div class="space-y-6">
    <h1 class="text-2xl font-bold">设置</h1>

    <div class="card space-y-4">
      <h2 class="text-lg font-semibold">ICBC 资料</h2>
      <div class="grid grid-cols-2 gap-4">
        <div>
          <label class="label">驾照号</label>
          <input v-model="profile.icbc_license_no" class="input" />
        </div>
        <div>
          <label class="label">姓氏（Last Name）</label>
          <input v-model="profile.icbc_last_name" class="input" />
        </div>
        <div class="col-span-2">
          <label class="label">首选考点（多个用英文逗号分隔，如：Vancouver, Burnaby）</label>
          <input v-model="profile.preferred_pos" class="input" />
        </div>
        <div class="col-span-2">
          <label class="label">可接受时间段</label>
          <div class="flex gap-4 text-sm">
            <label class="flex items-center gap-2">
              <input type="checkbox" v-model="profile.time_windows_morning" />上午
            </label>
            <label class="flex items-center gap-2">
              <input type="checkbox" v-model="profile.time_windows_afternoon" />下午
            </label>
            <label class="flex items-center gap-2">
              <input type="checkbox" v-model="profile.time_windows_evening" />傍晚
            </label>
          </div>
        </div>
        <div>
          <label class="label">最长等待天数</label>
          <input v-model.number="profile.max_wait_days" type="number" min="1" max="365" class="input" />
        </div>
      </div>
      <button class="btn-primary" @click="saveProfile">保存资料</button>
    </div>

    <div class="card space-y-4">
      <h2 class="text-lg font-semibold">ICBC 登录凭据</h2>
      <p class="text-sm text-slate-600">
        凭据会用 Fernet（AES-128）加密后保存，密钥只存本地 worker 的环境变量，云端无法解密。
      </p>
      <div v-if="hasSecret" class="text-sm text-green-700">✓ 已配置</div>
      <div class="grid grid-cols-2 gap-4">
        <div>
          <label class="label">ICBC 用户名</label>
          <input v-model="secret.icbc_username" class="input" />
        </div>
        <div>
          <label class="label">ICBC 密码</label>
          <input v-model="secret.icbc_password" type="password" class="input" />
        </div>
      </div>
      <div class="flex gap-2">
        <button class="btn-primary" @click="saveSecret">{{ hasSecret ? '更新' : '保存' }}凭据</button>
        <button v-if="hasSecret" class="btn-danger" @click="removeSecret">删除</button>
      </div>
    </div>

    <p v-if="message" class="text-sm text-green-600">{{ message }}</p>
    <p v-if="error" class="text-sm text-red-600">{{ error }}</p>
  </div>
</template>
