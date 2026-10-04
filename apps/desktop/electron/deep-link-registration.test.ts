import assert from 'node:assert/strict'

import { test } from 'vitest'

import { shouldRegisterDeepLinkProtocol } from './deep-link-registration'

test('registers by default', () => {
  assert.equal(shouldRegisterDeepLinkProtocol({}), true)
})

test('registers when the opt-out is empty, zero, or any other value', () => {
  assert.equal(shouldRegisterDeepLinkProtocol({ HERMES_DESKTOP_SKIP_PROTOCOL_REGISTRATION: '' }), true)
  assert.equal(shouldRegisterDeepLinkProtocol({ HERMES_DESKTOP_SKIP_PROTOCOL_REGISTRATION: '0' }), true)
  assert.equal(shouldRegisterDeepLinkProtocol({ HERMES_DESKTOP_SKIP_PROTOCOL_REGISTRATION: 'true' }), true)
})

test('skips only when the opt-out is exactly 1', () => {
  assert.equal(shouldRegisterDeepLinkProtocol({ HERMES_DESKTOP_SKIP_PROTOCOL_REGISTRATION: '1' }), false)
})
