//! Gate 258 — Swarm Topology Snapshot: hash-linked mesh state capture (T2)
//! EPISTEMIC TIER: T2 (engineering hypothesis)
//!
//! Captures the full peer mesh state at a given epoch into a TopologySnapshot.
//! Snapshots are hash-chained in a TopologyLog for tamper-evident history.
//!
//! TopologySnapshot:
//!   epoch            — u64
//!   peer_count       — usize
//!   operational_count— usize (peers in non-Critical phase)
//!   cap_gossip_count — usize (peers with GOSSIP capability)
//!   cap_consensus_count — usize (peers with CONSENSUS capability)
//!   max_epoch        — u64 (highest peer epoch in registry)
//!   snapshot_hash    — SHA-256(epoch_be8 ‖ peer_count_be8 ‖ operational_be8 ‖ max_epoch_be8 ‖ prev_hash)
//!
//! TopologyLog:
//!   snapshots        — Vec<TopologySnapshot>
//!   append(epoch, registry) — builds snapshot from PeerRegistry; chains hash
//!   verify_chain()   — validates full hash chain integrity
//!
//! Quorum check: quorum_reached(snapshot) → operational_count * 1_000_000 >= peer_count * 618_034

use sha2::{Sha256, Digest};
use crate::peer_manifest::PeerRegistry;
use crate::peer_manifest::cap;

// ─── Topology snapshot ────────────────────────────────────────────────────────

#[derive(Debug, Clone, PartialEq)]
pub struct TopologySnapshot {
    pub epoch:              u64,
    pub peer_count:         usize,
    pub operational_count:  usize,
    pub cap_gossip_count:   usize,
    pub cap_consensus_count: usize,
    pub max_peer_epoch:     u64,
    pub snapshot_hash:      [u8; 32],
    pub prev_hash:          [u8; 32],
}

impl TopologySnapshot {
    /// True if operational_count / peer_count >= 1/φ (integer arithmetic).
    pub fn quorum_reached(&self) -> bool {
        if self.peer_count == 0 { return false; }
        self.operational_count * 1_000_000 >= self.peer_count * 618_034
    }

    /// True if all peers with CONSENSUS capability are operational.
    pub fn consensus_capable(&self) -> bool {
        self.cap_consensus_count > 0
    }
}

pub const TOPOLOGY_GENESIS_HASH: [u8; 32] = [0u8; 32];

fn compute_snapshot_hash(
    epoch:             u64,
    peer_count:        usize,
    operational_count: usize,
    max_peer_epoch:    u64,
    prev_hash:         &[u8; 32],
) -> [u8; 32] {
    let mut h = Sha256::new();
    h.update(prev_hash);
    h.update(epoch.to_be_bytes());
    h.update((peer_count as u64).to_be_bytes());
    h.update((operational_count as u64).to_be_bytes());
    h.update(max_peer_epoch.to_be_bytes());
    h.finalize().into()
}

// ─── Build snapshot ───────────────────────────────────────────────────────────

pub fn build_snapshot(
    epoch:     u64,
    registry:  &PeerRegistry,
    prev_hash: &[u8; 32],
) -> TopologySnapshot {
    let peer_count         = registry.len();
    let operational_count  = registry.operational_peers().len();
    let cap_gossip_count   = registry.peers_with_cap(cap::GOSSIP).len();
    let cap_consensus_count = registry.peers_with_cap(cap::CONSENSUS).len();
    let max_peer_epoch     = registry.max_epoch();

    let snapshot_hash = compute_snapshot_hash(
        epoch, peer_count, operational_count, max_peer_epoch, prev_hash);

    TopologySnapshot {
        epoch,
        peer_count,
        operational_count,
        cap_gossip_count,
        cap_consensus_count,
        max_peer_epoch,
        snapshot_hash,
        prev_hash: *prev_hash,
    }
}

// ─── Topology log ─────────────────────────────────────────────────────────────

#[derive(Debug, Clone)]
pub struct TopologyLog {
    snapshots: Vec<TopologySnapshot>,
}

#[derive(Debug)]
pub enum TopologyError {
    StaleEpoch,
}

impl TopologyError {
    pub fn as_str(&self) -> &'static str {
        match self {
            Self::StaleEpoch => "stale epoch",
        }
    }
}

