import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import Ajv2020 from 'ajv/dist/2020.js'
import { describe, expect, it } from 'vitest'
import type { SHA256Hex } from '../../src/core/types.js'
import {
  HOLONNGRAM_COMPILER_VERSION,
  HOLONNGRAM_VISUAL_FEEDBACK_SCHEMA_VERSION,
  HolonngramCompilerError,
  classifyHolonngramDenialCodesV1,
  resolveAndCompileHolonngramVisualFeedbackV1,
  verifyHolonngramVisualFeedbackFrameIntegrityV1,
  type HolonngramCompilerInputV1,
} from '../../src/projection/holonngram-compiler.js'
import type {
  CrossRuntimeReceiptSourceV1,
  TrustedReceiptResolutionContextV1,
} from '../../src/provenance/receipt-resolver.js'

const H = (digit: string): SHA256Hex => digit.repeat(64) as SHA256Hex

interface VectorFile {
  readonly context: Omit<TrustedReceiptResolutionContextV1, 'operator_public_key'>
  readonly operator_public_key: string
  readonly receipts: readonly Record<string, unknown>[]
  readonly registry: Record<string, unknown> & { readonly registry_root: SHA256Hex }
  readonly terminal_receipt_id: SHA256Hex
}

class MemorySource implements CrossRuntimeReceiptSourceV1 {
  readonly receipts = new Map<string, unknown>()
  readonly registries = new Map<string, unknown>()

  resolveReceipt(receiptId: SHA256Hex): Promise<unknown | null> {
    return Promise.resolve(this.receipts.get(receiptId) ?? null)
  }

  resolveTrustRegistry(registryRoot: SHA256Hex): Promise<unknown | null> {
    return Promise.resolve(this.registries.get(registryRoot) ?? null)
  }
}

function loadVector(): VectorFile {
  return JSON.parse(readFileSync(
    resolve(process.cwd(), 'test/vectors/python-cross-runtime-receipt-v1.json'),
    'utf8',
  )) as VectorFile
}

function sourceFor(vector: VectorFile): MemorySource {
  const source = new MemorySource()
  source.registries.set(vector.registry.registry_root, vector.registry)
  for (const receipt of vector.receipts) {
    source.receipts.set(String(receipt.receipt_id), receipt)
  }
  return source
}

function compileVisualSchema() {
  const schema = JSON.parse(readFileSync(
    resolve(process.cwd(), '../schemas/holonngram-visual-feedback.v1.schema.json'),
    'utf8',
  )) as Record<string, unknown>
  return new Ajv2020({ allErrors: true }).compile(schema)
}

function contextFor(
  vector: VectorFile,
  overrides: Partial<TrustedReceiptResolutionContextV1> = {},
): TrustedReceiptResolutionContextV1 {
  return {
    ...vector.context,
    operator_public_key: vector.operator_public_key,
    ...overrides,
  }
}

function contextForReceipt(
  vector: VectorFile,
  receipt: Record<string, unknown>,
): TrustedReceiptResolutionContextV1 {
  const body = receipt.receipt_body as Record<string, unknown>
  return contextFor(vector, {
    expected_action_digest: body.action_digest as SHA256Hex,
    expected_observed_state_root: body.observed_state_root as SHA256Hex,
    observed_at_ms: String(body.timestamp_ms),
  })
}

function input(
  overrides: Partial<HolonngramCompilerInputV1> = {},
): HolonngramCompilerInputV1 {
  return {
    schema_version: HOLONNGRAM_VISUAL_FEEDBACK_SCHEMA_VERSION,
    compiler_version: HOLONNGRAM_COMPILER_VERSION,
    formula_id: 'FORMULA-001',
    formula_version: 'v1',
    formula_definition_digest: H('f'),
    transition_id: 'STU-001',
    measurement: {
      status: 'NOT_COMPUTED',
      resonance_ppm: null,
      value_delta_ppm: null,
    },
    edge_updates: [],
    next_route: 'route.review',
    ...overrides,
  }
}

