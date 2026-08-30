//! Gate 346 — Compaction Trend Analyzer (T2)
//! EPISTEMIC TIER: T2 (engineering hypothesis)
//!
//! Classifies multi-epoch compaction trends from a rolling window of
//! EpochDeltaRecords (Gate 345), providing higher-level trend signals.
//!
//! TREND_WINDOW: usize = 4  — number of recent deltas considered
//!
//! TrendClass:
//!   Improving  — improvement_count ≥ 3 out of last TREND_WINDOW deltas
//!   Degrading  — degradation_count ≥ 3 out of last TREND_WINDOW deltas
//!   Volatile   — both improvement_count ≥ 1 AND degradation_count ≥ 1
//!   Stable     — otherwise (no significant net movement)
//!
//! TrendRecord:
//!   epoch:              u64
//!   trend_class:        TrendClass
//!   window_size:        usize        — actual window used (≤ TREND_WINDOW)
//!   improvement_count:  u32          — improved/recovered deltas in window
//!   degradation_count:  u32          — worsened/degraded deltas in window
//!   net_pruned_delta:   i64          — sum of pruned_delta across window
//!   trend_hash:         [u8;32]
//!   prev_hash:          [u8;32]
//!
//! trend_hash = SHA-256(prev[32] ‖ epoch_be8 ‖ trend_byte ‖ window_size_be2
//!                        ‖ improvement_be4 ‖ degradation_be4 ‖ net_pruned_delta_be8)
//!
//! TrendAnalyzerLog: append(delta), improving_trend_count(), degrading_trend_count(),
//!   volatile_trend_count(), stable_trend_count(), verify_chain().

use sha2::{Sha256, Digest};
use crate::compaction_epoch_comparator::EpochDeltaRecord;

pub const TREND_GENESIS_HASH: [u8; 32] = [0u8; 32];
pub const TREND_WINDOW: usize = 4;

// ─── TrendClass ───────────────────────────────────────────────────────────────

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
#[repr(u8)]
pub enum TrendClass {
    Stable    = 0,
    Improving = 1,
    Degrading = 2,
    Volatile  = 3,
}

impl TrendClass {
    pub fn as_u8(self) -> u8 { self as u8 }

    fn classify(improvement_count: u32, degradation_count: u32, window_size: usize) -> Self {
        let threshold = if window_size >= TREND_WINDOW { 3u32 } else { (window_size as u32).saturating_sub(1).max(1) };
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

// ─── TrendRecord ──────────────────────────────────────────────────────────────

#[derive(Debug, Clone, PartialEq)]
pub struct TrendRecord {
    pub epoch:              u64,
    pub trend_class:        TrendClass,
    pub window_size:        usize,
    pub improvement_count:  u32,
    pub degradation_count:  u32,
    pub net_pruned_delta:   i64,
    pub trend_hash:         [u8; 32],
    pub prev_hash:          [u8; 32],
}

fn compute_trend_hash(
    prev:               &[u8; 32],
    epoch:              u64,
    trend_class:        TrendClass,
    window_size:        usize,
    improvement_count:  u32,
    degradation_count:  u32,
    net_pruned_delta:   i64,
) -> [u8; 32] {
    let mut h = Sha256::new();
    h.update(prev);
    h.update(epoch.to_be_bytes());
    h.update([trend_class.as_u8()]);
    h.update((window_size as u16).to_be_bytes());
    h.update(improvement_count.to_be_bytes());
    h.update(degradation_count.to_be_bytes());
    h.update(net_pruned_delta.to_be_bytes());
    h.finalize().into()
}

// ─── TrendAnalyzerLog ─────────────────────────────────────────────────────────

pub struct TrendAnalyzerLog {
    records: Vec<TrendRecord>,
    /// Rolling window of recent EpochDeltaRecord snapshots (only fields needed).
    window:  Vec<(bool, bool, i64)>, // (improvement_flag, degradation_flag, pruned_delta)
}

impl TrendAnalyzerLog {
    pub fn new() -> Self {
        Self {
            records: Vec::new(),
            window:  Vec::with_capacity(TREND_WINDOW),
        }
    }

    pub fn len(&self)      -> usize { self.records.len() }
    pub fn is_empty(&self) -> bool  { self.records.is_empty() }
    pub fn records(&self)  -> &[TrendRecord] { &self.records }
    pub fn latest(&self)   -> Option<&TrendRecord> { self.records.last() }

    pub fn append(&mut self, delta: &EpochDeltaRecord) -> &TrendRecord {
        // Update rolling window
        if self.window.len() == TREND_WINDOW {
            self.window.remove(0);
        }
        let is_improvement = delta.joint_improved || delta.chains_recovered;
        let is_degradation = delta.joint_worsened || delta.chains_degraded;
        self.window.push((is_improvement, is_degradation, delta.pruned_delta));

        let window_size = self.window.len();
        let improvement_count = self.window.iter().filter(|&&(imp, _, _)| imp).count() as u32;
        let degradation_count = self.window.iter().filter(|&&(_, deg, _)| deg).count() as u32;
        let net_pruned_delta: i64 = self.window.iter().map(|&(_, _, pd)| pd).sum();

        let trend_class = TrendClass::classify(improvement_count, degradation_count, window_size);

        let prev = self.records.last()
            .map(|r| r.trend_hash)
            .unwrap_or(TREND_GENESIS_HASH);

        let trend_hash = compute_trend_hash(
            &prev,
            delta.epoch,
            trend_class,
            window_size,
            improvement_count,
            degradation_count,
            net_pruned_delta,
        );

        self.records.push(TrendRecord {
            epoch: delta.epoch,
            trend_class,
            window_size,
            improvement_count,
            degradation_count,
            net_pruned_delta,
            trend_hash,
            prev_hash: prev,
        });
        self.records.last().unwrap()
    }

    pub fn improving_trend_count(&self) -> usize {
        self.records.iter().filter(|r| r.trend_class == TrendClass::Improving).count()
    }

    pub fn degrading_trend_count(&self) -> usize {
        self.records.iter().filter(|r| r.trend_class == TrendClass::Degrading).count()
    }

    pub fn volatile_trend_count(&self) -> usize {
        self.records.iter().filter(|r| r.trend_class == TrendClass::Volatile).count()
    }

    pub fn stable_trend_count(&self) -> usize {
        self.records.iter().filter(|r| r.trend_class == TrendClass::Stable).count()
    }

    pub fn verify_chain(&self) -> (bool, Option<usize>) {
        let mut prev = TREND_GENESIS_HASH;
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
                r.net_pruned_delta,
            );
            if r.trend_hash != expected {
                return (false, Some(i));
            }
            prev = r.trend_hash;
        }
        (true, None)
    }
}

