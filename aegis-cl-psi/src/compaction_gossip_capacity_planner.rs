//! Gate 366 — Compaction Gossip Capacity Planner (T2)
//! EPISTEMIC TIER: T2 (engineering hypothesis)
//!
//! Projects epochs-to-delivery-ceiling from the recent GossipEpochReport trend.
//! Mirrors Gate 344 for the gossip subsystem.
//! Uses a simple linear extrapolation over the last GOSSIP_CAPACITY_WINDOW=4 reports.
//!
//! GOSSIP_DELIVERY_CEILING: u64 = 1_000_000  — total_delivered that signals saturation
//!
//! Projection algorithm (integer arithmetic, no f64):
//!   1. Collect total_delivered values from the last min(GOSSIP_CAPACITY_WINDOW, len) reports.
//!   2. mean_delta = (last_total - first_total) / (window_len - 1)  [0 if window_len<2]
//!   3. If mean_delta ≤ 0 → no risk, epochs_to_ceiling = u32::MAX (sentinel "∞").
//!   4. If current_total ≥ GOSSIP_DELIVERY_CEILING → already_at_capacity (epochs_to_ceiling = 0).
//!   5. Else: epochs_to_ceiling = (GOSSIP_DELIVERY_CEILING - current_total) / mean_delta
//!            (saturate at u32::MAX).
//!
//! GossipCapacityProjection:
//!   epoch:               u64
//!   current_total:       u64
//!   mean_delta:          i64          — average per-epoch delivery delta across window
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
//! GossipCapacityPlannerLog: append(report), latest(), critical_projections()
//!   (epochs_to_ceiling ≤ 5 AND !at_capacity), verify_chain().

use sha2::{Sha256, Digest};
use crate::compaction_gossip_epoch_report::GossipEpochReport;

pub const GOSSIP_CAPACITY_GENESIS_HASH: [u8; 32] = [0u8; 32];
pub const GOSSIP_CAPACITY_WINDOW: usize = 4;
pub const GOSSIP_DELIVERY_CEILING: u64 = 1_000_000;

// ─── GossipCapacityProjection ─────────────────────────────────────────────────

#[derive(Debug, Clone, PartialEq)]
pub struct GossipCapacityProjection {
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
    prev:              &[u8; 32],
    epoch:             u64,
    current_total:     u64,
    mean_delta:        i64,
    window_len:        usize,
    epochs_to_ceiling: u32,
    at_capacity:       bool,
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

// ─── GossipCapacityPlannerLog ─────────────────────────────────────────────────

pub struct GossipCapacityPlannerLog {
    projections: Vec<GossipCapacityProjection>,
    /// Sliding window of recent total_delivered values.
    window: Vec<u64>,
}

impl GossipCapacityPlannerLog {
    pub fn new() -> Self {
        Self {
            projections: Vec::new(),
            window: Vec::with_capacity(GOSSIP_CAPACITY_WINDOW),
        }
    }

    pub fn len(&self)         -> usize { self.projections.len() }
    pub fn is_empty(&self)    -> bool  { self.projections.is_empty() }
    pub fn projections(&self) -> &[GossipCapacityProjection] { &self.projections }
    pub fn latest(&self)      -> Option<&GossipCapacityProjection> { self.projections.last() }

