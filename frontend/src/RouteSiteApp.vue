<script setup lang="ts">
import { RouterLink, RouterView, useRoute, useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import { useI18n } from '@/i18n'
import LanguageSelect from '@/components/LanguageSelect.vue'
import SiteFooter from '@/components/SiteFooter.vue'

// Layout for the route-pack site at the domain root: brand, language, login/logout.
// Deliberately no links or branding of the booking service.
const auth = useAuthStore()
const route = useRoute()
const router = useRouter()
const { tr } = useI18n()

async function onLogout() {
  await auth.logout()
  router.push({ name: 'routes' })
}
</script>

<template>
  <div class="min-h-screen overflow-x-hidden">
    <header class="bg-white border-b border-slate-200">
      <div class="max-w-3xl mx-auto px-4 py-3 flex items-center justify-between gap-3">
        <RouterLink to="/" class="min-w-0 leading-tight">
          <span class="block font-bold text-base sm:text-lg">{{ tr('路考练习路线', 'Road Test Practice Routes') }}</span>
          <span class="block text-xs text-slate-500">roadtestgo</span>
        </RouterLink>
        <div class="flex items-center gap-2 text-sm shrink-0">
          <span v-if="auth.user" class="hidden md:inline text-slate-600 truncate max-w-[14rem]">{{ auth.user.email }}</span>
          <LanguageSelect class="text-sm" />
          <button v-if="auth.user" class="btn-secondary whitespace-nowrap" @click="onLogout">{{ tr('登出', 'Log out') }}</button>
          <RouterLink
            v-else-if="route.name !== 'login'"
            :to="{ name: 'login', query: { redirect: '/' } }"
            class="btn-secondary whitespace-nowrap"
          >{{ tr('登录', 'Log in') }}</RouterLink>
        </div>
      </div>
    </header>
    <main class="max-w-6xl mx-auto px-4 py-6 sm:py-8">
      <RouterView />
    </main>
    <SiteFooter />
  </div>
</template>
