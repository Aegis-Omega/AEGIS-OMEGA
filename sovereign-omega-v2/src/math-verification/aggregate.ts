import { hashValue } from '../core/hashing.js';
import {
  type FormalizationBindingV1,
  type KernelVerificationResultV1,
  type MathClaimEnvelopeV1,
  validateFormalizationBindingV1,
  validateKernelVerificationResultV1,
  validateMathClaimEnvelopeV1,
} from './contracts.js';

export const MATH_RECEIPT_AUTHORITY = 'FORMAL_MATH_EVIDENCE_ONLY' as const;

export type MathTruthVerdictV1 = 'PROVED' | 'DISPROVED' | 'UNRESOLVED';
export type MathVerificationLevelV1 = 'SINGLE_KERNEL' | 'CROSS_KERNEL';

export interface MathVerificationReceiptV1 {
  readonly schema_version: '1.0.0';
  readonly receipt_kind: 'MATH_VERIFICATION_RECEIPT_V1';
  readonly claim_id: string;
  readonly claim_digest: string;
  readonly assumptions_digest: string;
  readonly formalization_binding_digest: string;
  readonly verdict: MathTruthVerdictV1;
  readonly verification_level: MathVerificationLevelV1;
  readonly accepted_kernel_result_hashes: readonly string[];
  readonly rejected_kernel_result_hashes: readonly string[];
  readonly proof_artifact_hashes: readonly string[];
  readonly counterexample_artifact_hashes: readonly string[];
  readonly diagnostics: readonly string[];
  readonly policy_commitment: string;
  readonly authority_epoch: number;
  readonly receipt_hash: string;
  readonly authority: typeof MATH_RECEIPT_AUTHORITY;
}

export interface AggregateMathVerificationInputV1 {
  readonly claim: unknown;
  readonly binding: unknown;
  readonly kernel_results: readonly unknown[];
}

type TruthSide = 'PROOF' | 'DISPROOF' | 'NONE';

interface ClassifiedResult {
  readonly hash: string;
  readonly result: KernelVerificationResultV1;
  readonly truth: TruthSide;
}

async function resultHash(value: unknown): Promise<string> {
  return hashValue({ domain: 'AEGIS_MATH_KERNEL_RESULT_V1', value });
}

function bindingMatchesClaim(claim: MathClaimEnvelopeV1, binding: FormalizationBindingV1): boolean {
  return binding.claim_id === claim.claim_id
    && binding.claim_digest === claim.claim_digest
    && binding.assumptions_digest === claim.assumptions_digest
    && binding.policy_commitment === claim.policy_commitment
    && binding.authority_epoch === claim.authority_epoch;
}

function resultMatchesBinding(result: KernelVerificationResultV1, binding: FormalizationBindingV1): boolean {
  const expectedSource = result.kernel_family === 'LEAN'
    ? binding.lean_source_sha256
    : binding.coq_source_sha256;
  return result.claim_digest === binding.claim_digest
    && result.assumptions_digest === binding.assumptions_digest
    && result.formalization_binding_digest === binding.formalization_binding_digest
    && result.formalization_sha256 === expectedSource;
}

function truthSide(result: KernelVerificationResultV1): TruthSide {
  if (result.process_status !== 'VERIFIED') return 'NONE';
  if (result.attempt_kind === 'PROVE') return 'PROOF';
  if (result.attempt_kind === 'DISPROVE_NEGATION' || result.attempt_kind === 'DISPROVE_COUNTEREXAMPLE') {
    return 'DISPROOF';
  }
  return 'NONE';
}

function sortedUnique(values: readonly string[]): readonly string[] {
  return Object.freeze([...new Set(values)].sort());
}

export async function aggregateMathVerificationV1(
  input: AggregateMathVerificationInputV1,
): Promise<MathVerificationReceiptV1> {
  const claim = validateMathClaimEnvelopeV1(input.claim);
  const binding = validateFormalizationBindingV1(input.binding);
  if (!Array.isArray(input.kernel_results) || input.kernel_results.length > 128) {
    throw new Error('MATH_AGGREGATE_KERNEL_RESULTS_INVALID');
  }

  const diagnostics: string[] = [];
  const accepted: ClassifiedResult[] = [];
  const rejectedHashes: string[] = [];
  const bindingValid = bindingMatchesClaim(claim, binding);
  if (!bindingValid) diagnostics.push('FORMALIZATION_BINDING_CLAIM_MISMATCH');

  for (const raw of input.kernel_results) {
    const hash = await resultHash(raw);
    try {
      const result = validateKernelVerificationResultV1(raw);
      if (!bindingValid || !resultMatchesBinding(result, binding)) {
        rejectedHashes.push(hash);
        continue;
      }
      accepted.push({ hash, result, truth: truthSide(result) });
    } catch {
      rejectedHashes.push(hash);
    }
  }

  const proofEvidence = accepted.filter((entry) => entry.truth === 'PROOF');
  const disproofEvidence = accepted.filter((entry) => entry.truth === 'DISPROOF');

  let verdict: MathTruthVerdictV1 = 'UNRESOLVED';
  let agreeingEvidence: readonly ClassifiedResult[] = [];
  if (proofEvidence.length > 0 && disproofEvidence.length > 0) {
    diagnostics.push('KERNEL_INCONSISTENCY_DETECTED');
  } else if (proofEvidence.length > 0) {
    verdict = 'PROVED';
    agreeingEvidence = proofEvidence;
  } else if (disproofEvidence.length > 0) {
    verdict = 'DISPROVED';
    agreeingEvidence = disproofEvidence;
  }

  const agreeingFamilies = new Set(agreeingEvidence.map((entry) => entry.result.kernel_family));
  const verificationLevel: MathVerificationLevelV1 = agreeingFamilies.has('LEAN') && agreeingFamilies.has('COQ')
    ? 'CROSS_KERNEL'
    : 'SINGLE_KERNEL';

  const proofArtifacts = accepted
    .filter((entry) => entry.truth !== 'NONE')
    .map((entry) => entry.result.proof_artifact_sha256)
    .filter((value): value is string => value !== null);
  const counterexampleArtifacts = accepted
    .filter((entry) => entry.truth === 'DISPROOF')
    .map((entry) => entry.result.counterexample_artifact_sha256)
    .filter((value): value is string => value !== null);

  const receiptWithoutHash = {
    schema_version: '1.0.0' as const,
    receipt_kind: 'MATH_VERIFICATION_RECEIPT_V1' as const,
    claim_id: claim.claim_id,
    claim_digest: claim.claim_digest,
    assumptions_digest: claim.assumptions_digest,
    formalization_binding_digest: binding.formalization_binding_digest,
    verdict,
    verification_level: verificationLevel,
    accepted_kernel_result_hashes: sortedUnique(accepted.map((entry) => entry.hash)),
    rejected_kernel_result_hashes: sortedUnique(rejectedHashes),
    proof_artifact_hashes: sortedUnique(proofArtifacts),
    counterexample_artifact_hashes: sortedUnique(counterexampleArtifacts),
    diagnostics: sortedUnique(diagnostics),
    policy_commitment: claim.policy_commitment,
    authority_epoch: claim.authority_epoch,
    authority: MATH_RECEIPT_AUTHORITY,
  };

  const receiptHash = await hashValue({
    domain: 'AEGIS_MATH_VERIFICATION_RECEIPT_V1',
    receipt: receiptWithoutHash,
  });

  return Object.freeze({ ...receiptWithoutHash, receipt_hash: receiptHash });
}
