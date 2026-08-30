//! Gate 357 — Compaction Gossip Epoch Seal (T2)
//! EPISTEMIC TIER: T2 (engineering hypothesis)
//!
//! Closes each gossip epoch with a tamper-evident seal binding:
//!   - Gate 355 CompactionGossipHealthMonitor terminal report_hash
//!   - Gate 356 GossipHealthCompactionLog terminal entry_hash
//!   - per-epoch aggregate counters (total_delivered, total_missed, red_epochs, yellow_epochs)
//!
//! seal_hash = SHA-256(prev[32] ‖ epoch_be8
//!                     ‖ health_terminal[32] ‖ compaction_terminal[32]
//!                     ‖ total_delivered_be8 ‖ total_missed_be8
//!                     ‖ red_epochs_be4 ‖ yellow_epochs_be4 ‖ green_epochs_be4)
//!
//! GossipEpochSealChain: append(), seal_count(), terminal_hash(), verify_chain().

use sha2::{Sha256, Digest};

pub const GOSSIP_EPOCH_SEAL_GENESIS_HASH: [u8; 32] = [0u8; 32];

// ─── GossipEpochSeal ─────────────────────────────────────────────────────────

#[derive(Debug, Clone, PartialEq)]
pub struct GossipEpochSeal {
    pub epoch:                u64,
    pub health_terminal:      [u8; 32],
    pub compaction_terminal:  [u8; 32],
    pub total_delivered:      u64,
    pub total_missed:         u64,
    pub red_epochs:           u32,
    pub yellow_epochs:        u32,
    pub green_epochs:         u32,
    pub prev_hash:            [u8; 32],
    pub seal_hash:            [u8; 32],
}

fn compute_seal_hash(
    prev:                &[u8; 32],
    epoch:               u64,
    health_terminal:     &[u8; 32],
    compaction_terminal: &[u8; 32],
    total_delivered:     u64,
    total_missed:        u64,
    red_epochs:          u32,
    yellow_epochs:       u32,
    green_epochs:        u32,
) -> [u8; 32] {
    let mut h = Sha256::new();
    h.update(prev);
    h.update(epoch.to_be_bytes());
    h.update(health_terminal);
    h.update(compaction_terminal);
    h.update(total_delivered.to_be_bytes());
    h.update(total_missed.to_be_bytes());
    h.update(red_epochs.to_be_bytes());
    h.update(yellow_epochs.to_be_bytes());
    h.update(green_epochs.to_be_bytes());
    h.finalize().into()
}

// ─── GossipEpochSealChain ─────────────────────────────────────────────────────

pub struct GossipEpochSealChain {
    seals: Vec<GossipEpochSeal>,
}

impl GossipEpochSealChain {
    pub fn new() -> Self { Self { seals: Vec::new() } }

    pub fn seal_count(&self)   -> usize { self.seals.len() }
    pub fn is_empty(&self)     -> bool  { self.seals.is_empty() }
    pub fn seals(&self)        -> &[GossipEpochSeal] { &self.seals }
    pub fn latest(&self)       -> Option<&GossipEpochSeal> { self.seals.last() }

    pub fn terminal_hash(&self) -> [u8; 32] {
        self.seals.last().map(|s| s.seal_hash).unwrap_or(GOSSIP_EPOCH_SEAL_GENESIS_HASH)
    }

    pub fn append(
        &mut self,
        epoch:               u64,
        health_terminal:     [u8; 32],
        compaction_terminal: [u8; 32],
        total_delivered:     u64,
        total_missed:        u64,
        red_epochs:          u32,
        yellow_epochs:       u32,
        green_epochs:        u32,
    ) -> &GossipEpochSeal {
        let prev = self.terminal_hash();
        let seal_hash = compute_seal_hash(
            &prev, epoch, &health_terminal, &compaction_terminal,
            total_delivered, total_missed, red_epochs, yellow_epochs, green_epochs,
        );
        self.seals.push(GossipEpochSeal {
            epoch, health_terminal, compaction_terminal,
            total_delivered, total_missed,
            red_epochs, yellow_epochs, green_epochs,
            prev_hash: prev, seal_hash,
        });
        self.seals.last().unwrap()
    }

    pub fn verify_chain(&self) -> (bool, Option<usize>) {
        let mut prev = GOSSIP_EPOCH_SEAL_GENESIS_HASH;
        for (i, s) in self.seals.iter().enumerate() {
            if s.prev_hash != prev { return (false, Some(i)); }
            let expected = compute_seal_hash(
                &prev, s.epoch, &s.health_terminal, &s.compaction_terminal,
                s.total_delivered, s.total_missed,
                s.red_epochs, s.yellow_epochs, s.green_epochs,
            );
            if s.seal_hash != expected { return (false, Some(i)); }
            prev = s.seal_hash;
        }
        (true, None)
    }
}

