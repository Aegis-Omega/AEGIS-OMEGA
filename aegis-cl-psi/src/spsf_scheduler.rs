//! Gate 330 — SPSF Compaction Scheduler (T2)
//! EPISTEMIC TIER: T2 (engineering hypothesis)
//!
//! Policy layer that determines WHEN to compact the SPSF entry log.
//! Decides based on two independent trigger conditions:
//!
//!   1. ENTRY_COUNT trigger: total entry count ≥ COMPACT_ENTRY_THRESHOLD (default 1000)
//!   2. EPOCH_AGE trigger:   current_epoch - last_compaction_epoch ≥ COMPACT_EPOCH_INTERVAL (default 50)
//!
//! Both triggers are evaluated independently; either alone is sufficient to schedule.
//!
//! CompactionPlan:
//!   triggered:              bool  — whether compaction is advised this epoch
//!   trigger_reason:         TriggerReason — EntryCount / EpochAge / Both / None
//!   recommended_retain:     usize — max(MIN_RETAIN, total - PRUNE_TARGET_SIZE)
//!   plan_epoch:             u64
//!   total_entries:          usize
//!   last_compaction_epoch:  u64
//!   plan_hash:              SHA-256(plan_epoch_be8 ‖ trigger_byte ‖ recommended_retain_be8
//!                                   ‖ total_entries_be8 ‖ last_epoch_be8)
//!
//! SchedulerLog: hash-chained CompactionPlanRecords — audit trail for all schedule evaluations.
//!   evaluate(), latest(), triggered_count(), verify_chain().
//!
//! Constants:
//!   COMPACT_ENTRY_THRESHOLD = 1000  — trigger compaction when entry count reaches this
//!   COMPACT_EPOCH_INTERVAL  = 50    — trigger compaction every N epochs regardless of count
//!   PRUNE_TARGET_SIZE       = 200   — target retained count after compaction
//!   MIN_RETAIN              = 10    — never retain fewer than this many entries

use sha2::{Sha256, Digest};

pub const SCHEDULER_GENESIS_HASH: [u8; 32] = [0u8; 32];

pub const COMPACT_ENTRY_THRESHOLD: usize = 1000;
pub const COMPACT_EPOCH_INTERVAL:  u64   = 50;
pub const PRUNE_TARGET_SIZE:       usize = 200;
pub const MIN_RETAIN:              usize = 10;

// ─── TriggerReason ───────────────────────────────────────────────────────────

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum TriggerReason {
    None       = 0,
    EntryCount = 1,
    EpochAge   = 2,
    Both       = 3,
}

impl TriggerReason {
    pub fn byte(self) -> u8 { self as u8 }

    pub fn from_flags(entry: bool, epoch: bool) -> Self {
        match (entry, epoch) {
            (false, false) => TriggerReason::None,
            (true,  false) => TriggerReason::EntryCount,
            (false, true)  => TriggerReason::EpochAge,
            (true,  true)  => TriggerReason::Both,
        }
    }
}

// ─── CompactionPlan ──────────────────────────────────────────────────────────

/// A scheduling decision for one epoch evaluation.
#[derive(Debug, Clone, PartialEq)]
pub struct CompactionPlan {
    pub triggered:             bool,
    pub trigger_reason:        TriggerReason,
    pub recommended_retain:    usize,
    pub plan_epoch:            u64,
    pub total_entries:         usize,
    pub last_compaction_epoch: u64,
    pub plan_hash:             [u8; 32],
}

fn compute_plan_hash(
    plan_epoch:            u64,
    trigger_reason:        TriggerReason,
    recommended_retain:    usize,
    total_entries:         usize,
    last_compaction_epoch: u64,
) -> [u8; 32] {
    let mut h = Sha256::new();
    h.update(plan_epoch.to_be_bytes());
    h.update([trigger_reason.byte()]);
    h.update((recommended_retain as u64).to_be_bytes());
    h.update((total_entries as u64).to_be_bytes());
    h.update(last_compaction_epoch.to_be_bytes());
    h.finalize().into()
}

