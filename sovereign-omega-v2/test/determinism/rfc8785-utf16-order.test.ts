import { describe, it, expect } from 'vitest'
import { canonicalizeJCSString } from '../../src/core/canonicalize.js'

// Narrow independent oracle for the integer/string JSON cases below.
// JavaScript Array.sort without a comparator orders UTF-16 code units.
function reference(value: unknown): string {
  if (value === null || typeof value !== 'object') return JSON.stringify(value)
  if (Array.isArray(value)) return '[' + value.map(reference).join(',') + ']'
  const rec = value as Record<string, unknown>
  return '{' + Object.keys(rec).sort()
    .map(k => JSON.stringify(k) + ':' + reference(rec[k])).join(',') + '}'
}

describe('RFC 8785 section 3.2.3 UTF-16 key order', () => {
  it('places a supplementary-plane key before a BMP private-use key', () => {
    expect(canonicalizeJCSString({ '\uE000': 1, '😀': 2 }))
      .toBe('{"😀":2,"\uE000":1}')
  })

  it('matches the RFC property sort example', () => {
    const input = { '\u20ac': 'Euro Sign', '\r': 'Carriage Return',
      '\ufb33': 'Hebrew Letter Dalet With Dagesh',
      '1': 'One', '😀': 'Emoji: Grinning Face',
      '\u0080': 'Control', '\u00f6': 'Latin Small Letter O With Diaeresis' }
    expect(canonicalizeJCSString(input)).toBe(reference(input))
  })

  it('retains Unicode payloads while sorting nested keys', () => {
    const input = { outer: [{ '\uE000': '漢字', '😀': '🧪' }], name: 'café' }
    expect(canonicalizeJCSString(input)).toBe(reference(input))
  })

  it('passes 570 deterministic pair, permutation and nesting cases', () => {
    const keys = ['', 'a', 'aa', 'a0', 'z', '\u0080', '\u00f6', '\u20ac',
      '\uD7FF', '\uE000', '\uFB33', '\uFFFF', '中文', '😀', '🧪',
      'a😀', 'a\uE000', '\u{10000}', '\u{10FFFF}', '🌌']
    let count = 0
    for (let i = 0; i < keys.length; i++) {
      for (let j = i + 1; j < keys.length; j++) {
        const a = keys[i]!, b = keys[j]!
        for (const obj of [
          { [a]: 1, [b]: 2 },
          { [b]: 2, [a]: 1 },
          { outer: [{ [a]: 1, [b]: 2 }, { [b]: 2, [a]: 1 }] },
        ]) {
          expect(canonicalizeJCSString(obj)).toBe(reference(obj))
          count++
        }
      }
    }
    expect(count).toBe(570)
  })
})
