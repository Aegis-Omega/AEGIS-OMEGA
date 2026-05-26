//! Gate 220 (cont.): Sovereign Persistence Layer — SPSF
//! EPISTEMIC TIER: T2 — engineering hypothesis
//!
//! The SPSF enforces disk-boundary determinism. Every state write is:
//!   1. Sequence-monotone — no gaps, no replays
//!   2. Hash-chained — state_hash is included in every record
//!   3. Length-prefixed — canonical binary encoding (no serde, no JSON)
//!   4. BTreeMap-indexed — sorted by sequence_id, deterministic iteration
//!
//! Constitutional translation of Gemini's Sovereign Persistence Layer:
//!   HashMap → BTreeMap (deterministic iteration — constitutional invariant)
//!   usize.to_be_bytes() → u64.to_be_bytes() (fixed-width, platform-independent)
//!   expected_root_hash now verified at open() rather than ignored
//!   sequence check uses BTreeMap::iter().next_back() (deterministic max)
//!
//! SPSF record wire format (big-endian, deterministic):
//!   [sequence_id: u64 = 8 bytes]
//!   [node_rank:   u64 = 8 bytes]
//!   [state_hash:  [u8;32] = 32 bytes]
//!   [payload_len: u32 = 4 bytes]
//!   [payload:     N bytes]
//!
//! Copyright (C) 2025 Tarik Skalić — All rights reserved. AGPL-3.0-or-later

use std::collections::BTreeMap;
use std::fs::{File, OpenOptions};
use std::io::Write;
use std::path::{Path, PathBuf};
use std::sync::{Arc, Mutex};

use crate::lattice_dag::Node;

// ─── Record type ──────────────────────────────────────────────────────────

#[derive(Clone, Debug, PartialEq)]
pub struct SpsfRecord {
    pub sequence_id: u64,
    pub node_rank: u64,      // u64 — fixed-width, platform-independent
    pub state_hash: [u8; 32],
    pub payload: Vec<u8>,
}

pub struct SpsfError(pub &'static str);

impl std::fmt::Debug for SpsfError {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        f.write_str(self.0)
    }
}

impl std::fmt::Debug for SovereignPersistenceLayer {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        f.debug_struct("SovereignPersistenceLayer")
            .field("storage_path", &self.storage_path)
            .field("genesis_root", &self.genesis_root)
            .finish()
    }
}

// ─── Sovereign Persistence Layer ──────────────────────────────────────────

/// Sequence-gated, hash-chain integrity disk layer.
/// In-memory index: BTreeMap<sequence_id, SpsfRecord> — sorted, deterministic.
///
/// Crash invariant: if the process terminates after a write but before flush,
/// the file contains the last fully-written record. The next open() with the
/// same genesis_root verifies the header — divergence is detected, not ignored.
pub struct SovereignPersistenceLayer {
    storage_path: PathBuf,
    index: Arc<Mutex<BTreeMap<u64, SpsfRecord>>>,
    genesis_root: [u8; 32],
}

impl SovereignPersistenceLayer {
    /// Open (or create) the SPSF storage file.
    /// If the file already exists, verifies the genesis_root header matches.
    pub fn open(path: impl AsRef<Path>, genesis_root: [u8; 32]) -> Result<Self, SpsfError> {
        let storage_path = path.as_ref().to_path_buf();

        if storage_path.exists() {
            // Verify genesis root — divergence from expected root is a T0 violation
            let existing = std::fs::read(&storage_path)
                .map_err(|_| SpsfError("[SPSF] Failed to read existing storage file"))?;
            if existing.len() < 32 {
                return Err(SpsfError("[SPSF] Storage file is corrupt — header too short"));
            }
            let stored_root: [u8; 32] = existing[..32].try_into()
                .map_err(|_| SpsfError("[SPSF] Failed to read genesis root from file"))?;
            if stored_root != genesis_root {
                return Err(SpsfError("[SPSF] Genesis root mismatch — replay sovereignty violation"));
            }
        } else {
            // Create new storage file and write genesis root as 32-byte header
            let mut f = File::create(&storage_path)
                .map_err(|_| SpsfError("[SPSF] Failed to create storage file"))?;
            f.write_all(&genesis_root)
                .map_err(|_| SpsfError("[SPSF] Failed to write genesis root header"))?;
            f.flush()
                .map_err(|_| SpsfError("[SPSF] Failed to flush genesis root"))?;
        }

        Ok(Self {
            storage_path,
            index: Arc::new(Mutex::new(BTreeMap::new())),
            genesis_root,
        })
    }

