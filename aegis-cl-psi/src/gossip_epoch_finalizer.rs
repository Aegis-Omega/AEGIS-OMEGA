//! Gate 280 — Gossip Epoch Finalizer: terminal gossip state seal at epoch close (T2)
//! EPISTEMIC TIER: T2 (engineering hypothesis)
//!
//! Produces a GossipEpochSeal that cryptographically binds the terminal state
//! of all gossip-layer subsystems at epoch close.
//!
//! GossipEpochSeal:
//!   epoch               — u64
//!   supervision_hash    — [u8; 32] (MeshSupervisionLog terminal)
//!   scheduler_hash      — [u8; 32] (GossipSchedule last interval_hash)
//!   spread_hash         — [u8; 32] (EstimateLog last estimate_hash)
//!   registry_peer_count — u32 (total peers at epoch close)
//!   trusted_count       — u32
//!   blocked_count       — u32
//!   seal_hash           — SHA-256(prev ‖ epoch_be8 ‖ supervision ‖ scheduler ‖ spread ‖
//!                                 registry_be4 ‖ trusted_be4 ‖ blocked_be4)
//!   prev_seal_hash      — [u8; 32]
//!
//! GossipEpochChain: hash-chained GossipEpochSeals.
//!   append(), terminal_hash(), seal_count(), verify_chain().

use sha2::{Sha256, Digest};

// ─── Gossip epoch seal ────────────────────────────────────────────────────────

#[derive(Debug, Clone, PartialEq)]
pub struct GossipEpochSeal {
    pub epoch:               u64,
    pub supervision_hash:    [u8; 32],
    pub scheduler_hash:      [u8; 32],
    pub spread_hash:         [u8; 32],
    pub registry_peer_count: u32,
    pub trusted_count:       u32,
    pub blocked_count:       u32,
    pub seal_hash:           [u8; 32],
    pub prev_seal_hash:      [u8; 32],
}

pub const GOSSIP_EPOCH_GENESIS_HASH: [u8; 32] = [0u8; 32];

fn compute_seal_hash(
    epoch:               u64,
    supervision_hash:    &[u8; 32],
    scheduler_hash:      &[u8; 32],
    spread_hash:         &[u8; 32],
    registry_peer_count: u32,
    trusted_count:       u32,
    blocked_count:       u32,
    prev:                &[u8; 32],
) -> [u8; 32] {
    let mut h = Sha256::new();
    h.update(prev);
    h.update(epoch.to_be_bytes());
    h.update(supervision_hash);
    h.update(scheduler_hash);
    h.update(spread_hash);
    h.update(registry_peer_count.to_be_bytes());
    h.update(trusted_count.to_be_bytes());
    h.update(blocked_count.to_be_bytes());
    h.finalize().into()
}

pub fn build_gossip_seal(
    epoch:               u64,
    supervision_hash:    [u8; 32],
    scheduler_hash:      [u8; 32],
    spread_hash:         [u8; 32],
    registry_peer_count: u32,
    trusted_count:       u32,
    blocked_count:       u32,
    prev_seal_hash:      &[u8; 32],
) -> GossipEpochSeal {
    let seal_hash = compute_seal_hash(
        epoch, &supervision_hash, &scheduler_hash, &spread_hash,
        registry_peer_count, trusted_count, blocked_count, prev_seal_hash,
    );
    GossipEpochSeal {
        epoch, supervision_hash, scheduler_hash, spread_hash,
        registry_peer_count, trusted_count, blocked_count,
        seal_hash, prev_seal_hash: *prev_seal_hash,
    }
}

impl GossipEpochSeal {
    /// True if at least half the known peers are trusted (integer arithmetic).
    pub fn majority_trusted(&self) -> bool {
        if self.registry_peer_count == 0 { return false; }
        self.trusted_count * 2 >= self.registry_peer_count
    }

    /// True if no blocked peers at this epoch.
    pub fn no_blocked_peers(&self) -> bool { self.blocked_count == 0 }
}

// ─── Gossip epoch chain ───────────────────────────────────────────────────────

#[derive(Debug, Clone)]
pub struct GossipEpochChain {
    seals: Vec<GossipEpochSeal>,
}

#[derive(Debug)]
pub enum GossipEpochError {
    StaleEpoch,
}

impl GossipEpochChain {
    pub fn new() -> Self { Self { seals: Vec::new() } }

    pub fn len(&self)      -> usize { self.seals.len() }
    pub fn is_empty(&self) -> bool  { self.seals.is_empty() }
    pub fn seals(&self)    -> &[GossipEpochSeal] { &self.seals }
    pub fn latest(&self)   -> Option<&GossipEpochSeal> { self.seals.last() }

    pub fn last_hash(&self) -> [u8; 32] {
        self.seals.last().map(|s| s.seal_hash).unwrap_or(GOSSIP_EPOCH_GENESIS_HASH)
    }

    pub fn terminal_hash(&self) -> [u8; 32] { self.last_hash() }
    pub fn seal_count(&self) -> usize { self.seals.len() }

    pub fn append(
        &mut self,
        epoch:               u64,
        supervision_hash:    [u8; 32],
        scheduler_hash:      [u8; 32],
        spread_hash:         [u8; 32],
        registry_peer_count: u32,
        trusted_count:       u32,
        blocked_count:       u32,
    ) -> Result<&GossipEpochSeal, GossipEpochError> {
        if let Some(last) = self.seals.last() {
            if epoch <= last.epoch {
                return Err(GossipEpochError::StaleEpoch);
            }
        }
        let prev = self.last_hash();
        let seal = build_gossip_seal(
            epoch, supervision_hash, scheduler_hash, spread_hash,
            registry_peer_count, trusted_count, blocked_count, &prev,
        );
        self.seals.push(seal);
        Ok(self.seals.last().unwrap())
    }

