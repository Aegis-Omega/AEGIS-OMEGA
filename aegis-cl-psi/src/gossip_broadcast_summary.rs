//! Gate 377 — Gossip Broadcast Summary (T2)
//! EPISTEMIC TIER: T2 (engineering hypothesis)
//!
//! Produces a per-epoch GossipBroadcastSummary by combining dispatch
//! statistics from GossipPeerDispatcher with validation outcome counts
//! from GossipBroadcastValidator into a single hash-chained summary.
//!
//! GossipBroadcastSummary (hash-chained):
//!   epoch_end:         u64
//!   dispatched:        u32   — frames dispatched this epoch
//!   delivered:         u32   — total peer-deliveries this epoch
//!   valid_count:       u32   — Valid verdicts recorded
//!   checksum_fail:     u32   — ChecksumFail verdicts recorded
//!   epoch_regressed:   u32   — EpochRegressed verdicts recorded
//!   checksum_and_epoch:u32   — ChecksumAndEpoch verdicts recorded
//!   summary_hash:      [u8;32]
//!   prev_hash:         [u8;32]
//!
//! summary_hash = SHA-256(prev[32] ‖ epoch_end_be8 ‖ dispatched_be4
//!                          ‖ delivered_be4 ‖ valid_be4 ‖ checksum_fail_be4
//!                          ‖ epoch_regressed_be4 ‖ checksum_and_epoch_be4)
//!
//! GossipBroadcastSummaryLog: record(epoch_end, dispatched, delivered,
//!   valid, checksum_fail, epoch_regressed, checksum_and_epoch),
//!   latest(), summary_count(), verify_chain().

use sha2::{Sha256, Digest};

pub const GOSSIP_SUMMARY_GENESIS_HASH: [u8; 32] = [0u8; 32];

// ─── GossipBroadcastSummary ───────────────────────────────────────────────────

#[derive(Debug, Clone, PartialEq)]
pub struct GossipBroadcastSummary {
    pub epoch_end:          u64,
    pub dispatched:         u32,
    pub delivered:          u32,
    pub valid_count:        u32,
    pub checksum_fail:      u32,
    pub epoch_regressed:    u32,
    pub checksum_and_epoch: u32,
    pub summary_hash:       [u8; 32],
    pub prev_hash:          [u8; 32],
}

fn compute_summary_hash(
    prev:               &[u8; 32],
    epoch_end:          u64,
    dispatched:         u32,
    delivered:          u32,
    valid_count:        u32,
    checksum_fail:      u32,
    epoch_regressed:    u32,
    checksum_and_epoch: u32,
) -> [u8; 32] {
    let mut h = Sha256::new();
    h.update(prev);
    h.update(epoch_end.to_be_bytes());
    h.update(dispatched.to_be_bytes());
    h.update(delivered.to_be_bytes());
    h.update(valid_count.to_be_bytes());
    h.update(checksum_fail.to_be_bytes());
    h.update(epoch_regressed.to_be_bytes());
    h.update(checksum_and_epoch.to_be_bytes());
    h.finalize().into()
}

// ─── GossipBroadcastSummaryLog ────────────────────────────────────────────────

pub struct GossipBroadcastSummaryLog {
    summaries: Vec<GossipBroadcastSummary>,
}

impl GossipBroadcastSummaryLog {
    pub fn new() -> Self { Self { summaries: Vec::new() } }

    pub fn summary_count(&self) -> usize { self.summaries.len() }
    pub fn is_empty(&self)      -> bool  { self.summaries.is_empty() }
    pub fn summaries(&self)     -> &[GossipBroadcastSummary] { &self.summaries }
    pub fn latest(&self)        -> Option<&GossipBroadcastSummary> { self.summaries.last() }

    /// Record a summary for one epoch.
    pub fn record(
        &mut self,
        epoch_end:          u64,
        dispatched:         u32,
        delivered:          u32,
        valid_count:        u32,
        checksum_fail:      u32,
        epoch_regressed:    u32,
        checksum_and_epoch: u32,
    ) -> &GossipBroadcastSummary {
        let prev = self.summaries.last()
            .map(|s| s.summary_hash)
            .unwrap_or(GOSSIP_SUMMARY_GENESIS_HASH);

        let summary_hash = compute_summary_hash(
            &prev, epoch_end, dispatched, delivered,
            valid_count, checksum_fail, epoch_regressed, checksum_and_epoch,
        );

        self.summaries.push(GossipBroadcastSummary {
            epoch_end,
            dispatched,
            delivered,
            valid_count,
            checksum_fail,
            epoch_regressed,
            checksum_and_epoch,
            summary_hash,
            prev_hash: prev,
        });
        self.summaries.last().unwrap()
    }

    /// Total valid verdicts across all summaries.
    pub fn total_valid(&self) -> u64 {
        self.summaries.iter().map(|s| s.valid_count as u64).sum()
    }

    /// Total failed verdicts (all non-Valid) across all summaries.
    pub fn total_failed(&self) -> u64 {
        self.summaries.iter().map(|s| {
            (s.checksum_fail + s.epoch_regressed + s.checksum_and_epoch) as u64
        }).sum()
    }