impl TopologyLog {
    pub fn new() -> Self { Self { snapshots: Vec::new() } }

    pub fn len(&self) -> usize { self.snapshots.len() }
    pub fn is_empty(&self) -> bool { self.snapshots.is_empty() }
    pub fn snapshots(&self) -> &[TopologySnapshot] { &self.snapshots }

    pub fn latest(&self) -> Option<&TopologySnapshot> { self.snapshots.last() }

    /// Append a new snapshot from the current registry state.
    /// Epoch must be strictly greater than the last recorded epoch.
    pub fn append(
        &mut self,
        epoch:    u64,
        registry: &PeerRegistry,
    ) -> Result<&TopologySnapshot, TopologyError> {
        if let Some(last) = self.snapshots.last() {
            if epoch <= last.epoch {
                return Err(TopologyError::StaleEpoch);
            }
        }
        let prev_hash = self.snapshots.last()
            .map(|s| s.snapshot_hash)
            .unwrap_or(TOPOLOGY_GENESIS_HASH);

        let snap = build_snapshot(epoch, registry, &prev_hash);
        self.snapshots.push(snap);
        Ok(self.snapshots.last().unwrap())
    }

    /// Verify the full hash chain. Returns (is_valid, first_broken_index).
    pub fn verify_chain(&self) -> (bool, Option<usize>) {
        let mut expected_prev = TOPOLOGY_GENESIS_HASH;
        for (i, snap) in self.snapshots.iter().enumerate() {
            if snap.prev_hash != expected_prev {
                return (false, Some(i));
            }
            let recomputed = compute_snapshot_hash(
                snap.epoch, snap.peer_count, snap.operational_count,
                snap.max_peer_epoch, &snap.prev_hash);
            if recomputed != snap.snapshot_hash {
                return (false, Some(i));
            }
            expected_prev = snap.snapshot_hash;
        }
        (true, None)
    }

    /// Terminal hash (last snapshot_hash or genesis if empty).
    pub fn last_hash(&self) -> [u8; 32] {
        self.snapshots.last()
            .map(|s| s.snapshot_hash)
            .unwrap_or(TOPOLOGY_GENESIS_HASH)
    }
}

impl Default for TopologyLog {
    fn default() -> Self { Self::new() }
}

// ─── Tests ───────────────────────────────────────────────────────────────────

#[cfg(test)]
mod tests {
    use super::*;
    use crate::peer_manifest::{build_manifest, cap, PeerRegistry};
    use crate::phase_transition::ConstitutionalPhase;

    fn make_registry(n_nominal: u32, n_critical: u32) -> PeerRegistry {
        let mut r = PeerRegistry::new();
        for i in 0..n_nominal {
            r.register(build_manifest(i, 1, cap::ALL, ConstitutionalPhase::Nominal)).unwrap();
        }
        for i in n_nominal..(n_nominal + n_critical) {
            r.register(build_manifest(i, 1, cap::ALL, ConstitutionalPhase::Critical)).unwrap();
        }
        r
    }

    // ── TopologySnapshot ─────────────────────────────────────────────────────

    #[test]
    fn empty_registry_snapshot() {
        let r = PeerRegistry::new();
        let s = build_snapshot(1, &r, &TOPOLOGY_GENESIS_HASH);
        assert_eq!(s.peer_count, 0);
        assert_eq!(s.operational_count, 0);
        assert!(!s.quorum_reached());
    }

    #[test]
    fn snapshot_counts_correct() {
        let r = make_registry(3, 1);
        let s = build_snapshot(5, &r, &TOPOLOGY_GENESIS_HASH);
        assert_eq!(s.peer_count, 4);
        assert_eq!(s.operational_count, 3);
        assert_eq!(s.cap_gossip_count, 4);
        assert_eq!(s.cap_consensus_count, 4);
    }

    #[test]
    fn quorum_reached_phi_threshold() {
        // 4/5 = 0.80 > 1/φ ≈ 0.618 → quorum
        let r = make_registry(4, 1);
        let s = build_snapshot(1, &r, &TOPOLOGY_GENESIS_HASH);
        assert!(s.quorum_reached());
    }

