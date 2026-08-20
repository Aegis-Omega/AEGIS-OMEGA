import { describe, expect, it } from 'vitest'
import { hashValue } from '../../../src/core/hashing.js'
import type { SHA256Hex, SequenceNumber } from '../../../src/core/types.js'
import {
  MetacognitiveLoop,
  certifyMetacognitiveLoop,
} from '../../../src/metacognition/loop.js'
import type { MetacognitiveEntry } from '../../../src/metacognition/loop.js'
import type { ReflexiveCycleReceiptV1 } from '../../../src/reflexive-self-model/contracts.js'
import {
  ReflexiveMetacognitionBridgeError,
  appendReflexiveCycleToMetacognition,
} from '../../../src/reflexive-self-model/metacognition-bridge.js'

const H1 = '1'.repeat(64)
const H2 = '2'.repeat(64)
const H3 = '3'.repeat(64)
const H4 = '4'.repeat(64)
const H5 = '5'.repeat(64)
const SEQ = (n: number) => BigInt(n) as SequenceNumber

async function cycleReceipt(
  cycle_status = 'CYCLE_CLOSED',
  contradiction_free = true,
): Promise<ReflexiveCycleReceiptV1> {
  const body = {
    record_kind: 'REFLEXIVE_CYCLE_RECEIPT_V1' as const,
    schema_version: '1.0.0' as const,
    cycle_id: 'cycle-bridge-1',
    snapshot_digest: H1,
    prediction_digest: H2,
    observation_digest: H3,
    prediction_error_receipt_digest: H4,
    update_proposal_digest: H5,
    replayable: true,
    scorable: cycle_status === 'CYCLE_CLOSED',
    contradiction_free,
    cycle_status,
    authority: 'REFLEXIVE_EVIDENCE_ONLY' as const,
  }
  return { ...body, cycle_digest: await hashValue(body) }
}

describe('REFLEXIVE_SELF_MODEL_V1 metacognition bridge', () => {
  it('projects a closed cycle into evidence-only metacognitive layers without CONSCIOUSNESS', async () => {
    const receipt = await cycleReceipt()
    const result = await appendReflexiveCycleToMetacognition(
      MetacognitiveLoop.empty(),
      receipt,
      SEQ(10),
    )

    expect(result.entries).toHaveLength(4)
    expect(result.entries.map(entry => entry.observation.layer)).toEqual([
      'SELF_MODEL',
      'PERCEPTION',
      'METACOGNITIVE',
      'SELF_MODEL',
    ])
    expect(result.entries.every(entry => entry.observation.tier === 'T2')).toBe(true)
    expect(result.entries.some(entry => entry.observation.layer === 'CONSCIOUSNESS')).toBe(false)
    expect(result.entries[0]!.observation.signal).toContain(receipt.prediction_digest.slice(0, 12))
    expect(result.entries[1]!.observation.signal).toContain(receipt.observation_digest.slice(0, 12))
    expect(result.entries[2]!.observation.signal).toContain(
      receipt.prediction_error_receipt_digest.slice(0, 12),
    )
    expect(result.entries[3]!.observation.signal).toContain(receipt.update_proposal_digest.slice(0, 12))
    expect(result.loop.length).toBe(4)
  })

  it('adds a separate METACOGNITIVE contradiction observation when contradiction is preserved', async () => {
    const receipt = await cycleReceipt('CONTRADICTION_DETECTED', false)
    const result = await appendReflexiveCycleToMetacognition(
      MetacognitiveLoop.empty(),
      receipt,
      SEQ(20),
    )

    expect(result.entries).toHaveLength(5)
    expect(result.entries[4]!.observation.layer).toBe('METACOGNITIVE')
    expect(result.entries[4]!.observation.signal).toContain('CONTRADICTION_DETECTED')
    expect(result.entries[4]!.observation.signal).toContain(receipt.cycle_digest.slice(0, 12))
  })

  it('rejects a cycle receipt whose body no longer matches cycle_digest', async () => {
    const receipt = await cycleReceipt()
    const forged: ReflexiveCycleReceiptV1 = {
      ...receipt,
      cycle_status: 'CONTRADICTION_DETECTED',
      contradiction_free: false,
    }

    await expect(
      appendReflexiveCycleToMetacognition(
        MetacognitiveLoop.empty(),
        forged,
        SEQ(30),
      ),
    ).rejects.toThrow(ReflexiveMetacognitionBridgeError)
  })

  it('replays the same cycle from the same genesis to identical terminal and certificate hashes', async () => {
    const receipt = await cycleReceipt()
    const first = await appendReflexiveCycleToMetacognition(
      MetacognitiveLoop.empty(),
      receipt,
      SEQ(40),
    )
    const second = await appendReflexiveCycleToMetacognition(
      MetacognitiveLoop.empty(),
      receipt,
      SEQ(40),
    )

    const certA = await certifyMetacognitiveLoop(first.loop.getAll())
    const certB = await certifyMetacognitiveLoop(second.loop.getAll())

    expect(certA.is_valid).toBe(true)
    expect(certB.is_valid).toBe(true)
    expect(first.loop.lastHash).toBe(second.loop.lastHash)
    expect(certA.certificate_hash).toBe(certB.certificate_hash)
  })

  it('metacognitive certification detects a tampered bridge entry', async () => {
    const receipt = await cycleReceipt()
    const result = await appendReflexiveCycleToMetacognition(
      MetacognitiveLoop.empty(),
      receipt,
      SEQ(50),
    )
    const entries = result.loop.getAll()
    const tampered: readonly MetacognitiveEntry[] = [
      {
        ...entries[0]!,
        entry_hash: 'f'.repeat(64) as SHA256Hex,
      },
      ...entries.slice(1),
    ]

    const certificate = await certifyMetacognitiveLoop(tampered)
    expect(certificate.is_valid).toBe(false)
  })
})
