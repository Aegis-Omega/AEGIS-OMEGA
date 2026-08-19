// ============================================================
// SOVEREIGN OMEGA - I-JSON Runtime Boundary
// EPISTEMIC TIER: T2 - deterministic, tested validation primitive
//
// Integrity roots are defined over JSON values. Reject JavaScript values
// whose canonical form can alias a different stored value (for example,
// bigint versus string or an omitted undefined member).
// ============================================================

export class IJsonValidationError extends Error {
  override readonly name = 'IJsonValidationError'

  constructor(message: string) {
    super(message)
    Object.setPrototypeOf(this, new.target.prototype)
  }
}

export function assertIJsonValue(value: unknown, label = 'value'): void {
  visit(value, label, new WeakSet<object>())
}

function visit(value: unknown, path: string, ancestors: WeakSet<object>): void {
  if (value === null || typeof value === 'boolean') return
  if (typeof value === 'string') {
    assertWellFormedUnicode(value, path)
    return
  }
  if (typeof value === 'number') {
    if (!Number.isFinite(value)) {
      throw new IJsonValidationError(`${path} must contain only finite numbers`)
    }
    if (Object.is(value, -0)) {
      throw new IJsonValidationError(`${path} must not contain negative zero`)
    }
    return
  }
  if (typeof value !== 'object') {
    throw new IJsonValidationError(`${path} contains a non-JSON ${typeof value} value`)
  }

  const object = value as object
  if (ancestors.has(object)) {
    throw new IJsonValidationError(`${path} contains a cycle`)
  }
  ancestors.add(object)
  try {
    if (Array.isArray(value)) {
      if (Object.getOwnPropertySymbols(value).length !== 0) {
        throw new IJsonValidationError(`${path} must not contain symbol keys`)
      }
      const ownNames = Object.getOwnPropertyNames(value)
      const keys = Object.keys(value)
      if (ownNames.length !== value.length + 1 || !ownNames.includes('length') ||
          keys.length !== value.length) {
        throw new IJsonValidationError(`${path} must not contain sparse or extended arrays`)
      }
      for (let index = 0; index < value.length; index += 1) {
        if (!Object.prototype.hasOwnProperty.call(value, index) || keys[index] !== String(index)) {
          throw new IJsonValidationError(`${path} must not contain sparse or extended arrays`)
        }
        const descriptor = Object.getOwnPropertyDescriptor(value, String(index))
        if (descriptor === undefined || !descriptor.enumerable || !('value' in descriptor)) {
          throw new IJsonValidationError(`${path}[${index}] must be an enumerable data property`)
        }
        visit(descriptor.value, `${path}[${index}]`, ancestors)
      }
      return
    }

    const prototype = Object.getPrototypeOf(value)
    if (prototype !== Object.prototype && prototype !== null) {
      throw new IJsonValidationError(`${path} must contain only plain objects`)
    }
    if (Object.getOwnPropertySymbols(value).length !== 0) {
      throw new IJsonValidationError(`${path} must not contain symbol keys`)
    }
    const ownNames = Object.getOwnPropertyNames(value)
    const enumerableKeys = Object.keys(value)
    if (ownNames.length !== enumerableKeys.length) {
      throw new IJsonValidationError(`${path} must contain only enumerable data properties`)
    }
    for (const key of ownNames) {
      assertWellFormedUnicode(key, `${path} key`)
      const descriptor = Object.getOwnPropertyDescriptor(value, key)
      if (descriptor === undefined || !descriptor.enumerable || !('value' in descriptor)) {
        throw new IJsonValidationError(`${path}.${key} must be an enumerable data property`)
      }
      visit(descriptor.value, `${path}.${key}`, ancestors)
    }
  } finally {
    ancestors.delete(object)
  }
}

function assertWellFormedUnicode(value: string, path: string): void {
  for (let index = 0; index < value.length; index += 1) {
    const codeUnit = value.charCodeAt(index)
    if (codeUnit >= 0xD800 && codeUnit <= 0xDBFF) {
      const next = value.charCodeAt(index + 1)
      if (!(next >= 0xDC00 && next <= 0xDFFF)) {
        throw new IJsonValidationError(`${path} contains an unpaired UTF-16 surrogate`)
      }
      index += 1
    } else if (codeUnit >= 0xDC00 && codeUnit <= 0xDFFF) {
      throw new IJsonValidationError(`${path} contains an unpaired UTF-16 surrogate`)
    }
  }
}