/// Evaluate whether compaction should be scheduled this epoch.
///
/// - `current_epoch`: the epoch being evaluated
/// - `total_entries`: current SPSF entry count
/// - `last_compaction_epoch`: epoch of the most recent compaction (0 if never compacted)
pub fn evaluate(
    current_epoch:         u64,
    total_entries:         usize,
    last_compaction_epoch: u64,
) -> CompactionPlan {
    let entry_trigger = total_entries >= COMPACT_ENTRY_THRESHOLD;
    let epoch_trigger = current_epoch.saturating_sub(last_compaction_epoch) >= COMPACT_EPOCH_INTERVAL;
    let trigger_reason = TriggerReason::from_flags(entry_trigger, epoch_trigger);
    let triggered = trigger_reason != TriggerReason::None;

    // Recommended retain: max(MIN_RETAIN, total - PRUNE_TARGET_SIZE), clamped to total.
    // saturating_sub: when total <= PRUNE_TARGET_SIZE, naive=0, then floor lifts to MIN_RETAIN.
    let recommended_retain = if triggered {
        let naive = total_entries.saturating_sub(PRUNE_TARGET_SIZE);
        naive.max(MIN_RETAIN).min(total_entries)
    } else {
        total_entries // no compaction — retain all
    };

    let plan_hash = compute_plan_hash(
        current_epoch,
        trigger_reason,
        recommended_retain,
        total_entries,
        last_compaction_epoch,
    );

    CompactionPlan {
        triggered,
        trigger_reason,
        recommended_retain,
        plan_epoch:            current_epoch,
        total_entries,
        last_compaction_epoch,
        plan_hash,
    }
}

// ─── CompactionPlanRecord ────────────────────────────────────────────────────

/// One hash-chained audit record for one schedule evaluation.
#[derive(Debug, Clone, PartialEq)]
pub struct CompactionPlanRecord {
    pub plan_epoch:     u64,
    pub triggered:      bool,
    pub trigger_reason: TriggerReason,
    pub total_entries:  usize,
    pub plan_hash:      [u8; 32],
    pub record_hash:    [u8; 32],
    pub prev_hash:      [u8; 32],
}

fn compute_record_hash(
    prev:           &[u8; 32],
    plan_epoch:     u64,
    triggered:      bool,
    trigger_reason: TriggerReason,
    total_entries:  usize,
    plan_hash:      &[u8; 32],
) -> [u8; 32] {
    let mut h = Sha256::new();
    h.update(prev);
    h.update(plan_epoch.to_be_bytes());
    h.update([triggered as u8]);
    h.update([trigger_reason.byte()]);
    h.update((total_entries as u64).to_be_bytes());
    h.update(plan_hash);
    h.finalize().into()
}

// ─── SchedulerLog ────────────────────────────────────────────────────────────

/// Append-only hash-chained audit log of compaction scheduling decisions.
pub struct SchedulerLog {
    records: Vec<CompactionPlanRecord>,
}

impl SchedulerLog {
    pub fn new() -> Self { Self { records: Vec::new() } }

    pub fn len(&self)      -> usize { self.records.len() }
    pub fn is_empty(&self) -> bool  { self.records.is_empty() }
    pub fn records(&self)  -> &[CompactionPlanRecord] { &self.records }

    /// Record a scheduling evaluation result.
    pub fn append(&mut self, plan: &CompactionPlan) -> CompactionPlanRecord {
        let prev = self.records.last()
            .map(|r| r.record_hash)
            .unwrap_or(SCHEDULER_GENESIS_HASH);

        let record_hash = compute_record_hash(
            &prev,
            plan.plan_epoch,
            plan.triggered,
            plan.trigger_reason,
            plan.total_entries,
            &plan.plan_hash,
        );

        let rec = CompactionPlanRecord {
            plan_epoch:     plan.plan_epoch,
            triggered:      plan.triggered,
            trigger_reason: plan.trigger_reason,
            total_entries:  plan.total_entries,
            plan_hash:      plan.plan_hash,
            record_hash,
            prev_hash:      prev,
        };
        self.records.push(rec.clone());
        rec
    }

    /// Count of evaluations that triggered compaction.
    pub fn triggered_count(&self) -> usize {
        self.records.iter().filter(|r| r.triggered).count()
    }

