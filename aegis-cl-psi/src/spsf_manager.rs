//! Gate 331 — SPSF Integrated Manager (T2)
//! EPISTEMIC TIER: T2 (engineering hypothesis)
//!
//! Unified facade wiring the SPSF compaction trilogy together:
//!   Gate 328 spsf_compactor — compact()
//!   Gate 329 spsf_verifier  — verify_suffix()
//!   Gate 330 spsf_scheduler — evaluate()
//!
//! SpsfManager lifecycle per epoch:
//!   1. ingest(sequence_id, state_hash) — append a new SPSF entry
//!   2. tick(current_epoch)             — evaluate schedule, compact if advised,
//!                                        verify the retained suffix, record all outcomes
//!   3. manager_hash()                  — SHA-256 over (scheduler, compaction, verification)
//!                                        terminal hashes — tamper-evident cross-module seal
//!
//! Management record per tick:
//!   epoch, compacted: bool, plan_triggered: bool,
//!   pruned_count, retained_count, verify_verdict,
//!   manager_hash, prev_hash
//!
//! ManagementLog: hash-chained ManagementRecords — full audit of all ticks.
//!   tick(), total_compacted_entries(), verify_chain().

use sha2::{Sha256, Digest};
use crate::spsf_compactor::{CompactionAnchor, CompactionInput, CompactionLog,
                             COMPACTOR_GENESIS_HASH, compact};
use crate::spsf_verifier::{VerificationLog, VerificationVerdict, verify_suffix};
use crate::spsf_scheduler::{SchedulerLog, evaluate};

pub const MANAGER_GENESIS_HASH: [u8; 32] = [0u8; 32];

// ─── ManagementRecord ────────────────────────────────────────────────────────

/// One hash-chained audit record produced by a single `tick()` call.
#[derive(Debug, Clone, PartialEq)]
pub struct ManagementRecord {
    pub epoch:           u64,
    pub compacted:       bool,
    pub plan_triggered:  bool,
    pub pruned_count:    usize,
    pub retained_count:  usize,
    pub verify_verdict:  VerificationVerdict,
    pub record_hash:     [u8; 32],
    pub prev_hash:       [u8; 32],
}

fn compute_record_hash(
    prev:           &[u8; 32],
    epoch:          u64,
    compacted:      bool,
    plan_triggered: bool,
    pruned_count:   usize,
    retained_count: usize,
    verdict:        VerificationVerdict,
) -> [u8; 32] {
    let mut h = Sha256::new();
    h.update(prev);
    h.update(epoch.to_be_bytes());
    h.update([compacted as u8, plan_triggered as u8]);
    h.update((pruned_count as u64).to_be_bytes());
    h.update((retained_count as u64).to_be_bytes());
    h.update([verdict.byte()]);
    h.finalize().into()
}

// ─── ManagementLog ───────────────────────────────────────────────────────────

pub struct ManagementLog {
    records: Vec<ManagementRecord>,
}

impl ManagementLog {
    pub fn new() -> Self { Self { records: Vec::new() } }

    pub fn len(&self)      -> usize { self.records.len() }
    pub fn is_empty(&self) -> bool  { self.records.is_empty() }
    pub fn records(&self)  -> &[ManagementRecord] { &self.records }

    fn append_inner(
        &mut self,
        epoch:          u64,
        compacted:      bool,
        plan_triggered: bool,
        pruned_count:   usize,
        retained_count: usize,
        verdict:        VerificationVerdict,
    ) -> ManagementRecord {
        let prev = self.records.last()
            .map(|r| r.record_hash)
            .unwrap_or(MANAGER_GENESIS_HASH);

        let record_hash = compute_record_hash(
            &prev, epoch, compacted, plan_triggered,
            pruned_count, retained_count, verdict,
        );

        let rec = ManagementRecord {
            epoch, compacted, plan_triggered, pruned_count,
            retained_count, verify_verdict: verdict, record_hash, prev_hash: prev,
        };
        self.records.push(rec.clone());
        rec
    }

    pub fn latest(&self) -> Option<&ManagementRecord> { self.records.last() }

