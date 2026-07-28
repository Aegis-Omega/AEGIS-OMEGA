// ============================================================
// SOVEREIGN OMEGA - Outcome Evidence Artifact Store
// EPISTEMIC TIER: T2 - durable browser adapter, mechanically checked
//
// This store snapshots, schema-checks, re-derives, and persists assessed
// evidence artifacts. Embedded signatures establish internal integrity;
// external operator trust remains the replay adapter's responsibility. The
// store never grants authority, executes mutations, or updates competence.
// Content roots are recomputed before and after persistence.
// ============================================================

import { canonicalizeJCS } from '../core/canonicalize.js'
import { hashValue } from '../core/hashing.js'
import { assertIJsonValue } from '../core/i-json.js'
import { deepFreeze } from '../core/immutable.js'
import type { SHA256Hex } from '../core/types.js'
import {
  assessAdaptationOutcome,
  normalizeAdaptationOutcomeInputV1,
  verifyOutcomeVerifierTrustPolicyV1,
} from './outcome-comparator.js'
import type {
  OutcomeEvidenceArtifactStore,
  OutcomeEvidenceArtifactV1,
  OutcomeEvidencePersistenceReceiptV1,
} from './outcome-comparator.js'

const DEFAULT_DATABASE_NAME = 'sovereign-omega-outcome-evidence'
const DATABASE_VERSION = 1
const ARTIFACTS_STORE = 'outcome-evidence-artifacts'
const HASH_PATTERN = /^[0-9a-f]{64}$/

export class OutcomeEvidenceArtifactStoreError extends Error {
  override readonly name = 'OutcomeEvidenceArtifactStoreError'

  constructor(message: string) {
    super(message)
    Object.setPrototypeOf(this, new.target.prototype)
  }
}

export interface ReadableOutcomeEvidenceArtifactStore extends OutcomeEvidenceArtifactStore {
  read(artifactRoot: SHA256Hex): Promise<OutcomeEvidenceArtifactV1 | null>
}

export class IndexedDBOutcomeEvidenceArtifactStore implements ReadableOutcomeEvidenceArtifactStore {
  private database: IDBDatabase | null = null
  private opening: Promise<IDBDatabase> | null = null
  private closeGeneration = 0

  constructor(private readonly databaseName = DEFAULT_DATABASE_NAME) {
    if (databaseName.trim() === '') {
      throw new OutcomeEvidenceArtifactStoreError('database name must not be empty')
    }
  }

  async open(): Promise<void> {
    if (this.database !== null) return
    if (this.opening === null) {
      const generation = this.closeGeneration
      this.opening = openDatabase(this.databaseName).then(database => {
        if (generation !== this.closeGeneration) {
          database.close()
          throw new OutcomeEvidenceArtifactStoreError('artifact store closed while opening')
        }
        database.onversionchange = () => {
          database.close()
          if (this.database === database) this.database = null
        }
        this.database = database
        return database
      }).finally(() => {
        this.opening = null
      })
    }
    await this.opening
  }

  close(): void {
    this.closeGeneration += 1
    this.database?.close()
    this.database = null
  }

  async persist(
    artifact: OutcomeEvidenceArtifactV1,
  ): Promise<OutcomeEvidencePersistenceReceiptV1> {
    const database = this.requireDatabase()
    const snapshot = snapshotArtifact(artifact, 'outcome evidence artifact')
    await verifyArtifact(snapshot)

    const existing = await readRecord(database, snapshot.artifact_root)
    if (existing !== null) {
      await assertIdenticalArtifact(existing, snapshot)
      return persistenceReceipt(this.databaseName, snapshot.artifact_root)
    }

    try {
      await addRecord(database, snapshot)
    } catch (error) {
      if (!isConstraintError(error)) throw error
      const racedRecord = await readRecord(database, snapshot.artifact_root)
      if (racedRecord === null) {
        throw new OutcomeEvidenceArtifactStoreError('artifact insert conflicted without a readable record')
      }
      await assertIdenticalArtifact(racedRecord, snapshot)
    }

    const persisted = await readRecord(database, snapshot.artifact_root)
    if (persisted === null) {
      throw new OutcomeEvidenceArtifactStoreError('artifact read-back failed')
    }
    await assertIdenticalArtifact(persisted, snapshot)
    return persistenceReceipt(this.databaseName, snapshot.artifact_root)
  }

