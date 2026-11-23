import { release } from 'node:os'
import { join } from 'node:path'
import { app, BrowserWindow, session, shell } from 'electron'

/**
 * Under WSL the window is drawn through WSLg's RDP bridge. With GPU compositing, resizing
 * or maximizing the window froze it and left WSLg unable to show any Linux window until
 * `wsl --shutdown`. Software rendering is plenty for the avatar's CSS animations; the AI
 * and the voice use the GPU in their own processes. MALFOID_GPU=1 turns it back on.
 */
function isWsl(): boolean {
  return (
    process.platform === 'linux' &&
    (Boolean(process.env['WSL_DISTRO_NAME']) || release().toLowerCase().includes('microsoft'))
  )
}

if (isWsl() && process.env['MALFOID_GPU'] !== '1') {
  app.disableHardwareAcceleration()
}

function createMainWindow(): BrowserWindow {
  const window = new BrowserWindow({
    width: 1100,
    height: 760,
    minWidth: 720,
    minHeight: 520,
    title: 'Virtual Companion',
    backgroundColor: '#14121c',
    show: false,
    webPreferences: {
      preload: join(__dirname, '../preload/index.js'),
      contextIsolation: true,
      sandbox: true,
      nodeIntegration: false,
      // The character's voice plays as soon as a reply arrives, not only after a click.
      autoplayPolicy: 'no-user-gesture-required',
    },
  })

  window.once('ready-to-show', () => window.show())

  // Never navigate the app window away; open external links in the system browser.
  window.webContents.setWindowOpenHandler(({ url }) => {
    if (url.startsWith('https://')) void shell.openExternal(url)
    return { action: 'deny' }
  })
  window.webContents.on('will-navigate', (event) => event.preventDefault())

  const devServerUrl = process.env['ELECTRON_RENDERER_URL']
  if (!app.isPackaged && devServerUrl) {
    void window.loadURL(devServerUrl)
  } else {
    void window.loadFile(join(__dirname, '../renderer/index.html'))
  }
  return window
}

/**
 * Privacy: deny camera/microphone and every other permission until the features that
 * need them exist and the user explicitly turns them on from the UI.
 */
function denyAllPermissions(): void {
  session.defaultSession.setPermissionRequestHandler((_webContents, _permission, callback) => {
    callback(false)
  })
  session.defaultSession.setPermissionCheckHandler(() => false)
}

void app.whenReady().then(() => {
  denyAllPermissions()
  createMainWindow()

  app.on('activate', () => {
    if (BrowserWindow.getAllWindows().length === 0) createMainWindow()
  })
})

app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') app.quit()
})
