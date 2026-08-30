//! Gate 333 — Resonance Chain Compactor (T2)
//! EPISTEMIC TIER: T2 (engineering hypothesis)
//!
//! Applies proof-preserving compaction (Gate 328 pattern) to the ResonanceChain
//! (Gate 321). Long-running epoch sequences cause the resonance anchor ledger to
//! grow without bound; this gate prunes old records while sealing them in a
//! ResonanceAnchor that preserves the proof-of-history.
//!
//! ResonanceAnchor:
//!   anchor_sequence:   u64      — highest sequence_id in the pruned set
//!   terminal_hash:     [u8;32]  — SHA-256 chain over pruned entries
//!   entry_count:       u64
//!   certified_count:   u64      — count of certified_constitutional=true in pruned set
//!   any_resonant:      bool     — true if any is_resonant=true was pruned
//!
//! Chain per entry: acc = SHA-256(acc ‖ sequence_id_be8 ‖ report_hash ‖ is_resonant_byte ‖ certified_byte)
//!
//! ResonanceCompactionResult:
//!   compaction_epoch, pruned_count, retained_count, anchor, certificate_hash
//!   certificate_hash = SHA-256(epoch_be8 ‖ pruned_be8 ‖ retained_be8
//!                               ‖ anchor.terminal_hash ‖ anchor_seq_be8
//!                               ‖ anchor.certified_count_be8 ‖ any_resonant_byte)
//!
//! ResonanceCompactionLog: hash-chained audit trail. verify_chain(), total_pruned().

use sha2::{Sha256, Digest};
use crate::resonance_anchor::AnchoredResonanceReport;

pub const RESONANCE_COMPACTOR_GENESIS_HASH: [u8; 32] = [0u8; 32];

// ─── ResonanceAnchor ──────────────────────────────────────────────────────────

/// Cryptographic anchor sealing a pruned resonance record prefix.
#[derive(Debug, Clone, PartialEq)]
pub struct ResonanceAnchor {
    pub anchor_sequence:  u64,
    pub terminal_hash:    [u8; 32],
    pub entry_count:      u64,
    pub certified_count:  u64,
    pub any_resonant:     bool,
}

impl ResonanceAnchor {
    /// Build anchor from a pruned slice of AnchoredResonanceReports.
    pub fn from_pruned(pruned: &[AnchoredResonanceReport]) -> Self {
        if pruned.is_empty() {
            return ResonanceAnchor {
                anchor_sequence:  0,
                terminal_hash:    RESONANCE_COMPACTOR_GENESIS_HASH,
                entry_count:      0,
                certified_count:  0,
                any_resonant:     false,
            };
        }

        let mut acc              = RESONANCE_COMPACTOR_GENESIS_HASH;
        let mut certified_count  = 0u64;
        let mut any_resonant     = false;

        for rec in pruned {
            let mut h = Sha256::new();
            h.update(acc);
            h.update(rec.sequence_id.to_be_bytes());
            h.update(rec.report_hash);
            h.update([rec.is_resonant as u8, rec.certified_constitutional as u8]);
            acc = h.finalize().into();

            if rec.certified_constitutional { certified_count += 1; }
            if rec.is_resonant              { any_resonant = true; }
        }

        ResonanceAnchor {
            anchor_sequence:  pruned.last().unwrap().sequence_id,
            terminal_hash:    acc,
            entry_count:      pruned.len() as u64,
            certified_count,
            any_resonant,
        }
    }
}

// ─── ResonanceCompactionInput ─────────────────────────────────────────────────

#[derive(Clone)]
pub struct ResonanceCompactionInput {
    pub records:          Vec<AnchoredResonanceReport>,
    pub retain_count:     usize,
    pub compaction_epoch: u64,
}

// ─── ResonanceCompactionResult ────────────────────────────────────────────────

#[derive(Debug, Clone, PartialEq)]
pub struct ResonanceCompactionResult {
    pub compaction_epoch: u64,
    pub pruned_count:     usize,
    pub retained_count:   usize,
    pub anchor:           ResonanceAnchor,
    pub certificate_hash: [u8; 32],
}

