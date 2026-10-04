export interface WindowsAppDetails {
  appId: string
  appIconPath?: string
  appIconIndex?: number
}

export interface WindowsAppDetailsTarget {
  setAppDetails(details: WindowsAppDetails): void
}

export function windowsAppDetails(appId: string, iconPath?: string): WindowsAppDetails {
  if (!iconPath) {
    return { appId }
  }

  return {
    appId,
    appIconPath: iconPath,
    appIconIndex: 0
  }
}

export function applyWindowsAppIdentity(
  target: WindowsAppDetailsTarget,
  opts: {
    isWindows: boolean
    appId: string
    iconPath?: string
  }
): void {
  if (!opts.isWindows) {
    return
  }

  target.setAppDetails(windowsAppDetails(opts.appId, opts.iconPath))
}
