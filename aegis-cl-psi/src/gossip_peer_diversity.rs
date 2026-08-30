//! Gate 414 — Gossip Peer Diversity Log (T2)
//! EPISTEMIC TIER: T2 (engineering hypothesis)
//!
//! Per-epoch tracking of peer diversity in the gossip overlay.
//! Diversity measures the spread of peers across distinct subnets or zones.
//!
//! distinct_zones:  u32 — number of distinct zones represented by active peers
//! total_peers:     u32 — total active peers this epoch
//! diversity_score: u32 — distinct_zones * 100 / max(total_peers, 1)
//!                         (capped at 100 — at most 100% diversity)
//! low_diversity:   bool — diversity_score < DIVERSITY_FLOOR (20%)
//!
//! DIVERSITY_FLOOR: u32 = 20
//!
//! GossipPeerDiversityEntry (hash-chained):
//!   epoch_end:       u64
//!   distinct_zones:  u32
//!   total_peers:     u32
//!   diversity_score: u32
//!   low_diversity:   bool
//!   entry_hash:      [u8;32]
//!   prev_hash:       [u8;32]
//!
//! entry_hash = SHA-256(prev[32] ‖ epoch_end_be8 ‖ distinct_zones_be4
//!                       ‖ total_peers_be4 ‖ diversity_score_be4 ‖ low_diversity_byte)
//!
//! GossipPeerDiversityLog: record(epoch_end, distinct_zones, total_peers),
//!   low_diversity_count(), max_diversity_score(), mean_diversity_score(), verify_chain().

use sha2::{Sha256, Digest};

pub const GOSSIP_PEER_DIVERSITY_GENESIS_HASH: [u8; 32] = [0u8; 32];
pub const DIVERSITY_FLOOR: u32 = 20; // percent

// ─── GossipPeerDiversityEntry ─────────────────────────────────────────────────

#[derive(Debug, Clone, PartialEq)]
pub struct GossipPeerDiversityEntry {
    pub epoch_end:       u64,
    pub distinct_zones:  u32,
    pub total_peers:     u32,
    pub diversity_score: u32,
    pub low_diversity:   bool,
    pub entry_hash:      [u8; 32],
    pub prev_hash:       [u8; 32],
}

fn compute_peer_diversity_hash(
    prev:            &[u8; 32],
    epoch_end:       u64,
    distinct_zones:  u32,
    total_peers:     u32,
    diversity_score: u32,
    low_diversity:   bool,
) -> [u8; 32] {
    let mut h = Sha256::new();
    h.update(prev);
    h.update(epoch_end.to_be_bytes());
    h.update(distinct_zones.to_be_bytes());
    h.update(total_peers.to_be_bytes());
    h.update(diversity_score.to_be_bytes());
    h.update([low_diversity as u8]);
    h.finalize().into()
}

// ─── GossipPeerDiversityLog ───────────────────────────────────────────────────

pub struct GossipPeerDiversityLog {
    entries: Vec<GossipPeerDiversityEntry>,
}

impl GossipPeerDiversityLog {
    pub fn new() -> Self { Self { entries: Vec::new() } }

    pub fn entry_count(&self) -> usize { self.entries.len() }
    pub fn is_empty(&self)    -> bool  { self.entries.is_empty() }
    pub fn entries(&self)     -> &[GossipPeerDiversityEntry] { &self.entries }
    pub fn latest(&self)      -> Option<&GossipPeerDiversityEntry> { self.entries.last() }

    /// Count of epochs where low_diversity == true.
    pub fn low_diversity_count(&self) -> usize {
        self.entries.iter().filter(|e| e.low_diversity).count()
    }

    /// Maximum diversity_score in any epoch. Returns 0 if empty.
    pub fn max_diversity_score(&self) -> u32 {
        self.entries.iter().map(|e| e.diversity_score).max().unwrap_or(0)
    }

