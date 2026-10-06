// VS Code's integrated terminal exports ELECTRON_RUN_AS_NODE=1, which makes Electron
// start as plain Node (`app` is undefined). Clear it before launching electron-vite.
import { spawn } from 'node:child_process'

delete process.env.ELECTRON_RUN_AS_NODE

const child = spawn('electron-vite', process.argv.slice(2), { stdio: 'inherit', shell: true })
child.on('exit', (code) => process.exit(code ?? 0))
