import test from 'node:test'
import assert from 'node:assert/strict'
import {shouldDismissDisclosure} from '../src/lib/disclosure.ts'
const inside = { label: 'inside' }
const trigger = { label: 'toggle' }
const outside = { label: 'outside' }
const menu = { contains(node) { return node === inside } }
const toggle = { contains(node) { return node === trigger } }

test('outside pointer closes menu', () => assert.equal(shouldDismissDisclosure(outside,menu,toggle),true))
test('focus entering an unrelated control closes menu', () => assert.equal(shouldDismissDisclosure(outside,menu,toggle),true))
test('internal navigation link does not close prematurely', () => assert.equal(shouldDismissDisclosure(inside,menu,toggle),false))
test('toggle is not treated as outside on pointerdown', () => assert.equal(shouldDismissDisclosure(trigger,menu,toggle),false))
test('missing menu ref does not infer outside event', () => assert.equal(shouldDismissDisclosure(outside,null,toggle),false))
test('missing toggle ref does not infer outside event', () => assert.equal(shouldDismissDisclosure(outside,menu,null),false))
