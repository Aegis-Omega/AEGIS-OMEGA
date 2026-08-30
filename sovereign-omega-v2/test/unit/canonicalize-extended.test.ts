// ============================================================
// Canonicalize Extended Tests — core/canonicalize.ts
// Targets uncovered branches:
//   function/symbol inputs → TypeError throws
//   backspace (\x08), form feed (\x0c), CR (\x0d) escape paths
//   lone high surrogate (\uD800), lone low surrogate (\uDC00)
// ============================================================

import { describe, it, expect } from 'vitest'
import { canonicalizeJCSString } from '../../src/core/canonicalize.js'

// ─── Non-JSON-serialisable types ─────────────────────────────

describe('canonicalizeJCSString: non-serialisable inputs', () => {
  it('throws TypeError for a function value', () => {
    expect(() => canonicalizeJCSString(() => {})).toThrow(TypeError)
  })

  it('error message mentions function', () => {
    expect(() => canonicalizeJCSString(function named() {})).toThrow(/function/)
  })

  it('throws TypeError for a Symbol value', () => {
    expect(() => canonicalizeJCSString(Symbol('test'))).toThrow(TypeError)
  })

  it('error message mentions symbol', () => {
    expect(() => canonicalizeJCSString(Symbol())).toThrow(/symbol/)
  })

  it('function inside array throws', () => {
    expect(() => canonicalizeJCSString([1, () => {}, 2])).toThrow(TypeError)
  })

  it('symbol inside object value throws', () => {
    expect(() => canonicalizeJCSString({ a: Symbol('s') })).toThrow(TypeError)
  })
})

// ─── Control character escape paths ──────────────────────────

describe('canonicalizeJCSString: control character escaping', () => {
  it('escapes backspace \\x08 as \\b', () => {
    expect(canonicalizeJCSString('\x08')).toBe('"\\b"')
  })

  it('escapes form feed \\x0c as \\f', () => {
    expect(canonicalizeJCSString('\x0c')).toBe('"\\f"')
  })

  it('escapes carriage return \\x0d as \\r', () => {
    expect(canonicalizeJCSString('\x0d')).toBe('"\\r"')
  })

  it('backspace inside a longer string', () => {
    expect(canonicalizeJCSString('a\x08b')).toBe('"a\\bb"')
  })
})

// ─── Lone surrogate handling ──────────────────────────────────

describe('canonicalizeJCSString: lone surrogates', () => {
  it('escapes lone high surrogate \\uD800', () => {
    const highSurrogate = String.fromCharCode(0xD800)
    const result = canonicalizeJCSString(highSurrogate)
    expect(result).toBe('"\\ud800"')
  })

  it('escapes lone low surrogate \\uDC00', () => {
    const lowSurrogate = String.fromCharCode(0xDC00)
    const result = canonicalizeJCSString(lowSurrogate)
    expect(result).toBe('"\\udc00"')
  })

  it('escapes lone high surrogate at end of DBFF range', () => {
    const result = canonicalizeJCSString(String.fromCharCode(0xDBFF))
    expect(result).toBe('"\\udbff"')
  })

  it('escapes lone low surrogate at end of DFFF range', () => {
    const result = canonicalizeJCSString(String.fromCharCode(0xDFFF))
    expect(result).toBe('"\\udfff"')
  })
})
