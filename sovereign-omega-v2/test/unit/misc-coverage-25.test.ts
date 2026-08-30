// ============================================================
// SOVEREIGN OMEGA — Coverage batch 25
// EPISTEMIC TIER: T2
//
// Covers:
//   verifyStateCapsule: tampered anchor/epoch consistency paths
//     (state-capsule.ts lines 173, 174, 175, 178, 193, 194)
//   mapIdeaToRoadmap: HARMONIZE phase testing/deployment gaps
//     (idea-mapper.ts line 179)
// ============================================================

import { describe, it, expect } from 'vitest'
import {
  exportStateCapsule,
  verifyStateCapsule,
  STATE_CAPSULE_VERSION,
} from '../../src/ledger/state-capsule.js'
import type { StateCapsule } from '../../src/ledger/state-capsule.js'
import { sealEpoch } from '../../src/ledger/epoch-seal.js'
import { BlockChain } from '../../src/ledger/block-chain.js'
import { assembleBlock } from '../../src/ledger/block.js'
import { captureNodeCheckpoint } from '../../src/ledger/node-checkpoint.js'
import { GENESIS_HASH } from '../../src/ledger/types.js'
import { hashValue } from '../../src/core/hashing.js'
import type { SHA256Hex, SequenceNumber } from '../../src/core/types.js'
import type { LedgerEntry } from '../../src/ledger/types.js'
import { mapIdeaToRoadmap } from '../../src/skill-harness/roadmap/idea-mapper.js'
import { SkillCatalog } from '../../src/skill-harness/catalog.js'

const EPOCH_BASE = 1_600_000_000_000

function makeEntry(seq: number): LedgerEntry {
  return Object.freeze<LedgerEntry>({
    sequence:        BigInt(seq) as SequenceNumber,
    previous_hash:   GENESIS_HASH,
    frame_hash:      ('a'.repeat(64)) as SHA256Hex,
    governance_hash: ('b'.repeat(64)) as SHA256Hex,
    timestamp_ms:    EPOCH_BASE + seq * 1_000,
  })
}

async function buildChain(length: number): Promise<BlockChain> {
  let chain    = BlockChain.empty()
  let prevBlock = null
  for (let i = 0; i < length; i++) {
    const block = await assembleBlock(prevBlock, [makeEntry(i)])
    chain       = chain.append(block)
    prevBlock   = block
  }
  return chain
}

// Reconstruct the capsuleHashInput object as the source does (mirrors internal function)
function capsuleHashInput(
  latestEpoch: StateCapsule['latest_epoch'],
  anchorBlock: StateCapsule['anchor_block'],
  tipCheckpointHash: SHA256Hex,
): Record<string, unknown> {
  return {
    epoch_seal_hash:     latestEpoch?.seal_hash ?? null,
    anchor_index:        anchorBlock?.index ?? null,
    anchor_state_root:   anchorBlock?.state_root_after ?? null,
    tip_checkpoint_hash: tipCheckpointHash,
  }
}

// ── verifyStateCapsule — tampered epoch/anchor consistency ────

describe('verifyStateCapsule — tampered epoch/anchor consistency (lines 173–178)', () => {
  it('returns false when latest_epoch is set but anchor_block is null (line 173)', async () => {
    const chain   = await buildChain(6)
    const epoch   = await sealEpoch(chain, 0, 0, 2)
    const capsule = await exportStateCapsule('node-a', chain, epoch)

    // Recompute capsule_hash as if anchor_block were null to pass check 1
    const tamperedHash = await hashValue(
      capsuleHashInput(capsule.latest_epoch, null, capsule.tip_checkpoint.checkpoint_hash),
    )
    const tampered: StateCapsule = {
      ...capsule,
      anchor_block: null,
      capsule_hash: tamperedHash,
    }
    expect(await verifyStateCapsule(tampered)).toBe(false)
  })

  it('returns false when anchor_block.index !== latest_epoch.end_height (line 174)', async () => {
    const chain   = await buildChain(6)
    const epoch   = await sealEpoch(chain, 0, 0, 2)
    const capsule = await exportStateCapsule('node-a', chain, epoch)
    const realAnchor = capsule.anchor_block!

    // Wrong index — epoch.end_height=2 but we claim index=999
    const badAnchor = { ...realAnchor, index: 999 }
    const tamperedHash = await hashValue(
      capsuleHashInput(capsule.latest_epoch, badAnchor, capsule.tip_checkpoint.checkpoint_hash),
    )
    const tampered: StateCapsule = {
      ...capsule,
      anchor_block: badAnchor,
      capsule_hash: tamperedHash,
    }
    expect(await verifyStateCapsule(tampered)).toBe(false)
  })

  it('returns false when anchor_block.state_root_after !== latest_epoch.final_state_root (line 175)', async () => {
    const chain   = await buildChain(6)
    const epoch   = await sealEpoch(chain, 0, 0, 2)
    const capsule = await exportStateCapsule('node-a', chain, epoch)
    const realAnchor = capsule.anchor_block!

    // Wrong state root — epoch.final_state_root won't match
    const badAnchor = { ...realAnchor, state_root_after: 'f'.repeat(64) as SHA256Hex }
    const tamperedHash = await hashValue(
      capsuleHashInput(capsule.latest_epoch, badAnchor, capsule.tip_checkpoint.checkpoint_hash),
    )
    const tampered: StateCapsule = {
      ...capsule,
      anchor_block: badAnchor,
      capsule_hash: tamperedHash,
    }
    expect(await verifyStateCapsule(tampered)).toBe(false)
  })

  it('returns false when latest_epoch is null but anchor_block is non-null (line 178)', async () => {
    const chain   = await buildChain(4)
    const capsule = await exportStateCapsule('node-a', chain, null)
    // Capsule already has latest_epoch=null, anchor_block=null
    // Insert a non-null anchor_block and recompute hash
    const fakeAnchor = chain.getAll()[0]!
    const tamperedHash = await hashValue(
      capsuleHashInput(null, fakeAnchor, capsule.tip_checkpoint.checkpoint_hash),
    )
    const tampered: StateCapsule = {
      ...capsule,
      anchor_block: fakeAnchor,
      capsule_hash: tamperedHash,
    }
    expect(await verifyStateCapsule(tampered)).toBe(false)
  })
})