impl Default for TrendAnalyzerLog {
    fn default() -> Self { Self::new() }
}

// ─── Tests ────────────────────────────────────────────────────────────────────

#[cfg(test)]
mod tests {
    use super::*;
    use crate::compaction_health_aggregator::{CompactionHealthGrade, JointCondition};
    use crate::compaction_momentum_tracker::CompactionMomentumDir;
    use crate::compaction_epoch_report::CompactionEpochReport;
    use crate::compaction_epoch_comparator::EpochComparatorLog;

    fn make_report(
        epoch:        u64,
        jc:           JointCondition,
        chains_valid: bool,
        total_pruned: u64,
        direction:    CompactionMomentumDir,
        momentum_int: i16,
    ) -> CompactionEpochReport {
        CompactionEpochReport {
            epoch,
            joint_condition:  jc,
            compaction_grade: CompactionHealthGrade::Healthy,
            total_pruned,
            chains_valid,
            direction,
            momentum_int,
            window_size:  2,
            spsf_pct:     0,
            health_pct:   0,
            res_pct:      0,
            report_hash:  [0u8; 32],
            prev_hash:    [0u8; 32],
        }
    }

    fn make_delta(improving: bool, worsening: bool, epoch: u64) -> EpochDeltaRecord {
        EpochDeltaRecord {
            epoch,
            prev_epoch:       epoch.saturating_sub(1),
            joint_improved:   improving,
            joint_worsened:   worsening,
            chains_recovered: false,
            chains_degraded:  false,
            pruned_delta:     100,
            momentum_delta:   0,
            direction_changed: false,
            delta_hash:       [0u8; 32],
            prev_hash:        [0u8; 32],
        }
    }

    // ── TrendClass classification ──────────────────────────────────────────────

    #[test]
    fn stable_when_no_movement() {
        assert_eq!(TrendClass::classify(0, 0, 4), TrendClass::Stable);
    }

    #[test]
    fn improving_when_three_improvements() {
        assert_eq!(TrendClass::classify(3, 0, 4), TrendClass::Improving);
    }

    #[test]
    fn improving_requires_no_degradations() {
        // 3 improvements but also 1 degradation → Volatile, not Improving
        assert_eq!(TrendClass::classify(3, 1, 4), TrendClass::Volatile);
    }

    #[test]
    fn degrading_when_three_degradations() {
        assert_eq!(TrendClass::classify(0, 3, 4), TrendClass::Degrading);
    }

    #[test]
    fn volatile_when_mixed() {
        assert_eq!(TrendClass::classify(2, 2, 4), TrendClass::Volatile);
    }

    #[test]
    fn volatile_when_one_each() {
        assert_eq!(TrendClass::classify(1, 1, 4), TrendClass::Volatile);
    }

    // ── Append and window rolling ──────────────────────────────────────────────

    #[test]
    fn single_delta_stable() {
        let mut l = TrendAnalyzerLog::new();
        let d = make_delta(false, false, 2);
        let r = l.append(&d).clone();
        assert_eq!(r.trend_class, TrendClass::Stable);
        assert_eq!(r.window_size, 1);
        assert_eq!(r.improvement_count, 0);
        assert_eq!(r.degradation_count, 0);
        assert_eq!(r.net_pruned_delta, 100);
    }

    #[test]
    fn three_improvements_yields_improving() {
        let mut l = TrendAnalyzerLog::new();
        for i in 2u64..=4 {
            let d = make_delta(true, false, i);
            l.append(&d);
        }
        let r = l.latest().unwrap();
        assert_eq!(r.trend_class, TrendClass::Improving);
        assert_eq!(r.improvement_count, 3);
    }

