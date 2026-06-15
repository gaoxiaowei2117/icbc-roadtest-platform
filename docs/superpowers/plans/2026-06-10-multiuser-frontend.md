# 多用户化 — 前端实现计划（计划 3/3）

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 前端 Settings 表单完整对齐 road.py 抢号参数（keyword/exam_class/考点多选/日期区间/时间区间/星期/上下午），建任务简化为无参数触发，让用户在网页上配置就能驱动抢号。

**Architecture:** User 类型与 api 层换成档案字段；Settings 页填完整档案 + keyword（考点从 `GET /api/pos-list` 渲染多选）；Bookings 页建任务无参数、列表去掉已删字段。前端无单测框架，验证用 `vue-tsc`（类型检查）+ `vite build`。

**Tech Stack:** Vue 3 + TypeScript + Pinia + axios + Tailwind。验证命令：`cd frontend && npm run build`（先 vue-tsc --noEmit 再 vite build）。

**总体说明：**
- 设计见 spec `docs/superpowers/specs/2026-06-10-multiuser-web-driven-booking-design.md` 第 6 节。
- 后端（计划1）已就位：`GET /api/pos-list` 返回 `[{name,pos_id}]`；`PATCH /api/users/me` 接收档案字段；`PUT /api/users/me/secret` 收 `{keyword}`；`POST /api/bookings` 无 body（建任务前置校验要求档案完整）。
- frontend 依赖已装（node_modules 存在）。

---

## 文件结构

| 文件 | 动作 | 责任 |
|---|---|---|
| `frontend/src/stores/auth.ts` | 改 | `User` 接口换档案字段 |
| `frontend/src/api/users.ts` | 改 | `setSecret({keyword})`、`updateMe` 档案 |
| `frontend/src/api/pos.ts` | 新 | `getPosList()` |
| `frontend/src/api/bookings.ts` | 改 | `Booking` 去 target_date/pos_code；`createBooking()` 无参数 |
| `frontend/src/views/Settings.vue` | 改 | 完整档案表单 + keyword + 考点多选 |
| `frontend/src/views/Bookings.vue` | 改 | 建任务无参数；列表去旧字段 |

---

## Task 1: 类型层 + api 层

**Files:**
- Modify: `frontend/src/stores/auth.ts`
- Modify: `frontend/src/api/users.ts`
- Create: `frontend/src/api/pos.ts`
- Modify: `frontend/src/api/bookings.ts`

- [ ] **Step 1: 改 User 接口**

把 `frontend/src/stores/auth.ts` 的 `User` 接口（第 5-15 行）替换为：
```typescript
export interface User {
  id: number
  email: string
  is_admin: boolean
  icbc_license_no: string | null
  icbc_last_name: string | null
  exam_class: string | null
  pos_ids: number[] | null
  expect_after_date: string | null
  expect_before_date: string | null
  expect_time_range: string | null
  pref_days_of_week: number[] | null
  pref_parts_of_day: number[] | null
  created_at: string
}
```

- [ ] **Step 2: 改 users.ts api**

把 `frontend/src/api/users.ts` 的 `setSecret` 改为收 keyword：
```typescript
export async function setSecret(payload: { keyword: string }) {
  return (await api.put('/api/users/me/secret', payload)).data
}
```
（`getMe`/`updateMe`/`getSecretStatus`/`deleteSecret` 保持不变——`updateMe` 已是 `Partial<User>`，自动支持新档案字段。）

- [ ] **Step 3: 建 pos.ts api**

Create `frontend/src/api/pos.ts`:
```typescript
import { api } from './client'

export interface PosEntry {
  name: string
  pos_id: number
}

export async function getPosList(): Promise<PosEntry[]> {
  return (await api.get('/api/pos-list')).data
}
```

- [ ] **Step 4: 改 bookings.ts api**

