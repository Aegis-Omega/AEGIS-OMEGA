//! Gate 257 — Peer Manifest: signed peer identity + capability advertisement (T2)
//! EPISTEMIC TIER: T2 (engineering hypothesis)
//!
//! Each node in the gossip mesh advertises a PeerManifest describing its capabilities
//! and constitutional state. Manifests are hash-chained in a PeerRegistry.
//!
//! PeerManifest:
//!   node_id        — u32 (opaque node identifier)
//!   epoch          — u64 (epoch at time of advertisement)
//!   capabilities   — u8 bitmask (see PeerCapability flags)
//!   phase          — ConstitutionalPhase
//!   manifest_hash  — SHA-256(node_id_be4 ‖ epoch_be8 ‖ capabilities ‖ phase_byte)
//!
//! PeerCapability flags (bitmask):
//!   GOSSIP    = 0b0001 — participates in gossip broadcast
//!   RELAY     = 0b0010 — relays messages for non-direct peers
//!   AUDIT     = 0b0100 — maintains audit log
//!   CONSENSUS = 0b1000 — participates in BFT quorum
//!
//! PeerRegistry:
//!   records          — BTreeMap<u32, PeerManifest> (latest manifest per node_id)
//!   insertion_order  — Vec<u32> (for deterministic iteration)
//!   register(manifest)   — validates hash; replaces if epoch is newer
//!   active_peers()       — all registered manifests in insertion order
//!   peers_with_cap(cap)  — peers whose capabilities include the given flag

use sha2::{Sha256, Digest};
use std::collections::BTreeMap;
use crate::phase_transition::ConstitutionalPhase;

// ─── Capability flags ─────────────────────────────────────────────────────────

pub mod cap {
    pub const GOSSIP:    u8 = 0b0001;
    pub const RELAY:     u8 = 0b0010;
    pub const AUDIT:     u8 = 0b0100;
    pub const CONSENSUS: u8 = 0b1000;
    pub const ALL:       u8 = 0b1111;
}

/// Check if a capabilities bitmask includes a given flag.
pub fn has_capability(capabilities: u8, flag: u8) -> bool {
    capabilities & flag == flag
}

// ─── Peer manifest ────────────────────────────────────────────────────────────

#[derive(Debug, Clone, PartialEq)]
pub struct PeerManifest {
    pub node_id:       u32,
    pub epoch:         u64,
    pub capabilities:  u8,
    pub phase:         ConstitutionalPhase,
    pub manifest_hash: [u8; 32],
}

impl PeerManifest {
    pub fn is_hash_valid(&self) -> bool {
        compute_manifest_hash(self.node_id, self.epoch, self.capabilities, self.phase)
            == self.manifest_hash
    }

    pub fn has_capability(&self, flag: u8) -> bool {
        has_capability(self.capabilities, flag)
    }

    pub fn is_operational(&self) -> bool {
        self.phase.is_operational()
    }
}

fn compute_manifest_hash(
    node_id:      u32,
    epoch:        u64,
    capabilities: u8,
    phase:        ConstitutionalPhase,
) -> [u8; 32] {
    let mut h = Sha256::new();
    h.update(node_id.to_be_bytes());
    h.update(epoch.to_be_bytes());
    h.update([capabilities]);
    h.update([phase.as_u8()]);
    h.finalize().into()
}

// ─── Build manifest ───────────────────────────────────────────────────────────

pub fn build_manifest(
    node_id:      u32,
    epoch:        u64,
    capabilities: u8,
    phase:        ConstitutionalPhase,
) -> PeerManifest {
    let manifest_hash = compute_manifest_hash(node_id, epoch, capabilities, phase);
    PeerManifest { node_id, epoch, capabilities, phase, manifest_hash }
}

// ─── Registry error ───────────────────────────────────────────────────────────

#[derive(Debug)]
pub enum RegistryError {
    InvalidHash,
    StaleEpoch,
}

impl RegistryError {
    pub fn as_str(&self) -> &'static str {
        match self {
            Self::InvalidHash => "invalid manifest hash",
            Self::StaleEpoch  => "stale epoch",
        }
    }
}

// ─── Peer registry ────────────────────────────────────────────────────────────

#[derive(Debug, Clone)]
pub struct PeerRegistry {
    records:         BTreeMap<u32, PeerManifest>,
    insertion_order: Vec<u32>,
}