    /// Total entries pruned across all compaction ticks.
    pub fn total_compacted_entries(&self) -> usize {
        self.records.iter()
            .filter(|r| r.compacted)
            .map(|r| r.pruned_count)
            .sum()
    }

    pub fn verify_chain(&self) -> (bool, Option<usize>) {
        let mut prev = MANAGER_GENESIS_HASH;
        for (i, r) in self.records.iter().enumerate() {
            if r.prev_hash != prev {
                return (false, Some(i));
            }
            let expected = compute_record_hash(
                &prev, r.epoch, r.compacted, r.plan_triggered,
                r.pruned_count, r.retained_count, r.verify_verdict,
            );
            if r.record_hash != expected {
                return (false, Some(i));
            }
            prev = r.record_hash;
        }
        (true, None)
    }
}

impl Default for ManagementLog {
    fn default() -> Self { Self::new() }
}

// ─── SpsfManager ─────────────────────────────────────────────────────────────

/// Unified SPSF lifecycle manager.
pub struct SpsfManager {
    /// Live entry buffer (sequence_id, state_hash), ascending.
    entries:               Vec<(u64, [u8; 32])>,
    /// Most recent compaction anchor (genesis if never compacted).
    current_anchor:        CompactionAnchor,
    /// Epoch of last compaction (0 if never compacted).
    last_compaction_epoch: u64,
    /// Sub-module audit logs.
    scheduler_log:         SchedulerLog,
    compaction_log:        CompactionLog,
    verification_log:      VerificationLog,
    /// Top-level management log.
    management_log:        ManagementLog,
}

impl SpsfManager {
    /// Create a new manager with an empty entry buffer.
    pub fn new() -> Self {
        Self {
            entries:               Vec::new(),
            current_anchor:        CompactionAnchor {
                anchor_sequence: 0,
                terminal_hash:   COMPACTOR_GENESIS_HASH,
                entry_count:     0,
            },
            last_compaction_epoch: 0,
            scheduler_log:         SchedulerLog::new(),
            compaction_log:        CompactionLog::new(),
            verification_log:      VerificationLog::new(),
            management_log:        ManagementLog::new(),
        }
    }

    // ── Accessors ─────────────────────────────────────────────────────────────

    pub fn entry_count(&self) -> usize { self.entries.len() }
    pub fn last_compaction_epoch(&self) -> u64 { self.last_compaction_epoch }
    pub fn current_anchor(&self) -> &CompactionAnchor { &self.current_anchor }
    pub fn management_log(&self) -> &ManagementLog { &self.management_log }
    pub fn scheduler_log(&self) -> &SchedulerLog { &self.scheduler_log }
    pub fn compaction_log(&self) -> &CompactionLog { &self.compaction_log }
    pub fn verification_log(&self) -> &VerificationLog { &self.verification_log }

    // ── Ingest ────────────────────────────────────────────────────────────────

