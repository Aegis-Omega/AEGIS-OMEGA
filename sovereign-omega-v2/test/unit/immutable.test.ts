import { describe, it, expect } from 'vitest'
import { deepFreeze, assertFrozen, assertNoSharedReferences, withImmutableBoundary, ImmutabilityViolationError } from '../../src/core/immutable'

describe('Immutability Infrastructure — Gate 3', () => {
  it('deeply freezes nested objects', () => {
    const obj = deepFreeze({ a: { b: { c: 1 } } })
    expect(Object.isFrozen(obj)).toBe(true)
    expect(Object.isFrozen(obj.a)).toBe(true)
    expect(Object.isFrozen(obj.a.b)).toBe(true)
  })

  it('deeply freezes arrays', () => {
    const arr = deepFreeze([1, { x: 2 }, [3]])
    expect(Object.isFrozen(arr)).toBe(true)
    expect(Object.isFrozen(arr[1])).toBe(true)
    expect(Object.isFrozen(arr[2])).toBe(true)
  })

  it('assertFrozen passes for frozen objects', () => {
    const frozen = deepFreeze({ a: 1, b: { c: 2 } })
    expect(() => assertFrozen(frozen)).not.toThrow()
  })

  it('assertFrozen throws for unfrozen objects', () => {
    expect(() => assertFrozen({ a: 1 })).toThrow(ImmutabilityViolationError)
  })

  it('assertNoSharedReferences passes for independent objects', () => {
    const a = deepFreeze({ x: 1 })
    const b = deepFreeze({ x: 2 })
    expect(() => assertNoSharedReferences(a, b)).not.toThrow()
  })

  it('assertNoSharedReferences throws for same reference', () => {
    const obj = deepFreeze({ x: 1 })
    expect(() => assertNoSharedReferences(obj, obj)).toThrow(ImmutabilityViolationError)
  })

  it('withImmutableBoundary freezes output state', () => {
    const reducer = (state: { count: number }) => ({ count: state.count + 1 })
    const wrapped = withImmutableBoundary(reducer)
    const initial = deepFreeze({ count: 0 })
    const next = wrapped(initial, undefined)
    expect(Object.isFrozen(next)).toBe(true)
    expect(next.count).toBe(1)
  })

  it('withImmutableBoundary throws on unfrozen input', () => {
    const reducer = (state: { count: number }) => ({ count: state.count + 1 })
    const wrapped = withImmutableBoundary(reducer)
    expect(() => wrapped({ count: 0 }, undefined)).toThrow(ImmutabilityViolationError)
  })

  it('prevents mutation of frozen objects', () => {
    const obj = deepFreeze({ x: 1 })
    expect(() => { (obj as { x: number }).x = 2 }).toThrow()
  })
})
