//! Gate 395 — Gossip Pipeline Summary Seal (T2)
//! EPISTEMIC TIER: T2 (engineering hypothesis)
//!
//! Per-epoch summary that seals all gossip pipeline signals from Gates 390–394
//! into a single hash-chained record:
//!   retransmit_count:   u32  — from Gate 390 (GossipRetransmitLog)
//!   mean_ack_latency:   u64  — from Gate 391 (GossipAckLatencyLog)
//!   delivery_ratio_pct: u32  — from Gate 392 (GossipDeliveryRatioLog)
//!   churn_count:        u32  — from Gate 393 (GossipPeerChurnLog)
//!   health_verdict:     EpochHealthVerdict — from Gate 394 (GossipEpochHealthLog)
//!
//! GossipPipelineSummaryEntry (hash-chained):
//!   epoch_end:          u64
//!   retransmit_count:   u32
//!   mean_ack_latency:   u64
//!   delivery_ratio_pct: u32
//!   churn_count:        u32
//!   health_verdict:     EpochHealthVerdict
//!   entry_hash:         [u8;32]
//!   prev_hash:          [u8;32]
//!
//! entry_hash = SHA-256(prev[32] ‖ epoch_end_be8 ‖ retransmit_count_be4
//!                       ‖ mean_ack_latency_be8 ‖ delivery_ratio_pct_be4
//!                       ‖ churn_count_be4 ‖ verdict_byte)
//!
//! GossipPipelineSummaryLog: record(...), healthy_epochs(), degraded_epochs(),
//!   critical_epochs(), verify_chain().

use sha2::{Sha256, Digest};
use crate::gossip_epoch_health::EpochHealthVerdict;

pub const GOSSIP_PIPELINE_SUMMARY_GENESIS_HASH: [u8; 32] = [0u8; 32];

// ─── GossipPipelineSummaryEntry ───────────────────────────────────────────────

#[derive(Debug, Clone, PartialEq)]
pub struct GossipPipelineSummaryEntry {
    pub epoch_end:          u64,
    pub retransmit_count:   u32,
    pub mean_ack_latency:   u64,
    pub delivery_ratio_pct: u32,
    pub churn_count:        u32,
    pub health_verdict:     EpochHealthVerdict,
    pub entry_hash:         [u8; 32],
    pub prev_hash:          [u8; 32],
}

fn compute_pipeline_summary_hash(
    prev:               &[u8; 32],
    epoch_end:          u64,
    retransmit_count:   u32,
    mean_ack_latency:   u64,
    delivery_ratio_pct: u32,
    churn_count:        u32,
    health_verdict:     EpochHealthVerdict,
) -> [u8; 32] {
    let mut h = Sha256::new();
    h.update(prev);
    h.update(epoch_end.to_be_bytes());
    h.update(retransmit_count.to_be_bytes());
    h.update(mean_ack_latency.to_be_bytes());
    h.update(delivery_ratio_pct.to_be_bytes());
    h.update(churn_count.to_be_bytes());
    h.update([health_verdict as u8]);
    h.finalize().into()
}

// ─── GossipPipelineSummaryLog ─────────────────────────────────────────────────

pub struct GossipPipelineSummaryLog {
    entries: Vec<GossipPipelineSummaryEntry>,
}

impl GossipPipelineSummaryLog {
    pub fn new() -> Self { Self { entries: Vec::new() } }

    pub fn entry_count(&self) -> usize { self.entries.len() }
    pub fn is_empty(&self)    -> bool  { self.entries.is_empty() }
    pub fn entries(&self)     -> &[GossipPipelineSummaryEntry] { &self.entries }
    pub fn latest(&self)      -> Option<&GossipPipelineSummaryEntry> { self.entries.last() }

    /// Count of epochs with Healthy verdict.
    pub fn healthy_epochs(&self) -> usize {
        self.entries.iter().filter(|e| e.health_verdict == EpochHealthVerdict::Healthy).count()
    }

    /// Count of epochs with Degraded verdict.
    pub fn degraded_epochs(&self) -> usize {
        self.entries.iter().filter(|e| e.health_verdict == EpochHealthVerdict::Degraded).count()
    }

    /// Count of epochs with Critical verdict.
    pub fn critical_epochs(&self) -> usize {
        self.entries.iter().filter(|e| e.health_verdict == EpochHealthVerdict::Critical).count()
    }

    /// Record a pipeline summary for one epoch.
    pub fn record(
        &mut self,
        epoch_end:          u64,
        retransmit_count:   u32,
        mean_ack_latency:   u64,
        delivery_ratio_pct: u32,
        churn_count:        u32,
        health_verdict:     EpochHealthVerdict,
    ) -> &GossipPipelineSummaryEntry {
        let prev = self.entries.last()
            .map(|e| e.entry_hash)
            .unwrap_or(GOSSIP_PIPELINE_SUMMARY_GENESIS_HASH);

        let entry_hash = compute_pipeline_summary_hash(
            &prev, epoch_end, retransmit_count, mean_ack_latency,
            delivery_ratio_pct, churn_count, health_verdict,
        );

        self.entries.push(GossipPipelineSummaryEntry {
            epoch_end,
            retransmit_count,
            mean_ack_latency,
            delivery_ratio_pct,
            churn_count,
            health_verdict,
            entry_hash,
            prev_hash: prev,
        });
        self.entries.last().unwrap()
    }

