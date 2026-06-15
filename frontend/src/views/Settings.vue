<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { useAuthStore } from '@/stores/auth'
import { deleteSecret, getSecretStatus, setSecret, updateMe } from '@/api/users'
import { getPosList, type PosEntry } from '@/api/pos'

const auth = useAuthStore()
const message = ref('')
const error = ref('')
const posList = ref<PosEntry[]>([])

const WEEK = [
  { v: 0, label: '周一' }, { v: 1, label: '周二' }, { v: 2, label: '周三' },
  { v: 3, label: '周四' }, { v: 4, label: '周五' }, { v: 5, label: '周六' }, { v: 6, label: '周日' },
]

const profile = reactive({
  icbc_license_no: '',
  icbc_last_name: '',
  exam_class: '5',
  pos_ids: [] as number[],
  expect_after_date: '',
  expect_before_date: '',
  expect_time_range: '09:00-17:00',
  pref_days_of_week: [0, 1, 2, 3, 4, 5, 6] as number[],
  pref_parts_of_day: [0, 1] as number[],
})

const secret = reactive({ keyword: '' })
const hasSecret = ref(false)

onMounted(async () => {
  posList.value = await getPosList()
  if (auth.user) {
    profile.icbc_license_no = auth.user.icbc_license_no || ''
    profile.icbc_last_name = auth.user.icbc_last_name || ''
    profile.exam_class = auth.user.exam_class || '5'
    profile.pos_ids = auth.user.pos_ids || []
    profile.expect_after_date = auth.user.expect_after_date || ''
    profile.expect_before_date = auth.user.expect_before_date || ''
    profile.expect_time_range = auth.user.expect_time_range || '09:00-17:00'
    profile.pref_days_of_week = auth.user.pref_days_of_week || [0, 1, 2, 3, 4, 5, 6]
    profile.pref_parts_of_day = auth.user.pref_parts_of_day || [0, 1]
  }
  const s = await getSecretStatus()
  hasSecret.value = s.has_secret
})

async function saveProfile() {
  error.value = ''
  message.value = ''
  try {
    const updated = await updateMe({
      icbc_license_no: profile.icbc_license_no || null,
      icbc_last_name: profile.icbc_last_name || null,
      exam_class: profile.exam_class || null,
      pos_ids: profile.pos_ids.length ? profile.pos_ids : null,
      expect_after_date: profile.expect_after_date || null,
      expect_before_date: profile.expect_before_date || null,
      expect_time_range: profile.expect_time_range || null,
      pref_days_of_week: profile.pref_days_of_week,
      pref_parts_of_day: profile.pref_parts_of_day,
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
    await setSecret({ keyword: secret.keyword })
    secret.keyword = ''
    hasSecret.value = true
    message.value = 'keyword 已加密保存'
  } catch (e: any) {
    error.value = e.response?.data?.detail || '保存失败'
  }
}

async function removeSecret() {
  if (!confirm('确定要删除 ICBC keyword 吗？删除后无法启动抢约。')) return
  await deleteSecret()
  hasSecret.value = false
  message.value = 'keyword 已删除'
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
        <div>
          <label class="label">考试类型（examClass，如 5=5 类车）</label>
          <input v-model="profile.exam_class" class="input" />
        </div>
        <div>
          <label class="label">时间区间（HH:MM-HH:MM）</label>
          <input v-model="profile.expect_time_range" class="input" placeholder="09:00-17:00" />
        </div>
        <div>
          <label class="label">期望最早日期</label>
          <input v-model="profile.expect_after_date" type="date" class="input" />
        </div>
        <div>
          <label class="label">期望最晚日期</label>
          <input v-model="profile.expect_before_date" type="date" class="input" />
        </div>
        <div class="col-span-2">
          <label class="label">考点（可多选）</label>
          <select v-model="profile.pos_ids" multiple class="input h-40">
            <option v-for="p in posList" :key="p.pos_id" :value="p.pos_id">{{ p.name }}</option>
          </select>
        </div>
        <div class="col-span-2">
          <label class="label">星期偏好</label>
          <div class="flex flex-wrap gap-3 text-sm">
            <label v-for="d in WEEK" :key="d.v" class="flex items-center gap-1">
              <input type="checkbox" :value="d.v" v-model="profile.pref_days_of_week" />{{ d.label }}
            </label>
          </div>
        </div>
        <div class="col-span-2">
          <label class="label">时段偏好</label>
          <div class="flex gap-4 text-sm">
            <label class="flex items-center gap-1">
              <input type="checkbox" :value="0" v-model="profile.pref_parts_of_day" />上午
            </label>
            <label class="flex items-center gap-1">
              <input type="checkbox" :value="1" v-model="profile.pref_parts_of_day" />下午
            </label>
          </div>
        </div>
      </div>
      <button class="btn-primary" @click="saveProfile">保存资料</button>
    </div>

    <div class="card space-y-4">
      <h2 class="text-lg font-semibold">ICBC 登录 keyword</h2>
      <p class="text-sm text-slate-600">
        ICBC 登录用 姓氏 + 驾照号 + keyword。keyword 用非对称加密保存，私钥只在本地 worker，云端无法解密。
      </p>
      <div v-if="hasSecret" class="text-sm text-green-700">✓ 已配置</div>
      <div>
        <label class="label">keyword</label>
        <input v-model="secret.keyword" type="password" class="input" />
      </div>
      <div class="flex gap-2">
        <button class="btn-primary" @click="saveSecret">{{ hasSecret ? '更新' : '保存' }} keyword</button>
        <button v-if="hasSecret" class="btn-danger" @click="removeSecret">删除</button>
      </div>
    </div>

    <p v-if="message" class="text-sm text-green-600">{{ message }}</p>
    <p v-if="error" class="text-sm text-red-600">{{ error }}</p>
  </div>
</template>
