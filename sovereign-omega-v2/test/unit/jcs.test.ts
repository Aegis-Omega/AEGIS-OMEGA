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

  it('sorts property names by unsigned UTF-16 code units', () => {
    const input = {
      '\u20ac': 'Euro Sign',
      '\r': 'Carriage Return',
      '\ufb33': 'Hebrew Letter Dalet With Dagesh',
      '1': 'One',
      '😀': 'Emoji: Grinning Face',
      '\u0080': 'Control',
      '\u00f6': 'Latin Small Letter O With Diaeresis',
    }

    expect(canonicalizeJCSString(input)).toBe(
      '{"\\r":"Carriage Return","1":"One","":"Control","ö":"Latin Small Letter O With Diaeresis","€":"Euro Sign","😀":"Emoji: Grinning Face","דּ":"Hebrew Letter Dalet With Dagesh"}'
    )
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

  it('throws on undefined values, including nested object properties', () => {
    expect(() => canonicalizeJCSString(undefined)).toThrow(TypeError)
    expect(() => canonicalizeJCSString({ permitted: true, hidden: undefined })).toThrow(TypeError)
  })

  it('throws on BigInt rather than silently changing its type', () => {
    expect(() => canonicalizeJCSString(1n)).toThrow(TypeError)
    expect(() => canonicalizeJCSString({ sequence: 1n })).toThrow(TypeError)
  })

  it('throws on Infinity', () => {
    expect(() => canonicalizeJCSString(Infinity)).toThrow(RangeError)
  })

  it('throws on NaN', () => {
    expect(() => canonicalizeJCSString(NaN)).toThrow(RangeError)
  })

  it('throws on lone surrogate code units in values and property names', () => {
    expect(() => canonicalizeJCSString('\ud800')).toThrow(TypeError)
    expect(() => canonicalizeJCSString('\udc00')).toThrow(TypeError)
    expect(() => canonicalizeJCSString({ ['\ud800']: 'invalid-key' })).toThrow(TypeError)
  })

  it('throws on sparse arrays and non-index array properties', () => {
    const sparse = new Array(2)
    sparse[0] = 'present'
    expect(() => canonicalizeJCSString(sparse)).toThrow(TypeError)

    const extended = [1, 2] as number[] & { extra?: number }
    extended.extra = 3
    expect(() => canonicalizeJCSString(extended)).toThrow(TypeError)
  })

  it('throws on custom objects and accessors without invoking a getter', () => {
    expect(() => canonicalizeJCSString(new Date(0))).toThrow(TypeError)
    expect(() => canonicalizeJCSString(new Map([['a', 1]]))).toThrow(TypeError)

    let invoked = false
    const withAccessor = {}
    Object.defineProperty(withAccessor, 'secret', {
      enumerable: true,
      get() {
        invoked = true
        return 'must-not-run'
      },
    })

    expect(() => canonicalizeJCSString(withAccessor)).toThrow(TypeError)
    expect(invoked).toBe(false)
  })

  it('throws on cycles', () => {
    const cyclic: Record<string, unknown> = {}
    cyclic.self = cyclic
    expect(() => canonicalizeJCSString(cyclic)).toThrow(TypeError)
  })

  it('handles all RFC 8785 test vectors individually', () => {
    for (const vec of RFC8785_TEST_VECTORS) {
      expect(canonicalizeJCSString(vec.input)).toBe(vec.expected)
    }
  })
})
