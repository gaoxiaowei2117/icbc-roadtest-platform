<script setup lang="ts">
import { ref } from 'vue'
import AdminUsersCard from '@/components/admin/AdminUsersCard.vue'
import AdminRoutePackAccessCard from '@/components/admin/AdminRoutePackAccessCard.vue'
import AdminRouteOpensCard from '@/components/admin/AdminRouteOpensCard.vue'
import { useI18n } from '@/i18n'

// Admin-only "Users" tab of the route-pack site: who registered, which packs
// they hold, and how they use them. Booking details stay in the booking console.
const usersCard = ref<InstanceType<typeof AdminUsersCard> | null>(null)
const { tr } = useI18n()
</script>

<template>
  <div class="space-y-6">
    <h1 class="text-2xl font-bold">{{ tr('用户', 'Users') }}</h1>
    <AdminUsersCard ref="usersCard" route-only />
    <AdminRoutePackAccessCard @changed="usersCard?.refresh()" />
    <AdminRouteOpensCard />
  </div>
</template>
