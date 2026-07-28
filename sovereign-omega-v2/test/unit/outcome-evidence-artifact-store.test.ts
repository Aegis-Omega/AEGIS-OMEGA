import 'fake-indexeddb/auto'

import { describe, expect, it } from 'vitest'
import { hashValue } from '../../src/core/hashing.js'
import {
  IndexedDBOutcomeEvidenceArtifactStore,
  OutcomeEvidenceArtifactStoreError,
} from '../../src/metacognition/outcome-evidence-artifact-store.js'
import type {
  AdaptationOutcomeInput,
  OutcomeEvidenceArtifactV1,
} from '../../src/metacognition/outcome-comparator.js'
import {
  createOutcomeEvidenceArtifactFixture,
  H,
} from '../helpers/outcome-evidence-fixture.js'

let databaseCounter = 0

function databaseName(): string {
  databaseCounter += 1
  return `outcome-evidence-test-${databaseCounter}`
}

async function artifact(): Promise<OutcomeEvidenceArtifactV1> {
  return createOutcomeEvidenceArtifactFixture()
}

function overwriteRaw(databaseNameValue: string, value: unknown): Promise<void> {
  return new Promise((resolve, reject) => {
    const open = indexedDB.open(databaseNameValue, 1)
    open.onerror = () => reject(open.error)
    open.onsuccess = () => {
      const database = open.result
      const transaction = database.transaction('outcome-evidence-artifacts', 'readwrite')
      transaction.objectStore('outcome-evidence-artifacts').put(value)
      transaction.oncomplete = () => { database.close(); resolve() }
      transaction.onerror = () => { database.close(); reject(transaction.error) }
    }
  })
}

function openVersion(databaseNameValue: string, version: number): Promise<void> {
  return new Promise((resolve, reject) => {
    const timeout = setTimeout(() => reject(new Error('database upgrade timed out')), 1_000)
    const open = indexedDB.open(databaseNameValue, version)
    open.onblocked = () => {
      clearTimeout(timeout)
      reject(new Error('database upgrade was blocked'))
    }
    open.onerror = () => {
      clearTimeout(timeout)
      reject(open.error)
    }
    open.onsuccess = () => {
      clearTimeout(timeout)
      open.result.close()
      resolve()
    }
  })
}

