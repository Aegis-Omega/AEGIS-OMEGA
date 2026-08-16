import { buildMcmObservation, routeVerificationDemand } from './mcm.mjs';
import { evaluateMemoryAuthority } from './memory-authority-gate.mjs';

function int(value, field) {
  const parsed = typeof value === 'string' ? Number(value) : value;
  if (!Number.isSafeInteger(parsed)) throw new TypeError(`${field} must be an integer`);
  return parsed;
}

export function createAgentTools({ store, embed }) {
  if (!store || typeof store.getNodeState !== 'function' || typeof store.findEvidence !== 'function') {
    throw new TypeError('memory store required');
  }
  if (typeof embed !== 'function') throw new TypeError('embed function required');

  async function observeCollectiveState({ nodeId }) {
    const row = await store.getNodeState(nodeId);
    if (!row) {
      return Object.freeze({ found: false, authorityEffect: 'OBSERVATION_ONLY', observationTier: 'T2' });
    }
    const observation = buildMcmObservation({
      nodeId: row.node_id,
      confidenceBps: int(row.confidence_bps, 'confidence_bps'),
      evidenceFreshnessBps: int(row.evidence_freshness_bps, 'evidence_freshness_bps'),
      loadBps: int(row.load_bps, 'load_bps'),
      reliabilityBps: int(row.reliability_bps, 'reliability_bps'),
      observedAuthorityEnvelope: row.observed_authority_envelope,
      contradictionCount: int(row.contradiction_count, 'contradiction_count'),
    });
    return Object.freeze({ found: true, observation, routing: routeVerificationDemand(observation) });
  }

  async function searchEvidence({ query, epistemicTier = 'T2', limit = 5 }) {
    if (typeof query !== 'string' || query.trim().length === 0) throw new TypeError('query required');
    const embedding = await embed(query);
    const matches = await store.findEvidence({ epistemicTier, embedding, limit });
    return Object.freeze({ authorityEffect: 'EVIDENCE_ONLY', matches });
  }

  async function evaluateAction(input) {
    const row = await store.getNodeState(input.nodeId);
    if (!row) {
      return Object.freeze({ verdict: 'DENY', reasons: Object.freeze(['MEMORY_STATE_NOT_FOUND']) });
    }

    return evaluateMemoryAuthority({
      requestId: input.requestId,
      actionDigest: input.actionDigest,
      observedStateDigest: input.observedStateDigest,
      admittedStateDigest: row.state_digest,
      observedPolicyDigest: input.observedPolicyDigest,
      admittedPolicyDigest: row.policy_digest,
      observedAuthorityEpoch: input.observedAuthorityEpoch,
      admittedAuthorityEpoch: int(row.authority_epoch, 'authority_epoch'),
      priorReceiptActionDigest: input.priorReceiptActionDigest ?? null,
    });
  }

  return Object.freeze({ observeCollectiveState, searchEvidence, evaluateAction });
}