impl PeerRegistry {
    pub fn new() -> Self {
        Self { records: BTreeMap::new(), insertion_order: Vec::new() }
    }

    pub fn len(&self) -> usize { self.records.len() }
    pub fn is_empty(&self) -> bool { self.records.is_empty() }

    /// Register a manifest. Validates hash; rejects if epoch is not strictly newer.
    pub fn register(&mut self, manifest: PeerManifest) -> Result<(), RegistryError> {
        if !manifest.is_hash_valid() {
            return Err(RegistryError::InvalidHash);
        }
        if let Some(existing) = self.records.get(&manifest.node_id) {
            if manifest.epoch <= existing.epoch {
                return Err(RegistryError::StaleEpoch);
            }
        } else {
            self.insertion_order.push(manifest.node_id);
        }
        self.records.insert(manifest.node_id, manifest);
        Ok(())
    }

    /// All registered manifests in insertion order.
    pub fn active_peers(&self) -> Vec<&PeerManifest> {
        self.insertion_order.iter()
            .filter_map(|id| self.records.get(id))
            .collect()
    }

    /// Peers whose capabilities include the given flag, in insertion order.
    pub fn peers_with_cap(&self, flag: u8) -> Vec<&PeerManifest> {
        self.active_peers().into_iter()
            .filter(|m| m.has_capability(flag))
            .collect()
    }

    /// Peers in operational phase (not Critical), in insertion order.
    pub fn operational_peers(&self) -> Vec<&PeerManifest> {
        self.active_peers().into_iter()
            .filter(|m| m.is_operational())
            .collect()
    }

    /// Look up latest manifest for a node_id.
    pub fn get(&self, node_id: u32) -> Option<&PeerManifest> {
        self.records.get(&node_id)
    }

    /// Latest epoch seen across all registered peers (0 if empty).
    pub fn max_epoch(&self) -> u64 {
        self.records.values().map(|m| m.epoch).max().unwrap_or(0)
    }
}

impl Default for PeerRegistry {
    fn default() -> Self { Self::new() }
}

// ─── Tests ───────────────────────────────────────────────────────────────────

#[cfg(test)]
mod tests {
    use super::*;

    fn nominal(node_id: u32, epoch: u64) -> PeerManifest {
        build_manifest(node_id, epoch, cap::ALL, ConstitutionalPhase::Nominal)
    }

    fn gossip_only(node_id: u32, epoch: u64) -> PeerManifest {
        build_manifest(node_id, epoch, cap::GOSSIP, ConstitutionalPhase::Nominal)
    }

    fn critical_peer(node_id: u32, epoch: u64) -> PeerManifest {
        build_manifest(node_id, epoch, cap::ALL, ConstitutionalPhase::Critical)
    }

    // ── capability flags ─────────────────────────────────────────────────────

    #[test]
    fn capability_constants() {
        assert_eq!(cap::GOSSIP,    0b0001);
        assert_eq!(cap::RELAY,     0b0010);
        assert_eq!(cap::AUDIT,     0b0100);
        assert_eq!(cap::CONSENSUS, 0b1000);
        assert_eq!(cap::ALL,       0b1111);
    }

    #[test]
    fn has_capability_flag() {
        assert!(has_capability(cap::ALL,    cap::GOSSIP));
        assert!(has_capability(cap::ALL,    cap::CONSENSUS));
        assert!(!has_capability(cap::GOSSIP, cap::RELAY));
        assert!(has_capability(cap::GOSSIP | cap::RELAY, cap::RELAY));
    }

    // ── PeerManifest ─────────────────────────────────────────────────────────

    #[test]
    fn build_manifest_hash_valid() {
        let m = nominal(1, 10);
        assert!(m.is_hash_valid());
    }

    #[test]
    fn tampered_node_id_invalidates_hash() {
        let mut m = nominal(1, 10);
        m.node_id = 99;
        assert!(!m.is_hash_valid());
    }

    #[test]
    fn tampered_epoch_invalidates_hash() {
        let mut m = nominal(1, 10);
        m.epoch = 99;
        assert!(!m.is_hash_valid());
    }

    #[test]
    fn tampered_capabilities_invalidates_hash() {
        let mut m = nominal(1, 10);
        m.capabilities = 0b0001;
        assert!(!m.is_hash_valid());
    }