    pub fn verify_chain(&self) -> (bool, Option<usize>) {
        let mut expected_prev = GOSSIP_EPOCH_GENESIS_HASH;
        for (i, seal) in self.seals.iter().enumerate() {
            if seal.prev_seal_hash != expected_prev {
                return (false, Some(i));
            }
            let recomputed = compute_seal_hash(
                seal.epoch,
                &seal.supervision_hash,
                &seal.scheduler_hash,
                &seal.spread_hash,
                seal.registry_peer_count,
                seal.trusted_count,
                seal.blocked_count,
                &seal.prev_seal_hash,
            );
            if recomputed != seal.seal_hash {
                return (false, Some(i));
            }
            expected_prev = seal.seal_hash;
        }
        (true, None)
    }
}

impl Default for GossipEpochChain {
    fn default() -> Self { Self::new() }
}

// ─── Tests ───────────────────────────────────────────────────────────────────

#[cfg(test)]
mod tests {
    use super::*;

    fn h(seed: u8) -> [u8; 32] { [seed; 32] }

    fn add_seal(chain: &mut GossipEpochChain, epoch: u64, seed: u8) {
        chain.append(
            epoch, h(seed), h(seed.wrapping_add(1)), h(seed.wrapping_add(2)),
            10, 7, 0,
        ).unwrap();
    }

    // ── build_gossip_seal ─────────────────────────────────────────────────────

    #[test]
    fn seal_hash_nonzero() {
        let s = build_gossip_seal(1, h(1), h(2), h(3), 10, 7, 0, &GOSSIP_EPOCH_GENESIS_HASH);
        assert_ne!(s.seal_hash, [0u8; 32]);
    }

    #[test]
    fn seal_hash_deterministic() {
        let s1 = build_gossip_seal(1, h(1), h(2), h(3), 10, 7, 0, &GOSSIP_EPOCH_GENESIS_HASH);
        let s2 = build_gossip_seal(1, h(1), h(2), h(3), 10, 7, 0, &GOSSIP_EPOCH_GENESIS_HASH);
        assert_eq!(s1.seal_hash, s2.seal_hash);
    }

    #[test]
    fn different_supervision_different_seal() {
        let s1 = build_gossip_seal(1, h(1), h(2), h(3), 10, 7, 0, &GOSSIP_EPOCH_GENESIS_HASH);
        let s2 = build_gossip_seal(1, h(9), h(2), h(3), 10, 7, 0, &GOSSIP_EPOCH_GENESIS_HASH);
        assert_ne!(s1.seal_hash, s2.seal_hash);
    }

    #[test]
    fn majority_trusted_true() {
        let s = build_gossip_seal(1, h(1), h(2), h(3), 10, 6, 0, &GOSSIP_EPOCH_GENESIS_HASH);
        assert!(s.majority_trusted()); // 6 * 2 = 12 >= 10
    }

    #[test]
    fn majority_trusted_false() {
        let s = build_gossip_seal(1, h(1), h(2), h(3), 10, 4, 0, &GOSSIP_EPOCH_GENESIS_HASH);
        assert!(!s.majority_trusted()); // 4 * 2 = 8 < 10
    }

    #[test]
    fn no_blocked_peers_flag() {
        let s1 = build_gossip_seal(1, h(1), h(2), h(3), 10, 7, 0, &GOSSIP_EPOCH_GENESIS_HASH);
        let s2 = build_gossip_seal(2, h(1), h(2), h(3), 10, 7, 3, &GOSSIP_EPOCH_GENESIS_HASH);
        assert!(s1.no_blocked_peers());
        assert!(!s2.no_blocked_peers());
    }

    // ── GossipEpochChain ──────────────────────────────────────────────────────

    #[test]
    fn new_chain_empty() {
        let c = GossipEpochChain::new();
        assert!(c.is_empty());
        assert_eq!(c.terminal_hash(), GOSSIP_EPOCH_GENESIS_HASH);
        assert_eq!(c.seal_count(), 0);
    }

    #[test]
    fn append_chains_hashes() {
        let mut c = GossipEpochChain::new();
        add_seal(&mut c, 1, 10);
        add_seal(&mut c, 2, 20);
        assert_eq!(c.seals()[1].prev_seal_hash, c.seals()[0].seal_hash);
    }

    #[test]
    fn stale_epoch_rejected() {
        let mut c = GossipEpochChain::new();
        add_seal(&mut c, 5, 10);
        assert!(matches!(
            c.append(5, h(1), h(2), h(3), 10, 7, 0),
            Err(GossipEpochError::StaleEpoch)
        ));
        assert!(matches!(
            c.append(4, h(1), h(2), h(3), 10, 7, 0),
            Err(GossipEpochError::StaleEpoch)
        ));
    }

    #[test]
    fn terminal_hash_matches_last() {
        let mut c = GossipEpochChain::new();
        add_seal(&mut c, 1, 10);
        add_seal(&mut c, 2, 20);
        assert_eq!(c.terminal_hash(), c.seals().last().unwrap().seal_hash);
    }

    #[test]
    fn verify_chain_valid() {
        let mut c = GossipEpochChain::new();
        for e in 1..=6u64 {
            add_seal(&mut c, e, e as u8 * 10);
        }
        let (valid, broken) = c.verify_chain();
        assert!(valid);
        assert!(broken.is_none());
    }
}
