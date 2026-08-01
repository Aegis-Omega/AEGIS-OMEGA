// ============================================================
// SOVEREIGN OMEGA — RFC 8785 JSON Canonicalization Scheme
// EPISTEMIC TIER: T0 deterministic primitive; conformance is test-gated
// GATE 1: byte-identical output across Node/Browser/WASM
// ============================================================
// This is the only permitted serialization method for integrity hashing.
// Callers must project application values into ordinary JSON data first.
// ============================================================

const ESCAPE_PREFIX = String.fromCharCode(0x5c)
const ESCAPED_QUOTE = ESCAPE_PREFIX + '"'
const ESCAPED_BACKSLASH = ESCAPE_PREFIX + ESCAPE_PREFIX
const ESCAPED_BACKSPACE = ESCAPE_PREFIX + 'b'
const ESCAPED_TAB = ESCAPE_PREFIX + 't'
const ESCAPED_NEWLINE = ESCAPE_PREFIX + 'n'
const ESCAPED_FORM_FEED = ESCAPE_PREFIX + 'f'
const ESCAPED_CARRIAGE_RETURN = ESCAPE_PREFIX + 'r'
const ESCAPED_UNICODE_PREFIX = ESCAPE_PREFIX + 'u'

/** Canonicalise an ordinary JSON value to RFC 8785 UTF-8 bytes. */
export function canonicalizeJCS(value: unknown): Uint8Array {
  return new TextEncoder().encode(serializeValue(value, new WeakSet<object>()))
}

/** Canonicalise to a string for tests and diagnostics. */
export function canonicalizeJCSString(value: unknown): string {
  return serializeValue(value, new WeakSet<object>())
}

function serializeValue(value: unknown, stack: WeakSet<object>): string {
  if (value === null) return 'null'
  if (value === true) return 'true'
  if (value === false) return 'false'

  const type = typeof value

  if (type === 'number') return serializeNumber(value as number)
  if (type === 'string') return serializeString(value as string)

  if (type === 'bigint') {
    throw new TypeError(
      'BigInt is not a JSON value; encode it explicitly as a decimal string before JCS canonicalization',
    )
  }
  if (value === undefined) throw new TypeError('undefined is not a JSON value')
  if (type === 'function') throw new TypeError('function is not a JSON value')
  if (type === 'symbol') throw new TypeError('symbol is not a JSON value')

  if (Array.isArray(value)) return serializeArray(value, stack)
  if (type === 'object') return serializeObject(value as object, stack)

  /* c8 ignore next -- all JavaScript value categories are exhausted above */
  throw new TypeError(`Unserializable type: ${type}`)
}

function serializeArray(value: unknown[], stack: WeakSet<object>): string {
  return withCycleGuard(value, stack, () => {
    if (Object.getOwnPropertySymbols(value).length !== 0) {
      throw new TypeError('Symbol-keyed array properties are not JSON values')
    }

    for (const name of Object.getOwnPropertyNames(value)) {
      if (name === 'length') continue
      if (!isCanonicalArrayIndex(name, value.length)) {
        throw new TypeError(
          `Non-index array property is not permitted at the JCS boundary: ${name}`,
        )
      }
    }

    const items: string[] = []
    for (let index = 0; index < value.length; index++) {
      if (!Object.prototype.hasOwnProperty.call(value, index)) {
        throw new TypeError(
          `Sparse arrays are not permitted at the JCS boundary: missing index ${index}`,
        )
      }

      const descriptor = Object.getOwnPropertyDescriptor(value, String(index))
      if (!descriptor || !descriptor.enumerable || !('value' in descriptor)) {
        throw new TypeError(`Array index ${index} must be an enumerable data property`)
      }

      items.push(serializeValue(descriptor.value, stack))
    }

    return '[' + items.join(',') + ']'
  })
}

function serializeObject(value: object, stack: WeakSet<object>): string {
  return withCycleGuard(value, stack, () => {
    const prototype = Object.getPrototypeOf(value)
    if (prototype !== Object.prototype && prototype !== null) {
      throw new TypeError('Only plain JSON objects are permitted at the JCS boundary')
    }

    if (Object.getOwnPropertySymbols(value).length !== 0) {
      throw new TypeError('Symbol-keyed object properties are not JSON values')
    }

    const descriptors = Object.getOwnPropertyDescriptors(value)
    const keys = Object.getOwnPropertyNames(value)

    for (const key of keys) {
      const descriptor = descriptors[key]
      if (!descriptor || !descriptor.enumerable) {
        throw new TypeError(
          `Non-enumerable object property is not permitted at the JCS boundary: ${key}`,
        )
      }
      if (!('value' in descriptor)) {
        throw new TypeError(
          `Accessor object property is not permitted at the JCS boundary: ${key}`,
        )
      }
    }

    keys.sort(compareUtf16CodeUnits)

    return (
      '{' +
      keys
        .map((key) => {
          const descriptor = descriptors[key]
          /* c8 ignore next -- descriptor validity was established above */
          if (!descriptor || !('value' in descriptor)) {
            throw new TypeError(`Invalid object property descriptor: ${key}`)
          }
          return serializeString(key) + ':' + serializeValue(descriptor.value, stack)
        })
        .join(',') +
      '}'
    )
  })
}