    pub fn verify_chain(&self) -> (bool, Option<usize>) {
        let mut prev = GOSSIP_SUMMARY_GENESIS_HASH;
        for (i, s) in self.summaries.iter().enumerate() {
            if s.prev_hash != prev {
                return (false, Some(i));
            }
            let expected = compute_summary_hash(
                &prev,
                s.epoch_end,
                s.dispatched,
                s.delivered,
                s.valid_count,
                s.checksum_fail,
                s.epoch_regressed,
                s.checksum_and_epoch,
            );
            if s.summary_hash != expected {
                return (false, Some(i));
            }
            prev = s.summary_hash;
        }
        (true, None)
    }
}

impl Default for GossipBroadcastSummaryLog {
    fn default() -> Self { Self::new() }
}

// ─── Tests ────────────────────────────────────────────────────────────────────

#[cfg(test)]
mod tests {
    use super::*;

    // ── record ────────────────────────────────────────────────────────────────

    #[test]
    fn record_single_summary() {
        let mut log = GossipBroadcastSummaryLog::new();
        let s = log.record(5, 10, 30, 8, 1, 1, 0);
        assert_eq!(s.epoch_end, 5);
        assert_eq!(s.dispatched, 10);
        assert_eq!(s.delivered, 30);
        assert_eq!(s.valid_count, 8);
        assert_eq!(s.checksum_fail, 1);
        assert_eq!(s.epoch_regressed, 1);
        assert_eq!(s.checksum_and_epoch, 0);
    }

    #[test]
    fn summary_hash_nonzero() {
        let mut log = GossipBroadcastSummaryLog::new();
        let s = log.record(1, 5, 10, 3, 1, 1, 0);
        assert_ne!(s.summary_hash, [0u8; 32]);
    }

    #[test]
    fn first_summary_prev_hash_is_genesis() {
        let mut log = GossipBroadcastSummaryLog::new();
        let s = log.record(1, 1, 3, 1, 0, 0, 0);
        assert_eq!(s.prev_hash, GOSSIP_SUMMARY_GENESIS_HASH);
    }

    #[test]
    fn second_summary_prev_links_to_first() {
        let mut log = GossipBroadcastSummaryLog::new();
        log.record(1, 2, 4, 2, 0, 0, 0);
        let h0 = log.summaries()[0].summary_hash;
        log.record(2, 3, 6, 3, 0, 0, 0);
        assert_eq!(log.summaries()[1].prev_hash, h0);
    }

    #[test]
    fn summary_count_increments() {
        let mut log = GossipBroadcastSummaryLog::new();
        assert_eq!(log.summary_count(), 0);
        log.record(1, 1, 3, 1, 0, 0, 0);
        log.record(2, 1, 3, 1, 0, 0, 0);
        assert_eq!(log.summary_count(), 2);
    }

    // ── aggregate stats ───────────────────────────────────────────────────────

    #[test]
    fn total_valid_accumulates() {
        let mut log = GossipBroadcastSummaryLog::new();
        log.record(1, 5, 15, 4, 1, 0, 0);
        log.record(2, 5, 15, 5, 0, 0, 0);
        assert_eq!(log.total_valid(), 9);
    }

    #[test]
    fn total_failed_sums_all_failure_types() {
        let mut log = GossipBroadcastSummaryLog::new();
        log.record(1, 10, 30, 5, 2, 2, 1);
        assert_eq!(log.total_failed(), 5); // 2+2+1
    }

    #[test]
    fn total_failed_zero_when_all_valid() {
        let mut log = GossipBroadcastSummaryLog::new();
        log.record(1, 5, 15, 5, 0, 0, 0);
        assert_eq!(log.total_failed(), 0);
    }

    #[test]
    fn latest_returns_most_recent() {
        let mut log = GossipBroadcastSummaryLog::new();
        log.record(1, 1, 3, 1, 0, 0, 0);
        log.record(2, 2, 6, 2, 0, 0, 0);
        assert_eq!(log.latest().unwrap().epoch_end, 2);
    }

    // ── verify_chain ──────────────────────────────────────────────────────────

    #[test]
    fn verify_chain_empty_ok() {
        let log = GossipBroadcastSummaryLog::new();
        let (ok, idx) = log.verify_chain();
        assert!(ok);
        assert!(idx.is_none());
    }

    #[test]
    fn verify_chain_multiple_summaries_ok() {
        let mut log = GossipBroadcastSummaryLog::new();
        for i in 1u64..=4 { log.record(i, i as u32, i as u32 * 3, i as u32, 0, 0, 0); }
        let (ok, idx) = log.verify_chain();
        assert!(ok);
        assert!(idx.is_none());
    }

    #[test]
    fn verify_chain_detects_tamper() {
        let mut log = GossipBroadcastSummaryLog::new();
        log.record(1, 1, 3, 1, 0, 0, 0);
        log.record(2, 2, 6, 2, 0, 0, 0);
        log.summaries[0].summary_hash[0] ^= 0xFF;
        let (ok, idx) = log.verify_chain();
        assert!(!ok);
        assert_eq!(idx, Some(0));
    }

    // ── determinism ───────────────────────────────────────────────────────────

    #[test]
    fn summary_hash_deterministic() {
        let mut l1 = GossipBroadcastSummaryLog::new();
        let mut l2 = GossipBroadcastSummaryLog::new();
        let h1 = l1.record(7, 5, 15, 4, 0, 1, 0).summary_hash;
        let h2 = l2.record(7, 5, 15, 4, 0, 1, 0).summary_hash;
        assert_eq!(h1, h2);
    }
}
