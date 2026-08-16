function isBps(value) {
  return Number.isInteger(value) && value >= 0 && value <= 10000;
}

export function buildMcmObservation(input) {
  if (!input || typeof input.nodeId !== 'string' || input.nodeId.length === 0) {
    throw new TypeError('nodeId required');
  }

  for (const key of ['confidenceBps', 'evidenceFreshnessBps', 'loadBps', 'reliabilityBps']) {
    if (!isBps(input[key])) throw new RangeError(`${key} must be integer basis points`);
  }

  if (!Number.isSafeInteger(input.contradictionCount) || input.contradictionCount < 0) {
    throw new RangeError('contradictionCount invalid');
  }

  return Object.freeze({
    nodeId: input.nodeId,
    confidenceBps: input.confidenceBps,
    evidenceFreshnessBps: input.evidenceFreshnessBps,
    loadBps: input.loadBps,
    reliabilityBps: input.reliabilityBps,
    contradictionCount: input.contradictionCount,
    observedAuthorityEnvelope: input.observedAuthorityEnvelope ?? null,
    proposedAuthorityEnvelope: null,
    authorityEffect: 'OBSERVATION_ONLY',
    observationTier: 'T2',
    authorityWeight: 0,
    mayGroundStateTransition: false,
  });
}

export function routeVerificationDemand(observation) {
  const reasons = [];

  if (observation.contradictionCount > 0) reasons.push('CONTRADICTION_CLUSTER');
  if (observation.evidenceFreshnessBps < 5000) reasons.push('EVIDENCE_FRESHNESS_LOW');
  if (observation.confidenceBps < 5000) reasons.push('CONFIDENCE_LOW');
  if (observation.loadBps >= 8000) reasons.push('CAPACITY_PRESSURE');

  return Object.freeze({
    requiresIndependentWitness:
      reasons.includes('CONTRADICTION_CLUSTER') ||
      reasons.includes('EVIDENCE_FRESHNESS_LOW') ||
      reasons.includes('CONFIDENCE_LOW'),
    routingPriority:
      observation.loadBps >= 8000 || observation.contradictionCount > 0 ? 'HIGH' : 'NORMAL',
    authorityMutationPermitted: false,
    reasons: Object.freeze(reasons),
  });
}
