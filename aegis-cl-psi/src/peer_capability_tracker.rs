//! Gate 312 — Gossip Peer Capability Tracker: per-peer capability bitmask management (T2)
//! EPISTEMIC TIER: T2 (engineering hypothesis)
//!
//! Tracks which capabilities each peer advertises. Capabilities are represented
//! as a u8 bitmask (up to 8 capability flags). Updates are only accepted if the
//! epoch is strictly greater than the last-seen epoch for that peer (monotone).
//! Capability changes are hash-chained for audit.
//!
//! Capability bit definitions:
//!   CAP_GOSSIP   = 0x01  (basic gossip relay)
//!   CAP_CONSENSUS= 0x02  (participates in consensus)
//!   CAP_RELAY    = 0x04  (full relay node)
//!   CAP_AUDIT    = 0x08  (provides audit log access)
//!   CAP_STORAGE  = 0x10  (persistent storage peer)
//!   CAP_EDGE     = 0x20  (edge/lightweight node)
//!
//! CapabilityRecord:
//!   peer_id, epoch, old_caps: u8, new_caps: u8
//!   record_hash = SHA-256(prev ‖ peer_be4 ‖ epoch_be8 ‖ old_caps ‖ new_caps)
//!   prev_hash
//!
//! CapabilityLog: hash-chained CapabilityRecords (global).
//!   push(), update_count(), verify_chain().
//!
//! PeerCapabilityTracker:
//!   update(peer_id, epoch, caps) → Result<bool, CapError>
//!     Returns Ok(true) if caps changed, Ok(false) if same, Err(Stale) if epoch not advancing.
//!   capabilities(peer_id) → Option<u8>
//!   has_capability(peer_id, cap_bit) → bool
//!   peers_with_capability(cap_bit) → Vec<u32>  (sorted)
//!   remove(peer_id, epoch) → bool
//!   tracked_count() → usize

use sha2::{Sha256, Digest};
use std::collections::BTreeMap;

pub const CAP_GOSSIP:    u8 = 0x01;
pub const CAP_CONSENSUS: u8 = 0x02;
pub const CAP_RELAY:     u8 = 0x04;
pub const CAP_AUDIT:     u8 = 0x08;
pub const CAP_STORAGE:   u8 = 0x10;
pub const CAP_EDGE:      u8 = 0x20;

// ─── Capability record ────────────────────────────────────────────────────────

#[derive(Debug, Clone, PartialEq)]
pub struct CapabilityRecord {
    pub peer_id:     u32,
    pub epoch:       u64,
    pub old_caps:    u8,
    pub new_caps:    u8,
    pub record_hash: [u8; 32],
    pub prev_hash:   [u8; 32],
}

pub const CAP_GENESIS_HASH: [u8; 32] = [0u8; 32];

fn compute_cap_hash(
    peer_id:  u32,
    epoch:    u64,
    old_caps: u8,
    new_caps: u8,
    prev:     &[u8; 32],
) -> [u8; 32] {
    let mut h = Sha256::new();
    h.update(prev);
    h.update(peer_id.to_be_bytes());
    h.update(epoch.to_be_bytes());
    h.update([old_caps, new_caps]);
    h.finalize().into()
}

pub fn build_capability_record(
    peer_id:  u32,
    epoch:    u64,
    old_caps: u8,
    new_caps: u8,
    prev_hash: &[u8; 32],
) -> CapabilityRecord {
    let record_hash = compute_cap_hash(peer_id, epoch, old_caps, new_caps, prev_hash);
    CapabilityRecord { peer_id, epoch, old_caps, new_caps, record_hash, prev_hash: *prev_hash }
}

// ─── Capability log ───────────────────────────────────────────────────────────

#[derive(Debug, Clone)]
pub struct CapabilityLog {
    records: Vec<CapabilityRecord>,
}

impl CapabilityLog {
    pub fn new() -> Self { Self { records: Vec::new() } }

    pub fn len(&self)      -> usize { self.records.len() }
    pub fn is_empty(&self) -> bool  { self.records.is_empty() }
    pub fn records(&self)  -> &[CapabilityRecord] { &self.records }

    pub fn last_hash(&self) -> [u8; 32] {
        self.records.last().map(|r| r.record_hash).unwrap_or(CAP_GENESIS_HASH)
    }

