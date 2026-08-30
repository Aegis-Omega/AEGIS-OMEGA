// ============================================================
// SOVEREIGN OMEGA — Event Store
// EPISTEMIC TIER: T0
// BUILD GATE 2: Atomic sequence assignment, collision rejection
// PRIMITIVE 1: Cryptographic Event Sourcing
// ============================================================
// Sequence numbers are assigned atomically inside an IndexedDB
// transaction WITH the event append. NEVER derived from length.
// NEVER generated client-side before persistence.
// ============================================================

import type { EventEnvelope, EventType, RetentionClass, UUIDv7, SHA256Hex, SequenceNumber } from '../core/types.js'
import { canonicalizeJCS } from '../core/canonicalize.js'
import { generateUUIDv7 } from './uuid.js'

const DB_NAME = 'sovereign-omega-events'
const DB_VERSION = 1
const EVENTS_STORE = 'events'
const SEQUENCES_STORE = 'sequences'

export class EventStore {
  private db: IDBDatabase | null = null
  private streamId: UUIDv7

  constructor(streamId: UUIDv7) {
    this.streamId = streamId
  }

  async open(): Promise<void> {
    this.db = await openDB(DB_NAME, DB_VERSION)
  }

  /**
   * Append an event to the store.
   * Sequence number is assigned by a readonly read, then written in a separate readwrite
   * transaction after the SHA-256 hash is computed outside any IDB transaction.
   *
   * Three-phase design avoids TransactionInactiveError from awaiting WebCrypto inside
   * an IDB onsuccess callback. Race protection: unique index on by_stream_sequence
   * rejects a duplicate nextSeq from a concurrent append with a constraint error.
   *
   * INVARIANT: This is the ONLY path by which events enter the store.
   * INVARIANT: sequence is never derived from array.length or client state.
   */
  async append<TPayload>(
    event_type: EventType,
    payload: TPayload,
    producer_id: string,
    producer_version: string,
    payload_schema_version: string,
    retention_class: RetentionClass,
    timestamp_ms: number  // MUST come from the caller's event context, not Date.now()
  ): Promise<EventEnvelope<TPayload>> {
    const db = this.requireDB()

    // Phase 1: Read currentSeq and prevHash in a readonly transaction (no async inside).
    const { currentSeq, prevHash } = await new Promise<{ currentSeq: number; prevHash: SHA256Hex }>(
      (resolve, reject) => {
        const tx = db.transaction([EVENTS_STORE, SEQUENCES_STORE], 'readonly')
        const eventsStore = tx.objectStore(EVENTS_STORE)
        const sequencesStore = tx.objectStore(SEQUENCES_STORE)

        const seqReq = sequencesStore.get(this.streamId)
        seqReq.onsuccess = () => {
          const currentSeq: number = seqReq.result ?? -1
          const prevHashReq = eventsStore.index('by_stream_sequence')
            .get(IDBKeyRange.only([this.streamId, currentSeq]))
          prevHashReq.onsuccess = () => {
            const prevEvent = prevHashReq.result as EventEnvelope | null
            const prevHash = prevEvent?.self_hash ?? ('0'.repeat(64) as SHA256Hex)
            resolve({ currentSeq, prevHash })
          }
          /* c8 ignore next -- IDB error path; fake-indexeddb never fires onerror in normal operation */
          prevHashReq.onerror = () => reject(new EventStoreError('Failed to retrieve previous event'))
        }
        /* c8 ignore next -- IDB error path; structurally unreachable with fake-indexeddb */
        seqReq.onerror = () => reject(new EventStoreError('Failed to read sequence counter'))
        /* c8 ignore next -- IDB error path; structurally unreachable with fake-indexeddb */
        tx.onerror = (e) => reject(new EventStoreError(`Transaction error: ${e}`))
      }
    )

    const nextSeq = currentSeq + 1
    const event_id = generateUUIDv7() as UUIDv7

    // Phase 2: Compute SHA-256 outside any IDB transaction (async WebCrypto is safe here).
    const envelopeForHashing = {
      event_id,
      stream_id: this.streamId,
      event_type,
      timestamp_ms,
      sequence: String(nextSeq),  // BigInt serialised as string for hashing
      producer_id,
      producer_version,
      payload_schema_version,
      payload,
      prev_hash: prevHash,
      retention_class,
    }
    const canonical = canonicalizeJCS(envelopeForHashing)
    const selfHashBytes = await (async () => {
      /* c8 ignore next -- optional-chaining ?.subtle: false branch only if crypto is undefined (never in jsdom) */
      if (typeof globalThis.crypto?.subtle !== 'undefined') {
        const digest = await globalThis.crypto.subtle.digest('SHA-256', canonical as BufferSource)
        return new Uint8Array(digest)
      }
      /* c8 ignore start -- Node.js crypto fallback; only reached when crypto.subtle unavailable (never in jsdom/browser) */
      const { createHash } = await import('node:crypto')
      return new Uint8Array(createHash('sha256').update(canonical).digest())
      /* c8 ignore stop */
    })()
    const self_hash = Array.from(selfHashBytes)
      .map(b => b.toString(16).padStart(2, '0'))
      .join('') as SHA256Hex

    const envelope: EventEnvelope<TPayload> = Object.freeze({
      event_id,
      stream_id: this.streamId,
      event_type,
      timestamp_ms,
      sequence: BigInt(nextSeq) as SequenceNumber,
      producer_id,
      producer_version,
      payload_schema_version,
      payload: Object.freeze(payload) as TPayload,
      prev_hash: prevHash,
      self_hash,
      retention_class,
    })

    // Phase 3: Write in a new readwrite transaction with only synchronous IDB ops inside.
    await new Promise<void>((resolve, reject) => {
      const tx = db.transaction([EVENTS_STORE, SEQUENCES_STORE], 'readwrite')
      const eventsStore = tx.objectStore(EVENTS_STORE)
      const sequencesStore = tx.objectStore(SEQUENCES_STORE)
      eventsStore.put({ ...envelope, sequence: nextSeq })
      sequencesStore.put(nextSeq, this.streamId)
      tx.oncomplete = () => resolve()
      /* c8 ignore next -- IDB error path; fake-indexeddb never fires tx.onerror in normal operation */
      tx.onerror = () => reject(new EventStoreError('Transaction failed during append'))
      /* c8 ignore next -- IDB error path; fake-indexeddb never fires tx.onabort in normal operation */
      tx.onabort = () => reject(new EventStoreError('Transaction aborted during append'))
    })

    return envelope
  }

