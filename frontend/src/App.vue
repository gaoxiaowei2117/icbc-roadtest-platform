<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { RouterView, RouterLink, useRoute, useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import { useI18n } from '@/i18n'
import LanguageSelect from '@/components/LanguageSelect.vue'
import SiteFooter from '@/components/SiteFooter.vue'

const auth = useAuthStore()
const route = useRoute()
const router = useRouter()
const { tr } = useI18n()
const menuOpen = ref(false)

const navLinks = computed(() => {
  if (!auth.user) return []
  if (auth.user.is_admin) {
    return [
      { to: '/admin', label: tr('管理', 'Admin') },
      { to: '/routes', label: tr('练习路线', 'Practice routes') },
    ]
  }
  return [
    { to: '/dashboard', label: tr('资料', 'Profile') },
    { to: '/bookings', label: tr('任务', 'Bookings') },
    { to: '/settings', label: tr('设置', 'Settings') },
    { to: '/routes', label: tr('练习路线', 'Practice routes') },
  ]
})

watch(() => route.fullPath, () => { menuOpen.value = false })

async function onLogout() {
  menuOpen.value = false
  await auth.logout()
  router.push('/login')
}
</script>

<template>
  <div class="min-h-screen overflow-x-hidden">
    <LanguageSelect v-if="!auth.user" class="fixed right-4 top-4 z-10 text-sm" />
    <nav
      v-if="!auth.user && !['login', 'register'].includes(String(route.name))"
      class="fixed left-4 top-4 z-10 flex gap-4 text-sm py-2"
    >
      <RouterLink to="/routes" class="hover:text-blue-600">{{ tr('练习路线', 'Practice routes') }}</RouterLink>
      <RouterLink to="/login" class="hover:text-blue-600">{{ tr('登录', 'Log in') }}</RouterLink>
    </nav>
    <header
      v-if="auth.user && !['login', 'register'].includes(String(route.name))"
      class="bg-white border-b border-slate-200"
    >
      <div class="max-w-6xl mx-auto px-4 py-3 flex items-center justify-between gap-3">
        <div class="flex items-center gap-6 min-w-0">
          <span class="font-bold text-lg whitespace-nowrap truncate">
            {{ auth.user.is_admin ? tr('ICBC 管理后台', 'ICBC Admin') : tr('ICBC 路考预约', 'ICBC Road Test Booking') }}
          </span>
          <nav class="hidden md:flex gap-4 text-sm whitespace-nowrap">
            <RouterLink v-for="link in navLinks" :key="link.to" :to="link.to" class="hover:text-blue-600">{{ link.label }}</RouterLink>
          </nav>
        </div>
        <div class="hidden md:flex items-center gap-3 text-sm shrink-0">
          <span class="hidden lg:inline text-slate-600 truncate max-w-[16rem]">{{ auth.user.email }}</span>
          <LanguageSelect />
          <button class="btn-secondary whitespace-nowrap" @click="onLogout">{{ tr('登出', 'Log out') }}</button>
        </div>
        <button
          class="md:hidden btn-secondary px-3 shrink-0"
          :aria-expanded="menuOpen"
          :aria-label="tr('菜单', 'Menu')"
          @click="menuOpen = !menuOpen"
        >
          <span aria-hidden="true">{{ menuOpen ? '✕' : '☰' }}</span>
        </button>
      </div>
      <div v-if="menuOpen" class="md:hidden border-t border-slate-200 px-4 py-3 space-y-3 text-sm">
        <nav class="flex flex-col">
          <RouterLink
            v-for="link in navLinks"
            :key="link.to"
            :to="link.to"
            class="py-2 hover:text-blue-600"
            active-class="text-blue-600 font-medium"
          >{{ link.label }}</RouterLink>
        </nav>
        <p class="text-slate-500 truncate">{{ auth.user.email }}</p>
        <div class="flex items-center gap-3">
          <LanguageSelect />
          <button class="btn-secondary" @click="onLogout">{{ tr('登出', 'Log out') }}</button>
        </div>
      </div>
    </header>
    <main class="max-w-6xl mx-auto px-4 py-8" :class="{ 'pt-16': !auth.user && route.name === 'routes' }">
      <RouterView />
    </main>
    <SiteFooter />
  </div>
</template>