  async read(artifactRoot: SHA256Hex): Promise<OutcomeEvidenceArtifactV1 | null> {
    assertArtifactRoot(artifactRoot)
    const record = await readRecord(this.requireDatabase(), artifactRoot)
    if (record === null) return null
    const snapshot = snapshotArtifact(record, 'persisted outcome evidence artifact')
    await verifyArtifact(snapshot)
    return snapshot
  }

  private requireDatabase(): IDBDatabase {
    if (this.database === null) {
      throw new OutcomeEvidenceArtifactStoreError('artifact store is not open')
    }
    return this.database
  }
}

async function verifyArtifact(artifact: OutcomeEvidenceArtifactV1): Promise<void> {
  assertExactKeys('artifact', artifact, [
    'artifact_kind',
    'artifact_root',
    'assessment',
    'evidence_input',
    'schema_version',
    'verifier_trust_anchor',
  ])
  assertArtifactRoot(artifact.artifact_root)
  if (artifact.schema_version !== '1.0.0' ||
      artifact.artifact_kind !== 'AEGIS_OUTCOME_EVIDENCE_ARTIFACT_V1') {
    throw new OutcomeEvidenceArtifactStoreError('artifact schema is unsupported')
  }
  const { artifact_root: _artifactRoot, ...body } = artifact
  const expectedRoot = await hashValue({
    domain: 'AEGIS_OUTCOME_EVIDENCE_ARTIFACT_V1',
    artifact: body,
  })
  if (artifact.artifact_root !== expectedRoot) {
    throw new OutcomeEvidenceArtifactStoreError('artifact root mismatch')
  }

  try {
    assertExactKeys('artifact.verifier_trust_anchor', artifact.verifier_trust_anchor, [
      'governed_policy_root',
      'trust_policy',
      'trust_policy_digest',
      'verifier_trust_root',
      'verifiers',
    ])
    const policy = artifact.verifier_trust_anchor.trust_policy
    const trustAnchor = await verifyOutcomeVerifierTrustPolicyV1(
      policy,
      policy.governed_policy_root,
      policy.signer_public_key,
    )
    const expectedAnchor = {
      governed_policy_root: trustAnchor.governed_policy_root,
      verifier_trust_root: trustAnchor.verifier_trust_root,
      verifiers: trustAnchor.verifiers,
      trust_policy_digest: trustAnchor.trust_policy_digest,
      trust_policy: trustAnchor.trust_policy,
    }
    assertCanonicalEqual(
      'artifact verifier trust anchor',
      artifact.verifier_trust_anchor,
      expectedAnchor,
    )
    const normalizedInput = normalizeAdaptationOutcomeInputV1(artifact.evidence_input)
    assertCanonicalEqual('artifact evidence input', artifact.evidence_input, normalizedInput)
    const expectedAssessment = await assessAdaptationOutcome(normalizedInput, trustAnchor)
    assertCanonicalEqual('artifact assessment', artifact.assessment, expectedAssessment)
  } catch (error) {
    if (error instanceof OutcomeEvidenceArtifactStoreError) throw error
    throw new OutcomeEvidenceArtifactStoreError(
      `artifact schema or derivation is invalid: ${error instanceof Error ? error.message : String(error)}`,
    )
  }
}

async function assertIdenticalArtifact(
  persisted: OutcomeEvidenceArtifactV1,
  expected: OutcomeEvidenceArtifactV1,
): Promise<void> {
  const snapshot = snapshotArtifact(persisted, 'persisted outcome evidence artifact')
  await verifyArtifact(snapshot)
  if (!equalBytes(canonicalizeJCS(snapshot), canonicalizeJCS(expected))) {
    throw new OutcomeEvidenceArtifactStoreError('artifact root collision or persisted payload mismatch')
  }
}

function assertArtifactRoot(value: unknown): asserts value is SHA256Hex {
  if (typeof value !== 'string' || !HASH_PATTERN.test(value) || value === '0'.repeat(64)) {
    throw new OutcomeEvidenceArtifactStoreError('artifact root must be resolved lowercase SHA-256 hex')
  }
}

function snapshotArtifact(value: unknown, label: string): OutcomeEvidenceArtifactV1 {
  try {
    assertIJsonValue(value, label)
    const snapshot = structuredClone(value) as unknown
    assertIJsonValue(snapshot, label)
    if (snapshot === null || typeof snapshot !== 'object' || Array.isArray(snapshot)) {
      throw new OutcomeEvidenceArtifactStoreError('artifact must be an object')
    }
    return deepFreeze(snapshot) as OutcomeEvidenceArtifactV1
  } catch (error) {
    if (error instanceof OutcomeEvidenceArtifactStoreError) throw error
    throw new OutcomeEvidenceArtifactStoreError(
      `${label} is not a closed I-JSON value: ${error instanceof Error ? error.message : String(error)}`,
    )
  }
}

