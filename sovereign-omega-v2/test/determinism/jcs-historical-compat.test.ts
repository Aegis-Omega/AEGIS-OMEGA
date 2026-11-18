import { describe, expect, it } from 'vitest'
import { canonicalizeJCS, canonicalizeJCSString } from '../../src/core/canonicalize.js'
import { hashValue, sha256Hex, verifyHash } from '../../src/core/hashing.js'
import { generateKeypair, signBytes, verifyBytes } from '../../src/consensus/crypto.js'
import { hashScaleOSPayloadV1 } from '../../src/scale-os/control-plane.js'

// JCS-1 Python receipts sort by Unicode code point; RFC 8785 uses UTF-16 units.
// These fixtures pin both byte sequences without migrating historical receipts.
const BMP = '\uE000'
const EMOJI = '\u{1F600}'
const bytes = (value: string): Uint8Array => new TextEncoder().encode(value)

describe('historical canonicalization compatibility', () => {
  it('pins legacy and corrected hashes of conflicting Unicode keys', async () => {
    const value = { [BMP]: 1, [EMOJI]: 2 }
    const legacy = '{"' + BMP + '":1,"' + EMOJI + '":2}'
    const corrected = '{"' + EMOJI + '":2,"' + BMP + '":1}'
    const historicalHash = await sha256Hex(bytes(legacy))

    expect(canonicalizeJCSString(value)).toBe(corrected)
    expect(historicalHash).toBe('871954531859c7572c6279f90eb83a594ddc3a289e8bdc28d2a84ffb8c1a1703')
    expect(await hashValue(value)).toBe('28c95d1bbb2209223307e62f489020e8f9e0cfa16adf2daf6d88127a1e8dd22a')
    expect(await verifyHash(bytes(corrected), historicalHash)).toBe(false)
  })

  it('does not change the hash of Unicode values under ASCII keys', async () => {
    const value = { a: EMOJI, z: BMP }
    expect(await hashValue(value)).toBe('daf9a5215bbf7f6aabd4878d9e641e7044d221c3ede348fc3e13752ed849f10a')
  })

  it('pins the nested Scale OS payload hash', async () => {
    const payload = { [BMP]: 'han', [EMOJI]: 'emoji' }
    expect(await hashScaleOSPayloadV1(payload)).toBe('93b9c5575b3a3380b5c6984529778ea696db8981d24e99d0658a9505c3dbb20f')
  })

  it('preserves representative ASCII-only LedgerEntry hashing', async () => {
    const entry = {
      frame_hash: 'f'.repeat(64),
      governance_hash: 'e'.repeat(64),
      previous_hash: '0'.repeat(64),
      sequence: 1n,
      timestamp_ms: 1600000000000,
    }
    expect(await hashValue(entry)).toBe('c65aa1d064f0a48299fa15807feb8dc2e3045f49d44e643895cc80012bbe36ba')
  })

  it('does not silently migrate legacy Ed25519 signatures', async () => {
    const value = { [BMP]: 1, [EMOJI]: 2 }
    const legacy = bytes('{"' + BMP + '":1,"' + EMOJI + '":2}')
    const corrected = canonicalizeJCS(value)
    const { privateKey, publicKey } = await generateKeypair(new Uint8Array(32).fill(7))
    const signature = await signBytes(privateKey, legacy)

    expect(await verifyBytes(publicKey, legacy, signature)).toBe(true)
    expect(await verifyBytes(publicKey, corrected, signature)).toBe(false)
  })
})
