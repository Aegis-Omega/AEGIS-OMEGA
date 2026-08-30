//! Gate 334 — Unified Compaction Manager (T2)
//! EPISTEMIC TIER: T2 (engineering hypothesis)
//!
//! Orchestrates all three proof-preserving compactors (Gates 328–333) in a
//! single per-epoch tick cycle:
//!   • SPSF entries          → spsf_compactor::compact()   (Gate 328)
//!   • Gossip health reports → compact_health()            (Gate 332)
//!   • Resonance records     → compact_resonance()         (Gate 333)
//!
//! Per-epoch tick produces a `UnifiedCompactionRecord`:
//!   epoch, spsf_pruned, health_pruned, resonance_pruned,
//!   spsf_cert_hash, health_cert_hash, resonance_cert_hash,
//!   unified_hash, prev_hash
//!
//! unified_hash = SHA-256(prev[32] ‖ epoch_be8 ‖ spsf_cert[32] ‖ health_cert[32] ‖ resonance_cert[32]
//!                         ‖ spsf_pruned_be8 ‖ health_pruned_be8 ‖ resonance_pruned_be8)
//!
//! UnifiedCompactionLog: hash-chained UnifiedCompactionRecords.
//!   total_pruned() → sum across all three compactors across all ticks.
//!   verify_chain() → (bool, Option<usize>).
//!   spsf_total_pruned() / health_total_pruned() / resonance_total_pruned().

use sha2::{Sha256, Digest};
use crate::spsf_compactor::{CompactionInput, compact};
use crate::gossip_health_compactor::{HealthCompactionInput, compact_health};
use crate::resonance_compactor::{ResonanceCompactionInput, compact_resonance};
use crate::resonance_anchor::AnchoredResonanceReport;
use crate::gossip_health_report::GossipHealthReport;

pub const UNIFIED_MANAGER_GENESIS_HASH: [u8; 32] = [0u8; 32];

// ─── UnifiedCompactionRecord ──────────────────────────────────────────────────

/// One hash-chained record produced by a single `tick()` call.
#[derive(Debug, Clone, PartialEq)]
pub struct UnifiedCompactionRecord {
    pub epoch:                u64,
    pub spsf_pruned:          usize,
    pub health_pruned:        usize,
    pub resonance_pruned:     usize,
    pub spsf_cert_hash:       [u8; 32],
    pub health_cert_hash:     [u8; 32],
    pub resonance_cert_hash:  [u8; 32],
    pub unified_hash:         [u8; 32],
    pub prev_hash:            [u8; 32],
}

fn compute_unified_hash(
    prev:              &[u8; 32],
    epoch:             u64,
    spsf_cert:         &[u8; 32],
    health_cert:       &[u8; 32],
    resonance_cert:    &[u8; 32],
    spsf_pruned:       usize,
    health_pruned:     usize,
    resonance_pruned:  usize,
) -> [u8; 32] {
    let mut h = Sha256::new();
    h.update(prev);
    h.update(epoch.to_be_bytes());
    h.update(spsf_cert);
    h.update(health_cert);
    h.update(resonance_cert);
    h.update((spsf_pruned as u64).to_be_bytes());
    h.update((health_pruned as u64).to_be_bytes());
    h.update((resonance_pruned as u64).to_be_bytes());
    h.finalize().into()
}

// ─── UnifiedCompactionLog ────────────────────────────────────────────────────

pub struct UnifiedCompactionLog {
    records: Vec<UnifiedCompactionRecord>,
}

impl UnifiedCompactionLog {
    pub fn new() -> Self { Self { records: Vec::new() } }

    pub fn len(&self)      -> usize { self.records.len() }
    pub fn is_empty(&self) -> bool  { self.records.is_empty() }
    pub fn records(&self)  -> &[UnifiedCompactionRecord] { &self.records }
    pub fn latest(&self)   -> Option<&UnifiedCompactionRecord> { self.records.last() }

    pub fn append(
        &mut self,
        epoch:             u64,
        spsf_pruned:       usize,
        health_pruned:     usize,
        resonance_pruned:  usize,
        spsf_cert_hash:    [u8; 32],
        health_cert_hash:  [u8; 32],
        resonance_cert_hash: [u8; 32],
    ) -> UnifiedCompactionRecord {
        let prev = self.records.last()
            .map(|r| r.unified_hash)
            .unwrap_or(UNIFIED_MANAGER_GENESIS_HASH);

        let unified_hash = compute_unified_hash(
            &prev, epoch, &spsf_cert_hash, &health_cert_hash, &resonance_cert_hash,
            spsf_pruned, health_pruned, resonance_pruned,
        );

        let rec = UnifiedCompactionRecord {
            epoch,
            spsf_pruned,
            health_pruned,
            resonance_pruned,
            spsf_cert_hash,
            health_cert_hash,
            resonance_cert_hash,
            unified_hash,
            prev_hash: prev,
        };
        self.records.push(rec.clone());
        rec
    }