    /// Latest record, or `None` if empty.
    pub fn latest(&self) -> Option<&CompactionPlanRecord> {
        self.records.last()
    }

    /// Verify hash chain integrity.
    pub fn verify_chain(&self) -> (bool, Option<usize>) {
        let mut prev = SCHEDULER_GENESIS_HASH;
        for (i, r) in self.records.iter().enumerate() {
            if r.prev_hash != prev {
                return (false, Some(i));
            }
            let expected = compute_record_hash(
                &prev,
                r.plan_epoch,
                r.triggered,
                r.trigger_reason,
                r.total_entries,
                &r.plan_hash,
            );
            if r.record_hash != expected {
                return (false, Some(i));
            }
            prev = r.record_hash;
        }
        (true, None)
    }
}

impl Default for SchedulerLog {
    fn default() -> Self { Self::new() }
}

// ─── Tests ────────────────────────────────────────────────────────────────────

#[cfg(test)]
mod tests {
    use super::*;

    // ── Constants ─────────────────────────────────────────────────────────────

    #[test]
    fn constants_sane() {
        assert_eq!(COMPACT_ENTRY_THRESHOLD, 1000);
        assert_eq!(COMPACT_EPOCH_INTERVAL,  50);
        assert_eq!(PRUNE_TARGET_SIZE,       200);
        assert_eq!(MIN_RETAIN,              10);
    }

    // ── TriggerReason ─────────────────────────────────────────────────────────

    #[test]
    fn trigger_reason_from_flags() {
        assert_eq!(TriggerReason::from_flags(false, false), TriggerReason::None);
        assert_eq!(TriggerReason::from_flags(true,  false), TriggerReason::EntryCount);
        assert_eq!(TriggerReason::from_flags(false, true),  TriggerReason::EpochAge);
        assert_eq!(TriggerReason::from_flags(true,  true),  TriggerReason::Both);
    }

    // ── evaluate() — no trigger ───────────────────────────────────────────────

    #[test]
    fn no_trigger_below_both_thresholds() {
        let p = evaluate(10, 500, 0); // entries < 1000; epoch_age=10 < 50
        assert!(!p.triggered);
        assert_eq!(p.trigger_reason, TriggerReason::None);
        assert_eq!(p.recommended_retain, 500);
    }

    #[test]
    fn no_trigger_exactly_one_below_entry() {
        let p = evaluate(51, 999, 0); // entries=999 < 1000; epoch_age=51 ≥ 50
        // epoch_age trigger fires
        assert!(p.triggered);
        assert_eq!(p.trigger_reason, TriggerReason::EpochAge);
    }

    // ── evaluate() — entry count trigger ─────────────────────────────────────

    #[test]
    fn entry_count_trigger_at_threshold() {
        let p = evaluate(5, 1000, 0); // entries=1000 >= 1000; epoch_age=5 < 50
        assert!(p.triggered);
        assert_eq!(p.trigger_reason, TriggerReason::EntryCount);
    }

    #[test]
    fn entry_count_trigger_above_threshold() {
        let p = evaluate(5, 1500, 3); // entries=1500 >= 1000; epoch_age=2 < 50
        assert!(p.triggered);
        assert_eq!(p.trigger_reason, TriggerReason::EntryCount);
        // recommended_retain = max(10, 1500-200) = 1300; but we KEEP that many, so retain=1300
        assert_eq!(p.recommended_retain, 1300);
    }

    // ── evaluate() — epoch age trigger ───────────────────────────────────────

    #[test]
    fn epoch_age_trigger_at_interval() {
        let p = evaluate(50, 100, 0); // entries=100 < 1000; epoch_age=50 >= 50
        assert!(p.triggered);
        assert_eq!(p.trigger_reason, TriggerReason::EpochAge);
    }

    #[test]
    fn epoch_age_trigger_above_interval() {
        let p = evaluate(200, 50, 100); // epoch_age=100 >= 50; entries=50 < 1000
        assert!(p.triggered);
        assert_eq!(p.trigger_reason, TriggerReason::EpochAge);
    }

    // ── evaluate() — both triggers ────────────────────────────────────────────

