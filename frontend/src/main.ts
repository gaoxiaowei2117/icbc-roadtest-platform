import { createApp } from 'vue'
import { createPinia } from 'pinia'
// `@site` is src/sites/booking.ts or src/sites/routes.ts depending on the build mode
// (see vite.config.ts), so each build only bundles its own layout and router.
import { App, router } from '@site'
import './style.css'

const app = createApp(App)
app.use(createPinia())
app.use(router)
app.mount('#app')
