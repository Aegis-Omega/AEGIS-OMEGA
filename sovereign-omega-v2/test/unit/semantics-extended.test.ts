// ============================================================
// Semantics Extended Tests — core/semantics.ts
// Targets uncovered branches in isReplaySafe:
//   bigint → true
//   symbol → false
//   function → false
//   circular reference → false
//   array with undefined element → false
//   object with undefined value (silently dropped) → continues
// Also covers assertReplaySafe throw and classifyNumber all branches.
// ============================================================

import { describe, it, expect } from 'vitest'
import {
  isReplaySafe,
  assertReplaySafe,
  classifyNumber,
  ReplaySafetyViolation,
} from '../../src/core/semantics.js'

// ─── ReplaySafetyViolation ────────────────────────────────

describe('ReplaySafetyViolation', () => {
  it('is an Error with correct name', () => {
    const e = new ReplaySafetyViolation('test')
    expect(e).toBeInstanceOf(Error)
    expect(e.name).toBe('ReplaySafetyViolation')
    expect(e.message).toBe('test')
  })
})

// ─── isReplaySafe: primitive types ───────────────────────

describe('isReplaySafe: bigint → true', () => {
  it('bigint is replay-safe', () => {
    expect(isReplaySafe(0n)).toBe(true)
    expect(isReplaySafe(BigInt(999))).toBe(true)
  })
})

describe('isReplaySafe: symbol → false', () => {
  it('symbol is not replay-safe', () => {
    expect(isReplaySafe(Symbol('x'))).toBe(false)
  })
})

describe('isReplaySafe: function → false', () => {
  it('function is not replay-safe', () => {
    expect(isReplaySafe(() => {})).toBe(false)
    expect(isReplaySafe(function named() {})).toBe(false)
  })
})

// ─── isReplaySafe: circular reference ────────────────────

describe('isReplaySafe: circular reference → false', () => {
  it('object with circular reference is not replay-safe', () => {
    const obj: Record<string, unknown> = {}
    obj['self'] = obj
    expect(isReplaySafe(obj)).toBe(false)
  })

  it('nested circular reference is not replay-safe', () => {
    const a: Record<string, unknown> = {}
    const b: Record<string, unknown> = {}
    a['b'] = b
    b['a'] = a
    expect(isReplaySafe(a)).toBe(false)
  })
})

// ─── isReplaySafe: array edge cases ──────────────────────

describe('isReplaySafe: arrays', () => {
  it('array with undefined element → false', () => {
    expect(isReplaySafe([1, undefined, 3])).toBe(false)
  })

  it('empty array → true', () => {
    expect(isReplaySafe([])).toBe(true)
  })

  it('array with nested non-safe value → false', () => {
    expect(isReplaySafe([1, Symbol('x')])).toBe(false)
  })

  it('array with bigint elements → true', () => {
    expect(isReplaySafe([1n, 2n, 3n])).toBe(true)
  })
})

// ─── isReplaySafe: object edge cases ─────────────────────

describe('isReplaySafe: objects', () => {
  it('object with undefined value — silently dropped, still safe', () => {
    // undefined object values are dropped per canonicalize.ts:57
    expect(isReplaySafe({ a: 1, b: undefined })).toBe(true)
  })

  it('object with non-safe nested value → false', () => {
    expect(isReplaySafe({ x: Symbol('bad') })).toBe(false)
  })

  it('null is replay-safe', () => {
    expect(isReplaySafe(null)).toBe(true)
  })

  it('deeply nested safe object → true', () => {
    expect(isReplaySafe({ a: { b: { c: 'ok', d: 42, e: true } } })).toBe(true)
  })
})

// ─── assertReplaySafe ─────────────────────────────────────

describe('assertReplaySafe', () => {
  it('does not throw for safe value', () => {
    expect(() => assertReplaySafe({ x: 1 }, 'test')).not.toThrow()
  })

  it('throws ReplaySafetyViolation for unsafe value', () => {
    expect(() => assertReplaySafe(NaN, 'myField')).toThrow(ReplaySafetyViolation)
  })

  it('thrown message includes the label', () => {
    expect(() => assertReplaySafe(Infinity, 'myLabel')).toThrow("'myLabel'")
  })

  it('throws for symbol', () => {
    expect(() => assertReplaySafe(Symbol('bad'), 'sym')).toThrow(ReplaySafetyViolation)
  })
})

// ─── classifyNumber ───────────────────────────────────────

describe('classifyNumber', () => {
  it('returns "finite" for regular numbers', () => {
    expect(classifyNumber(0)).toBe('finite')
    expect(classifyNumber(3.14)).toBe('finite')
    expect(classifyNumber(-100)).toBe('finite')
  })

  it('returns "nan" for NaN', () => {
    expect(classifyNumber(NaN)).toBe('nan')
  })

  it('returns "positive_infinity" for Infinity', () => {
    expect(classifyNumber(Infinity)).toBe('positive_infinity')
  })

  it('returns "negative_infinity" for -Infinity', () => {
    expect(classifyNumber(-Infinity)).toBe('negative_infinity')
  })
})
