// ============================================================
// SOVEREIGN OMEGA — JCS Canonicalization Tests
// BUILD GATE 1: byte-identical output across environments
// ============================================================

import { describe, it, expect } from 'vitest'
import { canonicalizeJCSString, verifyRFC8785Conformance, RFC8785_TEST_VECTORS } from '../../src/core/canonicalize'

describe('RFC 8785 Conformance — Gate 1', () => {
  it('passes all RFC 8785 test vectors', () => {
    const { failed } = verifyRFC8785Conformance()
    expect(failed).toHaveLength(0)
  })

  it('sorts object keys lexicographically', () => {
    expect(canonicalizeJCSString({ z: 1, a: 2, m: 3 })).toBe('{"a":2,"m":3,"z":1}')
  })

  it('sorts nested object keys', () => {
    expect(canonicalizeJCSString({ b: { z: 1, a: 2 }, a: 1 })).toBe('{"a":1,"b":{"a":2,"z":1}}')
  })

  it('handles -0 as 0', () => {
    expect(canonicalizeJCSString(-0)).toBe('0')
  })

  it('handles null', () => {
    expect(canonicalizeJCSString(null)).toBe('null')
  })

  it('handles empty object', () => {
    expect(canonicalizeJCSString({})).toBe('{}')
  })

  it('handles empty array', () => {
    expect(canonicalizeJCSString([])).toBe('[]')
  })

  it('escapes tab characters in strings', () => {
    expect(canonicalizeJCSString('a\tb')).toBe('"a\\tb"')
  })

  it('escapes newlines in strings', () => {
    expect(canonicalizeJCSString('a\nb')).toBe('"a\\nb"')
  })

  it('escapes backslash', () => {
    expect(canonicalizeJCSString('a\\b')).toBe('"a\\\\b"')
  })

  it('escapes double quote', () => {
    expect(canonicalizeJCSString('a"b')).toBe('"a\\"b"')
  })

  it('escapes control characters below 0x20', () => {
    expect(canonicalizeJCSString('\u0000')).toBe('"\\u0000"')
    expect(canonicalizeJCSString('\u001f')).toBe('"\\u001f"')
  })

  it('produces identical output for identical inputs (determinism)', () => {
    const obj = { c: [1, 2, 3], b: true, a: 'hello' }
    const run1 = canonicalizeJCSString(obj)
    const run2 = canonicalizeJCSString(obj)
    const run3 = canonicalizeJCSString(obj)
    expect(run1).toBe(run2)
    expect(run2).toBe(run3)
  })

  it('throws on undefined values', () => {
    expect(() => canonicalizeJCSString(undefined)).toThrow()
  })

  it('throws on Infinity', () => {
    expect(() => canonicalizeJCSString(Infinity)).toThrow()
  })

  it('throws on NaN', () => {
    expect(() => canonicalizeJCSString(NaN)).toThrow()
  })

  it('handles all RFC 8785 test vectors individually', () => {
    for (const vec of RFC8785_TEST_VECTORS) {
      expect(canonicalizeJCSString(vec.input)).toBe(vec.expected)
    }
  })
})
