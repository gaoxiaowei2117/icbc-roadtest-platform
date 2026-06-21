<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { useAuthStore } from '@/stores/auth'
import { deleteSecret, getSecretStatus, setSecret, updateMe } from '@/api/users'
import { getPosList, type PosEntry } from '@/api/pos'
import { useI18n } from '@/i18n'

const auth = useAuthStore()
const posList = ref<PosEntry[]>([])
const { tr, apiError } = useI18n()

const WEEK = [
  { v: 0, zh: '周一', en: 'Mon' }, { v: 1, zh: '周二', en: 'Tue' },
  { v: 2, zh: '周三', en: 'Wed' }, { v: 3, zh: '周四', en: 'Thu' },
  { v: 4, zh: '周五', en: 'Fri' }, { v: 5, zh: '周六', en: 'Sat' },
  { v: 6, zh: '周日', en: 'Sun' },
]

const profile = reactive({
  icbc_license_no: '',
  icbc_last_name: '',
  exam_class: '5',
  pos_id: null as number | null,
  expect_after_date: '',
  expect_before_date: '',
  time_start: '09:00',
  time_end: '17:00',
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
    profile.pos_id = (auth.user.pos_ids || [])[0] ?? null
    profile.expect_after_date = auth.user.expect_after_date || ''
    profile.expect_before_date = auth.user.expect_before_date || ''
    const [ts, te] = (auth.user.expect_time_range || '09:00-17:00').split('-')
    profile.time_start = ts || '09:00'
    profile.time_end = te || '17:00'
    profile.pref_days_of_week = auth.user.pref_days_of_week || [0, 1, 2, 3, 4, 5, 6]
    profile.pref_parts_of_day = auth.user.pref_parts_of_day || [0, 1]
  }
  const s = await getSecretStatus()
  hasSecret.value = s.has_secret
})

async function saveIcbcProfile() {
  try {
    const updated = await updateMe({
      icbc_license_no: profile.icbc_license_no || null,
      icbc_last_name: profile.icbc_last_name || null,
    })
    auth.user = updated
    if (secret.keyword) {
      await setSecret({ keyword: secret.keyword })
      secret.keyword = ''
      hasSecret.value = true
    }
    alert(tr('ICBC 资料已保存', 'ICBC profile saved'))
  } catch (e: any) {
    alert(tr('保存失败：', 'Save failed: ') + apiError(e, '未知错误', 'Unknown error'))
  }
}

async function saveBookingSettings() {
  if (profile.expect_after_date && profile.expect_before_date &&
      profile.expect_before_date < profile.expect_after_date) {
    alert(tr('结束日期不能早于开始日期', 'End date cannot be earlier than start date'))
    return
  }
  if (profile.time_start && profile.time_end && profile.time_end <= profile.time_start) {
    alert(tr('结束时间必须晚于开始时间', 'End time must be later than start time'))
    return
  }
  try {
    const updated = await updateMe({
      exam_class: profile.exam_class || null,
      pos_ids: profile.pos_id != null ? [profile.pos_id] : null,
      expect_after_date: profile.expect_after_date || null,
      expect_before_date: profile.expect_before_date || null,
      expect_time_range: `${profile.time_start}-${profile.time_end}`,
      pref_days_of_week: profile.pref_days_of_week,
      pref_parts_of_day: profile.pref_parts_of_day,
    })
    auth.user = updated
    alert(tr('预约设置已保存', 'Booking settings saved'))
  } catch (e: any) {
    alert(tr('保存失败：', 'Save failed: ') + apiError(e, '未知错误', 'Unknown error'))
  }
}

async function removeSecret() {
  if (!confirm(tr('确定要删除 ICBC keyword 吗？删除后无法启动抢约。', 'Delete the ICBC keyword? Booking cannot start without it.'))) return
  try {
    await deleteSecret()
    hasSecret.value = false
    alert(tr('keyword 已删除', 'Keyword deleted'))
  } catch (e: any) {
    alert(tr('删除失败：', 'Delete failed: ') + apiError(e, '未知错误', 'Unknown error'))
  }
}
</script>

