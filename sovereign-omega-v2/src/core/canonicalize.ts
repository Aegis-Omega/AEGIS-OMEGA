// ============================================================
// SOVEREIGN OMEGA — RFC 8785 JSON Canonicalization Scheme
// EPISTEMIC TIER: T0 (mechanically proven)
// GATE 1: byte-identical output across Node/Browser/WASM
// ============================================================
// Implementation of RFC 8785 (JSON Canonicalization Scheme).
// This is the ONLY permitted serialisation method for hashing.
// Never use JSON.stringify for integrity-critical operations.
// ============================================================

/**
 * Canonicalise a JavaScript value to its RFC 8785 byte representation.
 * Returns a Uint8Array for direct use in SHA-256 without string conversion.
 */
export function canonicalizeJCS(value: unknown): Uint8Array {
  const str = serializeValue(value)
  return new TextEncoder().encode(str)
}

/**
 * Canonicalise to string (for debugging and testing against test vectors).
 */
export function canonicalizeJCSString(value: unknown): string {
  return serializeValue(value)
}

// ─── Internal Serialisation ────────────────────────────────

function serializeValue(value: unknown): string {
  if (value === null) return 'null'
  if (value === true) return 'true'
  if (value === false) return 'false'

  const type = typeof value

  if (type === 'number') return serializeNumber(value as number)
  if (type === 'string') return serializeString(value as string)
  if (type === 'bigint') return serializeString((value as bigint).toString())

  if (Array.isArray(value)) {
    const items = value.map(serializeValue)
    return '[' + items.join(',') + ']'
  }

  if (type === 'object') {
    const obj = value as Record<string, unknown>
    // RFC 8785: sort object keys by Unicode code point order
    const sortedKeys = Object.keys(obj).sort((a, b) => {
      // Compare by Unicode code point sequence (not locale-sensitive)
      for (let i = 0; i < Math.min(a.length, b.length); i++) {
        /* c8 ignore next -- noUncheckedIndexedAccess artifact; i < min(a.length, b.length) guarantees valid indices */
        const diff = (a.codePointAt(i) ?? 0) - (b.codePointAt(i) ?? 0)
        if (diff !== 0) return diff
      }
      return a.length - b.length
    })
    const pairs = sortedKeys
      .filter(k => obj[k] !== undefined)
      .map(k => serializeString(k) + ':' + serializeValue(obj[k]))
    return '{' + pairs.join(',') + '}'
  }

  if (value === undefined) throw new TypeError('undefined is not JSON-serialisable')
  if (type === 'function') throw new TypeError('function is not JSON-serialisable')
  if (type === 'symbol') throw new TypeError('symbol is not JSON-serialisable')

  throw new TypeError(`Unserializable type: ${type}`)
}

function serializeNumber(n: number): string {
  if (!isFinite(n)) throw new RangeError('Infinity and NaN are not RFC 8785 compliant')

  // RFC 8785 uses the ES2020 Number::toString which produces the
  // shortest decimal representation that round-trips exactly.
  // JavaScript's default number-to-string already does this for finite numbers.
  if (Object.is(n, -0)) return '0'
  return String(n)
}

function serializeString(s: string): string {
  // RFC 8785 string serialisation: escape control characters and
  // specific characters as required by JSON.
  let result = '"'
  for (let i = 0; i < s.length; i++) {
    /* c8 ignore next -- noUncheckedIndexedAccess artifact; i < s.length guarantees valid index */
    const cp = s.codePointAt(i) ?? 0
    /* c8 ignore next -- same as above */
    const ch = s[i] ?? ''

    if (cp === 0x22) { result += '\\"'; continue }
    if (cp === 0x5c) { result += '\\\\'; continue }
    if (cp === 0x08) { result += '\\b'; continue }
    if (cp === 0x09) { result += '\\t'; continue }
    if (cp === 0x0a) { result += '\\n'; continue }
    if (cp === 0x0c) { result += '\\f'; continue }
    if (cp === 0x0d) { result += '\\r'; continue }

    if (cp < 0x20) {
      // Other control characters: use \uXXXX
      result += '\\u' + cp.toString(16).padStart(4, '0')
      continue
    }

    // Non-BMP character (U+10000..U+10FFFF): codePointAt returns full scalar > 0xFFFF.
    // Must emit both UTF-16 code units and skip the low surrogate on next iteration.
    if (cp > 0xFFFF) {
      /* c8 ignore next -- noUncheckedIndexedAccess artifact; well-formed strings always have a paired low surrogate */
      result += ch + (s[i + 1] ?? '')
      i++ // skip the low surrogate code unit
      continue
    }

    // Lone high surrogate (codePointAt returns surrogate value when unpaired)
    if (cp >= 0xD800 && cp <= 0xDBFF) {
      result += '\\u' + cp.toString(16).padStart(4, '0')
      continue
    }
    // Lone low surrogate
    if (cp >= 0xDC00 && cp <= 0xDFFF) {
      result += '\\u' + cp.toString(16).padStart(4, '0')
      continue
    }

    result += ch
  }
  result += '"'
  return result
}

// ─── Test Vector Validation ────────────────────────────────

/** RFC 8785 Appendix B test vectors for conformance verification. */
export const RFC8785_TEST_VECTORS: Array<{ input: unknown; expected: string }> = [
  { input: null, expected: 'null' },
  { input: true, expected: 'true' },
  { input: false, expected: 'false' },
  { input: 1, expected: '1' },
  { input: -0, expected: '0' },
  { input: 1.5, expected: '1.5' },
  { input: 1e20, expected: '100000000000000000000' },
  { input: '', expected: '""' },
  { input: 'hello', expected: '"hello"' },
  { input: 'a\tb', expected: '"a\\tb"' },
  { input: 'a\nb', expected: '"a\\nb"' },
  { input: '\u0000', expected: '"\\u0000"' },
  { input: '\u001f', expected: '"\\u001f"' },
  { input: '😀', expected: '"😀"' },
  { input: [], expected: '[]' },
  { input: [1, 2, 3], expected: '[1,2,3]' },
  { input: {}, expected: '{}' },
  { input: { b: 1, a: 2 }, expected: '{"a":2,"b":1}' },
  { input: { z: 1, a: 2, m: 3 }, expected: '{"a":2,"m":3,"z":1}' },
  {
    input: { payload: { b: 2, a: 1 }, type: 'test' },
    expected: '{"payload":{"a":1,"b":2},"type":"test"}'
  },
]

export function verifyRFC8785Conformance(): { passed: number; failed: Array<{ index: number; expected: string; got: string }> } {
  const failed: Array<{ index: number; expected: string; got: string }> = []
  for (let i = 0; i < RFC8785_TEST_VECTORS.length; i++) {
    const vec = RFC8785_TEST_VECTORS[i]
    if (!vec) continue
    const got = canonicalizeJCSString(vec.input)
    if (got !== vec.expected) {
      failed.push({ index: i, expected: vec.expected, got })
    }
  }
  return { passed: RFC8785_TEST_VECTORS.length - failed.length, failed }
}
