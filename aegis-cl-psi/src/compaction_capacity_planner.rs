//! Gate 344 — Compaction Capacity Planner (T2)
//! EPISTEMIC TIER: T2 (engineering hypothesis)
//!
//! Projects epochs-to-capacity-ceiling from the recent CompactionEpochReport trend.
//! Uses a simple linear extrapolation over the last CAPACITY_WINDOW=4 reports.
//!
//! CAPACITY_CEILING: u64 = 10_000  — prune entries per epoch that signals saturation
//!
//! Projection algorithm (integer arithmetic, no f64):
//!   1. Collect total_pruned values from the last min(CAPACITY_WINDOW, len) reports.
//!   2. mean_delta = (last_total - first_total) / (window_len - 1)  [0 if window_len<2]
//!   3. If mean_delta ≤ 0 → no risk, epochs_to_ceiling = u32::MAX (sentinel "∞").
//!   4. If current_total ≥ CAPACITY_CEILING → already_at_capacity (epochs_to_ceiling = 0).
//!   5. Else: epochs_to_ceiling = (CAPACITY_CEILING - current_total) / mean_delta (saturate at u32::MAX).
//!
//! CapacityProjection:
//!   epoch:               u64
//!   current_total:       u64
//!   mean_delta:          i64          — average per-epoch prune delta across window
//!   window_len:          usize
//!   epochs_to_ceiling:   u32          — u32::MAX = no foreseeable risk
//!   at_capacity:         bool
//!   projection_hash:     [u8;32]
//!   prev_hash:           [u8;32]
//!
//! projection_hash = SHA-256(prev[32] ‖ epoch_be8 ‖ current_total_be8
//!                             ‖ mean_delta_be8 ‖ window_len_be4
//!                             ‖ epochs_to_ceiling_be4 ‖ at_capacity_byte)
//!
//! CapacityPlannerLog: append(report), latest(), critical_projections() (epochs_to_ceiling ≤ 5),
//!   verify_chain().

use sha2::{Sha256, Digest};
use crate::compaction_epoch_report::CompactionEpochReport;

pub const CAPACITY_GENESIS_HASH: [u8; 32] = [0u8; 32];
pub const CAPACITY_WINDOW: usize = 4;
pub const CAPACITY_CEILING: u64 = 10_000;

// ─── CapacityProjection ───────────────────────────────────────────────────────

#[derive(Debug, Clone, PartialEq)]
pub struct CapacityProjection {
    pub epoch:               u64,
    pub current_total:       u64,
    pub mean_delta:          i64,
    pub window_len:          usize,
    pub epochs_to_ceiling:   u32,
    pub at_capacity:         bool,
    pub projection_hash:     [u8; 32],
    pub prev_hash:           [u8; 32],
}

fn compute_projection_hash(
    prev:               &[u8; 32],
    epoch:              u64,
    current_total:      u64,
    mean_delta:         i64,
    window_len:         usize,
    epochs_to_ceiling:  u32,
    at_capacity:        bool,
) -> [u8; 32] {
    let mut h = Sha256::new();
    h.update(prev);
    h.update(epoch.to_be_bytes());
    h.update(current_total.to_be_bytes());
    h.update(mean_delta.to_be_bytes());
    h.update((window_len as u32).to_be_bytes());
    h.update(epochs_to_ceiling.to_be_bytes());
    h.update([at_capacity as u8]);
    h.finalize().into()
}

// ─── CapacityPlannerLog ───────────────────────────────────────────────────────

pub struct CapacityPlannerLog {
    projections: Vec<CapacityProjection>,
    /// Sliding window of recent total_pruned values.
    window: Vec<u64>,
}

impl CapacityPlannerLog {
    pub fn new() -> Self {
        Self {
            projections: Vec::new(),
            window: Vec::with_capacity(CAPACITY_WINDOW),
        }
    }

    pub fn len(&self)         -> usize { self.projections.len() }
    pub fn is_empty(&self)    -> bool  { self.projections.is_empty() }
    pub fn projections(&self) -> &[CapacityProjection] { &self.projections }
    pub fn latest(&self)      -> Option<&CapacityProjection> { self.projections.last() }