    #[test]
    fn quorum_not_reached_below_phi() {
        // 3/8 = 0.375 < 0.618 → no quorum
        let r = make_registry(3, 5);
        let s = build_snapshot(1, &r, &TOPOLOGY_GENESIS_HASH);
        assert!(!s.quorum_reached());
    }

    #[test]
    fn quorum_boundary_at_phi() {
        // 5/8 = 0.625 > 0.618034 → quorum (same boundary as swarm module)
        let r = make_registry(5, 3);
        let s = build_snapshot(1, &r, &TOPOLOGY_GENESIS_HASH);
        assert!(s.quorum_reached());
    }

    #[test]
    fn snapshot_hash_deterministic() {
        let r = make_registry(3, 0);
        let s1 = build_snapshot(7, &r, &TOPOLOGY_GENESIS_HASH);
        let s2 = build_snapshot(7, &r, &TOPOLOGY_GENESIS_HASH);
        let s3 = build_snapshot(7, &r, &TOPOLOGY_GENESIS_HASH);
        assert_eq!(s1.snapshot_hash, s2.snapshot_hash);
        assert_eq!(s2.snapshot_hash, s3.snapshot_hash);
    }

    #[test]
    fn different_epoch_different_hash() {
        let r = make_registry(3, 0);
        let s1 = build_snapshot(1, &r, &TOPOLOGY_GENESIS_HASH);
        let s2 = build_snapshot(2, &r, &TOPOLOGY_GENESIS_HASH);
        assert_ne!(s1.snapshot_hash, s2.snapshot_hash);
    }

    #[test]
    fn snapshot_hash_nonzero() {
        let r = make_registry(2, 0);
        let s = build_snapshot(1, &r, &TOPOLOGY_GENESIS_HASH);
        assert_ne!(s.snapshot_hash, [0u8; 32]);
    }

    // ── TopologyLog ──────────────────────────────────────────────────────────

    #[test]
    fn new_log_empty() {
        let l = TopologyLog::new();
        assert!(l.is_empty());
        assert_eq!(l.last_hash(), TOPOLOGY_GENESIS_HASH);
        assert!(l.latest().is_none());
    }

    #[test]
    fn append_builds_chain() {
        let mut l = TopologyLog::new();
        let r = make_registry(3, 0);
        l.append(1, &r).unwrap();
        l.append(2, &r).unwrap();
        assert_eq!(l.len(), 2);
        let (valid, broken) = l.verify_chain();
        assert!(valid);
        assert!(broken.is_none());
    }

    #[test]
    fn stale_epoch_rejected() {
        let mut l = TopologyLog::new();
        let r = make_registry(2, 0);
        l.append(5, &r).unwrap();
        assert!(matches!(l.append(5, &r), Err(TopologyError::StaleEpoch)));
        assert!(matches!(l.append(4, &r), Err(TopologyError::StaleEpoch)));
    }

    #[test]
    fn chain_links_correctly() {
        let mut l = TopologyLog::new();
        let r = make_registry(2, 0);
        l.append(1, &r).unwrap();
        l.append(2, &r).unwrap();
        // Second snapshot's prev_hash must equal first snapshot's hash
        assert_eq!(l.snapshots()[1].prev_hash, l.snapshots()[0].snapshot_hash);
    }

    #[test]
    fn last_hash_updates() {
        let mut l = TopologyLog::new();
        let r = make_registry(2, 0);
        l.append(1, &r).unwrap();
        let after_first = l.last_hash();
        l.append(2, &r).unwrap();
        let after_second = l.last_hash();
        assert_ne!(after_first, after_second);
        assert_ne!(after_second, TOPOLOGY_GENESIS_HASH);
    }

    #[test]
    fn tampered_snapshot_fails_chain() {
        let mut l = TopologyLog::new();
        let r = make_registry(2, 0);
        l.append(1, &r).unwrap();
        l.append(2, &r).unwrap();
        l.snapshots[0].peer_count = 99;
        let (valid, broken) = l.verify_chain();
        assert!(!valid);
        assert_eq!(broken, Some(0));
    }

    #[test]
    fn error_as_str() {
        assert_eq!(TopologyError::StaleEpoch.as_str(), "stale epoch");
    }
}