impl Default for GossipEpochSealChain {
    fn default() -> Self { Self::new() }
}

// ─── Tests ────────────────────────────────────────────────────────────────────

#[cfg(test)]
mod tests {
    use super::*;

    fn ht() -> [u8; 32] { [0xAAu8; 32] }
    fn ct() -> [u8; 32] { [0xBBu8; 32] }

    fn append_one(chain: &mut GossipEpochSealChain, epoch: u64) -> [u8; 32] {
        chain.append(epoch, ht(), ct(), 100, 5, 0, 1, 9).seal_hash
    }

    #[test]
    fn empty_chain_terminal_is_genesis() {
        let c = GossipEpochSealChain::new();
        assert_eq!(c.terminal_hash(), GOSSIP_EPOCH_SEAL_GENESIS_HASH);
    }

    #[test]
    fn first_seal_prev_is_genesis() {
        let mut c = GossipEpochSealChain::new();
        let s = c.append(1, ht(), ct(), 10, 0, 0, 0, 1);
        assert_eq!(s.prev_hash, GOSSIP_EPOCH_SEAL_GENESIS_HASH);
    }

    #[test]
    fn seal_hash_nonzero() {
        let mut c = GossipEpochSealChain::new();
        let s = c.append(1, ht(), ct(), 50, 2, 0, 0, 1);
        assert_ne!(s.seal_hash, [0u8; 32]);
    }

    #[test]
    fn second_seal_prev_links_correctly() {
        let mut c = GossipEpochSealChain::new();
        let h0 = append_one(&mut c, 1);
        c.append(2, ht(), ct(), 100, 0, 0, 0, 1);
        assert_eq!(c.seals()[1].prev_hash, h0);
    }

    #[test]
    fn terminal_hash_updates() {
        let mut c = GossipEpochSealChain::new();
        append_one(&mut c, 1);
        let t1 = c.terminal_hash();
        append_one(&mut c, 2);
        let t2 = c.terminal_hash();
        assert_ne!(t1, t2);
    }

    #[test]
    fn seal_count_correct() {
        let mut c = GossipEpochSealChain::new();
        assert_eq!(c.seal_count(), 0);
        append_one(&mut c, 1);
        append_one(&mut c, 2);
        assert_eq!(c.seal_count(), 2);
    }

    #[test]
    fn verify_chain_empty_ok() {
        let c = GossipEpochSealChain::new();
        let (ok, idx) = c.verify_chain();
        assert!(ok);
        assert!(idx.is_none());
    }

    #[test]
    fn verify_chain_three_seals_ok() {
        let mut c = GossipEpochSealChain::new();
        for i in 1..=3 { append_one(&mut c, i); }
        let (ok, idx) = c.verify_chain();
        assert!(ok);
        assert!(idx.is_none());
    }

    #[test]
    fn verify_chain_detects_tamper() {
        let mut c = GossipEpochSealChain::new();
        append_one(&mut c, 1);
        append_one(&mut c, 2);
        c.seals[0].seal_hash[0] ^= 0xFF;
        let (ok, idx) = c.verify_chain();
        assert!(!ok);
        assert_eq!(idx, Some(0));
    }

    #[test]
    fn seal_hash_deterministic() {
        let mut c1 = GossipEpochSealChain::new();
        let mut c2 = GossipEpochSealChain::new();
        let h1 = c1.append(5, ht(), ct(), 200, 10, 1, 2, 7).seal_hash;
        let h2 = c2.append(5, ht(), ct(), 200, 10, 1, 2, 7).seal_hash;
        assert_eq!(h1, h2);
    }

    #[test]
    fn different_epoch_different_hash() {
        let mut c1 = GossipEpochSealChain::new();
        let mut c2 = GossipEpochSealChain::new();
        let h1 = c1.append(1, ht(), ct(), 100, 0, 0, 0, 1).seal_hash;
        let h2 = c2.append(2, ht(), ct(), 100, 0, 0, 0, 1).seal_hash;
        assert_ne!(h1, h2);
    }

    #[test]
    fn fields_preserved_in_seal() {
        let mut c = GossipEpochSealChain::new();
        let s = c.append(42, ht(), ct(), 300, 15, 2, 3, 5);
        assert_eq!(s.epoch, 42);
        assert_eq!(s.total_delivered, 300);
        assert_eq!(s.total_missed, 15);
        assert_eq!(s.red_epochs, 2);
        assert_eq!(s.yellow_epochs, 3);
        assert_eq!(s.green_epochs, 5);
        assert_eq!(s.health_terminal, ht());
        assert_eq!(s.compaction_terminal, ct());
    }

    #[test]
    fn latest_returns_last_seal() {
        let mut c = GossipEpochSealChain::new();
        assert!(c.latest().is_none());
        append_one(&mut c, 1);
        append_one(&mut c, 2);
        assert_eq!(c.latest().unwrap().epoch, 2);
    }
}
