//! Gate 367 — Compaction Gossip Epoch Comparator (T2)
//! EPISTEMIC TIER: T2 (engineering hypothesis)
//!
//! Compares consecutive GossipEpochReports and records the signed delta as a
//! hash-chained GossipEpochDeltaRecord. Mirrors Gate 345 for the gossip subsystem.
//!
//! GossipEpochDeltaRecord:
//!   epoch:              u64              — the *newer* epoch
//!   prev_epoch:         u64              — the *older* epoch
//!   joint_improved:     bool             — joint_condition ordinal decreased (better)
//!   joint_worsened:     bool             — joint_condition ordinal increased (worse)
//!   chains_recovered:   bool             — prev chains_valid=false, curr=true
//!   chains_degraded:    bool             — prev chains_valid=true,  curr=false
//!   delivered_delta:    i64              — curr.total_delivered as i64 - prev.total_delivered as i64
//!   momentum_delta:     i16              — curr.momentum_int - prev.momentum_int
//!   direction_changed:  bool             — direction differs between epochs
//!   delta_hash:         [u8;32]
//!   prev_hash:          [u8;32]
//!
//! delta_hash = SHA-256(prev[32] ‖ epoch_be8 ‖ prev_epoch_be8
//!                        ‖ flags_byte ‖ delivered_delta_be8 ‖ momentum_delta_be2)
//!
//! flags_byte: bit0=joint_improved, bit1=joint_worsened, bit2=chains_recovered,
//!             bit3=chains_degraded, bit4=direction_changed
//!
//! GossipEpochComparatorLog: compare(prev_report, curr_report), improvement_count(),
//!   degradation_count(), verify_chain().

use sha2::{Sha256, Digest};
use crate::compaction_gossip_epoch_report::GossipEpochReport;

pub const GOSSIP_COMPARATOR_GENESIS_HASH: [u8; 32] = [0u8; 32];

// ─── GossipEpochDeltaRecord ───────────────────────────────────────────────────

#[derive(Debug, Clone, PartialEq)]
pub struct GossipEpochDeltaRecord {
    pub epoch:              u64,
    pub prev_epoch:         u64,
    pub joint_improved:     bool,
    pub joint_worsened:     bool,
    pub chains_recovered:   bool,
    pub chains_degraded:    bool,
    pub delivered_delta:    i64,
    pub momentum_delta:     i16,
    pub direction_changed:  bool,
    pub delta_hash:         [u8; 32],
    pub prev_hash:          [u8; 32],
}

fn flags_byte(rec: &GossipEpochDeltaRecord) -> u8 {
      (rec.joint_improved     as u8)
    | ((rec.joint_worsened    as u8) << 1)
    | ((rec.chains_recovered  as u8) << 2)
    | ((rec.chains_degraded   as u8) << 3)
    | ((rec.direction_changed as u8) << 4)
}

fn compute_delta_hash(
    prev:            &[u8; 32],
    epoch:           u64,
    prev_epoch:      u64,
    flags:           u8,
    delivered_delta: i64,
    momentum_delta:  i16,
) -> [u8; 32] {
    let mut h = Sha256::new();
    h.update(prev);
    h.update(epoch.to_be_bytes());
    h.update(prev_epoch.to_be_bytes());
    h.update([flags]);
    h.update(delivered_delta.to_be_bytes());
    h.update(momentum_delta.to_be_bytes());
    h.finalize().into()
}

// ─── GossipEpochComparatorLog ─────────────────────────────────────────────────

pub struct GossipEpochComparatorLog {
    deltas: Vec<GossipEpochDeltaRecord>,
}

impl GossipEpochComparatorLog {
    pub fn new() -> Self { Self { deltas: Vec::new() } }

    pub fn len(&self)      -> usize { self.deltas.len() }
    pub fn is_empty(&self) -> bool  { self.deltas.is_empty() }
    pub fn deltas(&self)   -> &[GossipEpochDeltaRecord] { &self.deltas }
    pub fn latest(&self)   -> Option<&GossipEpochDeltaRecord> { self.deltas.last() }

    pub fn compare(
        &mut self,
        prev_r: &GossipEpochReport,
        curr_r: &GossipEpochReport,
    ) -> &GossipEpochDeltaRecord {
        let joint_improved    = (curr_r.joint_condition as u8) < (prev_r.joint_condition as u8);
        let joint_worsened    = (curr_r.joint_condition as u8) > (prev_r.joint_condition as u8);
        let chains_recovered  = !prev_r.chains_valid &&  curr_r.chains_valid;
        let chains_degraded   =  prev_r.chains_valid && !curr_r.chains_valid;
        let delivered_delta   = curr_r.total_delivered as i64 - prev_r.total_delivered as i64;
        let momentum_delta    = curr_r.momentum_int - prev_r.momentum_int;
        let direction_changed = curr_r.direction != prev_r.direction;

        let prev_hash = self.deltas.last()
            .map(|d| d.delta_hash)
            .unwrap_or(GOSSIP_COMPARATOR_GENESIS_HASH);

        let partial = GossipEpochDeltaRecord {
            epoch: curr_r.epoch,
            prev_epoch: prev_r.epoch,
            joint_improved,
            joint_worsened,
            chains_recovered,
            chains_degraded,
            delivered_delta,
            momentum_delta,
            direction_changed,
            delta_hash: [0u8; 32],
            prev_hash,
        };
        let flags = flags_byte(&partial);

        let delta_hash = compute_delta_hash(
            &prev_hash,
            curr_r.epoch,
            prev_r.epoch,
            flags,
            delivered_delta,
            momentum_delta,
        );

        self.deltas.push(GossipEpochDeltaRecord { delta_hash, ..partial });
        self.deltas.last().unwrap()
    }

