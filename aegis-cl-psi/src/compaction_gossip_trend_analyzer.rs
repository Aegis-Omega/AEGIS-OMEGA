//! Gate 368 — Compaction Gossip Trend Analyzer (T2)
//! EPISTEMIC TIER: T2 (engineering hypothesis)
//!
//! Classifies multi-epoch gossip trends from a rolling window of
//! GossipEpochDeltaRecords (Gate 367). Mirrors Gate 346 for the gossip subsystem.
//!
//! GOSSIP_TREND_WINDOW: usize = 4  — number of recent deltas considered
//!
//! GossipTrendClass:
//!   Improving  — improvement_count ≥ 3 out of last GOSSIP_TREND_WINDOW deltas
//!                (and degradation_count == 0)
//!   Degrading  — degradation_count ≥ 3 out of last GOSSIP_TREND_WINDOW deltas
//!                (and improvement_count == 0)
//!   Volatile   — both improvement_count ≥ 1 AND degradation_count ≥ 1
//!   Stable     — otherwise (no significant net movement)
//!
//! GossipTrendRecord:
//!   epoch:               u64
//!   trend_class:         GossipTrendClass
//!   window_size:         usize        — actual window used (≤ GOSSIP_TREND_WINDOW)
//!   improvement_count:   u32          — improved/recovered deltas in window
//!   degradation_count:   u32          — worsened/degraded deltas in window
//!   net_delivered_delta: i64          — sum of delivered_delta across window
//!   trend_hash:          [u8;32]
//!   prev_hash:           [u8;32]
//!
//! trend_hash = SHA-256(prev[32] ‖ epoch_be8 ‖ trend_byte ‖ window_size_be2
//!                        ‖ improvement_be4 ‖ degradation_be4 ‖ net_delivered_delta_be8)
//!
//! GossipTrendAnalyzerLog: append(delta), improving_trend_count(), degrading_trend_count(),
//!   volatile_trend_count(), stable_trend_count(), verify_chain().

use sha2::{Sha256, Digest};
use crate::compaction_gossip_epoch_comparator::GossipEpochDeltaRecord;

pub const GOSSIP_TREND_GENESIS_HASH: [u8; 32] = [0u8; 32];
pub const GOSSIP_TREND_WINDOW: usize = 4;

// ─── GossipTrendClass ─────────────────────────────────────────────────────────

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
#[repr(u8)]
pub enum GossipTrendClass {
    Stable    = 0,
    Improving = 1,
    Degrading = 2,
    Volatile  = 3,
}

impl GossipTrendClass {
    pub fn as_u8(self) -> u8 { self as u8 }

    fn classify(improvement_count: u32, degradation_count: u32, window_size: usize) -> Self {
        let threshold = if window_size >= GOSSIP_TREND_WINDOW {
            3u32
        } else {
            (window_size as u32).saturating_sub(1).max(1)
        };
        if improvement_count >= threshold && degradation_count == 0 {
            return Self::Improving;
        }
        if degradation_count >= threshold && improvement_count == 0 {
            return Self::Degrading;
        }
        if improvement_count >= 1 && degradation_count >= 1 {
            return Self::Volatile;
        }
        Self::Stable
    }
}

// ─── GossipTrendRecord ────────────────────────────────────────────────────────

#[derive(Debug, Clone, PartialEq)]
pub struct GossipTrendRecord {
    pub epoch:               u64,
    pub trend_class:         GossipTrendClass,
    pub window_size:         usize,
    pub improvement_count:   u32,
    pub degradation_count:   u32,
    pub net_delivered_delta: i64,
    pub trend_hash:          [u8; 32],
    pub prev_hash:           [u8; 32],
}

fn compute_trend_hash(
    prev:                &[u8; 32],
    epoch:               u64,
    trend_class:         GossipTrendClass,
    window_size:         usize,
    improvement_count:   u32,
    degradation_count:   u32,
    net_delivered_delta: i64,
) -> [u8; 32] {
    let mut h = Sha256::new();
    h.update(prev);
    h.update(epoch.to_be_bytes());
    h.update([trend_class.as_u8()]);
    h.update((window_size as u16).to_be_bytes());
    h.update(improvement_count.to_be_bytes());
    h.update(degradation_count.to_be_bytes());
    h.update(net_delivered_delta.to_be_bytes());
    h.finalize().into()
}