fn compute_certificate_hash(
    compaction_epoch: u64,
    pruned_count:     usize,
    retained_count:   usize,
    anchor:           &ResonanceAnchor,
) -> [u8; 32] {
    let mut h = Sha256::new();
    h.update(compaction_epoch.to_be_bytes());
    h.update((pruned_count as u64).to_be_bytes());
    h.update((retained_count as u64).to_be_bytes());
    h.update(anchor.terminal_hash);
    h.update(anchor.anchor_sequence.to_be_bytes());
    h.update(anchor.certified_count.to_be_bytes());
    h.update([anchor.any_resonant as u8]);
    h.finalize().into()
}

/// Execute compaction on the given resonance chain input.
pub fn compact_resonance(inp: ResonanceCompactionInput) -> ResonanceCompactionResult {
    let total          = inp.records.len();
    let pruned_count   = if inp.retain_count >= total { 0 } else { total - inp.retain_count };
    let retained_count = total - pruned_count;

    let pruned: Vec<AnchoredResonanceReport> = inp.records[..pruned_count].to_vec();
    let anchor = ResonanceAnchor::from_pruned(&pruned);
    let certificate_hash = compute_certificate_hash(
        inp.compaction_epoch, pruned_count, retained_count, &anchor,
    );

    ResonanceCompactionResult {
        compaction_epoch: inp.compaction_epoch,
        pruned_count,
        retained_count,
        anchor,
        certificate_hash,
    }
}

// ─── ResonanceCompactionRecord ────────────────────────────────────────────────

#[derive(Debug, Clone, PartialEq)]
pub struct ResonanceCompactionRecord {
    pub compaction_epoch:  u64,
    pub pruned_count:      u64,
    pub retained_count:    u64,
    pub anchor_sequence:   u64,
    pub anchor_term_hash:  [u8; 32],
    pub certified_count:   u64,
    pub any_resonant:      bool,
    pub record_hash:       [u8; 32],
    pub prev_hash:         [u8; 32],
}

fn compute_record_hash(
    prev:             &[u8; 32],
    compaction_epoch: u64,
    pruned_count:     u64,
    retained_count:   u64,
    anchor_sequence:  u64,
    term_hash:        &[u8; 32],
    certified_count:  u64,
    any_resonant:     bool,
) -> [u8; 32] {
    let mut h = Sha256::new();
    h.update(prev);
    h.update(compaction_epoch.to_be_bytes());
    h.update(pruned_count.to_be_bytes());
    h.update(retained_count.to_be_bytes());
    h.update(anchor_sequence.to_be_bytes());
    h.update(term_hash);
    h.update(certified_count.to_be_bytes());
    h.update([any_resonant as u8]);
    h.finalize().into()
}

// ─── ResonanceCompactionLog ───────────────────────────────────────────────────

pub struct ResonanceCompactionLog {
    records: Vec<ResonanceCompactionRecord>,
}

impl ResonanceCompactionLog {
    pub fn new() -> Self { Self { records: Vec::new() } }

    pub fn len(&self)      -> usize { self.records.len() }
    pub fn is_empty(&self) -> bool  { self.records.is_empty() }
    pub fn records(&self)  -> &[ResonanceCompactionRecord] { &self.records }

    pub fn record(&mut self, result: &ResonanceCompactionResult) -> ResonanceCompactionRecord {
        let prev = self.records.last()
            .map(|r| r.record_hash)
            .unwrap_or(RESONANCE_COMPACTOR_GENESIS_HASH);

        let record_hash = compute_record_hash(
            &prev,
            result.compaction_epoch,
            result.pruned_count as u64,
            result.retained_count as u64,
            result.anchor.anchor_sequence,
            &result.anchor.terminal_hash,
            result.anchor.certified_count,
            result.anchor.any_resonant,
        );

        let rec = ResonanceCompactionRecord {
            compaction_epoch:  result.compaction_epoch,
            pruned_count:      result.pruned_count as u64,
            retained_count:    result.retained_count as u64,
            anchor_sequence:   result.anchor.anchor_sequence,
            anchor_term_hash:  result.anchor.terminal_hash,
            certified_count:   result.anchor.certified_count,
            any_resonant:      result.anchor.any_resonant,
            record_hash,
            prev_hash:         prev,
        };
        self.records.push(rec.clone());
        rec
    }

    pub fn total_pruned(&self) -> u64 {
        self.records.iter().map(|r| r.pruned_count).sum()
    }

    pub fn latest(&self) -> Option<&ResonanceCompactionRecord> { self.records.last() }