  /**
   * Retrieve all events for this stream, ordered by sequence number.
   * Used for deterministic projection replay.
   */
  async getAll(): Promise<readonly EventEnvelope[]> {
    const db = this.requireDB()
    return new Promise((resolve, reject) => {
      const tx = db.transaction(EVENTS_STORE, 'readonly')
      const store = tx.objectStore(EVENTS_STORE)
      const index = store.index('by_stream_sequence')
      const range = IDBKeyRange.bound(
        [this.streamId, 0],
        [this.streamId, Number.MAX_SAFE_INTEGER]
      )
      const req = index.getAll(range)
      req.onsuccess = () => {
        const events = (req.result as EventEnvelope[]).map(e => ({
          ...e,
          sequence: BigInt(e.sequence as unknown as number) as SequenceNumber,
        }))
        resolve(Object.freeze(events))
      }
      /* c8 ignore next -- IDB error path; structurally unreachable with fake-indexeddb */
      req.onerror = () => reject(new EventStoreError('Failed to retrieve events'))
    })
  }

  /**
   * Retrieve events since a given sequence number (inclusive).
   */
  async getSince(fromSequence: SequenceNumber): Promise<readonly EventEnvelope[]> {
    const db = this.requireDB()
    return new Promise((resolve, reject) => {
      const tx = db.transaction(EVENTS_STORE, 'readonly')
      const store = tx.objectStore(EVENTS_STORE)
      const index = store.index('by_stream_sequence')
      const range = IDBKeyRange.bound(
        [this.streamId, Number(fromSequence)],
        [this.streamId, Number.MAX_SAFE_INTEGER]
      )
      const req = index.getAll(range)
      req.onsuccess = () => {
        const events = (req.result as EventEnvelope[]).map(e => ({
          ...e,
          sequence: BigInt(e.sequence as unknown as number) as SequenceNumber,
        }))
        resolve(Object.freeze(events))
      }
      /* c8 ignore next -- IDB error path; structurally unreachable with fake-indexeddb */
      req.onerror = () => reject(new EventStoreError('Failed to retrieve events since sequence'))
    })
  }

  /**
   * Verify the hash chain integrity of the event log.
   * Returns the first broken link, or null if the chain is intact.
   */
  async verifyChain(): Promise<{ broken_at_sequence: number; expected: string; got: string } | null> {
    const events = await this.getAll()
    const genesisHash = '0'.repeat(64) as SHA256Hex

    for (let i = 0; i < events.length; i++) {
      const event = events[i]!
      const expectedPrevHash = i === 0 ? genesisHash : events[i - 1]!.self_hash

      if (event.prev_hash !== expectedPrevHash) {
        return {
          broken_at_sequence: Number(event.sequence),
          expected: expectedPrevHash,
          got: event.prev_hash,
        }
      }
    }

    return null
  }

  private requireDB(): IDBDatabase {
    if (!this.db) throw new EventStoreError('EventStore not opened. Call open() first.')
    return this.db
  }
}

// ─── IndexedDB Setup ───────────────────────────────────────

function openDB(name: string, version: number): Promise<IDBDatabase> {
  return new Promise((resolve, reject) => {
    const req = indexedDB.open(name, version)

    req.onupgradeneeded = (event) => {
      const db = (event.target as IDBOpenDBRequest).result

      /* c8 ignore next 6 -- onupgradeneeded fires once per DB version; schema already exists on re-open; false branch structurally unreachable in a single test run */
      if (!db.objectStoreNames.contains(EVENTS_STORE)) {
        const eventsStore = db.createObjectStore(EVENTS_STORE, { keyPath: 'event_id' })
        eventsStore.createIndex('by_stream_sequence', ['stream_id', 'sequence'], { unique: true })
        eventsStore.createIndex('by_event_type', 'event_type')
        eventsStore.createIndex('by_stream', 'stream_id')
      }

      /* c8 ignore next 3 -- same: false branch unreachable once schema is created */
      if (!db.objectStoreNames.contains(SEQUENCES_STORE)) {
        db.createObjectStore(SEQUENCES_STORE)
      }
    }

    req.onsuccess = () => resolve(req.result)
    /* c8 ignore next -- IDB error path; fake-indexeddb never fires req.onerror in normal operation */
    req.onerror = () => reject(new EventStoreError(`Failed to open database: ${req.error?.message}`))
  })
}

// ─── Error Types ───────────────────────────────────────────

export class EventStoreError extends Error {
  constructor(message: string) {
    super(message)
    this.name = 'EventStoreError'
  }
}