// ─── GossipTrendAnalyzerLog ───────────────────────────────────────────────────

pub struct GossipTrendAnalyzerLog {
    records: Vec<GossipTrendRecord>,
    /// Rolling window: (improvement_flag, degradation_flag, delivered_delta)
    window:  Vec<(bool, bool, i64)>,
}

impl GossipTrendAnalyzerLog {
    pub fn new() -> Self {
        Self {
            records: Vec::new(),
            window:  Vec::with_capacity(GOSSIP_TREND_WINDOW),
        }
    }

    pub fn len(&self)      -> usize { self.records.len() }
    pub fn is_empty(&self) -> bool  { self.records.is_empty() }
    pub fn records(&self)  -> &[GossipTrendRecord] { &self.records }
    pub fn latest(&self)   -> Option<&GossipTrendRecord> { self.records.last() }

    pub fn append(&mut self, delta: &GossipEpochDeltaRecord) -> &GossipTrendRecord {
        // Update rolling window
        if self.window.len() == GOSSIP_TREND_WINDOW {
            self.window.remove(0);
        }
        let is_improvement = delta.joint_improved || delta.chains_recovered;
        let is_degradation = delta.joint_worsened || delta.chains_degraded;
        self.window.push((is_improvement, is_degradation, delta.delivered_delta));

        let window_size       = self.window.len();
        let improvement_count = self.window.iter().filter(|&&(imp, _, _)| imp).count() as u32;
        let degradation_count = self.window.iter().filter(|&&(_, deg, _)| deg).count() as u32;
        let net_delivered_delta: i64 = self.window.iter().map(|&(_, _, dd)| dd).sum();

        let trend_class = GossipTrendClass::classify(improvement_count, degradation_count, window_size);

        let prev = self.records.last()
            .map(|r| r.trend_hash)
            .unwrap_or(GOSSIP_TREND_GENESIS_HASH);

        let trend_hash = compute_trend_hash(
            &prev,
            delta.epoch,
            trend_class,
            window_size,
            improvement_count,
            degradation_count,
            net_delivered_delta,
        );

        self.records.push(GossipTrendRecord {
            epoch: delta.epoch,
            trend_class,
            window_size,
            improvement_count,
            degradation_count,
            net_delivered_delta,
            trend_hash,
            prev_hash: prev,
        });
        self.records.last().unwrap()
    }

    pub fn improving_trend_count(&self) -> usize {
        self.records.iter().filter(|r| r.trend_class == GossipTrendClass::Improving).count()
    }

    pub fn degrading_trend_count(&self) -> usize {
        self.records.iter().filter(|r| r.trend_class == GossipTrendClass::Degrading).count()
    }

    pub fn volatile_trend_count(&self) -> usize {
        self.records.iter().filter(|r| r.trend_class == GossipTrendClass::Volatile).count()
    }

    pub fn stable_trend_count(&self) -> usize {
        self.records.iter().filter(|r| r.trend_class == GossipTrendClass::Stable).count()
    }

    pub fn verify_chain(&self) -> (bool, Option<usize>) {
        let mut prev = GOSSIP_TREND_GENESIS_HASH;
        for (i, r) in self.records.iter().enumerate() {
            if r.prev_hash != prev {
                return (false, Some(i));
            }
            let expected = compute_trend_hash(
                &prev,
                r.epoch,
                r.trend_class,
                r.window_size,
                r.improvement_count,
                r.degradation_count,
                r.net_delivered_delta,
            );
            if r.trend_hash != expected {
                return (false, Some(i));
            }
            prev = r.trend_hash;
        }
        (true, None)
    }
}

impl Default for GossipTrendAnalyzerLog {
    fn default() -> Self { Self::new() }
}

// ─── Tests ────────────────────────────────────────────────────────────────────

#[cfg(test)]
mod tests {
    use super::*;
    use crate::compaction_gossip_health_aggregator::{GossipHealthGrade, GossipJointCondition};
    use crate::compaction_gossip_momentum_tracker::GossipMomentumDir;
    use crate::compaction_gossip_epoch_report::GossipEpochReport;
    use crate::compaction_gossip_epoch_comparator::GossipEpochComparatorLog;

