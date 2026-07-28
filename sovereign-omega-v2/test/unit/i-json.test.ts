import { describe, expect, it } from 'vitest'
import { assertIJsonValue, IJsonValidationError } from '../../src/core/i-json.js'

describe('assertIJsonValue', () => {
  it('accepts closed plain JSON values and shared acyclic references', () => {
    const shared = { stable: true }
    expect(() => assertIJsonValue({
      null_value: null,
      number: 1.25,
      string: 'omega',
      array: [shared, shared],
    })).not.toThrow()
  })

  it.each([
    ['bigint', { value: 1n }],
    ['undefined', { value: undefined }],
    ['non-finite number', { value: Number.NaN }],
    ['negative zero', { value: -0 }],
    ['non-plain object', { value: new Date(0) }],
    ['unpaired surrogate', { value: '\uD800' }],
  ])('rejects %s values', (_label, value) => {
    expect(() => assertIJsonValue(value)).toThrow(IJsonValidationError)
  })

  it('rejects sparse and extended arrays', () => {
    const sparse = new Array<unknown>(2)
    sparse[1] = 'present'
    expect(() => assertIJsonValue(sparse)).toThrow('sparse or extended arrays')

    const extended = [1] as unknown[] & { extra?: string }
    extended.extra = 'not an array element'
    expect(() => assertIJsonValue(extended)).toThrow('sparse or extended arrays')
  })

  it('rejects cycles without rejecting repeated acyclic values', () => {
    const cycle: { self?: unknown } = {}
    cycle.self = cycle
    expect(() => assertIJsonValue(cycle)).toThrow('contains a cycle')
  })

  it('rejects object and array accessors without invoking them', () => {
    let reads = 0
    const object = {}
    Object.defineProperty(object, 'value', {
      enumerable: true,
      get() { reads += 1; return 'not data' },
    })
    const array = [0]
    Object.defineProperty(array, '0', {
      enumerable: true,
      get() { reads += 1; return 'not data' },
    })

    expect(() => assertIJsonValue(object)).toThrow('enumerable data property')
    expect(() => assertIJsonValue(array)).toThrow('enumerable data property')
    expect(reads).toBe(0)
  })

  it('rejects symbol keys and non-enumerable own properties', () => {
    const symbolArray = [1] as unknown[] & { [key: symbol]: unknown }
    symbolArray[Symbol('unsigned')] = 'not canonical'
    const hiddenObject = { visible: true }
    Object.defineProperty(hiddenObject, 'hidden', {
      enumerable: false,
      value: 'not canonical',
    })

    expect(() => assertIJsonValue(symbolArray)).toThrow('symbol keys')
    expect(() => assertIJsonValue(hiddenObject)).toThrow('only enumerable data properties')
  })
})
