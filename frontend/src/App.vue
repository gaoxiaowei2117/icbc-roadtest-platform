<script setup lang="ts">
import { onMounted } from 'vue'
import { RouterView, RouterLink, useRoute, useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'

const auth = useAuthStore()
const route = useRoute()
const router = useRouter()

onMounted(() => {
  if (auth.token && !auth.user) {
    auth.fetchMe().catch(() => auth.logout())
  }
})

async function onLogout() {
  await auth.logout()
  router.push('/login')
}
</script>

<template>
  <div class="min-h-screen">
    <header
      v-if="auth.user && !['login', 'register'].includes(String(route.name))"
      class="bg-white border-b border-slate-200"
    >
      <div class="max-w-6xl mx-auto px-4 py-3 flex items-center justify-between">
        <div class="flex items-center gap-6">
          <span class="font-bold text-lg">ICBC 路考预约</span>
          <nav class="flex gap-4 text-sm">
            <RouterLink to="/dashboard" class="hover:text-blue-600">资料</RouterLink>
            <RouterLink to="/bookings" class="hover:text-blue-600">任务</RouterLink>
            <RouterLink to="/settings" class="hover:text-blue-600">设置</RouterLink>
            <RouterLink v-if="auth.user.is_admin" to="/admin" class="hover:text-blue-600">管理</RouterLink>
          </nav>
        </div>
        <div class="flex items-center gap-3 text-sm">
          <span class="text-slate-600">{{ auth.user.email }}</span>
          <button class="btn-secondary" @click="onLogout">登出</button>
        </div>
      </div>
    </header>
    <main class="max-w-6xl mx-auto px-4 py-8">
      <RouterView />
    </main>
  </div>
</template>