    pub fn append(&mut self, report: &CompactionEpochReport) -> &CapacityProjection {
        // Update sliding window
        if self.window.len() == CAPACITY_WINDOW {
            self.window.remove(0);
        }
        self.window.push(report.total_pruned);

        let window_len    = self.window.len();
        let current_total = report.total_pruned;

        // Compute mean_delta: (last - first) / (window_len - 1), 0 if single entry
        let mean_delta: i64 = if window_len < 2 {
            0
        } else {
            let first = *self.window.first().unwrap() as i64;
            let last  = *self.window.last().unwrap()  as i64;
            (last - first) / ((window_len - 1) as i64)
        };

        let at_capacity = current_total >= CAPACITY_CEILING;

        let epochs_to_ceiling: u32 = if at_capacity {
            0
        } else if mean_delta <= 0 {
            u32::MAX
        } else {
            let remaining = CAPACITY_CEILING - current_total;
            let steps = remaining / (mean_delta as u64);
            steps.min(u32::MAX as u64) as u32
        };

        let prev = self.projections.last()
            .map(|p| p.projection_hash)
            .unwrap_or(CAPACITY_GENESIS_HASH);

        let projection_hash = compute_projection_hash(
            &prev,
            report.epoch,
            current_total,
            mean_delta,
            window_len,
            epochs_to_ceiling,
            at_capacity,
        );

        self.projections.push(CapacityProjection {
            epoch: report.epoch,
            current_total,
            mean_delta,
            window_len,
            epochs_to_ceiling,
            at_capacity,
            projection_hash,
            prev_hash: prev,
        });
        self.projections.last().unwrap()
    }

    /// Count projections where epochs_to_ceiling ≤ 5 (imminent saturation).
    pub fn critical_projections(&self) -> usize {
        self.projections.iter()
            .filter(|p| p.epochs_to_ceiling <= 5 && !p.at_capacity)
            .count()
    }

    pub fn verify_chain(&self) -> (bool, Option<usize>) {
        let mut prev = CAPACITY_GENESIS_HASH;
        for (i, p) in self.projections.iter().enumerate() {
            if p.prev_hash != prev {
                return (false, Some(i));
            }
            let expected = compute_projection_hash(
                &prev,
                p.epoch,
                p.current_total,
                p.mean_delta,
                p.window_len,
                p.epochs_to_ceiling,
                p.at_capacity,
            );
            if p.projection_hash != expected {
                return (false, Some(i));
            }
            prev = p.projection_hash;
        }
        (true, None)
    }
}

impl Default for CapacityPlannerLog {
    fn default() -> Self { Self::new() }
}

// ─── Tests ────────────────────────────────────────────────────────────────────

#[cfg(test)]
mod tests {
    use super::*;
    use crate::compaction_health_aggregator::{CompactionHealthGrade, JointCondition};
    use crate::compaction_momentum_tracker::CompactionMomentumDir;

    fn make_report(epoch: u64, total_pruned: u64) -> CompactionEpochReport {
        CompactionEpochReport {
            epoch,
            joint_condition:  JointCondition::Nominal,
            compaction_grade: CompactionHealthGrade::Healthy,
            total_pruned,
            chains_valid:     true,
            direction:        CompactionMomentumDir::Stable,
            momentum_int:     0,
            window_size:      1,
            spsf_pct:         0,
            health_pct:       0,
            res_pct:          0,
            report_hash:      [0u8; 32],
            prev_hash:        [0u8; 32],
        }
    }

    // ── Single entry ──────────────────────────────────────────────────────────

    #[test]
    fn single_entry_no_delta() {
        let mut l = CapacityPlannerLog::new();
        let p = l.append(&make_report(1, 100)).clone();
        assert_eq!(p.window_len, 1);
        assert_eq!(p.mean_delta, 0);
        assert_eq!(p.epochs_to_ceiling, u32::MAX); // no trend → no risk
        assert!(!p.at_capacity);
    }

    // ── Trend detection ───────────────────────────────────────────────────────

    #[test]
    fn rising_trend_projects_ceiling() {
        let mut l = CapacityPlannerLog::new();
        // 500 → 1000 → 1500 → 2000: delta=500/epoch
        for (i, &total) in [500u64, 1000, 1500, 2000].iter().enumerate() {
            l.append(&make_report(i as u64 + 1, total));
        }
        let p = l.latest().unwrap();
        // mean_delta = (2000-500)/3 = 500
        assert_eq!(p.mean_delta, 500);
        // remaining = 10000 - 2000 = 8000 / 500 = 16 epochs
        assert_eq!(p.epochs_to_ceiling, 16);
        assert!(!p.at_capacity);
    }

    #[test]
    fn stable_trend_no_risk() {
        let mut l = CapacityPlannerLog::new();
        for i in 1u64..=4 {
            l.append(&make_report(i, 100)); // constant
        }
        let p = l.latest().unwrap();
        assert_eq!(p.mean_delta, 0);
        assert_eq!(p.epochs_to_ceiling, u32::MAX);
    }