    fn make_delta(improving: bool, worsening: bool, epoch: u64) -> GossipEpochDeltaRecord {
        GossipEpochDeltaRecord {
            epoch,
            prev_epoch:       epoch.saturating_sub(1),
            joint_improved:   improving,
            joint_worsened:   worsening,
            chains_recovered: false,
            chains_degraded:  false,
            delivered_delta:  1_000,
            momentum_delta:   0,
            direction_changed: false,
            delta_hash:       [0u8; 32],
            prev_hash:        [0u8; 32],
        }
    }

    fn make_report(
        epoch:           u64,
        jc:              GossipJointCondition,
        chains_valid:    bool,
        total_delivered: u64,
    ) -> GossipEpochReport {
        GossipEpochReport {
            epoch,
            joint_condition: jc,
            gossip_grade:    GossipHealthGrade::Healthy,
            total_delivered,
            chains_valid,
            direction:       GossipMomentumDir::Stable,
            momentum_int:    0,
            window_size:     2,
            red_pct:         0,
            yellow_pct:      0,
            green_pct:       100,
            report_hash:     [0u8; 32],
            prev_hash:       [0u8; 32],
        }
    }

    // ── GossipTrendClass classification ───────────────────────────────────────

    #[test]
    fn stable_when_no_movement() {
        assert_eq!(GossipTrendClass::classify(0, 0, 4), GossipTrendClass::Stable);
    }

    #[test]
    fn improving_when_three_improvements() {
        assert_eq!(GossipTrendClass::classify(3, 0, 4), GossipTrendClass::Improving);
    }

    #[test]
    fn improving_requires_no_degradations() {
        assert_eq!(GossipTrendClass::classify(3, 1, 4), GossipTrendClass::Volatile);
    }

    #[test]
    fn degrading_when_three_degradations() {
        assert_eq!(GossipTrendClass::classify(0, 3, 4), GossipTrendClass::Degrading);
    }

    #[test]
    fn volatile_when_mixed() {
        assert_eq!(GossipTrendClass::classify(2, 2, 4), GossipTrendClass::Volatile);
    }

    #[test]
    fn volatile_when_one_each() {
        assert_eq!(GossipTrendClass::classify(1, 1, 4), GossipTrendClass::Volatile);
    }

    // ── Append and window rolling ──────────────────────────────────────────────

    #[test]
    fn single_delta_stable() {
        let mut l = GossipTrendAnalyzerLog::new();
        let d = make_delta(false, false, 2);
        let r = l.append(&d).clone();
        assert_eq!(r.trend_class, GossipTrendClass::Stable);
        assert_eq!(r.window_size, 1);
        assert_eq!(r.improvement_count, 0);
        assert_eq!(r.degradation_count, 0);
        assert_eq!(r.net_delivered_delta, 1_000);
    }

    #[test]
    fn three_improvements_yields_improving() {
        let mut l = GossipTrendAnalyzerLog::new();
        for i in 2u64..=4 {
            l.append(&make_delta(true, false, i));
        }
        let r = l.latest().unwrap();
        assert_eq!(r.trend_class, GossipTrendClass::Improving);
        assert_eq!(r.improvement_count, 3);
    }

    #[test]
    fn three_degradations_yields_degrading() {
        let mut l = GossipTrendAnalyzerLog::new();
        for i in 2u64..=4 {
            l.append(&make_delta(false, true, i));
        }
        assert_eq!(l.latest().unwrap().trend_class, GossipTrendClass::Degrading);
    }

    #[test]
    fn mixed_yields_volatile() {
        let mut l = GossipTrendAnalyzerLog::new();
        for (i, imp, deg) in [(2u64, true, false), (3, false, true), (4, true, false), (5, false, true)] {
            l.append(&make_delta(imp, deg, i));
        }
        assert_eq!(l.latest().unwrap().trend_class, GossipTrendClass::Volatile);
    }