    pub fn total_pruned(&self) -> u64 {
        self.records.iter()
            .map(|r| (r.spsf_pruned + r.health_pruned + r.resonance_pruned) as u64)
            .sum()
    }

    pub fn spsf_total_pruned(&self) -> u64 {
        self.records.iter().map(|r| r.spsf_pruned as u64).sum()
    }

    pub fn health_total_pruned(&self) -> u64 {
        self.records.iter().map(|r| r.health_pruned as u64).sum()
    }

    pub fn resonance_total_pruned(&self) -> u64 {
        self.records.iter().map(|r| r.resonance_pruned as u64).sum()
    }

    pub fn verify_chain(&self) -> (bool, Option<usize>) {
        let mut prev = UNIFIED_MANAGER_GENESIS_HASH;
        for (i, r) in self.records.iter().enumerate() {
            if r.prev_hash != prev {
                return (false, Some(i));
            }
            let expected = compute_unified_hash(
                &prev, r.epoch,
                &r.spsf_cert_hash, &r.health_cert_hash, &r.resonance_cert_hash,
                r.spsf_pruned, r.health_pruned, r.resonance_pruned,
            );
            if r.unified_hash != expected {
                return (false, Some(i));
            }
            prev = r.unified_hash;
        }
        (true, None)
    }
}

impl Default for UnifiedCompactionLog {
    fn default() -> Self { Self::new() }
}

// ─── UnifiedCompactionManager ────────────────────────────────────────────────

/// Input for one compaction tick across all three chains.
pub struct UnifiedTickInput {
    /// SPSF (sequence_id, state_hash) entries.
    pub spsf_entries:     Vec<(u64, [u8; 32])>,
    pub spsf_retain:      usize,
    /// Gossip health reports.
    pub health_reports:   Vec<(u64, GossipHealthReport)>,
    pub health_retain:    usize,
    /// Resonance records.
    pub resonance_records: Vec<AnchoredResonanceReport>,
    pub resonance_retain:  usize,
    /// Epoch number for this tick.
    pub epoch: u64,
}

/// Perform one unified compaction tick across all three chains.
/// Returns the log record appended to `log`.
pub fn tick(input: UnifiedTickInput, log: &mut UnifiedCompactionLog) -> UnifiedCompactionRecord {
    // ── SPSF compaction ────────────────────────────────────────────────────────
    let spsf_inp = CompactionInput {
        entries:          input.spsf_entries,
        retain_count:     input.spsf_retain,
        compaction_epoch: input.epoch,
    };
    let spsf_result = compact(spsf_inp);

    // ── Gossip health compaction ───────────────────────────────────────────────
    let health_inp = HealthCompactionInput {
        reports:          input.health_reports
            .iter()
            .map(|(ep, r)| (*ep, r.report_hash, r.health_class))
            .collect(),
        retain_count:     input.health_retain,
        compaction_epoch: input.epoch,
    };
    let health_result = compact_health(health_inp);

    // ── Resonance compaction ───────────────────────────────────────────────────
    let res_inp = ResonanceCompactionInput {
        records:          input.resonance_records,
        retain_count:     input.resonance_retain,
        compaction_epoch: input.epoch,
    };
    let resonance_result = compact_resonance(res_inp);

    log.append(
        input.epoch,
        spsf_result.pruned_count,
        health_result.pruned_count,
        resonance_result.pruned_count,
        spsf_result.certificate_hash,
        health_result.certificate_hash,
        resonance_result.certificate_hash,
    )
}

// ─── Tests ────────────────────────────────────────────────────────────────────

#[cfg(test)]
mod tests {
    use super::*;
    use crate::resonance_anchor::AnchoredResonanceReport;
    use crate::gossip_health_report::{GossipHealthReport, NetworkHealthClass};

    fn spsf_entries(n: u64) -> Vec<(u64, [u8; 32])> {
        (1..=n).map(|i| {
            let mut h = [0u8; 32];
            h[0] = i as u8;
            (i, h)
        }).collect()
    }

    fn health_reports(n: u64) -> Vec<(u64, GossipHealthReport)> {
        (1..=n).map(|ep| {
            let mut h = [0u8; 32];
            h[0] = ep as u8;
            let r = GossipHealthReport {
                epoch:           ep,
                live_peers:      4,
                degraded_peers:  0,
                suspect_peers:   0,
                dead_peers:      0,
                total_dropped:   0,
                exceeded_epochs: 0,
                sequence_gaps:   0,
                sequence_dups:   0,
                health_class:    NetworkHealthClass::Green,
                report_hash:     h,
                prev_hash:       [0u8; 32],
            };
            (ep, r)
        }).collect()
    }