    #[test]
    fn manifest_hash_deterministic() {
        let m1 = nominal(5, 3);
        let m2 = nominal(5, 3);
        let m3 = nominal(5, 3);
        assert_eq!(m1.manifest_hash, m2.manifest_hash);
        assert_eq!(m2.manifest_hash, m3.manifest_hash);
    }

    #[test]
    fn different_node_different_hash() {
        let m1 = nominal(1, 1);
        let m2 = nominal(2, 1);
        assert_ne!(m1.manifest_hash, m2.manifest_hash);
    }

    #[test]
    fn manifest_capability_accessors() {
        let m = gossip_only(1, 1);
        assert!(m.has_capability(cap::GOSSIP));
        assert!(!m.has_capability(cap::RELAY));
        assert!(!m.has_capability(cap::CONSENSUS));
    }

    #[test]
    fn manifest_is_operational() {
        assert!(nominal(1, 1).is_operational());
        assert!(!critical_peer(1, 1).is_operational());
    }

    // ── PeerRegistry ─────────────────────────────────────────────────────────

    #[test]
    fn new_registry_empty() {
        let r = PeerRegistry::new();
        assert!(r.is_empty());
        assert_eq!(r.len(), 0);
        assert_eq!(r.max_epoch(), 0);
    }

    #[test]
    fn register_valid_manifest_succeeds() {
        let mut r = PeerRegistry::new();
        r.register(nominal(1, 5)).unwrap();
        assert_eq!(r.len(), 1);
        assert_eq!(r.get(1).unwrap().epoch, 5);
    }

    #[test]
    fn register_invalid_hash_rejected() {
        let mut r = PeerRegistry::new();
        let mut bad = nominal(1, 5);
        bad.manifest_hash[0] ^= 0xFF;
        assert!(matches!(r.register(bad), Err(RegistryError::InvalidHash)));
    }

    #[test]
    fn register_stale_epoch_rejected() {
        let mut r = PeerRegistry::new();
        r.register(nominal(1, 5)).unwrap();
        assert!(matches!(r.register(nominal(1, 5)), Err(RegistryError::StaleEpoch)));
        assert!(matches!(r.register(nominal(1, 4)), Err(RegistryError::StaleEpoch)));
    }

    #[test]
    fn newer_epoch_replaces_old() {
        let mut r = PeerRegistry::new();
        r.register(nominal(1, 5)).unwrap();
        r.register(nominal(1, 10)).unwrap();
        assert_eq!(r.len(), 1); // still 1 peer
        assert_eq!(r.get(1).unwrap().epoch, 10);
    }

    #[test]
    fn active_peers_insertion_order() {
        let mut r = PeerRegistry::new();
        r.register(nominal(3, 1)).unwrap();
        r.register(nominal(1, 1)).unwrap();
        r.register(nominal(2, 1)).unwrap();
        let ids: Vec<u32> = r.active_peers().iter().map(|m| m.node_id).collect();
        assert_eq!(ids, vec![3, 1, 2]);
    }

    #[test]
    fn peers_with_cap_filters() {
        let mut r = PeerRegistry::new();
        r.register(gossip_only(1, 1)).unwrap();
        r.register(nominal(2, 1)).unwrap(); // ALL caps
        r.register(build_manifest(3, 1, cap::RELAY, ConstitutionalPhase::Nominal)).unwrap();
        assert_eq!(r.peers_with_cap(cap::GOSSIP).len(), 2); // 1 and 2
        assert_eq!(r.peers_with_cap(cap::CONSENSUS).len(), 1); // only 2
        assert_eq!(r.peers_with_cap(cap::AUDIT).len(), 1); // only 2
    }

    #[test]
    fn operational_peers_excludes_critical() {
        let mut r = PeerRegistry::new();
        r.register(nominal(1, 1)).unwrap();
        r.register(critical_peer(2, 1)).unwrap();
        r.register(nominal(3, 1)).unwrap();
        assert_eq!(r.operational_peers().len(), 2);
    }

    #[test]
    fn max_epoch_tracks() {
        let mut r = PeerRegistry::new();
        r.register(nominal(1, 5)).unwrap();
        r.register(nominal(2, 10)).unwrap();
        r.register(nominal(3, 3)).unwrap();
        assert_eq!(r.max_epoch(), 10);
    }

    #[test]
    fn error_as_str() {
        assert_eq!(RegistryError::InvalidHash.as_str(), "invalid manifest hash");
        assert_eq!(RegistryError::StaleEpoch.as_str(),  "stale epoch");
    }
}