    #[test]
    fn window_caps_at_trend_window() {
        let mut l = GossipTrendAnalyzerLog::new();
        for i in 2u64..=(GOSSIP_TREND_WINDOW as u64 + 3) {
            l.append(&make_delta(true, false, i));
        }
        assert_eq!(l.latest().unwrap().window_size, GOSSIP_TREND_WINDOW);
    }

    #[test]
    fn window_eviction_uses_recent_only() {
        let mut l = GossipTrendAnalyzerLog::new();
        for i in 2u64..=5 {
            l.append(&make_delta(false, true, i));
        }
        for i in 6u64..=8 {
            l.append(&make_delta(true, false, i));
        }
        // Window: [imp,f], [imp,f], [imp,f], [f,deg] → improvement=3, degradation=1 → Volatile
        assert_eq!(l.latest().unwrap().trend_class, GossipTrendClass::Volatile);
    }

    #[test]
    fn net_delivered_delta_sums_window() {
        let mut l = GossipTrendAnalyzerLog::new();
        let mut d = make_delta(false, false, 2);
        d.delivered_delta = 2_000;
        l.append(&d);
        let mut d2 = make_delta(false, false, 3);
        d2.delivered_delta = 3_000;
        l.append(&d2);
        assert_eq!(l.latest().unwrap().net_delivered_delta, 5_000);
    }

    // ── Aggregation counts ─────────────────────────────────────────────────────

    #[test]
    fn trend_counts_correct() {
        let mut l = GossipTrendAnalyzerLog::new();
        for i in 2u64..=4 { l.append(&make_delta(true, false, i)); }
        l.append(&make_delta(false, false, 5));
        l.append(&make_delta(false, true, 6));

        assert!(l.improving_trend_count() >= 1);
        assert_eq!(l.volatile_trend_count(), 1);
        assert_eq!(l.degrading_trend_count(), 0);
    }

    #[test]
    fn stable_count_correct() {
        let mut l = GossipTrendAnalyzerLog::new();
        for i in 2u64..=4 { l.append(&make_delta(false, false, i)); }
        assert_eq!(l.stable_trend_count(), 3);
    }

    // ── Hash chain integrity ───────────────────────────────────────────────────

    #[test]
    fn verify_chain_empty_ok() {
        let l = GossipTrendAnalyzerLog::new();
        let (ok, idx) = l.verify_chain();
        assert!(ok);
        assert!(idx.is_none());
    }

    #[test]
    fn verify_chain_five_records_ok() {
        let mut l = GossipTrendAnalyzerLog::new();
        for i in 2u64..=6 {
            l.append(&make_delta(i % 2 == 0, i % 3 == 0, i));
        }
        let (ok, idx) = l.verify_chain();
        assert!(ok);
        assert!(idx.is_none());
    }

    #[test]
    fn verify_chain_detects_tamper() {
        let mut l = GossipTrendAnalyzerLog::new();
        for i in 2u64..=4 { l.append(&make_delta(true, false, i)); }
        l.records[0].trend_hash[0] ^= 0xFF;
        let (ok, idx) = l.verify_chain();
        assert!(!ok);
        assert_eq!(idx, Some(0));
    }

    #[test]
    fn trend_hash_deterministic() {
        let mut l1 = GossipTrendAnalyzerLog::new();
        let mut l2 = GossipTrendAnalyzerLog::new();
        let reports: Vec<_> = (2u64..=5).map(|i| make_report(
            i, GossipJointCondition::Nominal, true, i * 1000,
        )).collect();
        let mut cl1 = GossipEpochComparatorLog::new();
        let mut cl2 = GossipEpochComparatorLog::new();
        for w in reports.windows(2) {
            let d1 = cl1.compare(&w[0], &w[1]).clone();
            let d2 = cl2.compare(&w[0], &w[1]).clone();
            l1.append(&d1);
            l2.append(&d2);
        }
        assert_eq!(l1.records[0].trend_hash, l2.records[0].trend_hash);
    }

    #[test]
    fn prev_hash_links_correctly() {
        let mut l = GossipTrendAnalyzerLog::new();
        l.append(&make_delta(false, false, 2));
        let h0 = l.records[0].trend_hash;
        l.append(&make_delta(false, false, 3));
        assert_eq!(l.records[1].prev_hash, h0);
    }
}
