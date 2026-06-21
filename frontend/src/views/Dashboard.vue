<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useAuthStore } from '@/stores/auth'
import { getSecretStatus } from '@/api/users'
import { useI18n } from '@/i18n'

const auth = useAuthStore()
const hasSecret = ref(false)
const secretUpdatedAt = ref<string | null>(null)
const { tr, dateLocale } = useI18n()

onMounted(async () => {
  try {
    const s = await getSecretStatus()
    hasSecret.value = s.has_secret
    secretUpdatedAt.value = s.updated_at
  } catch (e) {
    /* ignore */
  }
})
</script>

<template>
  <div class="space-y-6">
    <h1 class="text-2xl font-bold">{{ tr('我的资料', 'My Profile') }}</h1>
    <div class="card">
      <h2 class="text-lg font-semibold mb-4">{{ tr('账号信息', 'Account') }}</h2>
      <dl class="grid grid-cols-2 gap-3 text-sm">
        <dt class="text-slate-500">{{ tr('邮箱', 'Email') }}</dt><dd>{{ auth.user?.email }}</dd>
        <dt class="text-slate-500">{{ tr('角色', 'Role') }}</dt>
        <dd>
          <span v-if="auth.user?.is_admin" class="badge bg-purple-100 text-purple-800">admin</span>
          <span v-else class="badge bg-slate-100 text-slate-800">{{ tr('普通用户', 'User') }}</span>
        </dd>
        <dt class="text-slate-500">{{ tr('注册时间', 'Registered') }}</dt>
        <dd>{{ auth.user?.created_at ? new Date(auth.user.created_at).toLocaleString(dateLocale) : '—' }}</dd>
      </dl>
    </div>

    <div class="card">
      <h2 class="text-lg font-semibold mb-4">{{ tr('ICBC 资料', 'ICBC Profile') }}</h2>
      <dl class="grid grid-cols-2 gap-3 text-sm">
        <dt class="text-slate-500">{{ tr('驾照号', 'Licence number') }}</dt>
        <dd>{{ auth.user?.icbc_license_no || tr('— 未填写', '— Not provided') }}</dd>
        <dt class="text-slate-500">{{ tr('姓氏', 'Last name') }}</dt>
        <dd>{{ auth.user?.icbc_last_name || tr('— 未填写', '— Not provided') }}</dd>
        <dt class="text-slate-500">{{ tr('考场类别', 'Exam class') }}</dt>
        <dd>{{ auth.user?.exam_class || tr('— 未填写', '— Not provided') }}</dd>
        <dt class="text-slate-500">{{ tr('预选考点', 'Locations') }}</dt>
        <dd>
          <span v-if="auth.user?.pos_ids?.length">{{ tr(
            `已配置 ${auth.user.pos_ids.length} 个考点`,
            `${auth.user.pos_ids.length} location(s) configured`,
            `${auth.user.pos_ids.length} centre(s) configuré(s)`,
            `${auth.user.pos_ids.length} centro(s) configurado(s)`,
            `已設定 ${auth.user.pos_ids.length} 個考點`,
          ) }}</span>
          <span v-else>{{ tr('— 未设置', '— Not configured') }}</span>
        </dd>
        <dt class="text-slate-500">{{ tr('预约日期范围', 'Date range') }}</dt>
        <dd>
          <span v-if="auth.user?.expect_after_date || auth.user?.expect_before_date">
            {{ auth.user.expect_after_date || tr('不限', 'Any') }} ~ {{ auth.user.expect_before_date || tr('不限', 'Any') }}
          </span>
          <span v-else>{{ tr('— 未设置', '— Not configured') }}</span>
        </dd>
      </dl>
      <RouterLink to="/settings" class="btn-primary inline-block mt-4">{{ tr('编辑资料 / 修改凭据', 'Edit profile / credentials') }}</RouterLink>
    </div>

    <div class="card">
      <h2 class="text-lg font-semibold mb-4">{{ tr('ICBC 登录凭据', 'ICBC Credentials') }}</h2>
      <p v-if="hasSecret" class="text-sm text-green-700">
        ✓ {{ tr('已配置', 'Configured') }}
        <span v-if="secretUpdatedAt" class="text-slate-500">
          {{ tr(
            `（更新于 ${new Date(secretUpdatedAt).toLocaleString(dateLocale)}）`,
            `(updated ${new Date(secretUpdatedAt).toLocaleString(dateLocale)})`,
            `(mis à jour ${new Date(secretUpdatedAt).toLocaleString(dateLocale)})`,
            `(actualizado ${new Date(secretUpdatedAt).toLocaleString(dateLocale)})`,
            `（更新於 ${new Date(secretUpdatedAt).toLocaleString(dateLocale)}）`,
          ) }}
        </span>
      </p>
      <p v-else class="text-sm text-red-600">✗ {{ tr('未配置，无法启动抢约', 'Not configured; booking cannot start') }}</p>
      <RouterLink to="/settings" class="btn-secondary inline-block mt-4">{{ tr('管理凭据', 'Manage credentials') }}</RouterLink>
    </div>
  </div>
</template>