    pub fn push(&mut self, peer_id: u32, epoch: u64, old_caps: u8, new_caps: u8) -> &CapabilityRecord {
        let prev = self.last_hash();
        let r = build_capability_record(peer_id, epoch, old_caps, new_caps, &prev);
        self.records.push(r);
        self.records.last().unwrap()
    }

    pub fn update_count(&self) -> usize {
        self.records.iter().filter(|r| r.old_caps != r.new_caps).count()
    }

    pub fn verify_chain(&self) -> (bool, Option<usize>) {
        let mut expected_prev = CAP_GENESIS_HASH;
        for (i, r) in self.records.iter().enumerate() {
            if r.prev_hash != expected_prev { return (false, Some(i)); }
            let recomputed = compute_cap_hash(r.peer_id, r.epoch, r.old_caps, r.new_caps, &r.prev_hash);
            if recomputed != r.record_hash { return (false, Some(i)); }
            expected_prev = r.record_hash;
        }
        (true, None)
    }
}

impl Default for CapabilityLog {
    fn default() -> Self { Self::new() }
}

// ─── Peer state (internal) ────────────────────────────────────────────────────

#[derive(Debug, Clone)]
struct PeerCapState {
    capabilities: u8,
    last_epoch:   u64,
}

// ─── Errors ───────────────────────────────────────────────────────────────────

#[derive(Debug)]
pub enum CapError {
    StaleEpoch,  // Reported epoch not greater than current
}

// ─── PeerCapabilityTracker ────────────────────────────────────────────────────

#[derive(Debug, Clone)]
pub struct PeerCapabilityTracker {
    peers: BTreeMap<u32, PeerCapState>,
    pub log: CapabilityLog,
}

impl PeerCapabilityTracker {
    pub fn new() -> Self { Self { peers: BTreeMap::new(), log: CapabilityLog::new() } }

    /// Update capabilities for a peer. Epoch must be strictly greater than previous.
    /// Returns Ok(true) if capabilities changed, Ok(false) if same caps (still advances epoch).
    pub fn update(&mut self, peer_id: u32, epoch: u64, caps: u8) -> Result<bool, CapError> {
        if let Some(state) = self.peers.get(&peer_id) {
            if epoch <= state.last_epoch { return Err(CapError::StaleEpoch); }
        }

        let old_caps = self.peers.get(&peer_id).map(|s| s.capabilities).unwrap_or(0);
        let changed = old_caps != caps;

        self.peers.insert(peer_id, PeerCapState { capabilities: caps, last_epoch: epoch });
        self.log.push(peer_id, epoch, old_caps, caps);
        Ok(changed)
    }

    pub fn capabilities(&self, peer_id: u32) -> Option<u8> {
        self.peers.get(&peer_id).map(|s| s.capabilities)
    }

    pub fn has_capability(&self, peer_id: u32, cap_bit: u8) -> bool {
        self.peers.get(&peer_id).map(|s| s.capabilities & cap_bit != 0).unwrap_or(false)
    }

    /// All peers advertising the given capability bit, sorted by peer_id.
    pub fn peers_with_capability(&self, cap_bit: u8) -> Vec<u32> {
        self.peers.iter()
            .filter(|(_, s)| s.capabilities & cap_bit != 0)
            .map(|(&pid, _)| pid)
            .collect()
    }

    /// Remove a peer from tracking. Records a zeroed capability update.
    pub fn remove(&mut self, peer_id: u32, epoch: u64) -> bool {
        if let Some(state) = self.peers.remove(&peer_id) {
            self.log.push(peer_id, epoch, state.capabilities, 0);
            true
        } else {
            false
        }
    }

    pub fn tracked_count(&self) -> usize { self.peers.len() }
}

impl Default for PeerCapabilityTracker {
    fn default() -> Self { Self::new() }
}

// ─── Tests ────────────────────────────────────────────────────────────────────

#[cfg(test)]
mod tests {
    use super::*;

    // ── Constants ─────────────────────────────────────────────────────────────

    #[test]
    fn cap_constants() {
        assert_eq!(CAP_GOSSIP,    0x01);
        assert_eq!(CAP_CONSENSUS, 0x02);
        assert_eq!(CAP_RELAY,     0x04);
        assert_eq!(CAP_AUDIT,     0x08);
        assert_eq!(CAP_STORAGE,   0x10);
        assert_eq!(CAP_EDGE,      0x20);
        // All 6 are distinct bits
        assert_eq!(CAP_GOSSIP | CAP_CONSENSUS | CAP_RELAY | CAP_AUDIT | CAP_STORAGE | CAP_EDGE, 0x3F);
    }