    #[test]
    fn three_degradations_yields_degrading() {
        let mut l = TrendAnalyzerLog::new();
        for i in 2u64..=4 {
            let d = make_delta(false, true, i);
            l.append(&d);
        }
        assert_eq!(l.latest().unwrap().trend_class, TrendClass::Degrading);
    }

    #[test]
    fn mixed_yields_volatile() {
        let mut l = TrendAnalyzerLog::new();
        for (i, imp, deg) in [(2, true, false), (3, false, true), (4, true, false), (5, false, true)] {
            let d = make_delta(imp, deg, i);
            l.append(&d);
        }
        assert_eq!(l.latest().unwrap().trend_class, TrendClass::Volatile);
    }

    #[test]
    fn window_caps_at_trend_window() {
        let mut l = TrendAnalyzerLog::new();
        for i in 2u64..=(TREND_WINDOW as u64 + 3) {
            let d = make_delta(true, false, i);
            l.append(&d);
        }
        assert_eq!(l.latest().unwrap().window_size, TREND_WINDOW);
    }

    #[test]
    fn window_eviction_uses_recent_only() {
        let mut l = TrendAnalyzerLog::new();
        // 4 degradations, then 3 improvements → window = [imp, imp, imp, deg] → Volatile
        for i in 2u64..=5 {
            l.append(&make_delta(false, true, i));
        }
        for i in 6u64..=8 {
            l.append(&make_delta(true, false, i));
        }
        // Window now: [true, false], [true, false], [true, false], [false, true]
        // improvement_count=3, degradation_count=1 → Volatile (not Improving, as degradation≥1)
        assert_eq!(l.latest().unwrap().trend_class, TrendClass::Volatile);
    }

    #[test]
    fn net_pruned_delta_sums_window() {
        let mut l = TrendAnalyzerLog::new();
        let mut d = make_delta(false, false, 2);
        d.pruned_delta = 200;
        l.append(&d);
        let mut d2 = make_delta(false, false, 3);
        d2.pruned_delta = 300;
        l.append(&d2);
        assert_eq!(l.latest().unwrap().net_pruned_delta, 500);
    }

    // ── Aggregation counts ─────────────────────────────────────────────────────

    #[test]
    fn trend_counts_correct() {
        let mut l = TrendAnalyzerLog::new();
        // 3 improving deltas → Improving record
        for i in 2u64..=4 { l.append(&make_delta(true, false, i)); }
        // 1 stable delta → window=[imp,imp,imp,stable] → still 3 improvements, 0 degradations → Improving
        l.append(&make_delta(false, false, 5));
        // 1 degradation → window=[imp,imp,stable,deg] → Volatile
        l.append(&make_delta(false, true, 6));

        assert_eq!(l.improving_trend_count(), 4); // records 3,4,5 still improving, record 4 (epoch 5) too
        assert_eq!(l.volatile_trend_count(), 1);
        assert_eq!(l.degrading_trend_count(), 0);
    }

    #[test]
    fn stable_count_correct() {
        let mut l = TrendAnalyzerLog::new();
        for i in 2u64..=4 { l.append(&make_delta(false, false, i)); }
        assert_eq!(l.stable_trend_count(), 3);
    }

    // ── Hash chain integrity ───────────────────────────────────────────────────

    #[test]
    fn verify_chain_empty_ok() {
        let l = TrendAnalyzerLog::new();
        let (ok, idx) = l.verify_chain();
        assert!(ok);
        assert!(idx.is_none());
    }

    #[test]
    fn verify_chain_five_records_ok() {
        let mut l = TrendAnalyzerLog::new();
        for i in 2u64..=6 {
            l.append(&make_delta(i % 2 == 0, i % 3 == 0, i));
        }
        let (ok, idx) = l.verify_chain();
        assert!(ok);
        assert!(idx.is_none());
    }

    #[test]
    fn verify_chain_detects_tamper() {
        let mut l = TrendAnalyzerLog::new();
        for i in 2u64..=4 { l.append(&make_delta(true, false, i)); }
        l.records[0].trend_hash[0] ^= 0xFF;
        let (ok, idx) = l.verify_chain();
        assert!(!ok);
        assert_eq!(idx, Some(0));
    }

    #[test]
    fn trend_hash_deterministic() {
        let mut l1 = TrendAnalyzerLog::new();
        let mut l2 = TrendAnalyzerLog::new();
        let reports: Vec<_> = (2u64..=5).map(|i| make_report(
            i, JointCondition::Nominal, true, i*100, CompactionMomentumDir::Stable, 0,
        )).collect();
        // Build deltas via comparator
        let mut cl1 = EpochComparatorLog::new();
        let mut cl2 = EpochComparatorLog::new();
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
        let mut l = TrendAnalyzerLog::new();
        l.append(&make_delta(false, false, 2));
        let h0 = l.records[0].trend_hash;
        l.append(&make_delta(false, false, 3));
        assert_eq!(l.records[1].prev_hash, h0);
    }
}