    /// Integer mean of all per-epoch diversity_score values. Returns 0 if empty.
    pub fn mean_diversity_score(&self) -> u32 {
        if self.entries.is_empty() { return 0; }
        let sum: u64 = self.entries.iter().map(|e| e.diversity_score as u64).sum();
        (sum / self.entries.len() as u64) as u32
    }

    /// Record peer diversity for one epoch.
    /// diversity_score = min(distinct_zones * 100 / max(total_peers, 1), 100).
    /// low_diversity = diversity_score < DIVERSITY_FLOOR.
    pub fn record(
        &mut self,
        epoch_end:      u64,
        distinct_zones: u32,
        total_peers:    u32,
    ) -> &GossipPeerDiversityEntry {
        let raw = (distinct_zones as u64 * 100
            / total_peers.max(1) as u64) as u32;
        let diversity_score = raw.min(100);
        let low_diversity = diversity_score < DIVERSITY_FLOOR;

        let prev = self.entries.last()
            .map(|e| e.entry_hash)
            .unwrap_or(GOSSIP_PEER_DIVERSITY_GENESIS_HASH);

        let entry_hash = compute_peer_diversity_hash(
            &prev, epoch_end, distinct_zones, total_peers,
            diversity_score, low_diversity,
        );

        self.entries.push(GossipPeerDiversityEntry {
            epoch_end,
            distinct_zones,
            total_peers,
            diversity_score,
            low_diversity,
            entry_hash,
            prev_hash: prev,
        });
        self.entries.last().unwrap()
    }

    pub fn verify_chain(&self) -> (bool, Option<usize>) {
        let mut prev = GOSSIP_PEER_DIVERSITY_GENESIS_HASH;
        for (i, e) in self.entries.iter().enumerate() {
            if e.prev_hash != prev {
                return (false, Some(i));
            }
            let expected = compute_peer_diversity_hash(
                &prev, e.epoch_end, e.distinct_zones, e.total_peers,
                e.diversity_score, e.low_diversity,
            );
            if e.entry_hash != expected {
                return (false, Some(i));
            }
            prev = e.entry_hash;
        }
        (true, None)
    }
}

impl Default for GossipPeerDiversityLog {
    fn default() -> Self { Self::new() }
}

// ─── Tests ────────────────────────────────────────────────────────────────────

#[cfg(test)]
mod tests {
    use super::*;

    // ── record fields ─────────────────────────────────────────────────────────

    #[test]
    fn record_fields_stored() {
        let mut log = GossipPeerDiversityLog::new();
        // 30 zones, 100 peers → score=30
        let e = log.record(1, 30, 100);
        assert_eq!(e.epoch_end, 1);
        assert_eq!(e.distinct_zones, 30);
        assert_eq!(e.total_peers, 100);
        assert_eq!(e.diversity_score, 30);
    }

    #[test]
    fn zero_peers_stored() {
        let mut log = GossipPeerDiversityLog::new();
        let e = log.record(1, 0, 0);
        assert_eq!(e.diversity_score, 0);
        assert!(e.low_diversity);
    }

    #[test]
    fn score_capped_at_100() {
        let mut log = GossipPeerDiversityLog::new();
        // more zones than peers: raw=200, capped at 100
        let e = log.record(1, 20, 10);
        assert_eq!(e.diversity_score, 100);
    }

    #[test]
    fn score_rounds_down() {
        let mut log = GossipPeerDiversityLog::new();
        // 21*100/101 = 20 (rounds down)
        let e = log.record(1, 21, 101);
        assert_eq!(e.diversity_score, 20);
    }

    // ── low_diversity threshold ───────────────────────────────────────────────

    #[test]
    fn low_diversity_below_floor() {
        let mut log = GossipPeerDiversityLog::new();
        let e = log.record(1, 19, 100);
        assert_eq!(e.diversity_score, 19);
        assert!(e.low_diversity);
    }

    #[test]
    fn diversity_at_floor_not_low() {
        let mut log = GossipPeerDiversityLog::new();
        let e = log.record(1, 20, 100);
        assert_eq!(e.diversity_score, 20);
        assert!(!e.low_diversity);
    }