    pub fn verify_chain(&self) -> (bool, Option<usize>) {
        let mut prev = GOSSIP_PIPELINE_SUMMARY_GENESIS_HASH;
        for (i, e) in self.entries.iter().enumerate() {
            if e.prev_hash != prev {
                return (false, Some(i));
            }
            let expected = compute_pipeline_summary_hash(
                &prev, e.epoch_end, e.retransmit_count, e.mean_ack_latency,
                e.delivery_ratio_pct, e.churn_count, e.health_verdict,
            );
            if e.entry_hash != expected {
                return (false, Some(i));
            }
            prev = e.entry_hash;
        }
        (true, None)
    }
}

impl Default for GossipPipelineSummaryLog {
    fn default() -> Self { Self::new() }
}

// ─── Tests ────────────────────────────────────────────────────────────────────

#[cfg(test)]
mod tests {
    use super::*;

    // ── record fields ─────────────────────────────────────────────────────────

    #[test]
    fn record_fields_stored() {
        let mut log = GossipPipelineSummaryLog::new();
        let e = log.record(1, 3, 2, 90, 4, EpochHealthVerdict::Healthy);
        assert_eq!(e.epoch_end, 1);
        assert_eq!(e.retransmit_count, 3);
        assert_eq!(e.mean_ack_latency, 2);
        assert_eq!(e.delivery_ratio_pct, 90);
        assert_eq!(e.churn_count, 4);
        assert_eq!(e.health_verdict, EpochHealthVerdict::Healthy);
    }

    #[test]
    fn degraded_verdict_stored() {
        let mut log = GossipPipelineSummaryLog::new();
        let e = log.record(2, 5, 4, 70, 6, EpochHealthVerdict::Degraded);
        assert_eq!(e.health_verdict, EpochHealthVerdict::Degraded);
    }

    #[test]
    fn critical_verdict_stored() {
        let mut log = GossipPipelineSummaryLog::new();
        let e = log.record(3, 10, 8, 40, 25, EpochHealthVerdict::Critical);
        assert_eq!(e.health_verdict, EpochHealthVerdict::Critical);
    }

    // ── epoch counts ──────────────────────────────────────────────────────────

    #[test]
    fn epoch_counts_correct() {
        let mut log = GossipPipelineSummaryLog::new();
        log.record(1, 2, 1, 90, 3, EpochHealthVerdict::Healthy);
        log.record(2, 4, 3, 70, 4, EpochHealthVerdict::Degraded);
        log.record(3, 8, 5, 40, 25, EpochHealthVerdict::Critical);
        log.record(4, 1, 1, 85, 2, EpochHealthVerdict::Healthy);
        assert_eq!(log.healthy_epochs(), 2);
        assert_eq!(log.degraded_epochs(), 1);
        assert_eq!(log.critical_epochs(), 1);
    }

    #[test]
    fn empty_counts_zero() {
        let log = GossipPipelineSummaryLog::new();
        assert_eq!(log.healthy_epochs(), 0);
        assert_eq!(log.degraded_epochs(), 0);
        assert_eq!(log.critical_epochs(), 0);
    }

    // ── hash chain ────────────────────────────────────────────────────────────

    #[test]
    fn entry_hash_nonzero() {
        let mut log = GossipPipelineSummaryLog::new();
        let e = log.record(1, 3, 2, 90, 4, EpochHealthVerdict::Healthy);
        assert_ne!(e.entry_hash, [0u8; 32]);
    }

    #[test]
    fn first_entry_prev_hash_is_genesis() {
        let mut log = GossipPipelineSummaryLog::new();
        let e = log.record(1, 3, 2, 90, 4, EpochHealthVerdict::Healthy);
        assert_eq!(e.prev_hash, GOSSIP_PIPELINE_SUMMARY_GENESIS_HASH);
    }

    #[test]
    fn chain_prev_links() {
        let mut log = GossipPipelineSummaryLog::new();
        log.record(1, 3, 2, 90, 4, EpochHealthVerdict::Healthy);
        let h0 = log.entries()[0].entry_hash;
        log.record(2, 5, 4, 70, 6, EpochHealthVerdict::Degraded);
        assert_eq!(log.entries()[1].prev_hash, h0);
    }

    // ── verify_chain ──────────────────────────────────────────────────────────

    #[test]
    fn verify_chain_empty_ok() {
        let log = GossipPipelineSummaryLog::new();
        let (ok, idx) = log.verify_chain();
        assert!(ok);
        assert!(idx.is_none());
    }

    #[test]
    fn verify_chain_multiple_ok() {
        let mut log = GossipPipelineSummaryLog::new();
        for i in 1u64..=5 {
            log.record(i, i as u32, i * 2, 80, i as u32, EpochHealthVerdict::Healthy);
        }
        let (ok, idx) = log.verify_chain();
        assert!(ok);
        assert!(idx.is_none());
    }

    #[test]
    fn verify_chain_detects_tamper() {
        let mut log = GossipPipelineSummaryLog::new();
        log.record(1, 3, 2, 90, 4, EpochHealthVerdict::Healthy);
        log.record(2, 5, 4, 70, 6, EpochHealthVerdict::Degraded);
        log.entries[0].entry_hash[0] ^= 0xFF;
        let (ok, idx) = log.verify_chain();
        assert!(!ok);
        assert_eq!(idx, Some(0));
    }

    // ── determinism ───────────────────────────────────────────────────────────

    #[test]
    fn entry_hash_deterministic() {
        let mut l1 = GossipPipelineSummaryLog::new();
        let mut l2 = GossipPipelineSummaryLog::new();
        let h1 = l1.record(5, 3, 7, 80, 4, EpochHealthVerdict::Degraded).entry_hash;
        let h2 = l2.record(5, 3, 7, 80, 4, EpochHealthVerdict::Degraded).entry_hash;
        assert_eq!(h1, h2);
    }
}