先读 `frontend/src/api/bookings.ts`。把 `Booking` 接口里的 `target_date`/`time_window`/`pos_code` 字段删除（保留 id/user_id/status/attempt_count/last_error/result/started_at/finished_at/created_at/updated_at）。把 `createBooking` 改为无参数：
```typescript
export async function createBooking() {
  return (await api.post('/api/bookings', {})).data
}
```
（如果原 `createBooking(payload)` 有入参类型，一并去掉。）

- [ ] **Step 5: 类型检查（局部）**

Run: `cd /home/xgao/workspace/icbc-roadtest-platform/frontend && npx vue-tsc --noEmit 2>&1 | head -30`
Expected: 此时 Settings.vue / Bookings.vue 仍引用旧字段，会报类型错误——这是预期的（Task 2/3 修）。**只确认 auth.ts / api 层这几个文件自身无语法错**（错误应都指向 Settings.vue / Bookings.vue，不指向本 task 改的文件）。

- [ ] **Step 6: Commit**

```bash
cd /home/xgao/workspace/icbc-roadtest-platform
git add frontend/src/stores/auth.ts frontend/src/api/users.ts frontend/src/api/pos.ts frontend/src/api/bookings.ts
git commit -m "frontend: User 类型 + api 层对齐多用户档案"
```

---

## Task 2: Settings.vue 完整档案表单

**Files:**
- Modify: `frontend/src/views/Settings.vue`

- [ ] **Step 1: 整体替换 Settings.vue**

把 `frontend/src/views/Settings.vue` 整体替换为：
```vue
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
```

- [ ] **Step 2: Commit**

```bash
cd /home/xgao/workspace/icbc-roadtest-platform
git add frontend/src/views/Settings.vue
git commit -m "frontend: Settings 完整对齐抢号档案 + keyword + 考点多选"
```

---

## Task 3: Bookings.vue 简化建任务

**Files:**
- Modify: `frontend/src/views/Bookings.vue`

- [ ] **Step 1: 整体替换 Bookings.vue**

把 `frontend/src/views/Bookings.vue` 整体替换为（建任务无参数；列表去掉 target_date/pos_code 列）：
```vue
<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { cancelBooking, createBooking, listBookings, type Booking } from '@/api/bookings'

const bookings = ref<Booking[]>([])
const error = ref('')
const message = ref('')
const loading = ref(false)

async function refresh() {
  loading.value = true
  try {
    bookings.value = await listBookings()
  } catch (e: any) {
    error.value = e.response?.data?.detail || '加载失败'
  } finally {
    loading.value = false
  }
}

async function onCreate() {
  error.value = ''
  message.value = ''
  try {
    await createBooking()
    message.value = '任务已创建，等待 worker 执行'
    await refresh()
  } catch (e: any) {
    error.value = e.response?.data?.detail || '创建失败'
  }
}

async function onCancel(b: Booking) {
  if (!confirm(`确定取消任务 #${b.id}？`)) return
  try {
    await cancelBooking(b.id)
    await refresh()
  } catch (e: any) {
    error.value = e.response?.data?.detail || '取消失败'
  }
}

function badgeClass(s: Booking['status']) {
  return {
    pending: 'badge-pending',
    running: 'badge-running',
    done: 'badge-done',
    failed: 'badge-failed',
    cancelled: 'badge-cancelled',
  }[s]
}

onMounted(refresh)
</script>