<template>
  <div class="space-y-6">
    <h1 class="text-2xl font-bold">{{ tr('设置', 'Settings') }}</h1>

    <div class="card space-y-4">
      <h2 class="text-lg font-semibold">{{ tr('ICBC 资料', 'ICBC Profile') }}</h2>
      <p class="text-sm text-slate-600">
        {{ tr('ICBC 登录使用姓氏、驾照号和 keyword。keyword 使用非对称加密保存，云端无法解密。', 'ICBC login uses your last name, licence number, and keyword. The keyword is asymmetrically encrypted and cannot be decrypted by the server.') }}
      </p>
      <div class="grid md:grid-cols-2 gap-4">
        <div>
          <label class="label">{{ tr('驾照号', 'Licence number') }}</label>
          <input v-model="profile.icbc_license_no" class="input" />
        </div>
        <div>
          <label class="label">{{ tr('姓氏（Last Name）', 'Last name') }}</label>
          <input v-model="profile.icbc_last_name" class="input" />
        </div>
        <div class="md:col-span-2">
          <label class="label">keyword</label>
          <input
            v-model="secret.keyword"
            type="password"
            class="input"
            :placeholder="hasSecret ? tr('已配置；留空表示不修改', 'Configured; leave blank to keep it') : tr('请输入 keyword', 'Enter keyword')"
          />
          <p v-if="hasSecret" class="mt-2 text-sm text-green-700">{{ tr('已加密配置', 'Encrypted and configured') }}</p>
        </div>
      </div>
      <div class="flex gap-2">
        <button class="btn-primary" @click="saveIcbcProfile">{{ tr('保存 ICBC 资料', 'Save ICBC profile') }}</button>
        <button v-if="hasSecret" class="btn-danger" @click="removeSecret">{{ tr('删除 keyword', 'Delete keyword') }}</button>
      </div>
    </div>

    <div class="card space-y-4">
      <h2 class="text-lg font-semibold">{{ tr('预约设置', 'Booking Settings') }}</h2>
      <div class="grid md:grid-cols-2 gap-4">
        <div>
          <label class="label">{{ tr('考试类型（examClass，如 5=5 类车）', 'Exam class (for example, 5 = Class 5)') }}</label>
          <input v-model="profile.exam_class" class="input" />
        </div>
        <div>
          <label class="label">{{ tr('时间区间（开始 — 结束）', 'Time range (start — end)') }}</label>
          <div class="flex items-center gap-2">
            <input v-model="profile.time_start" type="time" class="input" />
            <span>—</span>
            <input v-model="profile.time_end" type="time" class="input" />
          </div>
        </div>
        <div>
          <label class="label">{{ tr('期望最早日期', 'Earliest date') }}</label>
          <input v-model="profile.expect_after_date" type="date" class="input" />
        </div>
        <div>
          <label class="label">{{ tr('期望最晚日期', 'Latest date') }}</label>
          <input v-model="profile.expect_before_date" type="date" class="input" />
        </div>
        <div class="col-span-2">
          <label class="label">{{ tr('考点（单选）', 'Location') }}</label>
          <select v-model="profile.pos_id" class="input">
            <option :value="null" disabled>{{ tr('请选择考点', 'Select a location') }}</option>
            <option v-for="p in posList" :key="p.pos_id" :value="p.pos_id">{{ p.name }} ({{ p.pos_id }})</option>
          </select>
        </div>
        <div class="col-span-2">
          <label class="label">{{ tr('星期偏好', 'Preferred days') }}</label>
          <div class="flex flex-wrap gap-3 text-sm">
            <label v-for="d in WEEK" :key="d.v" class="flex items-center gap-1">
              <input type="checkbox" :value="d.v" v-model="profile.pref_days_of_week" />{{ tr(d.zh, d.en) }}
            </label>
          </div>
        </div>
        <div class="col-span-2">
          <label class="label">{{ tr('时段偏好', 'Preferred time of day') }}</label>
          <div class="flex gap-4 text-sm">
            <label class="flex items-center gap-1">
              <input type="checkbox" :value="0" v-model="profile.pref_parts_of_day" />{{ tr('上午', 'Morning') }}
            </label>
            <label class="flex items-center gap-1">
              <input type="checkbox" :value="1" v-model="profile.pref_parts_of_day" />{{ tr('下午', 'Afternoon') }}
            </label>
          </div>
        </div>
      </div>
      <button class="btn-primary" @click="saveBookingSettings">{{ tr('保存预约设置', 'Save booking settings') }}</button>
    </div>
  </div>
</template>
