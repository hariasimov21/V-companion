import { resolve } from 'node:path'
import react from '@vitejs/plugin-react'
import { defineConfig } from 'electron-vite'

// The repo-root .env is shared with the backend; Vite only exposes VITE_* variables
// to the renderer, so secrets like OPENAI_API_KEY never reach the bundle.
const repoRoot = resolve(__dirname, '../..')

export default defineConfig({
  main: {},
  preload: {},
  renderer: {
    envDir: repoRoot,
    plugins: [react()],
  },
})
