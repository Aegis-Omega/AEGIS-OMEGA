//! Gate 394 — Gossip Epoch Health Verdict (T2)
//! EPISTEMIC TIER: T2 (engineering hypothesis)
//!
//! Synthesises per-epoch gossip pipeline signals into a single health verdict:
//! Healthy / Degraded / Critical.
//!
//! Inputs per epoch:
//!   delivery_ratio_pct: u32  — from Gate 392 (GossipDeliveryRatioLog)
//!   drop_pct:           u32  — from Gate 385 (GossipDropRateLog)
//!   churn_count:        u32  — from Gate 393 (GossipPeerChurnLog)
//!   under_pressure:     bool — from Gate 388 (GossipBackpressureLog)
//!
//! Classification rules (evaluated in order, first match wins):
//!   Critical:  delivery_ratio_pct < 50 OR drop_pct > 50 OR churn_count > 20
//!   Degraded:  delivery_ratio_pct < 80 OR drop_pct > 10 OR under_pressure OR churn_count > 5
//!   Healthy:   otherwise
//!
//! GossipEpochHealthEntry (hash-chained):
//!   epoch_end:          u64
//!   delivery_ratio_pct: u32
//!   drop_pct:           u32
//!   churn_count:        u32
//!   under_pressure:     bool
//!   verdict:            EpochHealthVerdict
//!   entry_hash:         [u8;32]
//!   prev_hash:          [u8;32]
//!
//! entry_hash = SHA-256(prev[32] ‖ epoch_end_be8 ‖ delivery_ratio_pct_be4
//!                       ‖ drop_pct_be4 ‖ churn_count_be4
//!                       ‖ under_pressure_byte ‖ verdict_byte)
//!
//! GossipEpochHealthLog: record(...), healthy_count(), degraded_count(),
//!   critical_count(), verify_chain().

use sha2::{Sha256, Digest};

pub const GOSSIP_EPOCH_HEALTH_GENESIS_HASH: [u8; 32] = [0u8; 32];

// ─── EpochHealthVerdict ───────────────────────────────────────────────────────

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
#[repr(u8)]
pub enum EpochHealthVerdict {
    Healthy  = 0,
    Degraded = 1,
    Critical = 2,
}

impl EpochHealthVerdict {
    fn as_u8(self) -> u8 { self as u8 }

    fn classify(
        delivery_ratio_pct: u32,
        drop_pct:           u32,
        churn_count:        u32,
        under_pressure:     bool,
    ) -> Self {
        if delivery_ratio_pct < 50 || drop_pct > 50 || churn_count > 20 {
            EpochHealthVerdict::Critical
        } else if delivery_ratio_pct < 80 || drop_pct > 10 || under_pressure || churn_count > 5 {
            EpochHealthVerdict::Degraded
        } else {
            EpochHealthVerdict::Healthy
        }
    }
}

// ─── GossipEpochHealthEntry ───────────────────────────────────────────────────

#[derive(Debug, Clone, PartialEq)]
pub struct GossipEpochHealthEntry {
    pub epoch_end:          u64,
    pub delivery_ratio_pct: u32,
    pub drop_pct:           u32,
    pub churn_count:        u32,
    pub under_pressure:     bool,
    pub verdict:            EpochHealthVerdict,
    pub entry_hash:         [u8; 32],
    pub prev_hash:          [u8; 32],
}

fn compute_epoch_health_hash(
    prev:               &[u8; 32],
    epoch_end:          u64,
    delivery_ratio_pct: u32,
    drop_pct:           u32,
    churn_count:        u32,
    under_pressure:     bool,
    verdict:            EpochHealthVerdict,
) -> [u8; 32] {
    let mut h = Sha256::new();
    h.update(prev);
    h.update(epoch_end.to_be_bytes());
    h.update(delivery_ratio_pct.to_be_bytes());
    h.update(drop_pct.to_be_bytes());
    h.update(churn_count.to_be_bytes());
    h.update([under_pressure as u8]);
    h.update([verdict.as_u8()]);
    h.finalize().into()
}

// ─── GossipEpochHealthLog ─────────────────────────────────────────────────────

pub struct GossipEpochHealthLog {
    entries: Vec<GossipEpochHealthEntry>,
}

