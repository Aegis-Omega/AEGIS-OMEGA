// ============================================================
// AEGIS Add-Only Cross-Runtime Receipt Source V1
// PROVENANCE ASSURANCE: T2->T3 implemented; projection admission pending
// ============================================================

import { canonicalizeJCS } from '../core/canonicalize.js'
import { assertIJsonValue } from '../core/i-json.js'
import type { SHA256Hex } from '../core/types.js'
import {
  assertCrossRuntimeReceiptIdV1,
  assertReceiptTrustRegistryRootV1,
  normalizeCrossRuntimeReceiptEnvelopeV1,
  normalizeReceiptTrustRegistryV1,
} from './cross-runtime-receipts.js'
import type {
  CrossRuntimeReceiptEnvelopeV1,
  ReceiptTrustRegistryV1,
} from './cross-runtime-receipts.js'
import type { CrossRuntimeReceiptSourceV1 } from './receipt-resolver.js'

const DEFAULT_DATABASE_NAME = 'sovereign-omega-authoritative-receipts'
const DATABASE_VERSION = 1
const RECEIPTS_STORE = 'cross-runtime-receipts'
const REGISTRIES_STORE = 'receipt-trust-registries'
const HASH_PATTERN = /^[0-9a-f]{64}$/

interface StoredReceiptRecord {
  readonly receipt_id: SHA256Hex
  readonly envelope: CrossRuntimeReceiptEnvelopeV1
  readonly nonce_key: string
  readonly chain_slot: string
  readonly mutation_action_key?: string
}

interface StoredRegistryRecord {
  readonly registry_root: SHA256Hex
  readonly registry: ReceiptTrustRegistryV1
  readonly registry_version_key: string
}

export interface ReceiptSourcePersistenceResultV1 {
  readonly receipt_ids: readonly SHA256Hex[]
  readonly registry_roots: readonly SHA256Hex[]
}

export class IndexedDBCrossRuntimeReceiptSourceError extends Error {
  override readonly name = 'IndexedDBCrossRuntimeReceiptSourceError'

  constructor(message: string) {
    super(message)
    Object.setPrototypeOf(this, new.target.prototype)
  }
}

export class IndexedDBCrossRuntimeReceiptSourceV1 implements CrossRuntimeReceiptSourceV1 {
  private database: IDBDatabase | null = null
  private opening: Promise<IDBDatabase> | null = null
  private closeGeneration = 0

  constructor(private readonly databaseName = DEFAULT_DATABASE_NAME) {
    if (databaseName.trim() === '') fail('database name must not be empty')
  }

