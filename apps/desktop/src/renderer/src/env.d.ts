/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_BACKEND_WS_URL?: string
  readonly VITE_AVATAR_RENDERER?: 'sprite' | 'placeholder'
}

interface ImportMeta {
  readonly env: ImportMetaEnv
}
