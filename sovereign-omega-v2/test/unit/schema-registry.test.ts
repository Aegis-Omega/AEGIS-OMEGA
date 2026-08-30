// ============================================================
// SOVEREIGN OMEGA — Schema Registry Tests (T0)
// Verifies: register, seal, validate (fail-closed), get,
// fingerprint, SchemaRegistryError, singleton export.
// ============================================================

import { describe, it, expect } from 'vitest'
import { SchemaRegistry, SchemaRegistryError } from '../../src/core/schema-registry'
import type { SchemaDefinition } from '../../src/core/schema-registry'

// Fresh registry per test — do not use the singleton `schemaRegistry`
// to avoid cross-test state pollution.
function makeRegistry() {
  // Access SchemaRegistry class directly (not the singleton)
  return new (SchemaRegistry as any)() as InstanceType<typeof SchemaRegistry>
}

const SIMPLE_SCHEMA: SchemaDefinition = {
  schema_id: 'test-event',
  version: '1.0.0',
  fields: [
    { name: 'id', type: 'string', required: true },
    { name: 'score', type: 'number', required: true },
    { name: 'active', type: 'boolean', required: false },
  ],
}

describe('SchemaRegistry — registration', () => {

  it('registers and retrieves a schema', () => {
    const reg = makeRegistry()
    reg.register(SIMPLE_SCHEMA)
    const got = reg.get('test-event', '1.0.0')
    expect(got).toBeDefined()
    expect(got?.schema_id).toBe('test-event')
    expect(got?.version).toBe('1.0.0')
  })

  it('registered schema objects are frozen', () => {
    const reg = makeRegistry()
    reg.register(SIMPLE_SCHEMA)
    const got = reg.get('test-event', '1.0.0')!
    expect(Object.isFrozen(got)).toBe(true)
  })

  it('throws SchemaRegistryError on duplicate registration', () => {
    const reg = makeRegistry()
    reg.register(SIMPLE_SCHEMA)
    expect(() => reg.register(SIMPLE_SCHEMA)).toThrow(SchemaRegistryError)
  })

  it('throws SchemaRegistryError after seal()', () => {
    const reg = makeRegistry()
    reg.seal()
    expect(() => reg.register(SIMPLE_SCHEMA)).toThrow(SchemaRegistryError)
  })

  it('seal() message mentions "sealed"', () => {
    const reg = makeRegistry()
    reg.seal()
    let caught: unknown
    try { reg.register(SIMPLE_SCHEMA) } catch (e) { caught = e }
    expect((caught as SchemaRegistryError).message.toLowerCase()).toContain('sealed')
  })

  it('SchemaRegistryError has correct name', () => {
    const reg = makeRegistry()
    reg.seal()
    let caught: unknown
    try { reg.register(SIMPLE_SCHEMA) } catch (e) { caught = e }
    expect((caught as SchemaRegistryError).name).toBe('SchemaRegistryError')
  })

})

describe('SchemaRegistry — validate', () => {

  it('FAILS CLOSED: unknown schema version returns invalid result (does not throw)', () => {
    const reg = makeRegistry()
    const result = reg.validate({ id: 'x', score: 1 }, 'nonexistent', '99.0.0')
    expect(result.valid).toBe(false)
    expect(result.errors.length).toBeGreaterThan(0)
    expect(result.errors[0]).toContain('Unknown schema')
  })

  it('valid payload passes validation', () => {
    const reg = makeRegistry()
    reg.register(SIMPLE_SCHEMA)
    const result = reg.validate({ id: 'abc', score: 7.5 }, 'test-event', '1.0.0')
    expect(result.valid).toBe(true)
    expect(result.errors).toHaveLength(0)
  })

  it('missing required field returns invalid result', () => {
    const reg = makeRegistry()
    reg.register(SIMPLE_SCHEMA)
    const result = reg.validate({ score: 5 }, 'test-event', '1.0.0')  // missing 'id'
    expect(result.valid).toBe(false)
    expect(result.errors.some(e => e.includes('id'))).toBe(true)
  })

  it('wrong field type returns invalid result', () => {
    const reg = makeRegistry()
    reg.register(SIMPLE_SCHEMA)
    const result = reg.validate({ id: 123, score: 5 }, 'test-event', '1.0.0')  // id should be string
    expect(result.valid).toBe(false)
    expect(result.errors.some(e => e.includes("'id'"))).toBe(true)
  })

  it('optional missing field does not cause validation failure', () => {
    const reg = makeRegistry()
    reg.register(SIMPLE_SCHEMA)
    // 'active' is required: false — omitting it is fine
    const result = reg.validate({ id: 'x', score: 0 }, 'test-event', '1.0.0')
    expect(result.valid).toBe(true)
  })

  it('non-object payload fails validation', () => {
    const reg = makeRegistry()
    reg.register(SIMPLE_SCHEMA)
    expect(reg.validate(null, 'test-event', '1.0.0').valid).toBe(false)
    expect(reg.validate('string', 'test-event', '1.0.0').valid).toBe(false)
    expect(reg.validate(42, 'test-event', '1.0.0').valid).toBe(false)
  })

  it('validate result includes schema_id and version', () => {
    const reg = makeRegistry()
    const result = reg.validate({}, 'ghost-schema', '0.0.1')
    expect(result.schema_id).toBe('ghost-schema')
    expect(result.version).toBe('0.0.1')
  })

})

describe('SchemaRegistry — fingerprint', () => {

  it('returns a 64-char hex string for a known schema', async () => {
    const reg = makeRegistry()
    reg.register(SIMPLE_SCHEMA)
    const fp = await reg.fingerprint('test-event', '1.0.0')
    expect(fp).not.toBeNull()
    expect(fp).toMatch(/^[0-9a-f]{64}$/)
  })

  it('returns null for an unknown schema', async () => {
    const reg = makeRegistry()
    const fp = await reg.fingerprint('nonexistent', '1.0.0')
    expect(fp).toBeNull()
  })

  it('fingerprint is deterministic — 3 calls produce identical hash', async () => {
    const reg = makeRegistry()
    reg.register(SIMPLE_SCHEMA)
    const [f1, f2, f3] = await Promise.all([
      reg.fingerprint('test-event', '1.0.0'),
      reg.fingerprint('test-event', '1.0.0'),
      reg.fingerprint('test-event', '1.0.0'),
    ])
    expect(f1).toBe(f2)
    expect(f2).toBe(f3)
  })

})
