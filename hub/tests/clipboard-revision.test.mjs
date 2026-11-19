import {test} from 'node:test'
import assert from 'node:assert/strict'
import {copyDigestIfCurrent,verifyArtifactBytes,normalizeExpectedDigest} from '../src/lib/artifactIntegrity.ts'

test('known SHA-256 sample remains correct', async () => {
  const r=await verifyArtifactBytes(new Blob(['abc']), 'SHA256:ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad')
  assert.equal(r.verdict, 'matched')
})
test('valid current digest copies successfully', async () => {
  let revision=1, copied=[]
  const state=await copyDigestIfCurrent('a'.repeat(64),1,()=>revision,async text=>copied.push(text))
  assert.equal(state,'copied'); assert.deepEqual(copied,['a'.repeat(64)])
})
test('superseded revision does not call clipboard', async () => {
  let writes=0
  const state=await copyDigestIfCurrent('a'.repeat(64),1,()=>2,async()=>{writes++})
  assert.equal(state,'stale'); assert.equal(writes,0)
})
test('revision changed during unresolved clipboard promise never reports copied',async()=>{
  let finish,rev=0
  const writeText=()=>new Promise(resolve=>{finish=resolve})
  const p=copyDigestIfCurrent('old',0,()=>rev,writeText)
  rev=1; finish()
  assert.equal(await p,'stale')
})
test('clipboard denial still throws; no false positive',async()=>{
  await assert.rejects(copyDigestIfCurrent('hash',0,()=>0,async()=>{throw Error('permission denied')}),/permission denied/)
})
test('digest validation still rejects fabricated reference',()=>{
  assert.throws(()=>normalizeExpectedDigest('not_sha'),/64 hexadecimal/)
})