impl GossipEpochHealthLog {
    pub fn new() -> Self { Self { entries: Vec::new() } }

    pub fn entry_count(&self) -> usize { self.entries.len() }
    pub fn is_empty(&self)    -> bool  { self.entries.is_empty() }
    pub fn entries(&self)     -> &[GossipEpochHealthEntry] { &self.entries }
    pub fn latest(&self)      -> Option<&GossipEpochHealthEntry> { self.entries.last() }

    /// Count of epochs with Healthy verdict.
    pub fn healthy_count(&self) -> usize {
        self.entries.iter().filter(|e| e.verdict == EpochHealthVerdict::Healthy).count()
    }

    /// Count of epochs with Degraded verdict.
    pub fn degraded_count(&self) -> usize {
        self.entries.iter().filter(|e| e.verdict == EpochHealthVerdict::Degraded).count()
    }

    /// Count of epochs with Critical verdict.
    pub fn critical_count(&self) -> usize {
        self.entries.iter().filter(|e| e.verdict == EpochHealthVerdict::Critical).count()
    }

    /// Record epoch health verdict.
    pub fn record(
        &mut self,
        epoch_end:          u64,
        delivery_ratio_pct: u32,
        drop_pct:           u32,
        churn_count:        u32,
        under_pressure:     bool,
    ) -> &GossipEpochHealthEntry {
        let verdict = EpochHealthVerdict::classify(
            delivery_ratio_pct, drop_pct, churn_count, under_pressure,
        );

        let prev = self.entries.last()
            .map(|e| e.entry_hash)
            .unwrap_or(GOSSIP_EPOCH_HEALTH_GENESIS_HASH);

        let entry_hash = compute_epoch_health_hash(
            &prev, epoch_end, delivery_ratio_pct, drop_pct,
            churn_count, under_pressure, verdict,
        );

        self.entries.push(GossipEpochHealthEntry {
            epoch_end,
            delivery_ratio_pct,
            drop_pct,
            churn_count,
            under_pressure,
            verdict,
            entry_hash,
            prev_hash: prev,
        });
        self.entries.last().unwrap()
    }

    pub fn verify_chain(&self) -> (bool, Option<usize>) {
        let mut prev = GOSSIP_EPOCH_HEALTH_GENESIS_HASH;
        for (i, e) in self.entries.iter().enumerate() {
            if e.prev_hash != prev {
                return (false, Some(i));
            }
            let expected = compute_epoch_health_hash(
                &prev, e.epoch_end, e.delivery_ratio_pct, e.drop_pct,
                e.churn_count, e.under_pressure, e.verdict,
            );
            if e.entry_hash != expected {
                return (false, Some(i));
            }
            prev = e.entry_hash;
        }
        (true, None)
    }
}

impl Default for GossipEpochHealthLog {
    fn default() -> Self { Self::new() }
}

// ─── Tests ────────────────────────────────────────────────────────────────────

#[cfg(test)]
mod tests {
    use super::*;

    // ── verdict classification ────────────────────────────────────────────────

    #[test]
    fn healthy_verdict_all_good() {
        let mut log = GossipEpochHealthLog::new();
        let e = log.record(1, 90, 5, 3, false);
        assert_eq!(e.verdict, EpochHealthVerdict::Healthy);
    }

    #[test]
    fn degraded_low_delivery_ratio() {
        let mut log = GossipEpochHealthLog::new();
        // delivery_ratio_pct < 80 → Degraded
        let e = log.record(1, 70, 5, 3, false);
        assert_eq!(e.verdict, EpochHealthVerdict::Degraded);
    }

    #[test]
    fn degraded_under_pressure() {
        let mut log = GossipEpochHealthLog::new();
        let e = log.record(1, 90, 5, 3, true);
        assert_eq!(e.verdict, EpochHealthVerdict::Degraded);
    }

    #[test]
    fn degraded_high_drop_pct() {
        let mut log = GossipEpochHealthLog::new();
        // drop_pct > 10 → Degraded
        let e = log.record(1, 90, 15, 3, false);
        assert_eq!(e.verdict, EpochHealthVerdict::Degraded);
    }

    #[test]
    fn degraded_high_churn() {
        let mut log = GossipEpochHealthLog::new();
        // churn_count > 5 → Degraded
        let e = log.record(1, 90, 5, 8, false);
        assert_eq!(e.verdict, EpochHealthVerdict::Degraded);
    }

