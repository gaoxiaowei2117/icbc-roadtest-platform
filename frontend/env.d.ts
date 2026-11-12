/// <reference types="vite/client" />

declare module '*.vue' {
  import type { DefineComponent } from 'vue'
  const component: DefineComponent<{}, {}, any>
  export default component
}

interface ImportMetaEnv {
  /** 'routes' for the route-pack site build (`--mode routes`); unset for the booking site. */
  readonly VITE_SITE?: string
}