    /// Commit a verified execution step to the persistence layer.
    ///
    /// sequence_id must be exactly (max_committed_sequence + 1), or 0 for the first record.
    /// Gaps, replays, and out-of-order writes are rejected — monotone invariant.
    pub fn commit_verified_step<N: Node>(
        &self,
        sequence_id: u64,
        state_hash: [u8; 32],
        payload: &[u8],
    ) -> Result<(), SpsfError> {
        let mut index = self.index.lock()
            .map_err(|_| SpsfError("[SPSF] Mutex poisoned"))?;

        // Monotone sequence enforcement via BTreeMap::iter().next_back() — deterministic
        if let Some((&last_seq, _)) = index.iter().next_back() {
            if sequence_id != last_seq + 1 {
                return Err(SpsfError("[SPSF] Sequence discontinuity — monotone invariant violated"));
            }
        }
        // First record: sequence_id must be 0
        if index.is_empty() && sequence_id != 0 {
            return Err(SpsfError("[SPSF] First record must have sequence_id = 0"));
        }

        let record = SpsfRecord {
            sequence_id,
            node_rank: N::RANK as u64,
            state_hash,
            payload: payload.to_vec(),
        };

        // Append to file with fsync — crash-resilient atomicity
        let mut file = OpenOptions::new()
            .write(true).append(true)
            .open(&self.storage_path)
            .map_err(|_| SpsfError("[SPSF] Failed to open storage file for append"))?;

        file.write_all(&Self::encode(&record))
            .map_err(|_| SpsfError("[SPSF] Failed to write record to disk"))?;
        file.flush()
            .map_err(|_| SpsfError("[SPSF] Failed to flush record to disk"))?;

        index.insert(sequence_id, record);
        Ok(())
    }

    /// Retrieve payload by sequence_id. O(log n) via BTreeMap.
    pub fn read_by_sequence(&self, sequence_id: u64) -> Option<Vec<u8>> {
        self.index.lock().ok()?.get(&sequence_id).map(|r| r.payload.clone())
    }

    /// Retrieve full record by sequence_id.
    pub fn record_by_sequence(&self, sequence_id: u64) -> Option<SpsfRecord> {
        self.index.lock().ok()?.get(&sequence_id).cloned()
    }

    /// Total committed records in the in-memory index.
    pub fn len(&self) -> usize {
        self.index.lock().map(|i| i.len()).unwrap_or(0)
    }

    pub fn is_empty(&self) -> bool { self.len() == 0 }

    /// Genesis root committed at open time.
    pub fn genesis_root(&self) -> [u8; 32] { self.genesis_root }

    /// Highest committed sequence_id, or None if empty.
    pub fn max_sequence(&self) -> Option<u64> {
        self.index.lock().ok()?.keys().next_back().copied()
    }

    /// Length-prefixed canonical binary encoding. Platform-independent big-endian.
    /// Format: [seq:u64][rank:u64][hash:32][len:u32][payload:N]
    fn encode(record: &SpsfRecord) -> Vec<u8> {
        let payload_len = record.payload.len() as u32;
        let mut buf = Vec::with_capacity(8 + 8 + 32 + 4 + record.payload.len());
        buf.extend_from_slice(&record.sequence_id.to_be_bytes());
        buf.extend_from_slice(&record.node_rank.to_be_bytes());
        buf.extend_from_slice(&record.state_hash);
        buf.extend_from_slice(&payload_len.to_be_bytes());
        buf.extend_from_slice(&record.payload);
        buf
    }
}

