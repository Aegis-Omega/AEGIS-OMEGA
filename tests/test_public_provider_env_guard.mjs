import assert from 'node:assert/strict'
import { test } from 'node:test'
import { BLOCKED_PUBLIC_PROVIDER_KEYS, assertNoPublicProviderKeys } from '../packages/shared/build/public-provider-env-guard.mjs'

test('rejects every known provider secret exposed through Vite', () => {
  for (const key of BLOCKED_PUBLIC_PROVIDER_KEYS) {
    assert.throws(() => assertNoPublicProviderKeys({ [key]: 'dummy-test-secret-value' }), /Refusing public Vite build/)
  }
})
test('never echoes a sensitive value in errors', () => {
  assert.throws(() => assertNoPublicProviderKeys({ VITE_DASHSCOPE_API_KEY: 'dummy-test-secret-value' }), e => {
    assert.equal(e.message.includes('dummy-test-secret-value'), false)
    return true
  })
})
test('permits server-only credentials without VITE prefix', () => {
  assert.doesNotThrow(() => assertNoPublicProviderKeys({ DASHSCOPE_API_KEY: 'dummy-test-secret-value' }))
})
test('permits non-secret Vite settings and empty optional values', () => {
  assert.doesNotThrow(() => assertNoPublicProviderKeys({ VITE_DASHSCOPE_MODEL: 'qwen-plus', VITE_DASHSCOPE_API_KEY: '' }))
})
test('fails closed for malformed public environment objects', () => {
  assert.doesNotThrow(() => assertNoPublicProviderKeys(undefined))
  assert.doesNotThrow(() => assertNoPublicProviderKeys({ VITE_DASHSCOPE_API_KEY: null }))
})