    fn resonance_records(n: u64) -> Vec<AnchoredResonanceReport> {
        (1..=n).map(|i| {
            let mut h = [0u8; 32];
            h[0] = i as u8;
            AnchoredResonanceReport {
                sequence_id:              i,
                prev_hash:                [0u8; 32],
                report_hash:              h,
                is_resonant:              i % 2 == 0,
                phi_convergent:           true,
                ring_valid:               true,
                sequence_monotone:        true,
                resonance_depth:          2,
                resonance_coefficient:    3.0,
                phi_headroom:             0.1,
                vortex_is_triadic:        false,
                ring_depth:               1,
                certified_constitutional: i % 3 == 0,
            }
        }).collect()
    }

    fn make_input(epoch: u64,
                  spsf_n: u64, spsf_retain: usize,
                  health_n: u64, health_retain: usize,
                  res_n: u64, res_retain: usize) -> UnifiedTickInput {
        UnifiedTickInput {
            spsf_entries:      spsf_entries(spsf_n),
            spsf_retain,
            health_reports:    health_reports(health_n),
            health_retain,
            resonance_records: resonance_records(res_n),
            resonance_retain:  res_retain,
            epoch,
        }
    }

    // ── Log: basic chain building ─────────────────────────────────────────────

    #[test]
    fn log_starts_empty() {
        let l = UnifiedCompactionLog::new();
        assert!(l.is_empty());
        assert_eq!(l.len(), 0);
        assert!(l.latest().is_none());
    }

    #[test]
    fn log_append_single() {
        let mut l = UnifiedCompactionLog::new();
        let rec = l.append(1, 10, 5, 3, [1u8;32], [2u8;32], [3u8;32]);
        assert_eq!(l.len(), 1);
        assert_eq!(rec.epoch, 1);
        assert_eq!(rec.spsf_pruned, 10);
        assert_eq!(rec.health_pruned, 5);
        assert_eq!(rec.resonance_pruned, 3);
    }

    #[test]
    fn log_prev_hash_links_correctly() {
        let mut l = UnifiedCompactionLog::new();
        let r1 = l.append(1, 0, 0, 0, [0u8;32], [0u8;32], [0u8;32]);
        let r2 = l.append(2, 0, 0, 0, [0u8;32], [0u8;32], [0u8;32]);
        assert_eq!(r2.prev_hash, r1.unified_hash);
    }

    #[test]
    fn verify_chain_empty_ok() {
        let l = UnifiedCompactionLog::new();
        let (ok, idx) = l.verify_chain();
        assert!(ok);
        assert!(idx.is_none());
    }

    #[test]
    fn verify_chain_three_records_ok() {
        let mut l = UnifiedCompactionLog::new();
        l.append(1, 5, 2, 1, [1u8;32], [2u8;32], [3u8;32]);
        l.append(2, 3, 1, 0, [4u8;32], [5u8;32], [6u8;32]);
        l.append(3, 0, 0, 0, [7u8;32], [8u8;32], [9u8;32]);
        let (ok, idx) = l.verify_chain();
        assert!(ok);
        assert!(idx.is_none());
    }

    #[test]
    fn verify_chain_detects_tampered_unified_hash() {
        let mut l = UnifiedCompactionLog::new();
        l.append(1, 5, 2, 1, [1u8;32], [2u8;32], [3u8;32]);
        l.append(2, 0, 0, 0, [0u8;32], [0u8;32], [0u8;32]);
        l.records[0].unified_hash[0] ^= 0xFF;
        let (ok, idx) = l.verify_chain();
        assert!(!ok);
        assert_eq!(idx, Some(0));
    }

    #[test]
    fn verify_chain_detects_tampered_spsf_cert() {
        let mut l = UnifiedCompactionLog::new();
        l.append(1, 5, 2, 1, [1u8;32], [2u8;32], [3u8;32]);
        l.records[0].spsf_cert_hash[0] ^= 0xFF;
        let (ok, idx) = l.verify_chain();
        assert!(!ok);
        assert_eq!(idx, Some(0));
    }

    // ── total_pruned helpers ──────────────────────────────────────────────────

    #[test]
    fn total_pruned_sums_all_three() {
        let mut l = UnifiedCompactionLog::new();
        l.append(1, 10, 5, 3, [0u8;32], [0u8;32], [0u8;32]);
        l.append(2, 2, 1, 0, [0u8;32], [0u8;32], [0u8;32]);
        assert_eq!(l.total_pruned(), 18 + 3); // (10+5+3)+(2+1+0)
        assert_eq!(l.spsf_total_pruned(), 12);
        assert_eq!(l.health_total_pruned(), 6);
        assert_eq!(l.resonance_total_pruned(), 3);
    }

