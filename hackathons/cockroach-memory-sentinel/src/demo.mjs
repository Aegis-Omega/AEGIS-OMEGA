import { buildMcmObservation, routeVerificationDemand } from './mcm.mjs';
import { evaluateMemoryAuthority } from './memory-authority-gate.mjs';

const node = buildMcmObservation({
  nodeId: 'agent-7',
  confidenceBps: 6200,
  evidenceFreshnessBps: 4100,
  loadBps: 8800,
  reliabilityBps: 7300,
  observedAuthorityEnvelope: 'D2',
  contradictionCount: 2,
});

const routing = routeVerificationDemand(node);

const admission = evaluateMemoryAuthority({
  requestId: 'demo-001',
  actionDigest: 'sha256:action-a',
  observedStateDigest: 'sha256:state-4',
  admittedStateDigest: 'sha256:state-5',
  observedPolicyDigest: 'sha256:policy-3',
  admittedPolicyDigest: 'sha256:policy-3',
  observedAuthorityEpoch: 7,
  admittedAuthorityEpoch: 7,
  priorReceiptActionDigest: null,
});

console.log(JSON.stringify({ node, routing, admission }, null, 2));

if (routing.authorityMutationPermitted !== false || admission.verdict !== 'DENY') {
  process.exit(2);
}