    pub fn append(&mut self, report: &GossipEpochReport) -> &GossipCapacityProjection {
        // Update sliding window
        if self.window.len() == GOSSIP_CAPACITY_WINDOW {
            self.window.remove(0);
        }
        self.window.push(report.total_delivered);

        let window_len    = self.window.len();
        let current_total = report.total_delivered;

        // Compute mean_delta: (last - first) / (window_len - 1), 0 if single entry
        let mean_delta: i64 = if window_len < 2 {
            0
        } else {
            let first = *self.window.first().unwrap() as i64;
            let last  = *self.window.last().unwrap()  as i64;
            (last - first) / ((window_len - 1) as i64)
        };

        let at_capacity = current_total >= GOSSIP_DELIVERY_CEILING;

        let epochs_to_ceiling: u32 = if at_capacity {
            0
        } else if mean_delta <= 0 {
            u32::MAX
        } else {
            let remaining = GOSSIP_DELIVERY_CEILING - current_total;
            let steps = remaining / (mean_delta as u64);
            steps.min(u32::MAX as u64) as u32
        };

        let prev = self.projections.last()
            .map(|p| p.projection_hash)
            .unwrap_or(GOSSIP_CAPACITY_GENESIS_HASH);

        let projection_hash = compute_projection_hash(
            &prev,
            report.epoch,
            current_total,
            mean_delta,
            window_len,
            epochs_to_ceiling,
            at_capacity,
        );

        self.projections.push(GossipCapacityProjection {
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

    /// Count projections where epochs_to_ceiling ≤ 5 AND !at_capacity (imminent saturation).
    pub fn critical_projections(&self) -> usize {
        self.projections.iter()
            .filter(|p| p.epochs_to_ceiling <= 5 && !p.at_capacity)
            .count()
    }

    pub fn verify_chain(&self) -> (bool, Option<usize>) {
        let mut prev = GOSSIP_CAPACITY_GENESIS_HASH;
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

impl Default for GossipCapacityPlannerLog {
    fn default() -> Self { Self::new() }
}

// ─── Tests ────────────────────────────────────────────────────────────────────

#[cfg(test)]
mod tests {
    use super::*;
    use crate::compaction_gossip_health_aggregator::{GossipHealthGrade, GossipJointCondition};
    use crate::compaction_gossip_momentum_tracker::GossipMomentumDir;

    fn make_report(epoch: u64, total_delivered: u64) -> GossipEpochReport {
        GossipEpochReport {
            epoch,
            joint_condition: GossipJointCondition::Nominal,
            gossip_grade:    GossipHealthGrade::Healthy,
            total_delivered,
            chains_valid:    true,
            direction:       GossipMomentumDir::Stable,
            momentum_int:    0,
            window_size:     1,
            red_pct:         0,
            yellow_pct:      0,
            green_pct:       100,
            report_hash:     [0u8; 32],
            prev_hash:       [0u8; 32],
        }
    }

    // ── Single entry ──────────────────────────────────────────────────────────

    #[test]
    fn single_entry_no_delta() {
        let mut l = GossipCapacityPlannerLog::new();
        let p = l.append(&make_report(1, 1000)).clone();
        assert_eq!(p.window_len, 1);
        assert_eq!(p.mean_delta, 0);
        assert_eq!(p.epochs_to_ceiling, u32::MAX);
        assert!(!p.at_capacity);
    }

    // ── Trend detection ───────────────────────────────────────────────────────

    #[test]
    fn rising_trend_projects_ceiling() {
        let mut l = GossipCapacityPlannerLog::new();
        // 500_000 → 600_000 → 700_000 → 800_000: delta=100_000/epoch
        for (i, &total) in [500_000u64, 600_000, 700_000, 800_000].iter().enumerate() {
            l.append(&make_report(i as u64 + 1, total));
        }
        let p = l.latest().unwrap();
        // mean_delta = (800_000 - 500_000) / 3 = 100_000
        assert_eq!(p.mean_delta, 100_000);
        // remaining = 1_000_000 - 800_000 = 200_000 / 100_000 = 2 epochs
        assert_eq!(p.epochs_to_ceiling, 2);
        assert!(!p.at_capacity);
    }

    #[test]
    fn stable_trend_no_risk() {
        let mut l = GossipCapacityPlannerLog::new();
        for i in 1u64..=4 {
            l.append(&make_report(i, 50_000));
        }
        let p = l.latest().unwrap();
        assert_eq!(p.mean_delta, 0);
        assert_eq!(p.epochs_to_ceiling, u32::MAX);
    }

    #[test]
    fn declining_trend_no_risk() {
        let mut l = GossipCapacityPlannerLog::new();
        for (i, &total) in [800_000u64, 700_000, 600_000, 500_000].iter().enumerate() {
            l.append(&make_report(i as u64 + 1, total));
        }
        let p = l.latest().unwrap();
        assert!(p.mean_delta < 0);
        assert_eq!(p.epochs_to_ceiling, u32::MAX);
    }

    #[test]
    fn at_capacity_when_ceiling_reached() {
        let mut l = GossipCapacityPlannerLog::new();
        l.append(&make_report(1, GOSSIP_DELIVERY_CEILING));
        let p = l.latest().unwrap();
        assert!(p.at_capacity);
        assert_eq!(p.epochs_to_ceiling, 0);
    }

    #[test]
    fn at_capacity_above_ceiling() {
        let mut l = GossipCapacityPlannerLog::new();
        l.append(&make_report(1, GOSSIP_DELIVERY_CEILING + 50_000));
        let p = l.latest().unwrap();
        assert!(p.at_capacity);
    }

    // ── Window eviction ───────────────────────────────────────────────────────

    #[test]
    fn window_caps_at_capacity_window() {
        let mut l = GossipCapacityPlannerLog::new();
        for i in 1u64..=(GOSSIP_CAPACITY_WINDOW as u64 + 2) {
            l.append(&make_report(i, i * 10_000));
        }
        let p = l.latest().unwrap();
        assert_eq!(p.window_len, GOSSIP_CAPACITY_WINDOW);
    }

    #[test]
    fn window_eviction_uses_recent_values() {
        let mut l = GossipCapacityPlannerLog::new();
        // Fill with zeros, then add 300_000: window becomes [0, 0, 0, 300_000]
        for i in 1u64..=GOSSIP_CAPACITY_WINDOW as u64 {
            l.append(&make_report(i, 0));
        }
        l.append(&make_report(GOSSIP_CAPACITY_WINDOW as u64 + 1, 300_000));
        // window = [0, 0, 0, 300_000]; mean_delta = (300_000 - 0) / 3 = 100_000
        let p = l.latest().unwrap();
        assert_eq!(p.mean_delta, 100_000);
    }

    // ── Critical projection count ─────────────────────────────────────────────

    #[test]
    fn critical_projections_counted() {
        let mut l = GossipCapacityPlannerLog::new();
        // 900_000 → 950_000 → 980_000: fast approach
        // After epoch 2: mean_delta=(950_000-900_000)/1=50_000; remaining=50_000→1 epoch ≤5 ✓
        // After epoch 3: window=[900_000,950_000,980_000]; mean_delta=40_000; remaining=20_000→0 ≤5 ✓
        l.append(&make_report(1, 900_000));
        l.append(&make_report(2, 950_000));
        let p3 = l.append(&make_report(3, 980_000)).clone();
        assert!(p3.epochs_to_ceiling <= 5);
        assert!(l.critical_projections() >= 1);
    }

    #[test]
    fn at_capacity_not_counted_as_critical() {
        let mut l = GossipCapacityPlannerLog::new();
        l.append(&make_report(1, GOSSIP_DELIVERY_CEILING));
        assert_eq!(l.critical_projections(), 0);
    }

    // ── Chain integrity ───────────────────────────────────────────────────────

    #[test]
    fn verify_chain_empty_ok() {
        let l = GossipCapacityPlannerLog::new();
        let (ok, idx) = l.verify_chain();
        assert!(ok);
        assert!(idx.is_none());
    }

    #[test]
    fn verify_chain_five_projections_ok() {
        let mut l = GossipCapacityPlannerLog::new();
        for (i, &total) in [10_000u64, 20_000, 30_000, 40_000, 50_000].iter().enumerate() {
            l.append(&make_report(i as u64 + 1, total));
        }
        let (ok, idx) = l.verify_chain();
        assert!(ok);
        assert!(idx.is_none());
    }

    #[test]
    fn verify_chain_detects_tamper() {
        let mut l = GossipCapacityPlannerLog::new();
        l.append(&make_report(1, 10_000));
        l.append(&make_report(2, 20_000));
        l.projections[0].projection_hash[0] ^= 0xFF;
        let (ok, idx) = l.verify_chain();
        assert!(!ok);
        assert_eq!(idx, Some(0));
    }

    #[test]
    fn projection_hash_deterministic() {
        let mut l1 = GossipCapacityPlannerLog::new();
        let mut l2 = GossipCapacityPlannerLog::new();
        l1.append(&make_report(5, 100_000));
        l2.append(&make_report(5, 100_000));
        assert_eq!(l1.projections[0].projection_hash, l2.projections[0].projection_hash);
    }

    #[test]
    fn prev_hash_links_correctly() {
        let mut l = GossipCapacityPlannerLog::new();
        l.append(&make_report(1, 10_000));
        let h1 = l.projections[0].projection_hash;
        l.append(&make_report(2, 20_000));
        assert_eq!(l.projections[1].prev_hash, h1);
    }
}