  async open(): Promise<void> {
    if (this.database !== null) return
    if (this.opening === null) {
      const generation = this.closeGeneration
      this.opening = openDatabase(this.databaseName).then(database => {
        if (generation !== this.closeGeneration) {
          database.close()
          fail('receipt source closed while opening')
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

  async persistReceipt(receipt: CrossRuntimeReceiptEnvelopeV1): Promise<SHA256Hex> {
    const result = await this.persistBatch([], [receipt])
    return result.receipt_ids[0]!
  }

  async persistTrustRegistry(registry: ReceiptTrustRegistryV1): Promise<SHA256Hex> {
    const result = await this.persistBatch([registry], [])
    return result.registry_roots[0]!
  }

  async persistBatch(
    registries: readonly ReceiptTrustRegistryV1[],
    receipts: readonly CrossRuntimeReceiptEnvelopeV1[],
  ): Promise<ReceiptSourcePersistenceResultV1> {
    const database = this.requireDatabase()
    const batch = snapshotBatch(registries, receipts)
    const normalizedRegistries = await Promise.all(batch.registries.map(async value => {
      const registry = normalizeReceiptTrustRegistryV1(value)
      await assertReceiptTrustRegistryRootV1(registry)
      return registry
    }))
    const normalizedReceipts = await Promise.all(batch.receipts.map(async value => {
      const receipt = normalizeCrossRuntimeReceiptEnvelopeV1(value)
      await assertCrossRuntimeReceiptIdV1(receipt)
      return receipt
    }))
    assertBatchUnique(normalizedRegistries, normalizedReceipts)

    const registryRecords = normalizedRegistries.map(toStoredRegistry)
    const receiptRecords = normalizedReceipts.map(toStoredReceipt)
    const missingRegistries: StoredRegistryRecord[] = []
    const missingReceipts: StoredReceiptRecord[] = []
    for (const record of registryRecords) {
      const existing = await readRecord<StoredRegistryRecord>(database, REGISTRIES_STORE, record.registry_root)
      if (existing === null) missingRegistries.push(record)
      else await assertIdenticalRegistryRecord(existing, record)
    }
    for (const record of receiptRecords) {
      const existing = await readRecord<StoredReceiptRecord>(database, RECEIPTS_STORE, record.receipt_id)
      if (existing === null) missingReceipts.push(record)
      else await assertIdenticalReceiptRecord(existing, record)
    }

    if (missingRegistries.length > 0 || missingReceipts.length > 0) {
      try {
        await addBatch(database, missingRegistries, missingReceipts)
      } catch (error) {
        if (!isConstraintError(error)) throw error
        await assertBatchNowPersisted(database, registryRecords, receiptRecords)
      }
    }
    await assertBatchNowPersisted(database, registryRecords, receiptRecords)
    return Object.freeze({
      registry_roots: Object.freeze(normalizedRegistries.map(value => value.registry_root)),
      receipt_ids: Object.freeze(normalizedReceipts.map(value => value.receipt_id)),
    })
  }

  async resolveReceipt(receiptId: SHA256Hex): Promise<CrossRuntimeReceiptEnvelopeV1 | null> {
    assertResolvedHash('receipt id', receiptId)
    const record = await readRecord<StoredReceiptRecord>(
      this.requireDatabase(), RECEIPTS_STORE, receiptId,
    )
    if (record === null) return null
    const normalized = normalizeStoredReceipt(record)
    await assertCrossRuntimeReceiptIdV1(normalized.envelope)
    if (normalized.receipt_id !== receiptId) fail('stored receipt primary key mismatch')
    return normalized.envelope
  }

  async resolveTrustRegistry(registryRoot: SHA256Hex): Promise<ReceiptTrustRegistryV1 | null> {
    assertResolvedHash('registry root', registryRoot)
    const record = await readRecord<StoredRegistryRecord>(
      this.requireDatabase(), REGISTRIES_STORE, registryRoot,
    )
    if (record === null) return null
    const normalized = normalizeStoredRegistry(record)
    await assertReceiptTrustRegistryRootV1(normalized.registry)
    if (normalized.registry_root !== registryRoot) fail('stored registry primary key mismatch')
    return normalized.registry
  }

  private requireDatabase(): IDBDatabase {
    if (this.database === null) fail('receipt source is not open')
    return this.database
  }
}

async function assertBatchNowPersisted(
  database: IDBDatabase,
  registries: readonly StoredRegistryRecord[],
  receipts: readonly StoredReceiptRecord[],
): Promise<void> {
  for (const expected of registries) {
    const actual = await readRecord<StoredRegistryRecord>(
      database, REGISTRIES_STORE, expected.registry_root,
    )
    if (actual === null) fail('registry batch read-back failed')
    await assertIdenticalRegistryRecord(actual, expected)
  }
  for (const expected of receipts) {
    const actual = await readRecord<StoredReceiptRecord>(database, RECEIPTS_STORE, expected.receipt_id)
    if (actual === null) fail('receipt batch read-back failed')
    await assertIdenticalReceiptRecord(actual, expected)
  }
}

async function assertIdenticalReceiptRecord(
  actualValue: unknown,
  expected: StoredReceiptRecord,
): Promise<void> {
  const actual = normalizeStoredReceipt(actualValue)
  await assertCrossRuntimeReceiptIdV1(actual.envelope)
  if (!equalBytes(canonicalizeJCS(actual), canonicalizeJCS(expected))) {
    fail('receipt id collision or stored receipt mismatch')
  }
}

async function assertIdenticalRegistryRecord(
  actualValue: unknown,
  expected: StoredRegistryRecord,
): Promise<void> {
  const actual = normalizeStoredRegistry(actualValue)
  await assertReceiptTrustRegistryRootV1(actual.registry)
  if (!equalBytes(canonicalizeJCS(actual), canonicalizeJCS(expected))) {
    fail('registry root collision or stored registry mismatch')
  }
}

function normalizeStoredReceipt(value: unknown): StoredReceiptRecord {
  const snapshot = snapshotIJson(value, 'stored receipt record')
  if (snapshot === null || typeof snapshot !== 'object' || Array.isArray(snapshot)) {
    fail('stored receipt record must be an object')
  }
  const record = snapshot as Record<string, unknown>
  const expectedKeys = ['chain_slot', 'envelope', 'nonce_key', 'receipt_id']
  if ('mutation_action_key' in record) expectedKeys.push('mutation_action_key')
  assertExactKeys('stored receipt record', record, expectedKeys)
  const envelope = normalizeCrossRuntimeReceiptEnvelopeV1(record.envelope)
  const expected = toStoredReceipt(envelope)
  if (record.receipt_id !== expected.receipt_id || record.nonce_key !== expected.nonce_key ||
      record.chain_slot !== expected.chain_slot ||
      record.mutation_action_key !== expected.mutation_action_key) {
    fail('stored receipt indexes do not match their receipt derivation')
  }
  return expected
}

function normalizeStoredRegistry(value: unknown): StoredRegistryRecord {
  const snapshot = snapshotIJson(value, 'stored registry record')
  if (snapshot === null || typeof snapshot !== 'object' || Array.isArray(snapshot)) {
    fail('stored registry record must be an object')
  }
  const record = snapshot as Record<string, unknown>
  assertExactKeys('stored registry record', record, [
    'registry', 'registry_root', 'registry_version_key',
  ])
  const registry = normalizeReceiptTrustRegistryV1(record.registry)
  const expected = toStoredRegistry(registry)
  if (record.registry_root !== expected.registry_root ||
      record.registry_version_key !== expected.registry_version_key) {
    fail('stored registry indexes do not match their registry derivation')
  }
  return expected
}

function toStoredReceipt(envelope: CrossRuntimeReceiptEnvelopeV1): StoredReceiptRecord {
  const body = envelope.receipt_body
  const base = {
    receipt_id: envelope.receipt_id,
    envelope,
    nonce_key: `${envelope.proof.trust_registry_root}\u0000${envelope.proof.signer_key_id}\u0000${body.nonce}`,
    chain_slot: `${body.parent_receipt_hash}\u0000${body.receipt_sequence}`,
  }
  if (envelope.receipt_kind === 'MUTATION_ADMITTED') {
    return {
      ...base,
      mutation_action_key: mutationActionKeyFor(body),
    }
  }
  return base
}

function toStoredRegistry(registry: ReceiptTrustRegistryV1): StoredRegistryRecord {
  return {
    registry_root: registry.registry_root,
    registry,
    registry_version_key: `${registry.registry_body.operator_key_id}\u0000${registry.registry_body.registry_version}`,
  }
}

function snapshotBatch(
  registries: readonly ReceiptTrustRegistryV1[],
  receipts: readonly CrossRuntimeReceiptEnvelopeV1[],
): { registries: ReceiptTrustRegistryV1[]; receipts: CrossRuntimeReceiptEnvelopeV1[] } {
  const value = { registries, receipts }
  const snapshot = snapshotIJson(value, 'receipt persistence batch') as {
    registries: ReceiptTrustRegistryV1[]
    receipts: CrossRuntimeReceiptEnvelopeV1[]
  }
  return snapshot
}

function assertBatchUnique(
  registries: readonly ReceiptTrustRegistryV1[],
  receipts: readonly CrossRuntimeReceiptEnvelopeV1[],
): void {
  assertUnique('registry roots', registries.map(value => value.registry_root))
  assertUnique(
    'registry versions',
    registries.map(value => `${value.registry_body.operator_key_id}\u0000${value.registry_body.registry_version}`),
  )
  assertUnique('receipt ids', receipts.map(value => value.receipt_id))
  assertUnique(
    'receipt nonces',
    receipts.map(value =>
      `${value.proof.trust_registry_root}\u0000${value.proof.signer_key_id}\u0000${value.receipt_body.nonce}`),
  )
  assertUnique(
    'receipt chain slots',
    receipts.map(value => `${value.receipt_body.parent_receipt_hash}\u0000${value.receipt_body.receipt_sequence}`),
  )
  assertUnique(
    'mutation actions',
    receipts
      .filter(value => value.receipt_kind === 'MUTATION_ADMITTED')
      .map(value => mutationActionKeyFor(value.receipt_body)),
  )
}

function mutationActionKeyFor(body: CrossRuntimeReceiptEnvelopeV1['receipt_body']): string {
  return [
    body.actor_identity_root,
    body.session_identity_root,
    body.workspace_identity_root,
    body.holon_identity_root,
    body.authority_domain,
    body.action_digest,
  ].join('\u0000')
}

function assertUnique(label: string, values: readonly string[]): void {
  if (new Set(values).size !== values.length) fail(`persistence batch contains duplicate ${label}`)
}

function openDatabase(name: string): Promise<IDBDatabase> {
  return new Promise((resolve, reject) => {
    const request = indexedDB.open(name, DATABASE_VERSION)
    request.onupgradeneeded = () => {
      const database = request.result
      if (!database.objectStoreNames.contains(RECEIPTS_STORE)) {
        const receipts = database.createObjectStore(RECEIPTS_STORE, { keyPath: 'receipt_id' })
        receipts.createIndex('by_nonce', 'nonce_key', { unique: true })
        receipts.createIndex('by_chain_slot', 'chain_slot', { unique: true })
        receipts.createIndex('by_mutation_action', 'mutation_action_key', { unique: true })
      }
      if (!database.objectStoreNames.contains(REGISTRIES_STORE)) {
        const registries = database.createObjectStore(REGISTRIES_STORE, { keyPath: 'registry_root' })
        registries.createIndex('by_registry_version', 'registry_version_key', { unique: true })
      }
    }
    request.onsuccess = () => resolve(request.result)
    request.onerror = () => reject(new IndexedDBCrossRuntimeReceiptSourceError(
      `failed to open receipt source: ${request.error?.message ?? 'unknown error'}`,
    ))
  })
}

function addBatch(
  database: IDBDatabase,
  registries: readonly StoredRegistryRecord[],
  receipts: readonly StoredReceiptRecord[],
): Promise<void> {
  return new Promise((resolve, reject) => {
    const transaction = database.transaction([REGISTRIES_STORE, RECEIPTS_STORE], 'readwrite')
    const registryStore = transaction.objectStore(REGISTRIES_STORE)
    const receiptStore = transaction.objectStore(RECEIPTS_STORE)
    let operationError: DOMException | null = null
    for (const registry of registries) {
      const request = registryStore.add(registry)
      request.onerror = () => { operationError ??= request.error }
    }
    for (const receipt of receipts) {
      const request = receiptStore.add(receipt)
      request.onerror = () => { operationError ??= request.error }
    }
    transaction.oncomplete = () => resolve()
    transaction.onerror = () => { operationError ??= transaction.error }
    transaction.onabort = () => reject(
      operationError ?? transaction.error ??
      new IndexedDBCrossRuntimeReceiptSourceError('receipt batch insert aborted'),
    )
  })
}

function readRecord<T>(
  database: IDBDatabase,
  storeName: string,
  key: IDBValidKey,
): Promise<T | null> {
  return new Promise((resolve, reject) => {
    const transaction = database.transaction(storeName, 'readonly')
    const request = transaction.objectStore(storeName).get(key)
    let result: T | null = null
    let settled = false
    const rejectOnce = (message: string, error: DOMException | null) => {
      if (settled) return
      settled = true
      reject(new IndexedDBCrossRuntimeReceiptSourceError(
        `${message}: ${error?.message ?? 'unknown error'}`,
      ))
    }
    request.onsuccess = () => { result = (request.result as T | undefined) ?? null }
    request.onerror = () => rejectOnce('receipt source read failed', request.error)
    transaction.oncomplete = () => {
      if (settled) return
      settled = true
      resolve(result)
    }
    transaction.onerror = () => rejectOnce('receipt source read transaction failed', transaction.error)
    transaction.onabort = () => rejectOnce('receipt source read transaction aborted', transaction.error)
  })
}

function snapshotIJson(value: unknown, label: string): unknown {
  try {
    assertIJsonValue(value, label)
    const snapshot = structuredClone(value) as unknown
    assertIJsonValue(snapshot, label)
    return snapshot
  } catch (error) {
    fail(`${label} is not closed I-JSON: ${error instanceof Error ? error.message : String(error)}`)
  }
}

function assertExactKeys(field: string, value: Record<string, unknown>, expected: readonly string[]): void {
  const actual = Object.keys(value).sort()
  const sortedExpected = [...expected].sort()
  if (actual.length !== sortedExpected.length || actual.some((key, index) => key !== sortedExpected[index])) {
    fail(`${field} has unexpected or missing fields`)
  }
}

function assertResolvedHash(field: string, value: unknown): asserts value is SHA256Hex {
  if (typeof value !== 'string' || !HASH_PATTERN.test(value) || value === '0'.repeat(64)) {
    fail(`${field} must be a non-zero lowercase SHA-256 root`)
  }
}

function equalBytes(left: Uint8Array, right: Uint8Array): boolean {
  if (left.byteLength !== right.byteLength) return false
  for (let index = 0; index < left.byteLength; index += 1) {
    if (left[index] !== right[index]) return false
  }
  return true
}

function isConstraintError(error: unknown): boolean {
  return error !== null && typeof error === 'object' && 'name' in error && error.name === 'ConstraintError'
}

function fail(message: string): never {
  throw new IndexedDBCrossRuntimeReceiptSourceError(message)
}