describe('Holonñgram visual feedback compiler', () => {
  it('compiles only after resolving the signed chain and terminal receipt', async () => {
    const vector = loadVector()
    const frame = await resolveAndCompileHolonngramVisualFeedbackV1(
      sourceFor(vector),
      vector.terminal_receipt_id,
      contextFor(vector),
      input(),
    )

    expect(frame.source.terminal_receipt_kind).toBe('MUTATION_FAILED')
    expect(frame.source.provenance_status).toBe(
      'AUTHORITATIVE_RECEIPT_PROVENANCE_VERIFIED',
    )
    expect(frame.state_comparison.delta_type).toBe('FAILED')
    expect(frame.feedback.signal).toBe('ROLLBACK')
    expect(frame.visual.nodes).toHaveLength(19)
    expect(frame.visual.receipt_timeline.receipt_count).toBe('15')
    expect(frame.epistemic_status).toBe('DERIVED_NON_AUTHORITATIVE')
    expect(frame.safety).toEqual({
      grants_authority: false,
      executes_mutation: false,
      promotes_evidence: false,
      claims_authoritative_provenance: false,
      route_adjustment_authorized: false,
    })
    expect(frame.formula_trace.execution_status).toBe('NOT_EXECUTED')
    await expect(
      verifyHolonngramVisualFeedbackFrameIntegrityV1(frame),
    ).resolves.toEqual(frame)
  })

  it('labels caller-supplied measurements as unverified', async () => {
    const vector = loadVector()
    const terminal = vector.receipts.find(
      receipt => receipt.receipt_kind === 'MUTATION_COMPLETED',
    )
    if (terminal === undefined) throw new Error('completion receipt missing from vector')
    const terminalId = terminal.receipt_id as SHA256Hex
    const frame = await resolveAndCompileHolonngramVisualFeedbackV1(
      sourceFor(vector),
      terminalId,
      contextFor(vector, {
        expected_action_digest: H('b'),
        expected_observed_state_root: H('a'),
        observed_at_ms: '1700',
      }),
      input({
        measurement: {
          status: 'CALLER_SUPPLIED_UNVERIFIED',
          resonance_ppm: '875000',
          value_delta_ppm: '12500',
        },
        edge_updates: [{
          from_node: 'I5',
          to_node: 'I6',
          edge_kind: 'FEEDBACK',
          measurement_status: 'CALLER_SUPPLIED_UNVERIFIED',
          trust_delta_ppm: '12000',
          risk_delta_ppm: '-7000',
          schema_delta_ppm: '0',
          authority_delta_ppm: '0',
          basis_codes: ['FORMULA_TRACE'],
        }],
        next_route: 'route.commit',
      }),
    )

    expect(frame.source.terminal_receipt_kind).toBe('MUTATION_COMPLETED')
    expect(frame.state_comparison.delta_type).toBe('STATE_CHANGED')
    expect(frame.feedback.signal).toBe('REINFORCE')
    expect(frame.feedback.resonance.ppm).toBe('875000')
    expect(frame.formula_trace.execution_status).toBe('UNVERIFIED_CALLER_INPUT')
    expect(frame.visual.edge_updates).toHaveLength(1)
    expect(frame.formula_trace.trace_id).toMatch(/^[0-9a-f]{64}$/)
  })

  it('proves denied actions leave the canonical state root unchanged', async () => {
    const vector = loadVector()
    const terminal = vector.receipts.find(
      receipt => receipt.receipt_kind === 'MUTATION_DENIED',
    )
    if (terminal === undefined) throw new Error('denial receipt missing from vector')
    const frame = await resolveAndCompileHolonngramVisualFeedbackV1(
      sourceFor(vector),
      terminal.receipt_id as SHA256Hex,
      contextFor(vector, {
        expected_action_digest: H('d'),
        expected_observed_state_root: H('a'),
        observed_at_ms: '1500',
      }),
      input(),
    )

    expect(frame.state_comparison.delta_type).toBe('DENIED')
    expect(frame.state_comparison.before_state_root).toBe(H('a'))
    expect(frame.state_comparison.after_state_root).toBe(H('a'))
    expect(frame.feedback.signal).toBe('REQUEST_GRANT')
    expect(frame.feedback.boundary).toBe('AUTHORITY')
  })

  it.each([
    'LEASE_ISSUANCE_DENIED',
    'LEASE_RENEWAL_DENIED',
    'LEASE_EXPIRED',
    'LEASE_REVOKED',
  ] as const)('compiles terminal lease evidence without zero-sentinel visual refs: %s',
    async receiptKind => {
      const vector = loadVector()
      const terminal = vector.receipts.find(
        receipt => receipt.receipt_kind === receiptKind,
      )
      if (terminal === undefined) throw new Error(`${receiptKind} missing from vector`)
      const frame = await resolveAndCompileHolonngramVisualFeedbackV1(
        sourceFor(vector),
        terminal.receipt_id as SHA256Hex,
        contextForReceipt(vector, terminal),
        input(),
      )

      expect(frame.source.terminal_receipt_kind).toBe(receiptKind)
      expect(frame.state_comparison.before_state_root).toBe(
        frame.state_comparison.after_state_root,
      )
      expect(frame.visual.nodes).toHaveLength(19)
      expect(frame.visual.nodes.flatMap(node => node.source_refs)).not.toContain(H('0'))
      await expect(
        verifyHolonngramVisualFeedbackFrameIntegrityV1(frame),
      ).resolves.toEqual(frame)
    })

  it('is deterministic across caller property insertion order', async () => {
    const vector = loadVector()
    const canonical = input()
    const reordered = {
      next_route: canonical.next_route,
      edge_updates: canonical.edge_updates,
      measurement: canonical.measurement,
      transition_id: canonical.transition_id,
      formula_definition_digest: canonical.formula_definition_digest,
      formula_version: canonical.formula_version,
      formula_id: canonical.formula_id,
      compiler_version: canonical.compiler_version,
      schema_version: canonical.schema_version,
    }
    const first = await resolveAndCompileHolonngramVisualFeedbackV1(
      sourceFor(vector), vector.terminal_receipt_id, contextFor(vector), canonical,
    )
    const second = await resolveAndCompileHolonngramVisualFeedbackV1(
      sourceFor(vector), vector.terminal_receipt_id, contextFor(vector), reordered,
    )
    expect(second.frame_digest).toBe(first.frame_digest)
    expect(second.formula_trace.trace_id).toBe(first.formula_trace.trace_id)
  })

  it('survives restart-style structured read-back integrity validation', async () => {
    const vector = loadVector()
    const frame = await resolveAndCompileHolonngramVisualFeedbackV1(
      sourceFor(vector), vector.terminal_receipt_id, contextFor(vector), input(),
    )
    const readBack = structuredClone(frame)
    const verified = await verifyHolonngramVisualFeedbackFrameIntegrityV1(readBack)
    expect(verified).toEqual(frame)
    expect(Object.isFrozen(verified)).toBe(true)
    expect(Object.isFrozen(verified.visual.nodes)).toBe(true)
  })

  it('rejects an overstated formula execution claim during integrity read-back', async () => {
    const vector = loadVector()
    const frame = await resolveAndCompileHolonngramVisualFeedbackV1(
      sourceFor(vector), vector.terminal_receipt_id, contextFor(vector), input(),
    )
    await expect(verifyHolonngramVisualFeedbackFrameIntegrityV1({
      ...frame,
      formula_trace: {
        ...frame.formula_trace,
        execution_status: 'UNVERIFIED_CALLER_INPUT',
      },
    })).rejects.toThrow(/overstates execution or measurement provenance/)
  })

  it('rejects a missing trust root without producing a frame', async () => {
    const vector = loadVector()
    await expect(resolveAndCompileHolonngramVisualFeedbackV1(
      sourceFor(vector),
      vector.terminal_receipt_id,
      contextFor(vector, { accepted_registry_roots: [H('9')] }),
      input(),
    )).rejects.toThrow(/explicitly accepted/)
  })

  it('rejects a terminal receipt that is tampered after persistence', async () => {
    const vector = loadVector()
    const source = sourceFor(vector)
    const terminal = structuredClone(
      source.receipts.get(vector.terminal_receipt_id),
    ) as Record<string, unknown>
    const body = terminal.receipt_body as Record<string, unknown>
    body.after_state_root = H('1')
    source.receipts.set(vector.terminal_receipt_id, terminal)

    await expect(resolveAndCompileHolonngramVisualFeedbackV1(
      source, vector.terminal_receipt_id, contextFor(vector), input(),
    )).rejects.toThrow()
  })

  it('rejects malformed and non-I-JSON compiler input', async () => {
    const vector = loadVector()
    const malformed = {
      ...input(),
      measurement: {
        status: 'CALLER_SUPPLIED_UNVERIFIED',
        resonance_ppm: -0,
        value_delta_ppm: '0',
      },
    }
    await expect(resolveAndCompileHolonngramVisualFeedbackV1(
      sourceFor(vector), vector.terminal_receipt_id, contextFor(vector), malformed,
    )).rejects.toThrow(HolonngramCompilerError)
  })

  it('rejects unexpected input fields', async () => {
    const vector = loadVector()
    await expect(resolveAndCompileHolonngramVisualFeedbackV1(
      sourceFor(vector),
      vector.terminal_receipt_id,
      contextFor(vector),
      { ...input(), hidden_authority: true },
    )).rejects.toThrow(/unexpected or missing fields/)
  })

  it('rejects measurements when the formula trace says not computed', async () => {
    const vector = loadVector()
    await expect(resolveAndCompileHolonngramVisualFeedbackV1(
      sourceFor(vector),
      vector.terminal_receipt_id,
      contextFor(vector),
      input({
        measurement: {
          status: 'NOT_COMPUTED',
          resonance_ppm: '0',
          value_delta_ppm: null,
        },
      }),
    )).rejects.toThrow(/must be null/)
  })

  it('prioritizes fail-closed evidence across mixed denial codes', () => {
    expect(classifyHolonngramDenialCodesV1([
      'AUTHORITY_SCOPE_MISSING',
      'UNSIGNED_RECEIPT',
    ])).toEqual({
      signal: 'FAIL_CLOSED',
      severity: 'CRITICAL',
      boundary: 'TRUST',
    })
  })

  it('rejects out-of-bound fixed-point measurements', async () => {
    const vector = loadVector()
    await expect(resolveAndCompileHolonngramVisualFeedbackV1(
      sourceFor(vector),
      vector.terminal_receipt_id,
      contextFor(vector),
      input({
        measurement: {
          status: 'CALLER_SUPPLIED_UNVERIFIED',
          resonance_ppm: '1000001',
          value_delta_ppm: '0',
        },
      }),
    )).rejects.toThrow(/exceeds 1000000 ppm/)
  })

  it('rejects unsorted or duplicate edge tuples', async () => {
    const vector = loadVector()
    const edge = {
      from_node: 'I5' as const,
      to_node: 'I6' as const,
      edge_kind: 'FEEDBACK' as const,
      measurement_status: 'CALLER_SUPPLIED_UNVERIFIED' as const,
      trust_delta_ppm: '0',
      risk_delta_ppm: '0',
      schema_delta_ppm: '0',
      authority_delta_ppm: '0',
      basis_codes: ['TRACE'],
    }
    await expect(resolveAndCompileHolonngramVisualFeedbackV1(
      sourceFor(vector),
      vector.terminal_receipt_id,
      contextFor(vector),
      input({
        measurement: {
          status: 'CALLER_SUPPLIED_UNVERIFIED',
          resonance_ppm: '0',
          value_delta_ppm: '0',
        },
        edge_updates: [edge, edge],
      }),
    )).rejects.toThrow(/unique and strictly sorted/)
  })

  it('rejects edge updates in a not-computed frame during integrity read-back', async () => {
    const vector = loadVector()
    const frame = await resolveAndCompileHolonngramVisualFeedbackV1(
      sourceFor(vector), vector.terminal_receipt_id, contextFor(vector), input(),
    )
    await expect(verifyHolonngramVisualFeedbackFrameIntegrityV1({
      ...frame,
      visual: {
        ...frame.visual,
        edge_updates: [{
          from_node: 'I5',
          to_node: 'I6',
          edge_kind: 'FEEDBACK',
          measurement_status: 'NOT_COMPUTED',
          trust_delta_ppm: null,
          risk_delta_ppm: null,
          schema_delta_ppm: null,
          authority_delta_ppm: null,
          basis_codes: [],
        }],
      },
    })).rejects.toThrow(/NOT_COMPUTED frames cannot contain edge updates/)
  })

  it('schema rejects formula and feedback measurement-status mismatches', async () => {
    const vector = loadVector()
    const frame = await resolveAndCompileHolonngramVisualFeedbackV1(
      sourceFor(vector), vector.terminal_receipt_id, contextFor(vector), input(),
    )
    const validate = compileVisualSchema()
    expect(validate(frame), JSON.stringify(validate.errors)).toBe(true)
    expect(validate({
      ...frame,
      feedback: {
        ...frame.feedback,
        resonance: {
          measurement_status: 'CALLER_SUPPLIED_UNVERIFIED',
          ppm: '0',
        },
        value: {
          measurement_status: 'CALLER_SUPPLIED_UNVERIFIED',
          delta_ppm: '0',
        },
      },
    })).toBe(false)
  })

  it('schema rejects formula and edge measurement-status mismatches', async () => {
    const vector = loadVector()
    const frame = await resolveAndCompileHolonngramVisualFeedbackV1(
      sourceFor(vector),
      vector.terminal_receipt_id,
      contextFor(vector),
      input({
        measurement: {
          status: 'CALLER_SUPPLIED_UNVERIFIED',
          resonance_ppm: '0',
          value_delta_ppm: '0',
        },
        edge_updates: [{
          from_node: 'I5',
          to_node: 'I6',
          edge_kind: 'FEEDBACK',
          measurement_status: 'CALLER_SUPPLIED_UNVERIFIED',
          trust_delta_ppm: '0',
          risk_delta_ppm: '0',
          schema_delta_ppm: '0',
          authority_delta_ppm: '0',
          basis_codes: ['TRACE'],
        }],
      }),
    )
    const validate = compileVisualSchema()
    expect(validate(frame), JSON.stringify(validate.errors)).toBe(true)
    expect(validate({
      ...frame,
      visual: {
        ...frame.visual,
        edge_updates: [{
          ...frame.visual.edge_updates[0],
          measurement_status: 'NOT_COMPUTED',
          trust_delta_ppm: null,
          risk_delta_ppm: null,
          schema_delta_ppm: null,
          authority_delta_ppm: null,
          basis_codes: [],
        }],
      },
    })).toBe(false)
  })

  it('rejects frame digest tampering', async () => {
    const vector = loadVector()
    const frame = await resolveAndCompileHolonngramVisualFeedbackV1(
      sourceFor(vector), vector.terminal_receipt_id, contextFor(vector), input(),
    )
    await expect(verifyHolonngramVisualFeedbackFrameIntegrityV1({
      ...frame,
      frame_digest: H('1'),
    })).rejects.toThrow(/frame digest is invalid/)
  })

  it('rejects any attempt to promote the visual projection', async () => {
    const vector = loadVector()
    const frame = await resolveAndCompileHolonngramVisualFeedbackV1(
      sourceFor(vector), vector.terminal_receipt_id, contextFor(vector), input(),
    )
    await expect(verifyHolonngramVisualFeedbackFrameIntegrityV1({
      ...frame,
      safety: { ...frame.safety, promotes_evidence: true },
    })).rejects.toThrow(/non-authoritative/)
  })

  it('rejects fixed-topology tampering', async () => {
    const vector = loadVector()
    const frame = await resolveAndCompileHolonngramVisualFeedbackV1(
      sourceFor(vector), vector.terminal_receipt_id, contextFor(vector), input(),
    )
    const nodes = [...structuredClone(frame.visual.nodes)]
    nodes.reverse()
    await expect(verifyHolonngramVisualFeedbackFrameIntegrityV1({
      ...frame,
      visual: { ...frame.visual, nodes },
    })).rejects.toThrow(/fixed 19-node order/)
  })
})