    #[test]
    fn declining_trend_no_risk() {
        let mut l = CapacityPlannerLog::new();
        for (i, &total) in [2000u64, 1500, 1000, 500].iter().enumerate() {
            l.append(&make_report(i as u64 + 1, total));
        }
        let p = l.latest().unwrap();
        assert!(p.mean_delta < 0);
        assert_eq!(p.epochs_to_ceiling, u32::MAX);
    }

    #[test]
    fn at_capacity_when_ceiling_reached() {
        let mut l = CapacityPlannerLog::new();
        l.append(&make_report(1, CAPACITY_CEILING));
        let p = l.latest().unwrap();
        assert!(p.at_capacity);
        assert_eq!(p.epochs_to_ceiling, 0);
    }

    #[test]
    fn at_capacity_above_ceiling() {
        let mut l = CapacityPlannerLog::new();
        l.append(&make_report(1, CAPACITY_CEILING + 500));
        let p = l.latest().unwrap();
        assert!(p.at_capacity);
    }

    // ── Window eviction ───────────────────────────────────────────────────────

    #[test]
    fn window_caps_at_capacity_window() {
        let mut l = CapacityPlannerLog::new();
        for i in 1u64..=(CAPACITY_WINDOW as u64 + 2) {
            l.append(&make_report(i, i * 100));
        }
        let p = l.latest().unwrap();
        assert_eq!(p.window_len, CAPACITY_WINDOW);
    }

    #[test]
    fn window_eviction_uses_recent_values() {
        let mut l = CapacityPlannerLog::new();
        // Fill: 0,0,0,0 then add 2000: window becomes [0,0,0,2000]
        for i in 1u64..=CAPACITY_WINDOW as u64 {
            l.append(&make_report(i, 0));
        }
        l.append(&make_report(CAPACITY_WINDOW as u64 + 1, 2000));
        // After eviction window = [0, 0, 0, 2000] (WINDOW=4)
        // mean_delta = (2000 - 0) / 3 = 666
        let p = l.latest().unwrap();
        assert_eq!(p.mean_delta, 666);
    }

    // ── Critical projection count ─────────────────────────────────────────────

    #[test]
    fn critical_projections_counted() {
        let mut l = CapacityPlannerLog::new();
        // Build rising fast trend: 9500 → 9700 → 9900 (delta=200, ceiling in 0.5 = 0 epochs)
        // Actually: 9500,9700,9900 → mean_delta=(9900-9500)/2=200 → remaining=100 → 0 epochs
        l.append(&make_report(1, 9500));
        l.append(&make_report(2, 9700));
        let p = l.append(&make_report(3, 9900)).clone();
        assert!(p.epochs_to_ceiling <= 5);
        // epoch 2: remaining=300/200=1 ≤5 ✓; epoch 3: remaining=100/200=0 ≤5 ✓ → count=2
        assert_eq!(l.critical_projections(), 2);
    }

    #[test]
    fn at_capacity_not_counted_as_critical() {
        let mut l = CapacityPlannerLog::new();
        l.append(&make_report(1, CAPACITY_CEILING));
        assert_eq!(l.critical_projections(), 0); // at_capacity excludes from critical count
    }

    // ── Chain integrity ───────────────────────────────────────────────────────

    #[test]
    fn verify_chain_empty_ok() {
        let l = CapacityPlannerLog::new();
        let (ok, idx) = l.verify_chain();
        assert!(ok);
        assert!(idx.is_none());
    }

    #[test]
    fn verify_chain_five_projections_ok() {
        let mut l = CapacityPlannerLog::new();
        for (i, &total) in [100u64, 200, 300, 400, 500].iter().enumerate() {
            l.append(&make_report(i as u64 + 1, total));
        }
        let (ok, idx) = l.verify_chain();
        assert!(ok);
        assert!(idx.is_none());
    }

    #[test]
    fn verify_chain_detects_tamper() {
        let mut l = CapacityPlannerLog::new();
        l.append(&make_report(1, 100));
        l.append(&make_report(2, 200));
        l.projections[0].projection_hash[0] ^= 0xFF;
        let (ok, idx) = l.verify_chain();
        assert!(!ok);
        assert_eq!(idx, Some(0));
    }

    #[test]
    fn projection_hash_deterministic() {
        let mut l1 = CapacityPlannerLog::new();
        let mut l2 = CapacityPlannerLog::new();
        l1.append(&make_report(5, 1000));
        l2.append(&make_report(5, 1000));
        assert_eq!(l1.projections[0].projection_hash, l2.projections[0].projection_hash);
    }

    #[test]
    fn prev_hash_links_correctly() {
        let mut l = CapacityPlannerLog::new();
        l.append(&make_report(1, 100));
        let h1 = l.projections[0].projection_hash;
        l.append(&make_report(2, 200));
        assert_eq!(l.projections[1].prev_hash, h1);
    }
}
