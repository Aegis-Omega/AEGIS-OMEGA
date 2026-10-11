import test from 'node:test'
import assert from 'node:assert/strict'
import { verifyArtifactBytes, normalizeExpectedDigest, MAX_ARTIFACT_SIZE } from '../src/lib/artifactIntegrity.ts'

const abcHash = 'ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad'
const blob = new Blob(['abc'])

test('SHA-256 matches independent published abc test vector', async () => {
  const got = await verifyArtifactBytes(blob, '')
  assert.equal(got.digest, abcHash)
  assert.equal(got.verdict, 'computed')
  assert.equal(got.bytes, 3)
})
test('trusted reference comparison is byte-identical', async () => {
  const got = await verifyArtifactBytes(blob, 'SHA256:' + abcHash.toUpperCase())
  assert.equal(got.verdict, 'matched')
})
test('explicitly refuses a different reference', async () => {
  const got = await verifyArtifactBytes(blob, '0'.repeat(64))
  assert.equal(got.verdict, 'mismatch')
})
test('cannot silently accept malformed reference hash', async () => {
  await assert.rejects(() => verifyArtifactBytes(blob, 'not-actually-a-sha256'), /exactly 64/)
  assert.equal(normalizeExpectedDigest(''), null)
})
test('file-size cap fails closed before bytes are read', async () => {
  const oversized = { size: MAX_ARTIFACT_SIZE + 1, arrayBuffer(){throw Error('not expected to be called')} }
  await assert.rejects(() => verifyArtifactBytes(oversized, ''), /Maximum 32 MiB/)
})
test('cryptography unavailable results in error, never PASS', async () => {
  await assert.rejects(() => verifyArtifactBytes(blob, '', null), /unavailable/)
})
test('binary bytes are hashed rather than UTF-8 conversion', async () => {
  const raw = new Blob([new Uint8Array([0, 255, 0, 128])])
  const expected = '787a4bce1c8b1ef7f111820f3840c98b4ddf51d55f5e7a9b007fb6224bb563bc'
  const actual = await verifyArtifactBytes(raw, '')
  assert.equal(actual.digest, expected)
  assert.equal(actual.bytes, 4)
  assert.equal(actual.verdict, 'computed')
  // Confirms raw binary does not stringify to a text representation.
  assert.notEqual(actual.digest, (await verifyArtifactBytes(new Blob(['0,255,0,128']), '')).digest)
})