function withCycleGuard<T>(value: object, stack: WeakSet<object>, operation: () => T): T {
  if (stack.has(value)) throw new TypeError('Cyclic values are not JSON values')
  stack.add(value)
  try {
    return operation()
  } finally {
    stack.delete(value)
  }
}

function isCanonicalArrayIndex(name: string, length: number): boolean {
  if (!/^(0|[1-9][0-9]*)$/.test(name)) return false
  const index = Number(name)
  return (
    Number.isSafeInteger(index) &&
    index >= 0 &&
    index < length &&
    String(index) === name
  )
}

/** RFC 8785 sorts raw property names by unsigned UTF-16 code units. */
function compareUtf16CodeUnits(left: string, right: string): number {
  const commonLength = Math.min(left.length, right.length)
  for (let index = 0; index < commonLength; index++) {
    const difference = left.charCodeAt(index) - right.charCodeAt(index)
    if (difference !== 0) return difference
  }
  return left.length - right.length
}

function serializeNumber(value: number): string {
  if (!Number.isFinite(value)) {
    throw new RangeError('Infinity and NaN are not RFC 8785 compliant')
  }
  if (Object.is(value, -0)) return '0'
  return String(value)
}

function serializeString(value: string): string {
  assertWellFormedUnicode(value)

  let result = '"'
  for (let index = 0; index < value.length; index++) {
    const codePoint = value.codePointAt(index)
    /* c8 ignore next -- index is in range */
    if (codePoint === undefined) throw new TypeError('Invalid Unicode code point')

    if (codePoint === 0x22) {
      result += ESCAPED_QUOTE
      continue
    }
    if (codePoint === 0x5c) {
      result += ESCAPED_BACKSLASH
      continue
    }
    if (codePoint === 0x08) {
      result += ESCAPED_BACKSPACE
      continue
    }
    if (codePoint === 0x09) {
      result += ESCAPED_TAB
      continue
    }
    if (codePoint === 0x0a) {
      result += ESCAPED_NEWLINE
      continue
    }
    if (codePoint === 0x0c) {
      result += ESCAPED_FORM_FEED
      continue
    }
    if (codePoint === 0x0d) {
      result += ESCAPED_CARRIAGE_RETURN
      continue
    }
    if (codePoint < 0x20) {
      result += ESCAPED_UNICODE_PREFIX + codePoint.toString(16).padStart(4, '0')
      continue
    }

    if (codePoint > 0xffff) {
      result += value.slice(index, index + 2)
      index++
      continue
    }

    result += value[index]
  }

  return result + '"'
}

/** RFC 8785 requires invalid Unicode data, including lone surrogates, to fail. */
function assertWellFormedUnicode(value: string): void {
  for (let index = 0; index < value.length; index++) {
    const codeUnit = value.charCodeAt(index)

    if (codeUnit >= 0xd800 && codeUnit <= 0xdbff) {
      if (index + 1 >= value.length) {
        throw new TypeError('Lone high surrogate is not RFC 8785 compliant')
      }
      const next = value.charCodeAt(index + 1)
      if (next < 0xdc00 || next > 0xdfff) {
        throw new TypeError('Lone high surrogate is not RFC 8785 compliant')
      }
      index++
      continue
    }

    if (codeUnit >= 0xdc00 && codeUnit <= 0xdfff) {
      throw new TypeError('Lone low surrogate is not RFC 8785 compliant')
    }
  }
}

/** RFC 8785 Appendix B and Section 3.2.3 conformance vectors. */
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
    expected: '{"payload":{"a":1,"b":2},"type":"test"}',
  },
  {
    input: {
      '\u20ac': 'Euro Sign',
      '\r': 'Carriage Return',
      '\ufb33': 'Hebrew Letter Dalet With Dagesh',
      '1': 'One',
      '😀': 'Emoji: Grinning Face',
      '\u0080': 'Control',
      '\u00f6': 'Latin Small Letter O With Diaeresis',
    },
    expected:
      '{"\\r":"Carriage Return","1":"One","":"Control","ö":"Latin Small Letter O With Diaeresis","€":"Euro Sign","😀":"Emoji: Grinning Face","דּ":"Hebrew Letter Dalet With Dagesh"}',
  },
]

export function verifyRFC8785Conformance(): {
  passed: number
  failed: Array<{ index: number; expected: string; got: string }>
} {
  const failed: Array<{ index: number; expected: string; got: string }> = []

  for (let index = 0; index < RFC8785_TEST_VECTORS.length; index++) {
    const vector = RFC8785_TEST_VECTORS[index]
    /* c8 ignore next -- index is bounded by the array length */
    if (!vector) continue
    const got = canonicalizeJCSString(vector.input)
    if (got !== vector.expected) {
      failed.push({ index, expected: vector.expected, got })
    }
  }

  return { passed: RFC8785_TEST_VECTORS.length - failed.length, failed }
}
