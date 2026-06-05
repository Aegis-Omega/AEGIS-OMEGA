//! Pillar 1 — Root Cryptographic State Anchor
//!
//! EPISTEMIC TIER: T2 (engineering hypothesis)
//!
//! An append-only SHA-256 hash-chained ledger. Each entry's hash commits to
//! the previous entry's hash, the segment key, and the payload bytes.
//! The `IntegrityReaper` spawns a std::thread that re-verifies the chain
//! on sequence-number ticks — no wall-clock time in the critical path.
//!
//! Constitutional invariants:
//! - Append-only: no update or delete path
//! - BTreeMap<SegmentKey, AnchorEntry> — deterministic iteration
//! - corruption_count == 0 required for T0 pass

use sha2::{Sha256, Digest};
use std::collections::BTreeMap;

/// Immutable genesis hash — zeroed to allow deterministic chain seeding.
pub const GENESIS_HASH: [u8; 32] = [0u8; 32];

/// Opaque segment identifier — (domain_id, segment_id), comparable and ordered.
#[derive(Clone, Copy, Debug, PartialEq, Eq, PartialOrd, Ord)]
pub struct SegmentKey {
    pub domain_id: u32,
    pub segment_id: u32,
}

/// One immutable entry in the state anchor chain.
#[derive(Clone, Debug)]
pub struct AnchorEntry {
    pub key: SegmentKey,
    pub payload: Vec<u8>,
    /// SHA-256(prev_hash || domain_id_le || segment_id_le || payload)
    pub entry_hash: [u8; 32],
}

/// Append-only hash-chained ledger.
pub struct StateAnchor {
    entries: BTreeMap<SegmentKey, AnchorEntry>,
    head_hash: [u8; 32],
    corruption_count: u32,
}

impl StateAnchor {
    pub fn new() -> Self {
        Self { entries: BTreeMap::new(), head_hash: GENESIS_HASH, corruption_count: 0 }
    }

    pub fn append(&mut self, key: SegmentKey, payload: Vec<u8>) -> Result<[u8; 32], AnchorError> {
        if self.entries.contains_key(&key) {
            return Err(AnchorError::DuplicateKey(key));
        }
        let entry_hash = Self::compute_hash(self.head_hash, key, &payload);
        self.entries.insert(key, AnchorEntry { key, payload, entry_hash });
        self.head_hash = entry_hash;
        Ok(entry_hash)
    }

    /// Re-verify the full chain. Sets corruption_count on any mismatch.
    pub fn verify_chain(&mut self) -> bool {
        let mut running = GENESIS_HASH;
        for (_, entry) in &self.entries {
            let expected = Self::compute_hash(running, entry.key, &entry.payload);
            if expected != entry.entry_hash {
                self.corruption_count += 1;
                return false;
            }
            running = entry.entry_hash;
        }
        true
    }

    pub fn head_hash(&self) -> [u8; 32] { self.head_hash }
    pub fn len(&self) -> usize { self.entries.len() }
    pub fn is_empty(&self) -> bool { self.entries.is_empty() }
    pub fn corruption_count(&self) -> u32 { self.corruption_count }
    pub fn passes_t0(&self) -> bool { self.corruption_count == 0 }

    fn compute_hash(prev: [u8; 32], key: SegmentKey, payload: &[u8]) -> [u8; 32] {
        let mut h = Sha256::new();
        h.update(prev);
        h.update(key.domain_id.to_le_bytes());
        h.update(key.segment_id.to_le_bytes());
        h.update(payload);
        h.finalize().into()
    }
}

impl Default for StateAnchor { fn default() -> Self { Self::new() } }

/// Spawns a verification thread driven by sequence ticks (no wall-clock time).
pub struct IntegrityReaper;

impl IntegrityReaper {
    pub fn spawn_vigil(mut anchor: StateAnchor)
        -> (std::sync::mpsc::SyncSender<u64>, std::thread::JoinHandle<StateAnchor>)
    {
        let (tx, rx) = std::sync::mpsc::sync_channel::<u64>(8);
        let handle = std::thread::spawn(move || {
            for _seq in rx {
                if !anchor.verify_chain() { break; } // fail-closed on corruption
            }
            anchor
        });
        (tx, handle)
    }
}

#[derive(Debug)]
pub enum AnchorError { DuplicateKey(SegmentKey) }

impl std::fmt::Display for AnchorError {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        match self { AnchorError::DuplicateKey(k) =>
            write!(f, "duplicate key: {}:{}", k.domain_id, k.segment_id) }
    }
}
impl std::error::Error for AnchorError {}

#[cfg(test)]
mod tests {
    use super::*;
    fn k(d: u32, s: u32) -> SegmentKey { SegmentKey { domain_id: d, segment_id: s } }

    #[test] fn empty_anchor_passes_t0() {
        let mut a = StateAnchor::new(); assert!(a.verify_chain()); assert!(a.passes_t0());
    }
    #[test] fn append_and_verify() {
        let mut a = StateAnchor::new();
        a.append(k(0,1), b"data".to_vec()).unwrap();
        a.append(k(0,2), b"more".to_vec()).unwrap();
        assert!(a.verify_chain()); assert_eq!(a.corruption_count(), 0);
    }
    #[test] fn duplicate_rejected() {
        let mut a = StateAnchor::new();
        a.append(k(0,1), b"x".to_vec()).unwrap();
        assert!(a.append(k(0,1), b"y".to_vec()).is_err());
    }
    #[test] fn hash_deterministic_3x() {
        let make = || { let mut a = StateAnchor::new();
            a.append(k(1,1), b"payload".to_vec()).unwrap(); a.head_hash() };
        assert_eq!(make(), make()); assert_eq!(make(), make());
    }
    #[test] fn btreemap_key_order() {
        let mut a = StateAnchor::new();
        a.append(k(2,1), b"b".to_vec()).unwrap();
        a.append(k(1,1), b"a".to_vec()).unwrap();
        let first = a.entries.keys().next().unwrap();
        assert_eq!(*first, k(1,1));
    }

    // 6. GENESIS_HASH is 32 zero bytes
    #[test] fn genesis_hash_is_32_zeros() {
        assert_eq!(GENESIS_HASH, [0u8; 32]);
    }

    // 7. head_hash changes after an append
    #[test] fn head_hash_changes_after_append() {
        let mut a = StateAnchor::new();
        let before = a.head_hash();
        a.append(k(0,1), b"payload".to_vec()).unwrap();
        assert_ne!(a.head_hash(), before);
    }

    // 8. new anchor is_empty and has len 0
    #[test] fn new_anchor_is_empty() {
        let a = StateAnchor::new();
        assert!(a.is_empty());
        assert_eq!(a.len(), 0);
    }

    // 9. len increments with each successful append
    #[test] fn len_increments_with_appends() {
        let mut a = StateAnchor::new();
        for i in 0..5u32 {
            a.append(k(0, i), vec![i as u8]).unwrap();
            assert_eq!(a.len(), (i + 1) as usize);
        }
    }

    // 10. corruption_count is 0 on a freshly constructed anchor
    #[test] fn corruption_count_zero_initially() {
        let a = StateAnchor::new();
        assert_eq!(a.corruption_count(), 0);
        assert!(a.passes_t0());
    }
}