    pub fn verify_chain(&self) -> (bool, Option<usize>) {
        let mut prev = RESONANCE_COMPACTOR_GENESIS_HASH;
        for (i, r) in self.records.iter().enumerate() {
            if r.prev_hash != prev {
                return (false, Some(i));
            }
            let expected = compute_record_hash(
                &prev,
                r.compaction_epoch,
                r.pruned_count,
                r.retained_count,
                r.anchor_sequence,
                &r.anchor_term_hash,
                r.certified_count,
                r.any_resonant,
            );
            if r.record_hash != expected {
                return (false, Some(i));
            }
            prev = r.record_hash;
        }
        (true, None)
    }
}

impl Default for ResonanceCompactionLog {
    fn default() -> Self { Self::new() }
}

// ─── Tests ────────────────────────────────────────────────────────────────────

#[cfg(test)]
mod tests {
    use super::*;
    use crate::resonance_anchor::AnchoredResonanceReport;

    fn dummy_record(seq: u64, resonant: bool, certified: bool) -> AnchoredResonanceReport {
        let mut report_hash = [0u8; 32];
        report_hash[0] = seq as u8;
        report_hash[31] = (seq.wrapping_mul(7)) as u8;
        AnchoredResonanceReport {
            sequence_id:              seq,
            is_resonant:              resonant,
            phi_convergent:           resonant,
            vortex_is_triadic:        resonant,
            ring_valid:               resonant,
            sequence_monotone:        true,
            resonance_depth:          if resonant { 3 } else { 1 },
            ring_depth:               1,
            resonance_coefficient:    if resonant { 6.0 } else { 1.5 },
            phi_headroom:             0.1,
            certified_constitutional: certified,
            report_hash,
            prev_hash:                [0u8; 32],
        }
    }

    fn records(n: u64) -> Vec<AnchoredResonanceReport> {
        (1..=n).map(|i| dummy_record(i, i % 3 != 0, i % 2 == 0)).collect()
    }

    // ── ResonanceAnchor ───────────────────────────────────────────────────────

    #[test]
    fn anchor_empty_is_genesis() {
        let a = ResonanceAnchor::from_pruned(&[]);
        assert_eq!(a.terminal_hash, RESONANCE_COMPACTOR_GENESIS_HASH);
        assert_eq!(a.entry_count, 0);
        assert_eq!(a.certified_count, 0);
        assert!(!a.any_resonant);
    }

    #[test]
    fn anchor_single_resonant_certified() {
        let recs = vec![dummy_record(1, true, true)];
        let a = ResonanceAnchor::from_pruned(&recs);
        assert_eq!(a.anchor_sequence, 1);
        assert_eq!(a.entry_count, 1);
        assert_eq!(a.certified_count, 1);
        assert!(a.any_resonant);
        assert_ne!(a.terminal_hash, RESONANCE_COMPACTOR_GENESIS_HASH);
    }

    #[test]
    fn anchor_certified_count_and_any_resonant() {
        // 5 records: seqs 1-5; resonant = seq%3!=0; certified = seq%2==0
        let recs = records(5);
        let a = ResonanceAnchor::from_pruned(&recs);
        // resonant: seq 1,2,4,5 → 4 (not 3); certified: seq 2,4 → 2
        assert_eq!(a.certified_count, 2);
        assert!(a.any_resonant);
    }

    #[test]
    fn anchor_deterministic() {
        let recs = records(6);
        let a1 = ResonanceAnchor::from_pruned(&recs);
        let a2 = ResonanceAnchor::from_pruned(&recs);
        assert_eq!(a1.terminal_hash, a2.terminal_hash);
        assert_eq!(a1.certified_count, a2.certified_count);
    }

    #[test]
    fn anchor_order_matters() {
        let r1 = vec![dummy_record(1, true, false), dummy_record(2, false, true)];
        let r2 = vec![dummy_record(2, false, true), dummy_record(1, true, false)];
        let a1 = ResonanceAnchor::from_pruned(&r1);
        let a2 = ResonanceAnchor::from_pruned(&r2);
        assert_ne!(a1.terminal_hash, a2.terminal_hash);
    }

    // ── compact_resonance() ───────────────────────────────────────────────────

    #[test]
    fn compact_prunes_prefix() {
        let recs = records(10);
        let result = compact_resonance(ResonanceCompactionInput {
            records:          recs,
            retain_count:     4,
            compaction_epoch: 5,
        });
        assert_eq!(result.pruned_count, 6);
        assert_eq!(result.retained_count, 4);
        assert_eq!(result.anchor.anchor_sequence, 6);
        assert_eq!(result.anchor.entry_count, 6);
    }

