export interface DesktopBridge {
  readonly platform: string
}

declare global {
  interface Window {
    readonly desktop?: DesktopBridge
  }
}
