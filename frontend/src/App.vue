<script setup lang="ts">
import { ref } from 'vue'
import { RouterView, RouterLink, useRoute, useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import { useI18n } from '@/i18n'

const auth = useAuthStore()
const route = useRoute()
const router = useRouter()
const { tr, locale } = useI18n()

// ── 打赏配置 ──────────────────────────────────────────────
// 话术只谈“支持开发”，请勿在收款页 / 二维码备注里提及 ICBC / 抢约。
//
// 1) 信用卡 / PayPal：填你的 Ko-fi（或 Buy Me a Coffee / PayPal.me）链接；留空则隐藏该按钮。
const KOFI_URL = 'https://ko-fi.com/galaxtools'
// 2) 微信 / 支付宝收款码：把收款码图片放到 frontend/public/donate/ 下，
//    文件名保持 wechat.jpg / alipay.jpg 即可（jpg/png 均可，后缀和实际文件一致即可）。
const WECHAT_QR = `${import.meta.env.BASE_URL}donate/wechat.jpg`
const ALIPAY_QR = `${import.meta.env.BASE_URL}donate/alipay.jpg`

const currentYear = new Date().getFullYear()
const showDonate = ref(false)

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
    <footer class="border-t border-slate-200 mt-8">
      <div
        class="max-w-6xl mx-auto px-4 py-6 flex flex-col sm:flex-row items-center justify-between gap-3 text-sm text-slate-500"
      >
        <span>© {{ currentYear }} {{ tr('独立开发的小工具，与 ICBC 无任何关联。', 'An independent tool, not affiliated with ICBC.', 'Un outil indépendant, sans lien avec ICBC.', 'Una herramienta independiente, sin relación con ICBC.', '獨立開發的小工具，與 ICBC 無任何關聯。') }}</span>
        <button
          type="button"
          class="inline-flex items-center gap-2 rounded-full bg-rose-500 px-5 py-2.5 text-sm font-semibold text-white shadow-sm hover:bg-rose-600 hover:shadow-md transition-all"
          @click="showDonate = true"
        >
          <span aria-hidden="true" class="text-base">☕</span>
          {{ tr('请我喝杯咖啡', 'Buy me a coffee', 'Offrez-moi un café', 'Invítame un café', '請我喝杯咖啡') }}
        </button>
      </div>
    </footer>

    <!-- 打赏弹窗：同时覆盖 微信/支付宝 与 信用卡/PayPal -->
    <div
      v-if="showDonate"
      class="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4"
      @click.self="showDonate = false"
    >
      <div class="w-full max-w-lg max-h-[90vh] overflow-y-auto rounded-2xl bg-white p-6 shadow-xl">
        <div class="flex items-start justify-between">
          <div>
            <h2 class="text-lg font-bold text-slate-800">
              {{ tr('支持这个小工具', 'Support this tool', 'Soutenir cet outil', 'Apoyar esta herramienta', '支持這個小工具') }}
            </h2>
            <p class="mt-1 text-sm text-slate-500">
              {{ tr('它一直免费提供，你的支持用于服务器开销和功能改进，谢谢 ❤️', 'It is free to use — your support covers server costs and improvements. Thank you ❤️', 'Gratuit à utiliser — votre soutien couvre les frais de serveur et les améliorations. Merci ❤️', 'Es de uso gratuito — tu apoyo cubre los costos del servidor y mejoras. ¡Gracias ❤️', '它一直免費提供，你的支持用於伺服器開銷和功能改進，謝謝 ❤️') }}
            </p>
          </div>
          <button
            type="button"
            class="ml-3 text-2xl leading-none text-slate-400 hover:text-slate-600"
            :aria-label="tr('关闭', 'Close', 'Fermer', 'Cerrar', '關閉')"
            @click="showDonate = false"
          >
            ×
          </button>
        </div>

        <!-- 微信 / 支付宝收款码 -->
        <div class="mt-5 grid grid-cols-2 gap-4">
          <div class="flex flex-col items-center gap-2">
            <img :src="WECHAT_QR" alt="WeChat Pay" class="w-full rounded-lg border border-slate-200" />
            <span class="text-sm text-slate-600">{{ tr('微信', 'WeChat Pay', 'WeChat Pay', 'WeChat Pay', '微信') }}</span>
          </div>
          <div class="flex flex-col items-center gap-2">
            <img :src="ALIPAY_QR" alt="Alipay" class="w-full rounded-lg border border-slate-200" />
            <span class="text-sm text-slate-600">{{ tr('支付宝', 'Alipay', 'Alipay', 'Alipay', '支付寶') }}</span>
          </div>
        </div>
        <p class="mt-2 text-center text-xs text-slate-400">
          {{ tr('微信 / 支付宝扫码即可，无需登录', 'Scan with WeChat / Alipay — no login needed', 'Scannez avec WeChat / Alipay — sans connexion', 'Escanea con WeChat / Alipay — sin iniciar sesión', '微信 / 支付寶掃碼即可，無需登入') }}
        </p>

        <!-- 信用卡 / PayPal -->
        <a
          v-if="KOFI_URL"
          :href="KOFI_URL"
          target="_blank"
          rel="noopener noreferrer"
          class="mt-5 flex items-center justify-center gap-2 rounded-full bg-slate-800 px-5 py-3 text-sm font-semibold text-white hover:bg-slate-900 transition-colors"
        >
          <span aria-hidden="true">💳</span>
          {{ tr('用信用卡 / PayPal 支持', 'Pay with card / PayPal', 'Payer par carte / PayPal', 'Pagar con tarjeta / PayPal', '用信用卡 / PayPal 支持') }}
        </a>
      </div>
    </div>
  </div>
</template>