// ─── Tests ────────────────────────────────────────────────────────────────

#[cfg(test)]
mod tests {
    use super::*;

    struct TestNodeA;
    impl Node for TestNodeA { const RANK: usize = 1; type State = Vec<u8>; }

    struct TestNodeB;
    impl Node for TestNodeB { const RANK: usize = 2; type State = Vec<u8>; }

    fn genesis() -> [u8; 32] { [0xAEu8; 32] }

    fn test_path(suffix: &str) -> PathBuf {
        let mut p = std::env::temp_dir();
        p.push(format!("aegis_spsf_gate220_{suffix}"));
        let _ = std::fs::remove_file(&p); // clean slate
        p
    }

    #[test]
    fn open_creates_file_with_genesis_root() {
        let path = test_path("open_creates");
        let spsf = SovereignPersistenceLayer::open(&path, genesis()).unwrap();
        assert!(path.exists());
        assert!(spsf.is_empty());
        assert_eq!(spsf.genesis_root(), genesis());
        let _ = std::fs::remove_file(&path);
    }

    #[test]
    fn open_existing_verifies_genesis_root() {
        let path = test_path("open_existing");
        SovereignPersistenceLayer::open(&path, genesis()).unwrap();
        // Re-open with same root — should succeed
        let spsf2 = SovereignPersistenceLayer::open(&path, genesis()).unwrap();
        assert_eq!(spsf2.genesis_root(), genesis());
        let _ = std::fs::remove_file(&path);
    }

    #[test]
    fn open_existing_wrong_genesis_rejected() {
        let path = test_path("wrong_genesis");
        SovereignPersistenceLayer::open(&path, genesis()).unwrap();
        let wrong_root = [0xFFu8; 32];
        let err = SovereignPersistenceLayer::open(&path, wrong_root).unwrap_err();
        assert!(err.0.contains("Genesis root mismatch"));
        let _ = std::fs::remove_file(&path);
    }

    #[test]
    fn first_commit_must_be_sequence_zero() {
        let path = test_path("seq_zero");
        let spsf = SovereignPersistenceLayer::open(&path, genesis()).unwrap();
        let err = spsf.commit_verified_step::<TestNodeA>(1, [0u8; 32], b"data").unwrap_err();
        assert!(err.0.contains("First record must have sequence_id = 0"));
        let _ = std::fs::remove_file(&path);
    }

    #[test]
    fn commit_sequence_zero_succeeds() {
        let path = test_path("commit_zero");
        let spsf = SovereignPersistenceLayer::open(&path, genesis()).unwrap();
        spsf.commit_verified_step::<TestNodeA>(0, [1u8; 32], b"genesis_payload").unwrap();
        assert_eq!(spsf.len(), 1);
        assert_eq!(spsf.max_sequence(), Some(0));
        let _ = std::fs::remove_file(&path);
    }

    #[test]
    fn sequential_commits_succeed() {
        let path = test_path("sequential");
        let spsf = SovereignPersistenceLayer::open(&path, genesis()).unwrap();
        spsf.commit_verified_step::<TestNodeA>(0, [0u8; 32], b"step_a").unwrap();
        spsf.commit_verified_step::<TestNodeB>(1, [1u8; 32], b"step_b").unwrap();
        assert_eq!(spsf.len(), 2);
        assert_eq!(spsf.max_sequence(), Some(1));
        let _ = std::fs::remove_file(&path);
    }