    /// Append a new SPSF entry. Caller must supply strictly ascending sequence_ids.
    /// Returns `Err` if sequence_id ≤ last ingested sequence_id.
    pub fn ingest(&mut self, sequence_id: u64, state_hash: [u8; 32]) -> Result<(), &'static str> {
        if let Some(last) = self.entries.last() {
            if sequence_id <= last.0 {
                return Err("[SPSF_MANAGER] non-monotone sequence_id");
            }
        }
        self.entries.push((sequence_id, state_hash));
        Ok(())
    }

    // ── Tick ──────────────────────────────────────────────────────────────────

    /// Evaluate schedule for `current_epoch`; compact and verify if advised.
    /// Returns the ManagementRecord for this tick.
    pub fn tick(&mut self, current_epoch: u64) -> ManagementRecord {
        let plan = evaluate(
            current_epoch,
            self.entries.len(),
            self.last_compaction_epoch,
        );
        self.scheduler_log.append(&plan);

        if plan.triggered {
            // Execute compaction.
            let result = compact(CompactionInput {
                entries:          self.entries.clone(),
                retain_count:     plan.recommended_retain,
                compaction_epoch: current_epoch,
            });

            let pruned  = result.pruned_count;
            let retained = result.retained_count;

            // Update retained entries and anchor.
            let pruned_idx = pruned;
            self.entries = self.entries[pruned_idx..].to_vec();
            self.current_anchor = result.anchor.clone();
            self.last_compaction_epoch = current_epoch;
            self.compaction_log.record(&result);

            // Verify the retained suffix against the new anchor.
            let verify_result = verify_suffix(&self.current_anchor, &self.entries);
            let verdict = verify_result.verdict;
            self.verification_log.append(&self.current_anchor, &verify_result);

            self.management_log.append_inner(
                current_epoch, true, true, pruned, retained, verdict,
            )
        } else {
            // No compaction — still verify current suffix for integrity.
            let verify_result = verify_suffix(&self.current_anchor, &self.entries);
            let verdict = verify_result.verdict;
            self.verification_log.append(&self.current_anchor, &verify_result);

            self.management_log.append_inner(
                current_epoch, false, false, 0, self.entries.len(), verdict,
            )
        }
    }

    // ── Manager Hash ──────────────────────────────────────────────────────────

    /// Cross-module tamper-evident seal: SHA-256 over the three sub-log terminal hashes.
    pub fn manager_hash(&self) -> [u8; 32] {
        let sched_term = self.scheduler_log.latest()
            .map(|r| r.record_hash)
            .unwrap_or(MANAGER_GENESIS_HASH);
        let comp_term = self.compaction_log.latest()
            .map(|r| r.record_hash)
            .unwrap_or(MANAGER_GENESIS_HASH);
        let verif_term = self.verification_log.latest()
            .map(|r| r.record_hash)
            .unwrap_or(MANAGER_GENESIS_HASH);

        let mut h = Sha256::new();
        h.update(sched_term);
        h.update(comp_term);
        h.update(verif_term);
        h.finalize().into()
    }
}

impl Default for SpsfManager {
    fn default() -> Self { Self::new() }
}

// ─── Tests ────────────────────────────────────────────────────────────────────

#[cfg(test)]
mod tests {
    use super::*;

    fn state_hash(seed: u8) -> [u8; 32] {
        let mut h = [0u8; 32];
        h[0] = seed; h[31] = seed.wrapping_mul(7);
        h
    }

    fn manager_with_entries(n: u64) -> SpsfManager {
        let mut m = SpsfManager::new();
        for i in 1..=n {
            m.ingest(i, state_hash(i as u8)).unwrap();
        }
        m
    }

    // ── ingest ────────────────────────────────────────────────────────────────

    #[test]
    fn ingest_monotone_ok() {
        let mut m = SpsfManager::new();
        assert!(m.ingest(1, state_hash(1)).is_ok());
        assert!(m.ingest(2, state_hash(2)).is_ok());
        assert!(m.ingest(5, state_hash(5)).is_ok()); // gaps allowed
        assert_eq!(m.entry_count(), 3);
    }

    #[test]
    fn ingest_non_monotone_rejected() {
        let mut m = SpsfManager::new();
        m.ingest(5, state_hash(5)).unwrap();
        assert!(m.ingest(3, state_hash(3)).is_err());
        assert!(m.ingest(5, state_hash(5)).is_err()); // equal is also rejected
    }

    // ── tick — no compaction ──────────────────────────────────────────────────

    #[test]
    fn tick_no_compaction_below_thresholds() {
        let mut m = manager_with_entries(100);
        let rec = m.tick(10); // 100 entries < 1000; epoch_age=10 < 50
        assert!(!rec.compacted);
        assert!(!rec.plan_triggered);
        assert_eq!(rec.pruned_count, 0);
        assert_eq!(rec.retained_count, 100);
        // Genesis anchor (entry_count=0) + non-empty suffix → Verified
        assert_eq!(rec.verify_verdict, VerificationVerdict::Verified);
    }

    #[test]
    fn tick_no_compaction_verifies_current_suffix() {
        let mut m = manager_with_entries(50);
        let rec = m.tick(10);
        assert!(!rec.compacted);
        // Genesis anchor (entry_count=0) + 50 non-empty entries → Verified
        assert_eq!(rec.verify_verdict, VerificationVerdict::Verified);
    }

    // ── tick — with compaction ────────────────────────────────────────────────

