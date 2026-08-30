// ============================================================
// SOVEREIGN OMEGA — Schema Registry
// EPISTEMIC TIER: T0
// Fail closed on schema mismatch.
// Metadata-driven validation only — no semantic inference.
// ============================================================

import type { SHA256Hex } from './types.js'
import { hashValue } from './hashing.js'

export interface SchemaDefinition {
  readonly schema_id: string
  readonly version: string
  readonly fields: readonly SchemaField[]
  readonly migration_from?: string  // previous version for upcast registration
}

export interface SchemaField {
  readonly name: string
  readonly type: 'string' | 'number' | 'boolean' | 'array' | 'object' | 'null' | 'bigint'
  readonly required: boolean
  readonly branded?: string  // branded type name if applicable
}

export interface ValidationResult {
  readonly valid: boolean
  readonly schema_id: string
  readonly version: string
  readonly errors: readonly string[]
}

export class SchemaRegistry {
  private readonly schemas = new Map<string, SchemaDefinition>()
  private readonly versionIndex = new Map<string, string>()  // version → schema_id
  private sealed = false

  register(schema: SchemaDefinition): void {
    if (this.sealed) throw new SchemaRegistryError('SchemaRegistry is sealed. No new schemas after runtime start.')

    const key = `${schema.schema_id}:${schema.version}`
    if (this.schemas.has(key)) throw new SchemaRegistryError(`Schema already registered: ${key}`)

    this.schemas.set(key, Object.freeze(schema))
    this.versionIndex.set(schema.version, schema.schema_id)
  }

  seal(): void { this.sealed = true }

  /**
   * Validate a payload against a registered schema.
   * Fails closed: any unrecognised schema version is a validation failure.
   * Never falls back to lenient validation.
   */
  validate(payload: unknown, schemaId: string, version: string): ValidationResult {
    const key = `${schemaId}:${version}`
    const schema = this.schemas.get(key)

    if (!schema) {
      return {
        valid: false,
        schema_id: schemaId,
        version,
        errors: [`Unknown schema: ${key}. Fail closed — no fallback validation.`],
      }
    }

    const errors: string[] = []

    if (typeof payload !== 'object' || payload === null) {
      return { valid: false, schema_id: schemaId, version, errors: ['Payload must be a non-null object'] }
    }

    const obj = payload as Record<string, unknown>

    for (const field of schema.fields) {
      if (field.required && !(field.name in obj)) {
        errors.push(`Missing required field: ${field.name}`)
        continue
      }
      if (field.name in obj) {
        const val = obj[field.name]
        const actualType = val === null ? 'null' : typeof val === 'object' && Array.isArray(val) ? 'array' : typeof val
        if (actualType !== field.type) {
          errors.push(`Field '${field.name}': expected ${field.type}, got ${actualType}`)
        }
      }
    }

    return { valid: errors.length === 0, schema_id: schemaId, version, errors }
  }

  get(schemaId: string, version: string): SchemaDefinition | undefined {
    return this.schemas.get(`${schemaId}:${version}`)
  }

  async fingerprint(schemaId: string, version: string): Promise<SHA256Hex | null> {
    const schema = this.get(schemaId, version)
    if (!schema) return null
    return hashValue(schema)
  }
}

export const schemaRegistry = new SchemaRegistry()

export class SchemaRegistryError extends Error {
  constructor(message: string) {
    super(message)
    this.name = 'SchemaRegistryError'
  }
}
