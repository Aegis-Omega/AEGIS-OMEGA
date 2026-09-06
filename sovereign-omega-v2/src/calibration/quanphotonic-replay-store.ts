// ============================================================
// SOVEREIGN OMEGA — Persistent QuanPhotonic Replay Authority
// EPISTEMIC TIER: T0/T1 repository implementation
// Single-origin IndexedDB persistence; no distributed claim.
// ============================================================

import { openDB, type DBSchema, type IDBPDatabase } from 'idb'
import type {
  CalibrationRejectionReason,
  QuanPhotonicReplayAdmissionV1,
  QuanPhotonicReplayAuthority,
} from './quanphotonic.js'

const STORE_NAME = 'replay-authority'
const DATABASE_VERSION = 1

interface StoredReceiptHead {
  readonly kind: 'receipt-head'
  readonly digest: string
  readonly sequence: string
  readonly epoch_id: string
}

interface StoredMarker {
  readonly kind: 'marker'
}

interface StoredSequence {
  readonly kind: 'sequence'
  readonly sequence: string
}

type StoredReplayValue = StoredReceiptHead | StoredMarker | StoredSequence

interface QuanPhotonicReplayDatabase extends DBSchema {
  [STORE_NAME]: {
    key: string
    value: StoredReplayValue
  }
}

function batchIdKey(value: string): string {
  return `batch-id:${value}`
}

function batchDigestKey(value: string): string {
  return `batch-digest:${value}`
}

function epochSequenceKey(value: string): string {
  return `epoch-sequence:${value}`
}

function detectorHeadKey(value: string): string {
  return `detector-head:${value}`
}

export class IndexedDbQuanPhotonicReplayAuthority implements QuanPhotonicReplayAuthority {
  private readonly databaseName: string
  private database: IDBPDatabase<QuanPhotonicReplayDatabase> | null = null

  constructor(databaseName = 'sovereign-omega-quanphotonic-replay-v1') {
    if (databaseName.length === 0) throw new Error('QuanPhotonic replay database name is required')
    this.databaseName = databaseName
  }

  async open(): Promise<void> {
    if (this.database !== null) return
    this.database = await openDB<QuanPhotonicReplayDatabase>(this.databaseName, DATABASE_VERSION, {
      upgrade(database) {
        if (!database.objectStoreNames.contains(STORE_NAME)) database.createObjectStore(STORE_NAME)
      },
    })
  }

  close(): void {
    this.database?.close()
    this.database = null
  }

  async admit(admission: QuanPhotonicReplayAdmissionV1): Promise<CalibrationRejectionReason | null> {
    const database = this.requireDatabase()
    const transaction = database.transaction(STORE_NAME, 'readwrite')
    const store = transaction.objectStore(STORE_NAME)
    const batchId = batchIdKey(admission.measurement_batch_id)
    const batchDigest = batchDigestKey(admission.measurement_batch_digest)
    const epochSequence = epochSequenceKey(admission.calibration_epoch_id)
    const detectorHead = detectorHeadKey(admission.detector_id)

    const [storedBatchId, storedBatchDigest, storedEpochSequence, storedDetectorHead] = await Promise.all([
      store.get(batchId),
      store.get(batchDigest),
      store.get(epochSequence),
      store.get(detectorHead),
    ])

    let rejection: CalibrationRejectionReason | null = null
    if (storedBatchId !== undefined) rejection = 'BATCH_REPLAY'
    else if (storedBatchDigest !== undefined) rejection = 'BATCH_DIGEST_REPLAY'
    else if (storedEpochSequence?.kind === 'sequence'
      && BigInt(admission.measurement_sequence) <= BigInt(storedEpochSequence.sequence)) {
      rejection = 'SEQUENCE_ROLLBACK'
    } else if (storedDetectorHead === undefined) {
      if (admission.previous_calibration_receipt_digest !== null) rejection = 'RECEIPT_CHAIN_MISMATCH'
    } else if (storedDetectorHead.kind !== 'receipt-head') {
      rejection = 'PERSISTENCE_UNAVAILABLE'
    } else if (storedDetectorHead.digest !== admission.calibration_receipt_digest) {
      if (admission.previous_calibration_receipt_digest !== storedDetectorHead.digest) {
        rejection = 'RECEIPT_CHAIN_MISMATCH'
      } else if (BigInt(admission.calibration_receipt_sequence) <= BigInt(storedDetectorHead.sequence)) {
        rejection = 'RECEIPT_SEQUENCE_ROLLBACK'
      } else if (admission.calibration_epoch_id === storedDetectorHead.epoch_id) {
        rejection = 'CALIBRATION_EPOCH_REUSE'
      }
    }

    if (rejection === null) {
      await Promise.all([
        store.put({ kind: 'marker' }, batchId),
        store.put({ kind: 'marker' }, batchDigest),
        store.put({ kind: 'sequence', sequence: admission.measurement_sequence }, epochSequence),
        store.put({
          kind: 'receipt-head',
          digest: admission.calibration_receipt_digest,
          sequence: admission.calibration_receipt_sequence,
          epoch_id: admission.calibration_epoch_id,
        }, detectorHead),
      ])
    }
    await transaction.done
    return rejection
  }

  private requireDatabase(): IDBPDatabase<QuanPhotonicReplayDatabase> {
    if (this.database === null) throw new Error('QuanPhotonic replay authority is not open')
    return this.database
  }
}
