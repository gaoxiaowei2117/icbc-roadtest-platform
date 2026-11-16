<script setup lang="ts">
import { SUPPORT_EMAIL } from '@/config/support'
import { useI18n } from '@/i18n'
import { IS_ROUTE_SITE } from '@/site'

const { tr, locale } = useI18n()
const currentYear = new Date().getFullYear()
</script>

<template>
  <footer class="border-t border-slate-200 mt-8">
    <div
      class="max-w-6xl mx-auto px-4 py-6 flex flex-col sm:flex-row items-center justify-between gap-3 text-sm text-slate-500 text-center sm:text-left"
    >
      <span>© {{ currentYear }} {{ tr('独立开发的小工具，与 ICBC 无任何关联。', 'An independent tool, not affiliated with ICBC.', 'Un outil indépendant, sans lien avec ICBC.', 'Una herramienta independiente, sin relación con ICBC.', '獨立開發的小工具，與 ICBC 無任何關聯。') }}</span>
      <!-- Plain link to the static route pages (/zh/, /en/) so crawlers can find them from the app. -->
      <a
        v-if="IS_ROUTE_SITE"
        :href="locale.startsWith('zh') ? '/zh/' : '/en/'"
        class="hover:text-blue-600 hover:underline"
      >{{ tr('各考场路线介绍', 'Route guides by test centre', 'Guides des itinéraires par centre', 'Guías de rutas por centro', '各考場路線介紹') }}</a>
      <a :href="`mailto:${SUPPORT_EMAIL}`" class="hover:text-blue-600 hover:underline break-all">
        {{ tr('联系客服：', 'Contact support: ') }}{{ SUPPORT_EMAIL }}
      </a>
    </div>
  </footer>
</template>