    #[test]
    fn high_diversity_not_low() {
        let mut log = GossipPeerDiversityLog::new();
        let e = log.record(1, 60, 100);
        assert!(!e.low_diversity);
    }

    // ── aggregate stats ───────────────────────────────────────────────────────

    #[test]
    fn low_diversity_count_correct() {
        let mut log = GossipPeerDiversityLog::new();
        log.record(1, 30, 100); // 30% — ok
        log.record(2, 15, 100); // 15% — low
        log.record(3, 20, 100); // 20% — ok (at floor)
        log.record(4, 10, 100); // 10% — low
        assert_eq!(log.low_diversity_count(), 2);
    }

    #[test]
    fn max_diversity_score_correct() {
        let mut log = GossipPeerDiversityLog::new();
        log.record(1, 30, 100);
        log.record(2, 70, 100);
        log.record(3, 50, 100);
        assert_eq!(log.max_diversity_score(), 70);
    }

    #[test]
    fn max_diversity_score_empty_zero() {
        let log = GossipPeerDiversityLog::new();
        assert_eq!(log.max_diversity_score(), 0);
    }

    #[test]
    fn mean_diversity_score_correct() {
        let mut log = GossipPeerDiversityLog::new();
        log.record(1, 30, 100); // 30
        log.record(2, 50, 100); // 50
        log.record(3, 40, 100); // 40
        // (30+50+40)/3 = 40
        assert_eq!(log.mean_diversity_score(), 40);
    }

    #[test]
    fn mean_diversity_empty_zero() {
        let log = GossipPeerDiversityLog::new();
        assert_eq!(log.mean_diversity_score(), 0);
    }

    // ── hash chain ────────────────────────────────────────────────────────────

    #[test]
    fn entry_hash_nonzero() {
        let mut log = GossipPeerDiversityLog::new();
        let e = log.record(1, 30, 100);
        assert_ne!(e.entry_hash, [0u8; 32]);
    }

    #[test]
    fn first_entry_prev_hash_is_genesis() {
        let mut log = GossipPeerDiversityLog::new();
        let e = log.record(1, 30, 100);
        assert_eq!(e.prev_hash, GOSSIP_PEER_DIVERSITY_GENESIS_HASH);
    }

    #[test]
    fn chain_prev_links() {
        let mut log = GossipPeerDiversityLog::new();
        log.record(1, 30, 100);
        let h0 = log.entries()[0].entry_hash;
        log.record(2, 40, 100);
        assert_eq!(log.entries()[1].prev_hash, h0);
    }

    // ── verify_chain ──────────────────────────────────────────────────────────

    #[test]
    fn verify_chain_empty_ok() {
        let log = GossipPeerDiversityLog::new();
        let (ok, idx) = log.verify_chain();
        assert!(ok);
        assert!(idx.is_none());
    }

    #[test]
    fn verify_chain_multiple_ok() {
        let mut log = GossipPeerDiversityLog::new();
        for i in 1u64..=5 { log.record(i, i as u32 * 10, 100); }
        let (ok, idx) = log.verify_chain();
        assert!(ok);
        assert!(idx.is_none());
    }

    #[test]
    fn verify_chain_detects_tamper() {
        let mut log = GossipPeerDiversityLog::new();
        log.record(1, 30, 100);
        log.record(2, 40, 100);
        log.entries[0].entry_hash[0] ^= 0xFF;
        let (ok, idx) = log.verify_chain();
        assert!(!ok);
        assert_eq!(idx, Some(0));
    }

    // ── determinism ───────────────────────────────────────────────────────────

    #[test]
    fn entry_hash_deterministic() {
        let mut l1 = GossipPeerDiversityLog::new();
        let mut l2 = GossipPeerDiversityLog::new();
        let h1 = l1.record(5, 45, 100).entry_hash;
        let h2 = l2.record(5, 45, 100).entry_hash;
        assert_eq!(h1, h2);
    }
}