    #[test]
    fn both_triggers_fire() {
        let p = evaluate(100, 2000, 0); // entries=2000 >= 1000; epoch_age=100 >= 50
        assert!(p.triggered);
        assert_eq!(p.trigger_reason, TriggerReason::Both);
    }

    // ── recommended_retain ────────────────────────────────────────────────────

    #[test]
    fn recommended_retain_prune_to_target() {
        // 1000 entries → retain 1000-200=800
        let p = evaluate(5, 1000, 0);
        assert_eq!(p.recommended_retain, 800);
    }

    #[test]
    fn recommended_retain_min_floor() {
        // 15 entries → trigger epoch_age; retain = max(10, 15-200)=max(10,0)=10
        let p = evaluate(100, 15, 0);
        assert_eq!(p.recommended_retain, 10);
    }

    #[test]
    fn recommended_retain_clamps_to_total() {
        // 5 entries, MIN_RETAIN=10 → clamp to total=5
        let p = evaluate(100, 5, 0);
        assert_eq!(p.recommended_retain, 5); // can't retain more than total
    }

    // ── plan_hash ─────────────────────────────────────────────────────────────

    #[test]
    fn plan_hash_nonzero() {
        let p = evaluate(5, 1000, 0);
        assert_ne!(p.plan_hash, [0u8; 32]);
    }

    #[test]
    fn plan_hash_deterministic() {
        let p1 = evaluate(5, 1000, 0);
        let p2 = evaluate(5, 1000, 0);
        let p3 = evaluate(5, 1000, 0);
        assert_eq!(p1.plan_hash, p2.plan_hash);
        assert_eq!(p2.plan_hash, p3.plan_hash);
    }

    #[test]
    fn different_epoch_different_plan_hash() {
        let p1 = evaluate(5, 1000, 0);
        let p2 = evaluate(6, 1000, 0);
        assert_ne!(p1.plan_hash, p2.plan_hash);
    }

    // ── SchedulerLog ──────────────────────────────────────────────────────────

    #[test]
    fn fresh_log_empty() {
        let l = SchedulerLog::new();
        assert!(l.is_empty());
        assert_eq!(l.triggered_count(), 0);
    }

    #[test]
    fn log_chains_two_records() {
        let mut l = SchedulerLog::new();
        let p1 = evaluate(5,   1000, 0);
        let p2 = evaluate(55,  500,  5);
        let r1 = l.append(&p1);
        let r2 = l.append(&p2);
        assert_eq!(r2.prev_hash, r1.record_hash);
        assert_eq!(l.triggered_count(), 2); // both triggered
    }

    #[test]
    fn log_triggered_count() {
        let mut l = SchedulerLog::new();
        l.append(&evaluate(5, 1000, 0)); // triggered
        l.append(&evaluate(10, 100, 0)); // not triggered (100<1000, age=10<50)
        l.append(&evaluate(60, 1500, 0)); // triggered
        assert_eq!(l.triggered_count(), 2);
    }

    #[test]
    fn log_verify_chain_empty_ok() {
        let l = SchedulerLog::new();
        let (ok, idx) = l.verify_chain();
        assert!(ok);
        assert!(idx.is_none());
    }

    #[test]
    fn log_verify_chain_three_records_ok() {
        let mut l = SchedulerLog::new();
        for epoch in [5u64, 55, 105] {
            let p = evaluate(epoch, 1000, 0);
            l.append(&p);
        }
        let (ok, idx) = l.verify_chain();
        assert!(ok);
        assert!(idx.is_none());
    }

    #[test]
    fn log_verify_chain_tamper_detected() {
        let mut l = SchedulerLog::new();
        let p = evaluate(5, 1000, 0);
        l.append(&p);
        l.records[0].triggered = false; // tamper
        let (ok, idx) = l.verify_chain();
        assert!(!ok);
        assert_eq!(idx, Some(0));
    }

    #[test]
    fn log_latest() {
        let mut l = SchedulerLog::new();
        let p1 = evaluate(5, 1000, 0);
        let p2 = evaluate(55, 500, 5);
        l.append(&p1);
        let r2 = l.append(&p2);
        assert_eq!(l.latest().unwrap().record_hash, r2.record_hash);
    }
}