function assertExactKeys(
  label: string,
  value: unknown,
  expectedKeys: readonly string[],
): asserts value is Record<string, unknown> {
  if (value === null || typeof value !== 'object' || Array.isArray(value)) {
    throw new OutcomeEvidenceArtifactStoreError(`${label} must be an object`)
  }
  const keys = Object.keys(value).sort()
  const expected = [...expectedKeys].sort()
  if (keys.length !== expected.length || keys.some((key, index) => key !== expected[index])) {
    throw new OutcomeEvidenceArtifactStoreError(`${label} has unexpected or missing fields`)
  }
}

function assertCanonicalEqual(label: string, left: unknown, right: unknown): void {
  if (!equalBytes(canonicalizeJCS(left), canonicalizeJCS(right))) {
    throw new OutcomeEvidenceArtifactStoreError(`${label} does not match its verified derivation`)
  }
}

function equalBytes(left: Uint8Array, right: Uint8Array): boolean {
  if (left.byteLength !== right.byteLength) return false
  for (let index = 0; index < left.byteLength; index += 1) {
    if (left[index] !== right[index]) return false
  }
  return true
}

function persistenceReceipt(
  databaseName: string,
  artifactRoot: SHA256Hex,
): OutcomeEvidencePersistenceReceiptV1 {
  return deepFreeze({
    artifact_root: artifactRoot,
    artifact_reference: `indexeddb:${encodeURIComponent(databaseName)}/${ARTIFACTS_STORE}/${artifactRoot}`,
  })
}

function openDatabase(name: string): Promise<IDBDatabase> {
  return new Promise((resolve, reject) => {
    const request = indexedDB.open(name, DATABASE_VERSION)
    request.onupgradeneeded = () => {
      const database = request.result
      if (!database.objectStoreNames.contains(ARTIFACTS_STORE)) {
        database.createObjectStore(ARTIFACTS_STORE, { keyPath: 'artifact_root' })
      }
    }
    request.onsuccess = () => resolve(request.result)
    request.onerror = () => reject(new OutcomeEvidenceArtifactStoreError(
      `failed to open artifact store: ${request.error?.message ?? 'unknown error'}`,
    ))
  })
}

function readRecord(
  database: IDBDatabase,
  artifactRoot: SHA256Hex,
): Promise<OutcomeEvidenceArtifactV1 | null> {
  return new Promise((resolve, reject) => {
    const transaction = database.transaction(ARTIFACTS_STORE, 'readonly')
    const request = transaction.objectStore(ARTIFACTS_STORE).get(artifactRoot)
    let result: OutcomeEvidenceArtifactV1 | null = null
    let settled = false
    const fail = (message: string, error: DOMException | null) => {
      if (settled) return
      settled = true
      reject(new OutcomeEvidenceArtifactStoreError(
        `${message}: ${error?.message ?? 'unknown error'}`,
      ))
    }
    request.onsuccess = () => {
      result = (request.result as OutcomeEvidenceArtifactV1 | undefined) ?? null
    }
    request.onerror = () => fail('failed to read artifact', request.error)
    transaction.oncomplete = () => {
      if (settled) return
      settled = true
      resolve(result)
    }
    transaction.onerror = () => fail('artifact read transaction failed', transaction.error)
    transaction.onabort = () => fail('artifact read transaction aborted', transaction.error)
  })
}

function addRecord(database: IDBDatabase, artifact: OutcomeEvidenceArtifactV1): Promise<void> {
  return new Promise((resolve, reject) => {
    const transaction = database.transaction(ARTIFACTS_STORE, 'readwrite')
    const request = transaction.objectStore(ARTIFACTS_STORE).add(artifact)
    let operationError: DOMException | null = null
    request.onerror = () => { operationError = request.error }
    transaction.oncomplete = () => resolve()
    transaction.onerror = () => { operationError ??= transaction.error }
    transaction.onabort = () => reject(
      operationError ?? transaction.error ??
      new OutcomeEvidenceArtifactStoreError('artifact insert aborted'),
    )
  })
}

function isConstraintError(error: unknown): boolean {
  return error !== null && typeof error === 'object' &&
    'name' in error && error.name === 'ConstraintError'
}