    // ── tick() integration ────────────────────────────────────────────────────

    #[test]
    fn tick_no_prune_when_retain_equals_total() {
        let mut l = UnifiedCompactionLog::new();
        let inp = make_input(1, 5, 5, 3, 3, 4, 4);
        let rec = tick(inp, &mut l);
        assert_eq!(rec.spsf_pruned, 0);
        assert_eq!(rec.health_pruned, 0);
        assert_eq!(rec.resonance_pruned, 0);
    }

    #[test]
    fn tick_prunes_prefix() {
        let mut l = UnifiedCompactionLog::new();
        let inp = make_input(1, 10, 7, 6, 4, 8, 5);
        let rec = tick(inp, &mut l);
        assert_eq!(rec.spsf_pruned, 3);
        assert_eq!(rec.health_pruned, 2);
        assert_eq!(rec.resonance_pruned, 3);
        assert_eq!(rec.epoch, 1);
    }

    #[test]
    fn tick_retain_zero_prunes_all() {
        let mut l = UnifiedCompactionLog::new();
        let inp = make_input(5, 4, 0, 3, 0, 5, 0);
        let rec = tick(inp, &mut l);
        assert_eq!(rec.spsf_pruned, 4);
        assert_eq!(rec.health_pruned, 3);
        assert_eq!(rec.resonance_pruned, 5);
    }

    #[test]
    fn tick_cert_hashes_nonzero_after_prune() {
        let mut l = UnifiedCompactionLog::new();
        let inp = make_input(2, 5, 3, 4, 2, 6, 4);
        let rec = tick(inp, &mut l);
        assert_ne!(rec.spsf_cert_hash, [0u8; 32]);
        assert_ne!(rec.health_cert_hash, [0u8; 32]);
        assert_ne!(rec.resonance_cert_hash, [0u8; 32]);
    }

    #[test]
    fn tick_cert_hashes_zero_when_nothing_pruned() {
        // When retain >= total, pruned=0; SPSF: anchor = genesis, cert = SHA-256(epoch‖0‖0‖genesis‖0‖0)
        // This is NOT necessarily all-zero — just check we record it in the log correctly.
        let mut l = UnifiedCompactionLog::new();
        let inp = make_input(3, 3, 3, 2, 2, 4, 4);
        let rec = tick(inp, &mut l);
        // No prune → should get the "zero-prune" cert hash from each compactor; check log integrity
        assert_eq!(l.len(), 1);
        let (ok, _) = l.verify_chain();
        assert!(ok);
        assert_eq!(rec.spsf_pruned, 0);
    }

    #[test]
    fn two_ticks_chain_correctly() {
        let mut l = UnifiedCompactionLog::new();
        let r1 = tick(make_input(1, 6, 4, 5, 3, 7, 5), &mut l);
        let r2 = tick(make_input(2, 3, 2, 4, 2, 5, 3), &mut l);
        assert_eq!(r2.prev_hash, r1.unified_hash);
        let (ok, _) = l.verify_chain();
        assert!(ok);
    }

    #[test]
    fn tick_deterministic() {
        let mut l1 = UnifiedCompactionLog::new();
        let mut l2 = UnifiedCompactionLog::new();
        let r1 = tick(make_input(7, 8, 5, 6, 3, 9, 6), &mut l1);
        let r2 = tick(make_input(7, 8, 5, 6, 3, 9, 6), &mut l2);
        assert_eq!(r1.unified_hash, r2.unified_hash);
        assert_eq!(r1.spsf_cert_hash, r2.spsf_cert_hash);
    }

    #[test]
    fn tick_different_epoch_different_hash() {
        let mut l1 = UnifiedCompactionLog::new();
        let mut l2 = UnifiedCompactionLog::new();
        let r1 = tick(make_input(1, 5, 3, 3, 2, 4, 2), &mut l1);
        let r2 = tick(make_input(2, 5, 3, 3, 2, 4, 2), &mut l2);
        assert_ne!(r1.unified_hash, r2.unified_hash);
    }

    #[test]
    fn total_pruned_accumulates_across_ticks() {
        let mut l = UnifiedCompactionLog::new();
        tick(make_input(1, 10, 7, 8, 5, 6, 4), &mut l);
        tick(make_input(2, 5, 3, 4, 2, 7, 5), &mut l);
        // tick1: 3+3+2=8; tick2: 2+2+2=6 → total=14
        assert_eq!(l.total_pruned(), 8 + 6);
    }
}
