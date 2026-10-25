import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { test } from 'node:test'
import { serverGrantAllowsProduct } from '../packages/shared/lib/access.ts'

const full = {
  plan: 'full',
  tools: ['platform-picker', 'hook-generator', 'content-calendar'],
  grantedAt: 1,
  exp: 4102444800000,
}
const single = { ...full, plan: 'single', tools: ['platform-picker'] }

test('allows only explicitly entitled products', () => {
  assert.equal(serverGrantAllowsProduct(full, 'hook-generator'), true)
  assert.equal(serverGrantAllowsProduct(single, 'platform-picker'), true)
})
test('rejects a signed grant for the wrong product', () => {
  assert.equal(serverGrantAllowsProduct(single, 'hook-generator'), false)
})
test('fails closed for null or malformed permissions', () => {
  assert.equal(serverGrantAllowsProduct(null, 'hook-generator'), false)
  assert.equal(serverGrantAllowsProduct({ ...full, tools: undefined }, 'hook-generator'), false)
  assert.equal(serverGrantAllowsProduct({ ...full, tools: {} }, 'hook-generator'), false)
  assert.equal(serverGrantAllowsProduct({ ...full, tools: ['hook-generator', 3] }, 'hook-generator'), false)
})
test('uses exact product names, not substring matches', () => {
  assert.equal(serverGrantAllowsProduct({ ...full, tools: ['hook-generator-preview'] }, 'hook-generator'), false)
})
test('new-token and stored-token paths enforce identical entitlement checks', () => {
  const source = readFileSync(new URL('../packages/shared/components/AccessGate.tsx', import.meta.url), 'utf8')
  assert.equal((source.match(/serverGrantAllowsProduct\(serverPayload, product\)/g) || []).length, 2)
  assert.ok(!source.includes('if (serverPayload) { setUnlocked(true)'))
})
