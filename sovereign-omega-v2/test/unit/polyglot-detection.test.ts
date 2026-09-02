import { describe, expect, it } from 'vitest'
import { POLYGLOT_FRONTIER_CATALOG } from '../../src/polyglot/fabric'
import {
  TOOLCHAIN_DETECTOR_REGISTRY,
  ToolchainDetectionError,
  ToolchainUnavailableError,
  admitDetectedToolchain,
  buildToolchainDetectionSpec,
  type ToolchainDetectionObservation,
} from '../../src/polyglot/detection'

const SHA_EXEC = '1'.repeat(64)
const SHA_RECEIPT = '2'.repeat(64)

function observation(
  toolchain_id: string,
  overrides: Partial<ToolchainDetectionObservation> = {},
): ToolchainDetectionObservation {
  return {
    schema_version: 'AEGIS-POLYGLOT-DETECTION-OBSERVATION-V1',
    toolchain_id,
    detected: true,
    toolchain_version: 'v-test-1.0.0',
    executable_digest_sha256: SHA_EXEC,
    capability_receipt_digest: SHA_RECEIPT,
    authority_class: 'NONE',
    authority_effect: 'NONE',
    ...overrides,
  }
}

describe('Polyglot toolchain detection and capability admission', () => {
  it('registers one deterministic detector specification for every catalogued toolchain', () => {
    const ids = TOOLCHAIN_DETECTOR_REGISTRY.map(x => x.toolchain_id)
    expect(new Set(ids).size).toBe(ids.length)
    expect(ids).toEqual(POLYGLOT_FRONTIER_CATALOG.map(x => x.toolchain_id))

    for (const detector of TOOLCHAIN_DETECTOR_REGISTRY) {
      expect(detector.probe_locator.length).toBeGreaterThan(0)
      expect(detector.version_probe.length).toBeGreaterThan(0)
      expect(detector.digest_algorithm).toBe('SHA-256')
      expect(detector.capability_receipt_required).toBe(true)
      expect(detector.authority_class).toBe('NONE')
      expect(detector.authority_effect).toBe('NONE')
    }
  })

  it('builds a pure detection spec without exposing an executor or command runner', () => {
    const spec = buildToolchainDetectionSpec('cvc5')
    expect(spec.toolchain_id).toBe('cvc5')
    expect(spec.probe_locator).toBe('cvc5')
    expect(buildToolchainDetectionSpec.toString()).not.toContain('executor')
    expect(buildToolchainDetectionSpec.toString()).not.toContain('commandRunner')
    expect(buildToolchainDetectionSpec.toString()).not.toContain('mock')
  })

  it('fails closed with TOOLCHAIN_UNAVAILABLE when the detector reports absence', () => {
    expect(() => admitDetectedToolchain(observation('egg', {
      detected: false,
      toolchain_version: null,
      executable_digest_sha256: null,
      capability_receipt_digest: null,
    }))).toThrow(ToolchainUnavailableError)

    try {
      admitDetectedToolchain(observation('egg', {
        detected: false,
        toolchain_version: null,
        executable_digest_sha256: null,
        capability_receipt_digest: null,
      }))
    } catch (error) {
      expect(error).toBeInstanceOf(ToolchainUnavailableError)
      expect((error as ToolchainUnavailableError).code).toBe('TOOLCHAIN_UNAVAILABLE')
    }
  })

  it('rejects malformed detected observations instead of fabricating capability evidence', () => {
    expect(() => admitDetectedToolchain(observation('cvc5', {
      executable_digest_sha256: 'abc',
    }))).toThrow(ToolchainDetectionError)

    expect(() => admitDetectedToolchain(observation('cvc5', {
      capability_receipt_digest: 'def',
    }))).toThrow(ToolchainDetectionError)

    expect(() => admitDetectedToolchain(observation('cvc5', {
      toolchain_version: '',
    }))).toThrow(ToolchainDetectionError)
  })

  it('rejects authority-bearing and unknown toolchain observations', () => {
    expect(() => admitDetectedToolchain(observation('cvc5', {
      authority_effect: 'KNOWLEDGE_ADMISSION' as never,
    }))).toThrow(/AUTHORITY/)

    expect(() => admitDetectedToolchain(observation('not-catalogued'))).toThrow(/UNKNOWN_TOOLCHAIN/)
  })

  it('converts verified detection evidence into authority-neutral capability evidence', () => {
    const capability = admitDetectedToolchain(observation('lean4'))

    expect(capability.schema_version).toBe('AEGIS-POLYGLOT-CAPABILITY-EVIDENCE-V1')
    expect(capability.toolchain_id).toBe('lean4')
    expect(capability.status).toBe('VERIFIED_AVAILABLE')
    expect(capability.toolchain_version).toBe('v-test-1.0.0')
    expect(capability.executable_digest_sha256).toBe(SHA_EXEC)
    expect(capability.source_receipt_digest).toBe(SHA_RECEIPT)
    expect(capability.authority_class).toBe('NONE')
    expect(capability.authority_effect).toBe('NONE')
    expect(Object.isFrozen(capability)).toBe(true)
  })
})