    #[test]
    fn critical_very_low_delivery() {
        let mut log = GossipEpochHealthLog::new();
        // delivery_ratio_pct < 50 → Critical
        let e = log.record(1, 40, 5, 3, false);
        assert_eq!(e.verdict, EpochHealthVerdict::Critical);
    }

    #[test]
    fn critical_very_high_drop() {
        let mut log = GossipEpochHealthLog::new();
        // drop_pct > 50 → Critical
        let e = log.record(1, 90, 60, 3, false);
        assert_eq!(e.verdict, EpochHealthVerdict::Critical);
    }

    #[test]
    fn critical_very_high_churn() {
        let mut log = GossipEpochHealthLog::new();
        // churn_count > 20 → Critical
        let e = log.record(1, 90, 5, 25, false);
        assert_eq!(e.verdict, EpochHealthVerdict::Critical);
    }

    #[test]
    fn critical_beats_degraded_signals() {
        let mut log = GossipEpochHealthLog::new();
        // Both degraded (under_pressure) and critical (churn=25) signals — Critical wins
        let e = log.record(1, 90, 5, 25, true);
        assert_eq!(e.verdict, EpochHealthVerdict::Critical);
    }

    // ── counts ────────────────────────────────────────────────────────────────

    #[test]
    fn counts_correct() {
        let mut log = GossipEpochHealthLog::new();
        log.record(1, 90, 5, 3, false);   // Healthy
        log.record(2, 70, 5, 3, false);   // Degraded (delivery<80)
        log.record(3, 40, 5, 3, false);   // Critical (delivery<50)
        log.record(4, 85, 12, 3, false);  // Degraded (drop>10)
        assert_eq!(log.healthy_count(), 1);
        assert_eq!(log.degraded_count(), 2);
        assert_eq!(log.critical_count(), 1);
    }

    // ── hash chain ────────────────────────────────────────────────────────────

    #[test]
    fn entry_hash_nonzero() {
        let mut log = GossipEpochHealthLog::new();
        let e = log.record(1, 90, 5, 3, false);
        assert_ne!(e.entry_hash, [0u8; 32]);
    }

    #[test]
    fn first_entry_prev_hash_is_genesis() {
        let mut log = GossipEpochHealthLog::new();
        let e = log.record(1, 90, 5, 3, false);
        assert_eq!(e.prev_hash, GOSSIP_EPOCH_HEALTH_GENESIS_HASH);
    }

    #[test]
    fn chain_prev_links() {
        let mut log = GossipEpochHealthLog::new();
        log.record(1, 90, 5, 3, false);
        let h0 = log.entries()[0].entry_hash;
        log.record(2, 70, 5, 3, true);
        assert_eq!(log.entries()[1].prev_hash, h0);
    }

    // ── verify_chain ──────────────────────────────────────────────────────────

    #[test]
    fn verify_chain_empty_ok() {
        let log = GossipEpochHealthLog::new();
        let (ok, idx) = log.verify_chain();
        assert!(ok);
        assert!(idx.is_none());
    }

    #[test]
    fn verify_chain_multiple_ok() {
        let mut log = GossipEpochHealthLog::new();
        for i in 1u64..=5 { log.record(i, 90, 5, 3, i % 2 == 0); }
        let (ok, idx) = log.verify_chain();
        assert!(ok);
        assert!(idx.is_none());
    }

    #[test]
    fn verify_chain_detects_tamper() {
        let mut log = GossipEpochHealthLog::new();
        log.record(1, 90, 5, 3, false);
        log.record(2, 70, 5, 3, true);
        log.entries[0].entry_hash[0] ^= 0xFF;
        let (ok, idx) = log.verify_chain();
        assert!(!ok);
        assert_eq!(idx, Some(0));
    }

    // ── determinism ───────────────────────────────────────────────────────────

    #[test]
    fn entry_hash_deterministic() {
        let mut l1 = GossipEpochHealthLog::new();
        let mut l2 = GossipEpochHealthLog::new();
        let h1 = l1.record(5, 80, 8, 4, true).entry_hash;
        let h2 = l2.record(5, 80, 8, 4, true).entry_hash;
        assert_eq!(h1, h2);
    }
}
