// ============================================================
// SOVEREIGN OMEGA — Ledger subsystem barrel export
// EPISTEMIC TIER: T0/T2
//
// Exposes the full distributed ledger API surface:
//   T0: LedgerEntry, LedgerChain, LedgerSnapshot, verify
//   T2: CommittedBlock, BlockChain, replay, checkpoints,
//       divergence, epoch seals, event bridge, state capsule,
//       constitutional audit, ledger-observer
// ============================================================

// ── T0: Core ledger primitives ────────────────────────────
export { GENESIS_HASH, LEDGER_SCHEMA_VERSION, LedgerConstraintError } from './types.js'
export type { LedgerEntry, LedgerSnapshot } from './types.js'

export { LedgerChain } from './chain.js'
export { captureCheckpoint } from './checkpoint.js'
export { verifyChain, verifySequences } from './verify.js'
export type { ChainVerificationResult } from './verify.js'

export {
  serializeSnapshot,
  deserializeSnapshot,
  serializeChain,
  deserializeChain,
  LedgerPersistenceError,
} from './persistence.js'

// ── T2: Distributed block layer ───────────────────────────
export {
  BLOCK_SCHEMA_VERSION,
  assembleBlock,
  verifyBlock,
  BlockError,
} from './block.js'
export type { CommittedBlock, ValidatorSignature, ValidatorId } from './block.js'

export { BlockChain, BlockChainError } from './block-chain.js'

export { replayChain, replayRange, BlockReplayError } from './block-replay.js'
export type { ReplayResult } from './block-replay.js'

// ── T2: Cross-node divergence & consensus ─────────────────
export {
  captureNodeCheckpoint,
  verifyNodeCheckpoint,
  compareCheckpoints,
  NodeCheckpointError,
  NODE_CHECKPOINT_VERSION,
} from './node-checkpoint.js'
export type { NodeCheckpoint, CheckpointComparison } from './node-checkpoint.js'

export {
  assessDivergence,
  allAgree,
  DivergenceMonitorError,
} from './divergence-monitor.js'
export type { DivergenceReport } from './divergence-monitor.js'

// ── T2: Epoch sealing ─────────────────────────────────────
export {
  sealEpoch,
  verifyEpochSeal,
  EpochSealError,
  EPOCH_SEAL_VERSION,
} from './epoch-seal.js'
export type { EpochSeal } from './epoch-seal.js'

// ── T2: Event → Block bridge ──────────────────────────────
export { bridgeToBlockChain, EventBridgeError } from './event-bridge.js'
export type { BridgeResult } from './event-bridge.js'

// ── T2: State transfer ────────────────────────────────────
export {
  exportStateCapsule,
  verifyStateCapsule,
  importStateCapsule,
  StateCapsuleError,
  STATE_CAPSULE_VERSION,
} from './state-capsule.js'
export type { StateCapsule } from './state-capsule.js'

// ── T2: Constitutional audit ──────────────────────────────
export {
  buildAuditEntry,
  verifyAuditEntry,
  ConstitutionalAuditLog,
  AuditLogError,
  AUDIT_LOG_VERSION,
} from './constitutional-audit.js'
export type { AuditTrailEntry, AuditLogSnapshot } from './constitutional-audit.js'

// ── T2: Consciousness bridge ──────────────────────────────
export { LedgerObserver } from './ledger-observer.js'