<template>
  <div class="space-y-6">
    <h1 class="text-2xl font-bold">抢约任务</h1>

    <div class="card space-y-4">
      <h2 class="text-lg font-semibold">新建任务</h2>
      <p class="text-sm text-slate-600">
        抢号参数来自「设置」页的档案（考点 / 日期 / 时间 / 偏好）。请先在设置页填好档案与 keyword，再创建任务。
      </p>
      <button class="btn-primary" @click="onCreate">创建任务</button>
    </div>

    <p v-if="message" class="text-sm text-green-600">{{ message }}</p>
    <p v-if="error" class="text-sm text-red-600">{{ error }}</p>

    <div class="card">
      <div class="flex items-center justify-between mb-4">
        <h2 class="text-lg font-semibold">我的任务</h2>
        <button class="btn-secondary" @click="refresh" :disabled="loading">刷新</button>
      </div>
      <div v-if="!bookings.length" class="text-sm text-slate-500 text-center py-8">暂无任务</div>
      <table v-else class="w-full text-sm">
        <thead class="text-left text-slate-500 border-b">
          <tr>
            <th class="py-2">#</th>
            <th>状态</th>
            <th>尝试</th>
            <th>最后错误</th>
            <th>创建</th>
            <th></th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="b in bookings" :key="b.id" class="border-b last:border-0">
            <td class="py-2">{{ b.id }}</td>
            <td><span :class="badgeClass(b.status)">{{ b.status }}</span></td>
            <td>{{ b.attempt_count }}</td>
            <td class="text-red-600 text-xs truncate max-w-xs">{{ b.last_error || '—' }}</td>
            <td>{{ new Date(b.created_at).toLocaleString() }}</td>
            <td>
              <button
                v-if="b.status === 'pending' || b.status === 'running'"
                class="text-red-600 hover:underline"
                @click="onCancel(b)"
              >
                取消
              </button>
            </td>
          </tr>
        </tbody>
      </table>
    </div>
  </div>
</template>
```

- [ ] **Step 2: Commit**

```bash
cd /home/xgao/workspace/icbc-roadtest-platform
git add frontend/src/views/Bookings.vue
git commit -m "frontend: Bookings 建任务无参数 + 列表去旧字段"
```

---

## Task 4: 构建验证 + 收尾

**Files:** 视 vue-tsc 报错而定（可能 Dashboard.vue / Admin.vue 引用了旧字段）

- [ ] **Step 1: 全量类型检查 + 构建**

Run: `cd /home/xgao/workspace/icbc-roadtest-platform/frontend && npm run build 2>&1 | tail -30`
Expected: `vue-tsc` 无错误，`vite build` 成功（输出 dist/）。
若 vue-tsc 报错指向 `Dashboard.vue` / `Admin.vue` / 其它文件仍引用旧字段（preferred_pos / time_windows / max_wait_days / target_date / pos_code / icbc_username / icbc_password）：读该文件，按多用户档案字段修正（例如 Dashboard 若展示 preferred_pos，改为展示 pos_ids 或移除该展示；Admin 若展示 booking 的 target_date/pos_code，移除该列）。把每处修复如实记录。

- [ ] **Step 2: 确认 build 产物**

Run: `ls /home/xgao/workspace/icbc-roadtest-platform/frontend/dist/`
Expected: 有 `index.html` 和 `assets/`。

- [ ] **Step 3: grep 前端无残留旧字段**

Run:
```bash
cd /home/xgao/workspace/icbc-roadtest-platform/frontend && \
grep -rnE "preferred_pos|time_windows|max_wait_days|target_date|pos_code|icbc_username|icbc_password" src/ || echo "✅ 前端无残留旧字段"
```
Expected: `✅ 前端无残留旧字段`。

- [ ] **Step 4: Commit（如 Step 1 有顺带修复）**

```bash
cd /home/xgao/workspace/icbc-roadtest-platform
git add frontend/src/
git commit -m "frontend: 多用户化构建通过（清理残留旧字段引用）" || echo "无新改动"
```

---

## 验收标准

- [ ] User 类型 + api 层用档案字段；setSecret 收 keyword。
- [ ] Settings 页能填完整档案（含考点多选 from pos-list）+ keyword。
- [ ] Bookings 建任务无参数；列表不引用已删字段。
- [ ] `npm run build` 通过（vue-tsc + vite）；dist 产物存在。
- [ ] 前端 src 无残留旧字段引用。

## 后续（多用户化完成后）

- 真实端到端联调：用户网页填档案 + keyword → 建任务 → worker 用系统 Gmail dry-run 验证（autoBooking 实际由 road_adapter 强制 true，dry-run 需临时调整或在测试账号上小心验证）→ 真实抢号由用户亲自盯。
- known-issues 标记多用户化三计划全部完成。