    #[test]
    fn compact_retain_all_no_pruning() {
        let recs = records(5);
        let result = compact_resonance(ResonanceCompactionInput {
            records:          recs,
            retain_count:     10,
            compaction_epoch: 1,
        });
        assert_eq!(result.pruned_count, 0);
        assert_eq!(result.retained_count, 5);
        assert_eq!(result.anchor.terminal_hash, RESONANCE_COMPACTOR_GENESIS_HASH);
    }

    #[test]
    fn compact_retain_zero_prunes_all() {
        let recs = records(8);
        let result = compact_resonance(ResonanceCompactionInput {
            records:          recs,
            retain_count:     0,
            compaction_epoch: 3,
        });
        assert_eq!(result.pruned_count, 8);
        assert_eq!(result.retained_count, 0);
        assert_eq!(result.anchor.anchor_sequence, 8);
    }

    #[test]
    fn certificate_hash_nonzero() {
        let recs = records(5);
        let result = compact_resonance(ResonanceCompactionInput {
            records:          recs,
            retain_count:     2,
            compaction_epoch: 10,
        });
        assert_ne!(result.certificate_hash, [0u8; 32]);
    }

    #[test]
    fn certificate_hash_deterministic() {
        let recs = records(6);
        let inp = ResonanceCompactionInput {
            records:          recs,
            retain_count:     3,
            compaction_epoch: 7,
        };
        let r1 = compact_resonance(inp.clone());
        let r2 = compact_resonance(inp.clone());
        let r3 = compact_resonance(inp);
        assert_eq!(r1.certificate_hash, r2.certificate_hash);
        assert_eq!(r2.certificate_hash, r3.certificate_hash);
    }

    // ── ResonanceCompactionLog ────────────────────────────────────────────────

    #[test]
    fn fresh_log_empty() {
        let l = ResonanceCompactionLog::new();
        assert!(l.is_empty());
        assert_eq!(l.total_pruned(), 0);
    }

    #[test]
    fn record_chains_correctly() {
        let mut l = ResonanceCompactionLog::new();
        let r1 = compact_resonance(ResonanceCompactionInput { records: records(10), retain_count: 7, compaction_epoch: 1 });
        let r2 = compact_resonance(ResonanceCompactionInput { records: records(15), retain_count: 5, compaction_epoch: 2 });
        let rec1 = l.record(&r1);
        let rec2 = l.record(&r2);
        assert_eq!(rec2.prev_hash, rec1.record_hash);
        assert_eq!(l.total_pruned(), 3 + 10);
    }

    #[test]
    fn verify_chain_empty_ok() {
        let l = ResonanceCompactionLog::new();
        let (ok, idx) = l.verify_chain();
        assert!(ok);
        assert!(idx.is_none());
    }

    #[test]
    fn verify_chain_three_records_ok() {
        let mut l = ResonanceCompactionLog::new();
        for epoch in 1..=3u64 {
            let r = compact_resonance(ResonanceCompactionInput {
                records:          records(10),
                retain_count:     7,
                compaction_epoch: epoch,
            });
            l.record(&r);
        }
        let (ok, idx) = l.verify_chain();
        assert!(ok);
        assert!(idx.is_none());
    }

    #[test]
    fn verify_chain_tampered_pruned_count() {
        let mut l = ResonanceCompactionLog::new();
        let r = compact_resonance(ResonanceCompactionInput { records: records(10), retain_count: 7, compaction_epoch: 1 });
        l.record(&r);
        l.records[0].pruned_count = 99;
        let (ok, idx) = l.verify_chain();
        assert!(!ok);
        assert_eq!(idx, Some(0));
    }

    #[test]
    fn verify_chain_tampered_any_resonant() {
        let mut l = ResonanceCompactionLog::new();
        // Use a non-resonant chain (seq%3==0 only)
        let non_resonant: Vec<_> = (3..=30u64).step_by(3)
            .map(|i| dummy_record(i, false, false))
            .collect();
        let r = compact_resonance(ResonanceCompactionInput {
            records:          non_resonant,
            retain_count:     7,
            compaction_epoch: 1,
        });
        assert!(!r.anchor.any_resonant);
        l.record(&r);
        l.records[0].any_resonant = true; // tamper (was false)
        let (ok, idx) = l.verify_chain();
        assert!(!ok);
        assert_eq!(idx, Some(0));
    }
}
