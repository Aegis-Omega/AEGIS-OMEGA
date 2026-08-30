// ============================================================
// Immutable Extended Tests — core/immutable.ts
// Targets uncovered branches:
//   deepFreeze: primitive passthrough (L16 arm 0)
//   checkNoSharedRefs: shared nested reference (L66 arm 0)
//   checkNoSharedRefs: circular visited guard (L70 arm 0)
//   withImmutableBoundary: non-object (primitive) state (L110 arm 1)
// ============================================================

import { describe, it, expect } from 'vitest'
import {
  deepFreeze,
  assertNoSharedReferences,
  withImmutableBoundary,
  ImmutabilityViolationError,
} from '../../src/core/immutable.js'

// ─── deepFreeze: primitive passthrough ───────────────────────

describe('deepFreeze: primitive values are returned unchanged', () => {
  it('returns null unchanged', () => {
    expect(deepFreeze(null)).toBeNull()
  })

  it('returns number unchanged', () => {
    expect(deepFreeze(42)).toBe(42)
  })

  it('returns string unchanged', () => {
    expect(deepFreeze('hello')).toBe('hello')
  })

  it('returns undefined unchanged', () => {
    expect(deepFreeze(undefined)).toBeUndefined()
  })

  it('returns boolean unchanged', () => {
    expect(deepFreeze(true)).toBe(true)
  })
})

// ─── checkNoSharedRefs: shared nested reference ───────────────

describe('assertNoSharedReferences: shared nested object throws', () => {
  it('throws ImmutabilityViolationError when nested object is shared', () => {
    const shared = Object.freeze({ nested: true })
    const a = deepFreeze({ x: shared })
    const b = deepFreeze({ x: shared }) // same shared ref for x
    expect(() => assertNoSharedReferences(a, b)).toThrow(ImmutabilityViolationError)
  })

  it('error message contains the path of the shared reference', () => {
    const shared = Object.freeze({ v: 1 })
    const a = deepFreeze({ prop: shared })
    const b = deepFreeze({ prop: shared })
    expect(() => assertNoSharedReferences(a, b)).toThrow(/prop/)
  })

  it('does not throw when nested objects are different instances', () => {
    const a = deepFreeze({ x: { v: 1 } })
    const b = deepFreeze({ x: { v: 1 } })
    expect(() => assertNoSharedReferences(a, b)).not.toThrow()
  })
})

// ─── checkNoSharedRefs: circular visited guard ────────────────

describe('assertNoSharedReferences: circular structure handled without infinite loop', () => {
  it('handles circular reference in orig without infinite recursion', () => {
    // Cannot call deepFreeze on a circular structure — it would stack overflow.
    // Use plain objects with Object.freeze to avoid that, but still cover
    // the visited-set guard path in checkNoSharedRefs.
    const aInner: Record<string, unknown> = { name: 'a' }
    const bInner: Record<string, unknown> = { name: 'b' }
    aInner['self'] = aInner  // circular — aInner.self === aInner
    bInner['self'] = bInner  // circular — bInner.self === bInner
    // checkNoSharedRefs visits aInner, recurses into aInner.self (=aInner again),
    // finds it already in visited → returns (L70 arm 0 covered)
    expect(() => assertNoSharedReferences(
      aInner as unknown as { name: string },
      bInner as unknown as { name: string }
    )).not.toThrow()
  })
})

// ─── withImmutableBoundary: primitive state ───────────────────

describe('withImmutableBoundary: non-object state skips shared-reference check', () => {
  it('works with a numeric state (no assertNoSharedReferences called)', () => {
    const reducer = (state: number, delta: number) => state + delta
    const wrapped = withImmutableBoundary(reducer)
    expect(wrapped(0, 5)).toBe(5)
    expect(wrapped(10, -3)).toBe(7)
  })

  it('works with a string state', () => {
    const reducer = (state: string, suffix: string) => state + suffix
    const wrapped = withImmutableBoundary(reducer)
    expect(wrapped('hello', ' world')).toBe('hello world')
  })

  it('no-op reducer (returns same reference) is allowed for frozen state', () => {
    const state = deepFreeze({ val: 42 })
    const noop = (s: Readonly<{ val: number }>) => s
    const wrapped = withImmutableBoundary(noop)
    expect(wrapped(state, undefined)).toBe(state)
  })
})