    /// Count deltas where joint_improved OR chains_recovered (positive transitions).
    pub fn improvement_count(&self) -> usize {
        self.deltas.iter().filter(|d| d.joint_improved || d.chains_recovered).count()
    }

    /// Count deltas where joint_worsened OR chains_degraded (negative transitions).
    pub fn degradation_count(&self) -> usize {
        self.deltas.iter().filter(|d| d.joint_worsened || d.chains_degraded).count()
    }

    pub fn verify_chain(&self) -> (bool, Option<usize>) {
        let mut prev = GOSSIP_COMPARATOR_GENESIS_HASH;
        for (i, d) in self.deltas.iter().enumerate() {
            if d.prev_hash != prev {
                return (false, Some(i));
            }
            let flags = flags_byte(d);
            let expected = compute_delta_hash(
                &prev,
                d.epoch,
                d.prev_epoch,
                flags,
                d.delivered_delta,
                d.momentum_delta,
            );
            if d.delta_hash != expected {
                return (false, Some(i));
            }
            prev = d.delta_hash;
        }
        (true, None)
    }
}

impl Default for GossipEpochComparatorLog {
    fn default() -> Self { Self::new() }
}

// ─── Tests ────────────────────────────────────────────────────────────────────

#[cfg(test)]
mod tests {
    use super::*;
    use crate::compaction_gossip_health_aggregator::{GossipHealthGrade, GossipJointCondition};
    use crate::compaction_gossip_momentum_tracker::GossipMomentumDir;

    fn make_report(
        epoch:           u64,
        jc:              GossipJointCondition,
        chains_valid:    bool,
        total_delivered: u64,
        direction:       GossipMomentumDir,
        momentum_int:    i16,
    ) -> GossipEpochReport {
        GossipEpochReport {
            epoch,
            joint_condition: jc,
            gossip_grade:    GossipHealthGrade::Healthy,
            total_delivered,
            chains_valid,
            direction,
            momentum_int,
            window_size:     2,
            red_pct:         0,
            yellow_pct:      0,
            green_pct:       100,
            report_hash:     [0u8; 32],
            prev_hash:       [0u8; 32],
        }
    }

    // ── Flag detection ────────────────────────────────────────────────────────

    #[test]
    fn joint_improved_detected() {
        let prev = make_report(1, GossipJointCondition::Critical, true, 0, GossipMomentumDir::Stable, 0);
        let curr = make_report(2, GossipJointCondition::Nominal,  true, 0, GossipMomentumDir::Stable, 0);
        let mut l = GossipEpochComparatorLog::new();
        let d = l.compare(&prev, &curr).clone();
        assert!(d.joint_improved);
        assert!(!d.joint_worsened);
    }

    #[test]
    fn joint_worsened_detected() {
        let prev = make_report(1, GossipJointCondition::Optimal,  true, 0, GossipMomentumDir::Stable, 0);
        let curr = make_report(2, GossipJointCondition::Degraded, true, 0, GossipMomentumDir::Stable, 0);
        let mut l = GossipEpochComparatorLog::new();
        let d = l.compare(&prev, &curr).clone();
        assert!(d.joint_worsened);
        assert!(!d.joint_improved);
    }

    #[test]
    fn no_joint_change_both_false() {
        let prev = make_report(1, GossipJointCondition::Nominal, true, 0, GossipMomentumDir::Stable, 0);
        let curr = make_report(2, GossipJointCondition::Nominal, true, 0, GossipMomentumDir::Stable, 0);
        let mut l = GossipEpochComparatorLog::new();
        let d = l.compare(&prev, &curr).clone();
        assert!(!d.joint_improved && !d.joint_worsened);
    }

    #[test]
    fn chains_recovered_detected() {
        let prev = make_report(1, GossipJointCondition::Nominal, false, 0, GossipMomentumDir::Stable, 0);
        let curr = make_report(2, GossipJointCondition::Nominal, true,  0, GossipMomentumDir::Stable, 0);
        let mut l = GossipEpochComparatorLog::new();
        let d = l.compare(&prev, &curr).clone();
        assert!(d.chains_recovered);
        assert!(!d.chains_degraded);
    }

    #[test]
    fn chains_degraded_detected() {
        let prev = make_report(1, GossipJointCondition::Nominal, true,  0, GossipMomentumDir::Stable, 0);
        let curr = make_report(2, GossipJointCondition::Nominal, false, 0, GossipMomentumDir::Stable, 0);
        let mut l = GossipEpochComparatorLog::new();
        let d = l.compare(&prev, &curr).clone();
        assert!(d.chains_degraded);
        assert!(!d.chains_recovered);
    }

