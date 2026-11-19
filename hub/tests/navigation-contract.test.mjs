import test from 'node:test'
import assert from 'node:assert/strict'
import {FIRST_VALUE_ACTION} from '../src/lib/navigationContract.ts'

test('first action opens a real product route', () => {
  assert.equal(FIRST_VALUE_ACTION.href, '/console')
  assert.equal(FIRST_VALUE_ACTION.label, 'Open console')
})
test('public CTA is not disguised pricing or external redirect', () => {
  assert.notEqual(FIRST_VALUE_ACTION.href, '/pricing')
  assert.match(FIRST_VALUE_ACTION.href, /^\/[a-z-]+$/)
  assert.doesNotMatch(FIRST_VALUE_ACTION.href, /claim-sponsor|checkout|buy|pay/i)
})
test('visually abbreviated phone CTA retains an explicit accessible name', () => {
  assert.match(FIRST_VALUE_ACTION.accessibleName, /AEGIS operator console/)
})
test('navigation by itself never asserts execution authority', () => {
  assert.equal(FIRST_VALUE_ACTION.authorityEffect, 'NONE')
})
test('single frozen contract prevents accidental runtime mutation', () => {
  assert.equal(Object.isFrozen(FIRST_VALUE_ACTION), true)
  assert.throws(() => {FIRST_VALUE_ACTION.href = '/pricing'}, TypeError)
})
test('the first-value action is a read-only route with no checkout parameters', () => {
  assert.deepEqual(Object.keys(FIRST_VALUE_ACTION).sort(), ['accessibleName','authorityEffect','href','label'].sort())
  assert.equal(FIRST_VALUE_ACTION.href.includes('?'), false)
})
