import { sha256Hex } from '../core/hashing.js'
import type { FrontierInferenceProvider } from './frontier-inference-gateway.js'

export const PROVIDER_EXECUTION_EVIDENCE_BINDING_KIND = 'PROVIDER_EXECUTION_EVIDENCE_BINDING_V1' as const
export const PROVIDER_EXECUTION_EVIDENCE_BINDING_DOMAIN = 'AEGIS_PROVIDER_EXECUTION_EVIDENCE_BINDING_V1' as const

const SHA256_HEX = /^[0-9a-f]{64}$/
const SAFE_ID = /^[A-Za-z0-9._:/@+#=-]+$/

export interface ProviderExecutionEvidenceBindingV1 {
  readonly binding_kind: typeof PROVIDER_EXECUTION_EVIDENCE_BINDING_KIND
  readonly provider: FrontierInferenceProvider
  readonly request_id: string
  readonly provider_operation_id: string
  readonly response_digest: string
  readonly work_order_digest: string
  readonly authority_receipt_root: string
  readonly transition_id: string
  readonly execution_instance_id: string
  readonly expected_parent_state_root: string
  readonly grants_authority: false
}

export interface ProviderBindingRequestContext {
  readonly provider: FrontierInferenceProvider
  readonly requestId: string
  readonly expectedParentStateRoot: string
}

export interface ProviderBindingResultContext {
  readonly providerOperationId: string
  readonly responseDigest: string
  readonly grantsAuthority: boolean
}

export interface ProviderBindingUsageContext {
  readonly provider: FrontierInferenceProvider
  readonly requestId: string
  readonly status: string
  readonly workOrderDigest: string
  readonly authorityReceiptRoot: string
  readonly providerOperationId?: string | undefined
  readonly responseDigest?: string | undefined
  readonly grantsAuthority: boolean
}

export interface CreateProviderExecutionEvidenceBindingInput {
  readonly request: ProviderBindingRequestContext
  readonly result: ProviderBindingResultContext
  readonly usage: ProviderBindingUsageContext
  readonly transitionId: string
  readonly executionInstanceId: string
}

export class ProviderExecutionEvidenceBindingError extends Error {
  constructor(readonly code: string) {
    super(code)
    this.name = 'ProviderExecutionEvidenceBindingError'
  }
}

function fail(code: string): never {
  throw new ProviderExecutionEvidenceBindingError(code)
}

function requireHash(value: string, code: string): string {
  if (typeof value !== 'string' || !SHA256_HEX.test(value)) fail(code)
  return value
}

function requireId(value: string, code: string): string {
  if (typeof value !== 'string' || !SAFE_ID.test(value)) fail(code)
  return value
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value)
}

const BINDING_KEYS = [
  'binding_kind',
  'provider',
  'request_id',
  'provider_operation_id',
  'response_digest',
  'work_order_digest',
  'authority_receipt_root',
  'transition_id',
  'execution_instance_id',
  'expected_parent_state_root',
  'grants_authority',
] as const

export function validateProviderExecutionEvidenceBinding(value: unknown): ProviderExecutionEvidenceBindingV1 {
  if (!isRecord(value)) fail('PROVIDER_EXECUTION_BINDING_MALFORMED')
  const actual = Object.keys(value).sort()
  const expected = [...BINDING_KEYS].sort()
  if (actual.length !== expected.length || actual.some((key, index) => key !== expected[index])) {
    fail('PROVIDER_EXECUTION_BINDING_SCHEMA_DRIFT')
  }
  if (value.binding_kind !== PROVIDER_EXECUTION_EVIDENCE_BINDING_KIND) fail('PROVIDER_EXECUTION_BINDING_KIND_MISMATCH')
  const provider = requireId(value.provider as string, 'PROVIDER_EXECUTION_BINDING_PROVIDER_INVALID') as FrontierInferenceProvider
  const requestId = requireId(value.request_id as string, 'PROVIDER_EXECUTION_BINDING_REQUEST_INVALID')
  const operationId = requireId(value.provider_operation_id as string, 'PROVIDER_EXECUTION_BINDING_OPERATION_INVALID')
  const executionId = requireId(value.execution_instance_id as string, 'PROVIDER_EXECUTION_BINDING_EXECUTION_INVALID')
  requireHash(value.response_digest as string, 'PROVIDER_EXECUTION_BINDING_RESPONSE_DIGEST_INVALID')
  requireHash(value.work_order_digest as string, 'PROVIDER_EXECUTION_BINDING_WORK_ORDER_DIGEST_INVALID')
  requireHash(value.authority_receipt_root as string, 'PROVIDER_EXECUTION_BINDING_AUTHORITY_ROOT_INVALID')
  requireHash(value.transition_id as string, 'PROVIDER_EXECUTION_BINDING_TRANSITION_INVALID')
  requireHash(value.expected_parent_state_root as string, 'PROVIDER_EXECUTION_BINDING_PARENT_STATE_INVALID')
  if (value.grants_authority !== false) fail('PROVIDER_EXECUTION_BINDING_AUTHORITY_ESCALATION')
  return Object.freeze({
    binding_kind: PROVIDER_EXECUTION_EVIDENCE_BINDING_KIND,
    provider,
    request_id: requestId,
    provider_operation_id: operationId,
    response_digest: value.response_digest as string,
    work_order_digest: value.work_order_digest as string,
    authority_receipt_root: value.authority_receipt_root as string,
    transition_id: value.transition_id as string,
    execution_instance_id: executionId,
    expected_parent_state_root: value.expected_parent_state_root as string,
    grants_authority: false,
  })
}