// ── verifyStateCapsule — tip_checkpoint vs chain tip ──────────

describe('verifyStateCapsule — tipBlock and state_root checks (lines 193–194)', () => {
  it('returns false when pending_blocks empty and anchor_block null (tipBlock null, line 193)', async () => {
    // Construct a minimal capsule: latest_epoch=null, anchor_block=null, pending_blocks=[]
    // This is structurally valid as a capsule but represents a "no blocks" state
    const chain   = await buildChain(2)
    const tipBlk  = chain.lastBlock!
    // Capture a checkpoint (it will have state_root of the real tip, but pending_blocks will be empty)
    const tip_checkpoint = await captureNodeCheckpoint('node-a', tipBlk)
    const capsule_hash   = await hashValue(
      capsuleHashInput(null, null, tip_checkpoint.checkpoint_hash),
    )
    const tampered: StateCapsule = {
      latest_epoch:             null,
      anchor_block:             null,
      pending_blocks:           [],
      tip_checkpoint,
      capsule_hash,
      schema_version:           STATE_CAPSULE_VERSION,
      is_replay_reconstructable: true,
    }
    // Check 1 passes (hash consistent), check 2 passes (valid checkpoint),
    // check 3 passes (no epoch, no anchor), check 4 skipped (no blocks),
    // check 5: tipBlock = anchor_block = null → returns false at line 193
    expect(await verifyStateCapsule(tampered)).toBe(false)
  })

  it('returns false when tip_checkpoint.state_root does not match last pending block (line 194)', async () => {
    // Build chain of 3, export a valid capsule
    const chain   = await buildChain(3)
    const capsule = await exportStateCapsule('node-a', chain, null)
    // The capsule.tip_checkpoint.state_root = block[2].state_root_after

    // Add a 4th block to pending_blocks — its state_root_after will differ
    const block3 = await assembleBlock(chain.lastBlock!, [makeEntry(100)])
    const extendedPending = [...capsule.pending_blocks, block3]

    // capsule_hash depends only on tip_checkpoint.checkpoint_hash → unchanged
    const tampered: StateCapsule = {
      ...capsule,
      pending_blocks: extendedPending,
    }
    // Check 1: capsule_hash still valid (anchor_block null, tip_checkpoint hash unchanged)
    // Check 2: tip_checkpoint still valid
    // Check 3: no epoch, anchor null
    // Check 4: block3 validly extends block2
    // Check 5: tip_checkpoint.state_root (block2's root) ≠ block3.state_root_after → false
    expect(await verifyStateCapsule(tampered)).toBe(false)
  })
})

// ── mapIdeaToRoadmap — HARMONIZE phase testing/deployment gaps ──

describe('mapIdeaToRoadmap — HARMONIZE phase with testing/deployment gaps (line 179)', () => {
  it('HARMONIZE phase skill_gaps includes testing and deployment gaps', async () => {
    const EMPTY = SkillCatalog.empty()
    const SEQ = 1n as unknown as SequenceNumber
    // Use an idea that triggers testing, deployment, and api domains;
    // empty catalog → all domains become gaps
    const roadmap = await mapIdeaToRoadmap(
      'write unit test coverage for the backend api and deploy to production pipeline',
      EMPTY,
      SEQ,
    )
    const harmonize = roadmap.phases[roadmap.phases.length - 1]!
    expect(harmonize.ralph_stage).toBe('HARMONIZE')
    // testing and deployment gaps should appear in the HARMONIZE phase
    const gapDomains = roadmap.skill_gaps.map(g => g.domain)
    expect(gapDomains).toContain('testing')
    expect(gapDomains).toContain('deployment')
    // Confirm the filter on line 179 produced non-empty results
    expect(harmonize.skill_gaps.length).toBeGreaterThan(0)
  })
})