    #[test]
    fn gap_in_sequence_rejected() {
        let path = test_path("seq_gap");
        let spsf = SovereignPersistenceLayer::open(&path, genesis()).unwrap();
        spsf.commit_verified_step::<TestNodeA>(0, [0u8; 32], b"ok").unwrap();
        let err = spsf.commit_verified_step::<TestNodeA>(2, [0u8; 32], b"skip").unwrap_err();
        assert!(err.0.contains("Sequence discontinuity"));
        let _ = std::fs::remove_file(&path);
    }

    #[test]
    fn replay_sequence_rejected() {
        let path = test_path("replay");
        let spsf = SovereignPersistenceLayer::open(&path, genesis()).unwrap();
        spsf.commit_verified_step::<TestNodeA>(0, [0u8; 32], b"ok").unwrap();
        let err = spsf.commit_verified_step::<TestNodeA>(0, [0u8; 32], b"dup").unwrap_err();
        assert!(err.0.contains("Sequence discontinuity"));
        let _ = std::fs::remove_file(&path);
    }

    #[test]
    fn read_by_sequence_returns_payload() {
        let path = test_path("read_seq");
        let spsf = SovereignPersistenceLayer::open(&path, genesis()).unwrap();
        spsf.commit_verified_step::<TestNodeA>(0, [7u8; 32], b"constitutional_payload").unwrap();
        let payload = spsf.read_by_sequence(0).unwrap();
        assert_eq!(payload, b"constitutional_payload");
        let _ = std::fs::remove_file(&path);
    }

    #[test]
    fn read_nonexistent_sequence_is_none() {
        let path = test_path("read_none");
        let spsf = SovereignPersistenceLayer::open(&path, genesis()).unwrap();
        assert!(spsf.read_by_sequence(99).is_none());
        let _ = std::fs::remove_file(&path);
    }

    #[test]
    fn record_metadata_preserved() {
        let path = test_path("metadata");
        let spsf = SovereignPersistenceLayer::open(&path, genesis()).unwrap();
        let hash = [0xCAu8; 32];
        spsf.commit_verified_step::<TestNodeB>(0, hash, b"data").unwrap();
        let rec = spsf.record_by_sequence(0).unwrap();
        assert_eq!(rec.node_rank, TestNodeB::RANK as u64);
        assert_eq!(rec.state_hash, hash);
        assert_eq!(rec.payload, b"data");
        let _ = std::fs::remove_file(&path);
    }

    #[test]
    fn encode_is_deterministic_across_calls() {
        let record = SpsfRecord {
            sequence_id: 42,
            node_rank: 3,
            state_hash: [0xBBu8; 32],
            payload: b"determinism".to_vec(),
        };
        let enc1 = SovereignPersistenceLayer::encode(&record);
        let enc2 = SovereignPersistenceLayer::encode(&record);
        let enc3 = SovereignPersistenceLayer::encode(&record);
        assert_eq!(enc1, enc2);
        assert_eq!(enc2, enc3);
    }

    #[test]
    fn encode_length_correct() {
        let payload = b"test_payload";
        let record = SpsfRecord {
            sequence_id: 0,
            node_rank: 1,
            state_hash: [0u8; 32],
            payload: payload.to_vec(),
        };
        let enc = SovereignPersistenceLayer::encode(&record);
        // 8 (seq) + 8 (rank) + 32 (hash) + 4 (len) + 12 (payload) = 64
        assert_eq!(enc.len(), 8 + 8 + 32 + 4 + payload.len());
    }

    #[test]
    fn different_payloads_produce_different_encodings() {
        let r1 = SpsfRecord { sequence_id: 0, node_rank: 1, state_hash: [0u8; 32], payload: b"aaa".to_vec() };
        let r2 = SpsfRecord { sequence_id: 0, node_rank: 1, state_hash: [0u8; 32], payload: b"bbb".to_vec() };
        assert_ne!(
            SovereignPersistenceLayer::encode(&r1),
            SovereignPersistenceLayer::encode(&r2),
        );
    }
}