    // ── build_capability_record ───────────────────────────────────────────────

    #[test]
    fn record_hash_nonzero() {
        let r = build_capability_record(1, 1, 0, CAP_GOSSIP, &CAP_GENESIS_HASH);
        assert_ne!(r.record_hash, [0u8; 32]);
    }

    #[test]
    fn record_hash_deterministic() {
        let r1 = build_capability_record(1, 1, 0, CAP_GOSSIP | CAP_RELAY, &CAP_GENESIS_HASH);
        let r2 = build_capability_record(1, 1, 0, CAP_GOSSIP | CAP_RELAY, &CAP_GENESIS_HASH);
        assert_eq!(r1.record_hash, r2.record_hash);
    }

    // ── CapabilityLog ─────────────────────────────────────────────────────────

    #[test]
    fn log_update_count() {
        let mut l = CapabilityLog::new();
        l.push(1, 1, 0, CAP_GOSSIP);           // changed
        l.push(1, 2, CAP_GOSSIP, CAP_GOSSIP);  // same
        l.push(2, 1, 0, CAP_RELAY);            // changed
        assert_eq!(l.update_count(), 2);
    }

    #[test]
    fn log_chain_links() {
        let mut l = CapabilityLog::new();
        l.push(1, 1, 0, CAP_GOSSIP);
        l.push(1, 2, CAP_GOSSIP, CAP_GOSSIP | CAP_RELAY);
        assert_eq!(l.records()[1].prev_hash, l.records()[0].record_hash);
    }

    #[test]
    fn log_verify_chain_valid() {
        let mut l = CapabilityLog::new();
        for i in 0..5u32 {
            l.push(i, i as u64, 0, i as u8);
        }
        let (valid, broken) = l.verify_chain();
        assert!(valid);
        assert!(broken.is_none());
    }

    // ── PeerCapabilityTracker ─────────────────────────────────────────────────

    #[test]
    fn update_new_peer() {
        let mut t = PeerCapabilityTracker::new();
        assert_eq!(t.update(1, 1, CAP_GOSSIP | CAP_RELAY).unwrap(), true);
        assert_eq!(t.capabilities(1), Some(CAP_GOSSIP | CAP_RELAY));
    }

    #[test]
    fn update_same_caps_returns_false() {
        let mut t = PeerCapabilityTracker::new();
        t.update(1, 1, CAP_GOSSIP).unwrap();
        assert_eq!(t.update(1, 2, CAP_GOSSIP).unwrap(), false); // same caps
    }

    #[test]
    fn stale_epoch_errors() {
        let mut t = PeerCapabilityTracker::new();
        t.update(1, 5, CAP_GOSSIP).unwrap();
        assert!(matches!(t.update(1, 5, CAP_RELAY), Err(CapError::StaleEpoch)));
        assert!(matches!(t.update(1, 3, CAP_RELAY), Err(CapError::StaleEpoch)));
    }

    #[test]
    fn has_capability_check() {
        let mut t = PeerCapabilityTracker::new();
        t.update(1, 1, CAP_GOSSIP | CAP_AUDIT).unwrap();
        assert!(t.has_capability(1, CAP_GOSSIP));
        assert!(t.has_capability(1, CAP_AUDIT));
        assert!(!t.has_capability(1, CAP_RELAY));
        assert!(!t.has_capability(99, CAP_GOSSIP)); // unknown peer
    }

    #[test]
    fn peers_with_capability_sorted() {
        let mut t = PeerCapabilityTracker::new();
        t.update(3, 1, CAP_GOSSIP | CAP_RELAY).unwrap();
        t.update(1, 1, CAP_GOSSIP).unwrap();
        t.update(2, 1, CAP_RELAY).unwrap();
        assert_eq!(t.peers_with_capability(CAP_GOSSIP), vec![1, 3]);
        assert_eq!(t.peers_with_capability(CAP_RELAY), vec![2, 3]);
    }

    #[test]
    fn remove_peer() {
        let mut t = PeerCapabilityTracker::new();
        t.update(1, 1, CAP_GOSSIP).unwrap();
        assert!(t.remove(1, 2));
        assert_eq!(t.capabilities(1), None);
        assert_eq!(t.tracked_count(), 0);
    }
}
