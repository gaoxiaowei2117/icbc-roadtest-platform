<script setup lang="ts">
import { useI18n } from '@/i18n'

const { locale } = useI18n()
</script>

<template>
  <select v-model="locale" class="input w-auto py-2" aria-label="Language">
    <option value="zh">简体中文</option>
    <option value="zh-Hant">繁體中文</option>
    <option value="en">English</option>
    <option value="fr">Français</option>
    <option value="es">Español</option>
  </select>
</template>
