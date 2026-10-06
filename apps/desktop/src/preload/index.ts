import { contextBridge } from 'electron'

import type { DesktopBridge } from './bridge'

// Keep this surface minimal: the renderer talks to the backend over WebSocket,
// not through Node APIs.
const bridge: DesktopBridge = {
  platform: process.platform,
}

contextBridge.exposeInMainWorld('desktop', bridge)
