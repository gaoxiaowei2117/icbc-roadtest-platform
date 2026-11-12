import { createRouter, createWebHistory } from 'vue-router'
import { useAuthStore } from '@/stores/auth'

// Route-pack site at the domain root: the packs page plus what buying needs.
// No booking pages here; those stay in the /booking/ build.
const router = createRouter({
  history: createWebHistory('/'),
  routes: [
    {
      path: '/',
      name: 'routes',
      component: () => import('@/views/RoutePacks.vue'),
    },
    {
      path: '/login',
      name: 'login',
      component: () => import('@/views/Login.vue'),
      meta: { guest: true },
    },
    {
      path: '/register',
      name: 'register',
      component: () => import('@/views/Register.vue'),
      meta: { guest: true },
    },
    {
      path: '/verify',
      name: 'verify',
      component: () => import('@/views/VerifyEmail.vue'),
      meta: { guest: true },
    },
    { path: '/:pathMatch(.*)*', redirect: '/' },
  ],
})

router.beforeEach(async (to) => {
  const auth = useAuthStore()
  if (auth.token && !auth.user) {
    try {
      await auth.fetchMe()
    } catch {
      await auth.logout()
    }
  }
  if (to.meta.guest && auth.token) return { name: 'routes' }
})

export default router
