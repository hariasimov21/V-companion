import { resolve } from 'node:path'
import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

/**
 * The same UI served as a plain web page, without Electron. Useful under WSL: a browser
 * on Windows plays the character's voice through Windows directly, while the desktop
 * window's audio goes through WSLg's PulseAudio→RDP channel, which stutters and stalls.
 * Open http://127.0.0.1:5173 (with WSL's mirrored networking, `localhost` can hang).
 */
export default defineConfig({
  root: resolve(__dirname, 'src/renderer'),
  envDir: resolve(__dirname, '../..'),
  plugins: [react()],
  server: { host: '127.0.0.1', port: 5173, strictPort: true },
})
