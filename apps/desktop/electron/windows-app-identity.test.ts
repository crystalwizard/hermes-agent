import assert from 'node:assert/strict'

import { test } from 'vitest'

import { applyWindowsAppIdentity, windowsAppDetails, type WindowsAppDetails } from './windows-app-identity'

test('windowsAppDetails binds the app id and resolved icon', () => {
  assert.deepEqual(windowsAppDetails('com.example.ari', 'F:\\Ari\\Ari.ico'), {
    appId: 'com.example.ari',
    appIconPath: 'F:\\Ari\\Ari.ico',
    appIconIndex: 0
  })
})

test('windowsAppDetails keeps the app id when no icon resolves', () => {
  assert.deepEqual(windowsAppDetails('com.example.hermes'), {
    appId: 'com.example.hermes'
  })
})

test('applyWindowsAppIdentity applies details only on Windows', () => {
  const calls: WindowsAppDetails[] = []
  const target = {
    setAppDetails(details: WindowsAppDetails) {
      calls.push(details)
    }
  }

  applyWindowsAppIdentity(target, {
    isWindows: false,
    appId: 'com.example.hermes',
    iconPath: '/tmp/hermes.png'
  })
  applyWindowsAppIdentity(target, {
    isWindows: true,
    appId: 'com.example.ari',
    iconPath: 'F:\\Ari\\Ari.ico'
  })

  assert.deepEqual(calls, [
    {
      appId: 'com.example.ari',
      appIconPath: 'F:\\Ari\\Ari.ico',
      appIconIndex: 0
    }
  ])
})