export function createProviderExecutionEvidenceBinding(
  input: CreateProviderExecutionEvidenceBindingInput,
): ProviderExecutionEvidenceBindingV1 {
  const { request, result, usage } = input
  requireId(request.provider, 'PROVIDER_EXECUTION_BINDING_PROVIDER_INVALID')
  requireId(request.requestId, 'PROVIDER_EXECUTION_BINDING_REQUEST_INVALID')
  requireId(result.providerOperationId, 'PROVIDER_EXECUTION_BINDING_OPERATION_INVALID')
  requireHash(result.responseDigest, 'PROVIDER_EXECUTION_BINDING_RESPONSE_DIGEST_INVALID')
  requireHash(usage.workOrderDigest, 'PROVIDER_EXECUTION_BINDING_WORK_ORDER_DIGEST_INVALID')
  requireHash(usage.authorityReceiptRoot, 'PROVIDER_EXECUTION_BINDING_AUTHORITY_ROOT_INVALID')
  requireHash(input.transitionId, 'PROVIDER_EXECUTION_BINDING_TRANSITION_INVALID')
  requireId(input.executionInstanceId, 'PROVIDER_EXECUTION_BINDING_EXECUTION_INVALID')
  requireHash(request.expectedParentStateRoot, 'PROVIDER_EXECUTION_BINDING_PARENT_STATE_INVALID')

  if (result.grantsAuthority || usage.grantsAuthority) fail('PROVIDER_EXECUTION_BINDING_AUTHORITY_ESCALATION')
  if (usage.status !== 'succeeded') fail('PROVIDER_EXECUTION_BINDING_USAGE_NOT_SUCCEEDED')
  if (usage.provider !== request.provider) fail('PROVIDER_EXECUTION_BINDING_PROVIDER_MISMATCH')
  if (usage.requestId !== request.requestId) fail('PROVIDER_EXECUTION_BINDING_REQUEST_MISMATCH')
  if (usage.providerOperationId !== result.providerOperationId) fail('PROVIDER_EXECUTION_BINDING_OPERATION_MISMATCH')
  if (usage.responseDigest !== result.responseDigest) fail('PROVIDER_EXECUTION_BINDING_RESPONSE_MISMATCH')

  return validateProviderExecutionEvidenceBinding({
    binding_kind: PROVIDER_EXECUTION_EVIDENCE_BINDING_KIND,
    provider: request.provider,
    request_id: request.requestId,
    provider_operation_id: result.providerOperationId,
    response_digest: result.responseDigest,
    work_order_digest: usage.workOrderDigest,
    authority_receipt_root: usage.authorityReceiptRoot,
    transition_id: input.transitionId,
    execution_instance_id: input.executionInstanceId,
    expected_parent_state_root: request.expectedParentStateRoot,
    grants_authority: false,
  })
}

function canonicalBindingEnvelope(binding: ProviderExecutionEvidenceBindingV1): string {
  const value = {
    authority_receipt_root: binding.authority_receipt_root,
    binding_kind: binding.binding_kind,
    execution_instance_id: binding.execution_instance_id,
    expected_parent_state_root: binding.expected_parent_state_root,
    grants_authority: false,
    provider: binding.provider,
    provider_operation_id: binding.provider_operation_id,
    request_id: binding.request_id,
    response_digest: binding.response_digest,
    transition_id: binding.transition_id,
    work_order_digest: binding.work_order_digest,
  }
  return JSON.stringify({ domain: PROVIDER_EXECUTION_EVIDENCE_BINDING_DOMAIN, value })
}

export async function providerExecutionEvidenceBindingRoot(value: unknown): Promise<string> {
  const binding = validateProviderExecutionEvidenceBinding(value)
  return sha256Hex(new TextEncoder().encode(canonicalBindingEnvelope(binding)))
}

export function verifyProviderExecutionEvidenceBinding(
  value: unknown,
  expected: ProviderExecutionEvidenceBindingV1,
): boolean {
  try {
    const binding = validateProviderExecutionEvidenceBinding(value)
    const target = validateProviderExecutionEvidenceBinding(expected)
    return BINDING_KEYS.every((key) => binding[key] === target[key])
  } catch {
    return false
  }
}