    #[test]
    fn delivered_delta_signed() {
        let prev = make_report(1, GossipJointCondition::Nominal, true, 10_000, GossipMomentumDir::Stable, 0);
        let curr = make_report(2, GossipJointCondition::Nominal, true, 15_000, GossipMomentumDir::Stable, 0);
        let mut l = GossipEpochComparatorLog::new();
        let d = l.compare(&prev, &curr).clone();
        assert_eq!(d.delivered_delta, 5_000);
    }

    #[test]
    fn delivered_delta_negative() {
        let prev = make_report(1, GossipJointCondition::Nominal, true, 20_000, GossipMomentumDir::Stable, 0);
        let curr = make_report(2, GossipJointCondition::Nominal, true, 12_000, GossipMomentumDir::Stable, 0);
        let mut l = GossipEpochComparatorLog::new();
        let d = l.compare(&prev, &curr).clone();
        assert_eq!(d.delivered_delta, -8_000);
    }

    #[test]
    fn momentum_delta_computed() {
        let prev = make_report(1, GossipJointCondition::Nominal, true, 0, GossipMomentumDir::Stable, -1);
        let curr = make_report(2, GossipJointCondition::Nominal, true, 0, GossipMomentumDir::Stable,  2);
        let mut l = GossipEpochComparatorLog::new();
        let d = l.compare(&prev, &curr).clone();
        assert_eq!(d.momentum_delta, 3);
    }

    #[test]
    fn direction_changed_detected() {
        let prev = make_report(1, GossipJointCondition::Nominal, true, 0, GossipMomentumDir::Stable,    0);
        let curr = make_report(2, GossipJointCondition::Nominal, true, 0, GossipMomentumDir::Declining, 0);
        let mut l = GossipEpochComparatorLog::new();
        let d = l.compare(&prev, &curr).clone();
        assert!(d.direction_changed);
    }

    // ── Aggregation ───────────────────────────────────────────────────────────

    #[test]
    fn improvement_count() {
        let mut l = GossipEpochComparatorLog::new();
        let a = make_report(1, GossipJointCondition::Critical, false, 0, GossipMomentumDir::Stable, 0);
        let b = make_report(2, GossipJointCondition::Nominal,  true,  0, GossipMomentumDir::Stable, 0);
        let c = make_report(3, GossipJointCondition::Nominal,  true,  0, GossipMomentumDir::Stable, 0);
        l.compare(&a, &b);
        l.compare(&b, &c);
        assert_eq!(l.improvement_count(), 1);
    }

    #[test]
    fn degradation_count() {
        let mut l = GossipEpochComparatorLog::new();
        let a = make_report(1, GossipJointCondition::Optimal,  true,  0, GossipMomentumDir::Stable, 0);
        let b = make_report(2, GossipJointCondition::Critical, false, 0, GossipMomentumDir::Stable, 0);
        l.compare(&a, &b);
        assert_eq!(l.degradation_count(), 1);
    }

    // ── Chain integrity ───────────────────────────────────────────────────────

    #[test]
    fn verify_chain_empty_ok() {
        let l = GossipEpochComparatorLog::new();
        let (ok, idx) = l.verify_chain();
        assert!(ok);
        assert!(idx.is_none());
    }

    #[test]
    fn verify_chain_three_deltas_ok() {
        let mut l = GossipEpochComparatorLog::new();
        let reports: Vec<_> = (1u64..=4).map(|i| {
            make_report(i, GossipJointCondition::Nominal, true, i * 1000, GossipMomentumDir::Stable, 0)
        }).collect();
        for w in reports.windows(2) {
            l.compare(&w[0], &w[1]);
        }
        let (ok, idx) = l.verify_chain();
        assert!(ok);
        assert!(idx.is_none());
    }

    #[test]
    fn verify_chain_detects_tamper() {
        let mut l = GossipEpochComparatorLog::new();
        let a = make_report(1, GossipJointCondition::Nominal, true, 1_000, GossipMomentumDir::Stable, 0);
        let b = make_report(2, GossipJointCondition::Nominal, true, 2_000, GossipMomentumDir::Stable, 0);
        l.compare(&a, &b);
        l.deltas[0].delta_hash[0] ^= 0xFF;
        let (ok, idx) = l.verify_chain();
        assert!(!ok);
        assert_eq!(idx, Some(0));
    }

    #[test]
    fn delta_hash_deterministic() {
        let mut l1 = GossipEpochComparatorLog::new();
        let mut l2 = GossipEpochComparatorLog::new();
        let a = make_report(1, GossipJointCondition::Degraded, true, 5_000, GossipMomentumDir::Declining, -1);
        let b = make_report(2, GossipJointCondition::Nominal,  true, 8_000, GossipMomentumDir::Stable,     1);
        l1.compare(&a, &b);
        l2.compare(&a, &b);
        assert_eq!(l1.deltas[0].delta_hash, l2.deltas[0].delta_hash);
    }
}
