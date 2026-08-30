//! Gate 383 — Gossip Epoch Seal (T2)
//! EPISTEMIC TIER: T2 (engineering hypothesis)
//!
//! Produces a final immutable seal for each gossip epoch by committing all
//! epoch-level signals — fanout coverage, average latency, window average,
//! window state, and peer score — into a single hash-chained GossipEpochSeal.
//!
//! GossipEpochSeal (hash-chained):
//!   epoch_end:       u64
//!   coverage_pct:    u32   — fanout coverage for this epoch
//!   avg_latency:     u64   — average latency_epochs (integer floor)
//!   window_avg_pct:  u32   — rolling-window coverage average
//!   window_state:    u8    — 0=Healthy 1=Degraded 2=Critical
//!   peer_score_pct:  u32   — overall peer score (avg of all peer scores, floor)
//!   seal_hash:       [u8;32]
//!   prev_hash:       [u8;32]
//!
//! seal_hash = SHA-256(prev[32] ‖ epoch_end_be8 ‖ coverage_pct_be4
//!                       ‖ avg_latency_be8 ‖ window_avg_pct_be4
//!                       ‖ window_state_byte ‖ peer_score_pct_be4)
//!
//! GossipEpochSealChain: seal(epoch_end, coverage_pct, avg_latency,
//!   window_avg_pct, window_state, peer_score_pct),
//!   latest(), seal_count(), verify_chain().

use sha2::{Sha256, Digest};

pub const GOSSIP_SEAL_GENESIS_HASH: [u8; 32] = [0u8; 32];

// ─── GossipEpochSeal ──────────────────────────────────────────────────────────

#[derive(Debug, Clone, PartialEq)]
pub struct GossipEpochSeal {
    pub epoch_end:      u64,
    pub coverage_pct:   u32,
    pub avg_latency:    u64,
    pub window_avg_pct: u32,
    pub window_state:   u8,
    pub peer_score_pct: u32,
    pub seal_hash:      [u8; 32],
    pub prev_hash:      [u8; 32],
}

fn compute_seal_hash(
    prev:           &[u8; 32],
    epoch_end:      u64,
    coverage_pct:   u32,
    avg_latency:    u64,
    window_avg_pct: u32,
    window_state:   u8,
    peer_score_pct: u32,
) -> [u8; 32] {
    let mut h = Sha256::new();
    h.update(prev);
    h.update(epoch_end.to_be_bytes());
    h.update(coverage_pct.to_be_bytes());
    h.update(avg_latency.to_be_bytes());
    h.update(window_avg_pct.to_be_bytes());
    h.update([window_state]);
    h.update(peer_score_pct.to_be_bytes());
    h.finalize().into()
}

// ─── GossipEpochSealChain ─────────────────────────────────────────────────────

pub struct GossipEpochSealChain {
    seals: Vec<GossipEpochSeal>,
}

impl GossipEpochSealChain {
    pub fn new() -> Self { Self { seals: Vec::new() } }

    pub fn seal_count(&self) -> usize { self.seals.len() }
    pub fn is_empty(&self)   -> bool  { self.seals.is_empty() }
    pub fn seals(&self)      -> &[GossipEpochSeal] { &self.seals }
    pub fn latest(&self)     -> Option<&GossipEpochSeal> { self.seals.last() }

    /// Seal the gossip state for one epoch.
    pub fn seal(
        &mut self,
        epoch_end:      u64,
        coverage_pct:   u32,
        avg_latency:    u64,
        window_avg_pct: u32,
        window_state:   u8,
        peer_score_pct: u32,
    ) -> &GossipEpochSeal {
        let prev = self.seals.last()
            .map(|s| s.seal_hash)
            .unwrap_or(GOSSIP_SEAL_GENESIS_HASH);

        let seal_hash = compute_seal_hash(
            &prev,
            epoch_end,
            coverage_pct,
            avg_latency,
            window_avg_pct,
            window_state,
            peer_score_pct,
        );

        self.seals.push(GossipEpochSeal {
            epoch_end,
            coverage_pct,
            avg_latency,
            window_avg_pct,
            window_state,
            peer_score_pct,
            seal_hash,
            prev_hash: prev,
        });
        self.seals.last().unwrap()
    }

