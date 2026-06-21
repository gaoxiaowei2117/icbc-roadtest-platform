<script setup lang="ts">
import { RouterView, RouterLink, useRoute, useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import { useI18n } from '@/i18n'

const auth = useAuthStore()
const route = useRoute()
const router = useRouter()
const { tr, locale } = useI18n()

async function onLogout() {
  await auth.logout()
  router.push('/login')
}
</script>

<template>
  <div class="min-h-screen">
    <select
      v-if="!auth.user"
      v-model="locale"
      class="input fixed right-4 top-4 z-10 w-auto text-sm"
      aria-label="Language"
    >
      <option value="zh">简体中文</option>
      <option value="zh-Hant">繁體中文</option>
      <option value="en">English</option>
      <option value="fr">Français</option>
      <option value="es">Español</option>
    </select>
    <header
      v-if="auth.user && !['login', 'register'].includes(String(route.name))"
      class="bg-white border-b border-slate-200"
    >
      <div class="max-w-6xl mx-auto px-4 py-3 flex items-center justify-between">
        <div class="flex items-center gap-6">
          <span class="font-bold text-lg">
            {{ auth.user.is_admin ? tr('ICBC 管理后台', 'ICBC Admin') : tr('ICBC 路考预约', 'ICBC Road Test Booking') }}
          </span>
          <nav class="flex gap-4 text-sm">
            <RouterLink v-if="auth.user.is_admin" to="/admin" class="hover:text-blue-600">{{ tr('管理', 'Admin') }}</RouterLink>
            <template v-else>
              <RouterLink to="/dashboard" class="hover:text-blue-600">{{ tr('资料', 'Profile') }}</RouterLink>
              <RouterLink to="/bookings" class="hover:text-blue-600">{{ tr('任务', 'Bookings') }}</RouterLink>
              <RouterLink to="/settings" class="hover:text-blue-600">{{ tr('设置', 'Settings') }}</RouterLink>
            </template>
          </nav>
        </div>
        <div class="flex items-center gap-3 text-sm">
          <span class="text-slate-600">{{ auth.user.email }}</span>
          <select v-model="locale" class="input w-auto py-2" aria-label="Language">
            <option value="zh">简体中文</option>
            <option value="zh-Hant">繁體中文</option>
            <option value="en">English</option>
            <option value="fr">Français</option>
            <option value="es">Español</option>
          </select>
          <button class="btn-secondary" @click="onLogout">{{ tr('登出', 'Log out') }}</button>
        </div>
      </div>
    </header>
    <main class="max-w-6xl mx-auto px-4 py-8">
      <RouterView />
    </main>
  </div>
</template>