    #[test]
    fn tick_compaction_triggered_by_epoch_age() {
        let mut m = manager_with_entries(200);
        let rec = m.tick(50); // epoch_age=50 >= 50
        assert!(rec.compacted);
        assert!(rec.plan_triggered);
        assert!(rec.pruned_count > 0);
    }

    #[test]
    fn tick_compaction_triggered_by_entry_count() {
        let mut m = manager_with_entries(1000);
        let rec = m.tick(5); // 1000 entries >= 1000
        assert!(rec.compacted);
        assert!(rec.plan_triggered);
        // recommended_retain = max(10, 1000-200) = 800; prune = 1000-800 = 200
        assert_eq!(rec.pruned_count, 200);
        assert_eq!(rec.retained_count, 800);
    }

    #[test]
    fn tick_compaction_reduces_entry_count() {
        let mut m = manager_with_entries(1000);
        assert_eq!(m.entry_count(), 1000);
        m.tick(5);
        assert!(m.entry_count() < 1000);
    }

    #[test]
    fn tick_compaction_updates_anchor() {
        let mut m = manager_with_entries(1000);
        assert_eq!(m.current_anchor().entry_count, 0); // genesis
        m.tick(5);
        assert!(m.current_anchor().entry_count > 0);
        assert_ne!(m.current_anchor().terminal_hash, COMPACTOR_GENESIS_HASH);
    }

    #[test]
    fn tick_compaction_verdict_verified() {
        let mut m = manager_with_entries(1000);
        let rec = m.tick(5);
        assert!(rec.compacted);
        assert_eq!(rec.verify_verdict, VerificationVerdict::Verified);
    }

    #[test]
    fn tick_updates_last_compaction_epoch() {
        let mut m = manager_with_entries(1000);
        assert_eq!(m.last_compaction_epoch(), 0);
        m.tick(5);
        assert_eq!(m.last_compaction_epoch(), 5);
    }

    // ── multiple ticks ────────────────────────────────────────────────────────

    #[test]
    fn multiple_ticks_management_log_chains() {
        let mut m = manager_with_entries(500);
        m.tick(10);
        m.tick(20);
        m.tick(60); // epoch_age=60 >= 50 → triggers
        let (ok, idx) = m.management_log().verify_chain();
        assert!(ok);
        assert!(idx.is_none());
        assert_eq!(m.management_log().len(), 3);
    }

    #[test]
    fn total_compacted_entries_accumulates() {
        let mut m = manager_with_entries(1000);
        m.tick(5); // compacts 200 entries (prune 200, retain 800)
        // Add more and compact again
        for i in 1001..=2001u64 {
            m.ingest(i, state_hash((i % 256) as u8)).unwrap();
        }
        m.tick(10); // another 200 compacted
        assert!(m.management_log().total_compacted_entries() > 0);
    }

    // ── manager_hash ──────────────────────────────────────────────────────────

    #[test]
    fn manager_hash_nonzero_after_ticks() {
        let mut m = manager_with_entries(1000);
        m.tick(5);
        assert_ne!(m.manager_hash(), [0u8; 32]);
    }

    #[test]
    fn manager_hash_deterministic() {
        // Two managers with the same operations produce the same hash
        let mut m1 = manager_with_entries(1000);
        let mut m2 = manager_with_entries(1000);
        m1.tick(5);
        m2.tick(5);
        assert_eq!(m1.manager_hash(), m2.manager_hash());
    }

    #[test]
    fn manager_hash_differs_after_different_ticks() {
        let mut m1 = manager_with_entries(1000);
        let mut m2 = manager_with_entries(1000);
        m1.tick(5);
        m2.tick(50); // different epoch
        assert_ne!(m1.manager_hash(), m2.manager_hash());
    }

    // ── sub-log integrity ─────────────────────────────────────────────────────

    #[test]
    fn scheduler_log_verify_chain_after_ticks() {
        let mut m = manager_with_entries(500);
        for epoch in [10u64, 20, 60] { m.tick(epoch); }
        let (ok, _) = m.scheduler_log().verify_chain();
        assert!(ok);
    }

    #[test]
    fn verification_log_verify_chain_after_ticks() {
        let mut m = manager_with_entries(1000);
        m.tick(5);
        m.tick(10);
        let (ok, _) = m.verification_log().verify_chain();
        assert!(ok);
    }
}