    pub fn verify_chain(&self) -> (bool, Option<usize>) {
        let mut prev = GOSSIP_SEAL_GENESIS_HASH;
        for (i, s) in self.seals.iter().enumerate() {
            if s.prev_hash != prev {
                return (false, Some(i));
            }
            let expected = compute_seal_hash(
                &prev,
                s.epoch_end,
                s.coverage_pct,
                s.avg_latency,
                s.window_avg_pct,
                s.window_state,
                s.peer_score_pct,
            );
            if s.seal_hash != expected {
                return (false, Some(i));
            }
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

    // ── seal ──────────────────────────────────────────────────────────────────

    #[test]
    fn seal_fields_stored() {
        let mut chain = GossipEpochSealChain::new();
        let s = chain.seal(10, 90, 2, 85, 0, 95);
        assert_eq!(s.epoch_end, 10);
        assert_eq!(s.coverage_pct, 90);
        assert_eq!(s.avg_latency, 2);
        assert_eq!(s.window_avg_pct, 85);
        assert_eq!(s.window_state, 0);
        assert_eq!(s.peer_score_pct, 95);
    }

    #[test]
    fn seal_hash_nonzero() {
        let mut chain = GossipEpochSealChain::new();
        let s = chain.seal(1, 80, 3, 80, 0, 90);
        assert_ne!(s.seal_hash, [0u8; 32]);
    }

    #[test]
    fn first_seal_prev_hash_is_genesis() {
        let mut chain = GossipEpochSealChain::new();
        let s = chain.seal(1, 80, 3, 80, 0, 90);
        assert_eq!(s.prev_hash, GOSSIP_SEAL_GENESIS_HASH);
    }

    #[test]
    fn chain_prev_links() {
        let mut chain = GossipEpochSealChain::new();
        chain.seal(1, 80, 3, 80, 0, 90);
        let h0 = chain.seals()[0].seal_hash;
        chain.seal(2, 75, 4, 78, 0, 88);
        assert_eq!(chain.seals()[1].prev_hash, h0);
    }

    #[test]
    fn seal_count_increments() {
        let mut chain = GossipEpochSealChain::new();
        assert_eq!(chain.seal_count(), 0);
        chain.seal(1, 80, 1, 80, 0, 90);
        chain.seal(2, 60, 5, 65, 1, 70);
        assert_eq!(chain.seal_count(), 2);
    }

    // ── different fields → different hash ─────────────────────────────────────

    #[test]
    fn different_epoch_gives_different_hash() {
        let mut c1 = GossipEpochSealChain::new();
        let mut c2 = GossipEpochSealChain::new();
        let h1 = c1.seal(1, 80, 2, 80, 0, 90).seal_hash;
        let h2 = c2.seal(2, 80, 2, 80, 0, 90).seal_hash;
        assert_ne!(h1, h2);
    }

    #[test]
    fn different_window_state_gives_different_hash() {
        let mut c1 = GossipEpochSealChain::new();
        let mut c2 = GossipEpochSealChain::new();
        let h1 = c1.seal(1, 80, 2, 80, 0, 90).seal_hash;
        let h2 = c2.seal(1, 80, 2, 80, 1, 90).seal_hash;
        assert_ne!(h1, h2);
    }

    // ── latest / empty ────────────────────────────────────────────────────────

    #[test]
    fn latest_returns_most_recent() {
        let mut chain = GossipEpochSealChain::new();
        chain.seal(1, 80, 1, 80, 0, 90);
        chain.seal(2, 70, 3, 75, 1, 85);
        assert_eq!(chain.latest().unwrap().epoch_end, 2);
    }

    #[test]
    fn latest_on_empty_returns_none() {
        let chain = GossipEpochSealChain::new();
        assert!(chain.latest().is_none());
    }

    // ── verify_chain ──────────────────────────────────────────────────────────

    #[test]
    fn verify_chain_empty_ok() {
        let chain = GossipEpochSealChain::new();
        let (ok, idx) = chain.verify_chain();
        assert!(ok);
        assert!(idx.is_none());
    }

    #[test]
    fn verify_chain_multiple_ok() {
        let mut chain = GossipEpochSealChain::new();
        for i in 1u64..=5 {
            chain.seal(i, 80, 2, 80, 0, 90);
        }
        let (ok, idx) = chain.verify_chain();
        assert!(ok);
        assert!(idx.is_none());
    }

    #[test]
    fn verify_chain_detects_tamper() {
        let mut chain = GossipEpochSealChain::new();
        chain.seal(1, 80, 2, 80, 0, 90);
        chain.seal(2, 75, 3, 78, 0, 88);
        chain.seals[0].seal_hash[0] ^= 0xFF;
        let (ok, idx) = chain.verify_chain();
        assert!(!ok);
        assert_eq!(idx, Some(0));
    }

    // ── determinism ───────────────────────────────────────────────────────────

    #[test]
    fn seal_hash_deterministic() {
        let mut c1 = GossipEpochSealChain::new();
        let mut c2 = GossipEpochSealChain::new();
        let h1 = c1.seal(7, 85, 4, 82, 0, 92).seal_hash;
        let h2 = c2.seal(7, 85, 4, 82, 0, 92).seal_hash;
        assert_eq!(h1, h2);
    }
}