describe('IndexedDBOutcomeEvidenceArtifactStore', () => {
  it('requires an open store', async () => {
    const store = new IndexedDBOutcomeEvidenceArtifactStore(databaseName())
    await expect(store.persist(await artifact())).rejects.toThrow('artifact store is not open')
    await expect(store.read(H('a'))).rejects.toThrow('artifact store is not open')
  })

  it('persists, reads back, re-hashes, and freezes an artifact', async () => {
    const name = databaseName()
    const store = new IndexedDBOutcomeEvidenceArtifactStore(name)
    await store.open()
    const value = await artifact()

    const receipt = await store.persist(value)
    expect(receipt).toEqual({
      artifact_root: value.artifact_root,
      artifact_reference: `indexeddb:${name}/outcome-evidence-artifacts/${value.artifact_root}`,
    })
    const restored = await store.read(value.artifact_root)
    expect(restored).toEqual(value)
    expect(Object.isFrozen(restored)).toBe(true)
    expect(Object.isFrozen(restored?.assessment)).toBe(true)
    store.close()
  })

  it('treats an identical duplicate as idempotent', async () => {
    const store = new IndexedDBOutcomeEvidenceArtifactStore(databaseName())
    await store.open()
    const value = await artifact()
    const first = await store.persist(value)
    const second = await store.persist(structuredClone(value))
    expect(second).toEqual(first)
    store.close()
  })

  it('coalesces concurrent opens without leaking a connection', async () => {
    const name = databaseName()
    const store = new IndexedDBOutcomeEvidenceArtifactStore(name)
    await Promise.all([store.open(), store.open(), store.open()])
    store.close()
    await expect(openVersion(name, 2)).resolves.toBeUndefined()
  })

  it('recovers an identical concurrent insert race across store instances', async () => {
    const name = databaseName()
    const firstStore = new IndexedDBOutcomeEvidenceArtifactStore(name)
    const secondStore = new IndexedDBOutcomeEvidenceArtifactStore(name)
    await firstStore.open()
    await secondStore.open()
    const value = await artifact()

    const [first, second] = await Promise.all([
      firstStore.persist(value),
      secondStore.persist(structuredClone(value)),
    ])
    expect(second).toEqual(first)
    expect(await firstStore.read(value.artifact_root)).toEqual(value)
    firstStore.close()
    secondStore.close()
  })

  it('survives close and reopen with verified read-back', async () => {
    const store = new IndexedDBOutcomeEvidenceArtifactStore(databaseName())
    await store.open()
    const value = await artifact()
    await store.persist(value)
    store.close()

    await store.open()
    expect(await store.read(value.artifact_root)).toEqual(value)
    store.close()
  })

  it('rejects an artifact with a forged content root', async () => {
    const store = new IndexedDBOutcomeEvidenceArtifactStore(databaseName())
    await store.open()
    const value = await artifact()
    const forged = { ...value, artifact_root: H('0') }
    await expect(store.persist(forged)).rejects.toThrow('artifact root')
    store.close()
  })

  it('snapshots mutable input before its first asynchronous boundary', async () => {
    const store = new IndexedDBOutcomeEvidenceArtifactStore(databaseName())
    await store.open()
    const value = await artifact()
    const mutable = structuredClone(value)
    const expected = structuredClone(value)

    const persistence = store.persist(mutable)
    ;(mutable as unknown as {
      evidence_input: { post_gaps: typeof mutable.evidence_input.baseline.gaps }
    }).evidence_input.post_gaps = mutable.evidence_input.baseline.gaps
    await expect(persistence).resolves.toMatchObject({ artifact_root: value.artifact_root })
    expect(await store.read(value.artifact_root)).toEqual(expected)
    store.close()
  })

  it('rejects non-I-JSON values before canonical aliases can be persisted', async () => {
    const store = new IndexedDBOutcomeEvidenceArtifactStore(databaseName())
    await store.open()
    const value = await artifact()
    const aliased = structuredClone(value) as OutcomeEvidenceArtifactV1 & {
      evidence_input: AdaptationOutcomeInput & { alias?: bigint; ignored?: undefined }
    }
    aliased.evidence_input.alias = 1n
    aliased.evidence_input.ignored = undefined
    const { artifact_root: _root, ...body } = aliased
    const rootedAlias = {
      ...body,
      artifact_root: await hashValue({
        domain: 'AEGIS_OUTCOME_EVIDENCE_ARTIFACT_V1',
        artifact: body,
      }),
    } as OutcomeEvidenceArtifactV1

    await expect(store.persist(rootedAlias)).rejects.toThrow('non-JSON bigint')

    const negativeZero = structuredClone(value) as OutcomeEvidenceArtifactV1 & {
      evidence_input: AdaptationOutcomeInput & {
        verification: Array<{ step_index: number }>
      }
    }
    negativeZero.evidence_input.verification[0]!.step_index = -0
    await expect(store.persist(negativeZero)).rejects.toThrow('negative zero')
    store.close()
  })

  it('rejects accessors without invoking them before snapshotting', async () => {
    const store = new IndexedDBOutcomeEvidenceArtifactStore(databaseName())
    await store.open()
    const value = structuredClone(await artifact())
    const assessment = value.assessment
    let reads = 0
    Object.defineProperty(value, 'assessment', {
      enumerable: true,
      get() { reads += 1; return assessment },
    })

    await expect(store.persist(value)).rejects.toThrow('enumerable data property')
    expect(reads).toBe(0)
    store.close()
  })

  it('rejects a self-consistent but malformed derived artifact', async () => {
    const store = new IndexedDBOutcomeEvidenceArtifactStore(databaseName())
    await store.open()
    const value = await artifact()
    const malformedBody = {
      ...value,
      assessment: null,
    }
    const { artifact_root: _oldRoot, ...body } = malformedBody
    const malformed = {
      ...body,
      artifact_root: await hashValue({
        domain: 'AEGIS_OUTCOME_EVIDENCE_ARTIFACT_V1',
        artifact: body,
      }),
    } as unknown as OutcomeEvidenceArtifactV1

    await expect(store.persist(malformed)).rejects.toThrow('assessment does not match')
    store.close()
  })

  it('fails closed when persisted bytes are changed behind the store', async () => {
    const name = databaseName()
    const store = new IndexedDBOutcomeEvidenceArtifactStore(name)
    await store.open()
    const value = await artifact()
    await store.persist(value)
    await overwriteRaw(name, {
      ...value,
      evidence_input: {
        ...value.evidence_input,
        post_gaps: value.evidence_input.baseline.gaps,
      },
    })

    await expect(store.read(value.artifact_root)).rejects.toThrow('artifact root mismatch')
    await expect(store.persist(value)).rejects.toThrow(OutcomeEvidenceArtifactStoreError)
    store.close()
  })

  it('rejects canonical aliases in an existing record during idempotent persistence', async () => {
    const name = databaseName()
    const store = new IndexedDBOutcomeEvidenceArtifactStore(name)
    await store.open()
    const value = await artifact()
    await store.persist(value)
    const aliased = structuredClone(value) as OutcomeEvidenceArtifactV1 & {
      evidence_input: AdaptationOutcomeInput & {
        verification: Array<{ step_index: number }>
      }
    }
    aliased.evidence_input.verification[0]!.step_index = -0
    await overwriteRaw(name, aliased)

    await expect(store.persist(value)).rejects.toThrow('negative zero')
    store.close()
  })

  it('returns null for a resolved root that is not present', async () => {
    const store = new IndexedDBOutcomeEvidenceArtifactStore(databaseName())
    await store.open()
    await expect(store.read(H('a'))).resolves.toBeNull()
    store.close()
  })

  it('rejects empty database names and unresolved lookup roots', async () => {
    expect(() => new IndexedDBOutcomeEvidenceArtifactStore(' ')).toThrow('database name')
    const store = new IndexedDBOutcomeEvidenceArtifactStore(databaseName())
    await store.open()
    await expect(store.read(H('0'))).rejects.toThrow('artifact root')
    store.close()
  })
})
