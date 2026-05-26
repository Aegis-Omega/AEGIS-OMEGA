//! Gate 332 — Gossip Health Compactor (T2)
//! EPISTEMIC TIER: T2 (engineering hypothesis)
//!
//! Applies the same proof-preserving compaction pattern (Gate 328) to the
//! GossipHealthMonitor record chain (Gate 320). Long-running epoch sequences
//! cause the health report chain to grow without bound; this gate prunes old
//! reports while sealing them in a HealthAnchor.
//!
//! HealthAnchor:
//!   anchor_epoch:   u64          — highest epoch in the pruned prefix
//!   terminal_hash:  [u8;32]      — sequential SHA-256 chain over pruned records
//!   entry_count:    u64          — number of pruned entries sealed into anchor
//!   peak_class:     NetworkHealthClass — worst class seen in pruned set
//!
//! The terminal_hash chain: acc[i] = SHA-256(acc[i-1] ‖ epoch_be8 ‖ report_hash ‖ class_byte)
//!
//! HealthCompactionResult:
//!   compaction_epoch, pruned_count, retained_count, anchor, certificate_hash
//!   certificate_hash = SHA-256(compaction_epoch_be8 ‖ pruned_be8 ‖ retained_be8
//!                               ‖ anchor.terminal_hash ‖ anchor_epoch_be8
//!                               ‖ anchor.peak_class_byte)
//!
//! HealthCompactionLog: hash-chained audit trail. verify_chain(), total_pruned().

use sha2::{Sha256, Digest};
use crate::gossip_health_report::{GossipHealthReport, NetworkHealthClass};

pub const HEALTH_COMPACTOR_GENESIS_HASH: [u8; 32] = [0u8; 32];

// ─── HealthAnchor ─────────────────────────────────────────────────────────────

/// Cryptographic anchor sealing the pruned health report prefix.
#[derive(Debug, Clone, PartialEq)]
pub struct HealthAnchor {
    pub anchor_epoch:   u64,
    pub terminal_hash:  [u8; 32],
    pub entry_count:    u64,
    pub peak_class:     NetworkHealthClass,
}

impl HealthAnchor {
    /// Build an anchor from a pruned slice of (epoch, report_hash, health_class) triples.
    pub fn from_pruned(pruned: &[(u64, [u8; 32], NetworkHealthClass)]) -> Self {
        if pruned.is_empty() {
            return HealthAnchor {
                anchor_epoch:  0,
                terminal_hash: HEALTH_COMPACTOR_GENESIS_HASH,
                entry_count:   0,
                peak_class:    NetworkHealthClass::Green,
            };
        }
        let mut acc   = HEALTH_COMPACTOR_GENESIS_HASH;
        let mut peak  = NetworkHealthClass::Green;

        for (epoch, report_hash, class) in pruned {
            let mut h = Sha256::new();
            h.update(acc);
            h.update(epoch.to_be_bytes());
            h.update(report_hash);
            h.update([class_byte(*class)]);
            acc = h.finalize().into();

            if class_severity(*class) > class_severity(peak) {
                peak = *class;
            }
        }

        HealthAnchor {
            anchor_epoch:  pruned.last().unwrap().0,
            terminal_hash: acc,
            entry_count:   pruned.len() as u64,
            peak_class:    peak,
        }
    }
}

fn class_byte(c: NetworkHealthClass) -> u8 {
    match c {
        NetworkHealthClass::Green  => 0,
        NetworkHealthClass::Yellow => 1,
        NetworkHealthClass::Red    => 2,
    }
}

fn class_severity(c: NetworkHealthClass) -> u8 { class_byte(c) }

// ─── HealthCompactionInput ────────────────────────────────────────────────────

/// Input for one health-chain compaction.
#[derive(Debug, Clone)]
pub struct HealthCompactionInput {
    /// Ordered slice of (epoch, report_hash, class), ascending by epoch.
    pub reports:          Vec<(u64, [u8; 32], NetworkHealthClass)>,
    pub retain_count:     usize,
    pub compaction_epoch: u64,
}

/// Extract compaction input from a slice of GossipHealthReports.
pub fn build_input(
    reports:          &[GossipHealthReport],
    retain_count:     usize,
    compaction_epoch: u64,
) -> HealthCompactionInput {
    let entries = reports.iter()
        .map(|r| (r.epoch, r.report_hash, r.health_class))
        .collect();
    HealthCompactionInput { reports: entries, retain_count, compaction_epoch }
}

// ─── HealthCompactionResult ───────────────────────────────────────────────────

#[derive(Debug, Clone, PartialEq)]
pub struct HealthCompactionResult {
    pub compaction_epoch: u64,
    pub pruned_count:     usize,
    pub retained_count:   usize,
    pub anchor:           HealthAnchor,
    pub certificate_hash: [u8; 32],
}

fn compute_certificate_hash(
    compaction_epoch: u64,
    pruned_count:     usize,
    retained_count:   usize,
    anchor:           &HealthAnchor,
) -> [u8; 32] {
    let mut h = Sha256::new();
    h.update(compaction_epoch.to_be_bytes());
    h.update((pruned_count as u64).to_be_bytes());
    h.update((retained_count as u64).to_be_bytes());
    h.update(anchor.terminal_hash);
    h.update(anchor.anchor_epoch.to_be_bytes());
    h.update([class_byte(anchor.peak_class)]);
    h.finalize().into()
}

/// Execute compaction on the given health chain input.
pub fn compact_health(inp: HealthCompactionInput) -> HealthCompactionResult {
    let total         = inp.reports.len();
    let pruned_count  = if inp.retain_count >= total { 0 } else { total - inp.retain_count };
    let retained_count = total - pruned_count;

    let pruned: Vec<(u64, [u8; 32], NetworkHealthClass)> = inp.reports[..pruned_count].to_vec();
    let anchor = HealthAnchor::from_pruned(&pruned);
    let certificate_hash = compute_certificate_hash(
        inp.compaction_epoch, pruned_count, retained_count, &anchor,
    );

    HealthCompactionResult {
        compaction_epoch: inp.compaction_epoch,
        pruned_count,
        retained_count,
        anchor,
        certificate_hash,
    }
}

// ─── HealthCompactionRecord ───────────────────────────────────────────────────

#[derive(Debug, Clone, PartialEq)]
pub struct HealthCompactionRecord {
    pub compaction_epoch:  u64,
    pub pruned_count:      u64,
    pub retained_count:    u64,
    pub anchor_epoch:      u64,
    pub anchor_term_hash:  [u8; 32],
    pub peak_class:        NetworkHealthClass,
    pub record_hash:       [u8; 32],
    pub prev_hash:         [u8; 32],
}

fn compute_record_hash(
    prev:             &[u8; 32],
    compaction_epoch: u64,
    pruned_count:     u64,
    retained_count:   u64,
    anchor_epoch:     u64,
    term_hash:        &[u8; 32],
    peak:             NetworkHealthClass,
) -> [u8; 32] {
    let mut h = Sha256::new();
    h.update(prev);
    h.update(compaction_epoch.to_be_bytes());
    h.update(pruned_count.to_be_bytes());
    h.update(retained_count.to_be_bytes());
    h.update(anchor_epoch.to_be_bytes());
    h.update(term_hash);
    h.update([class_byte(peak)]);
    h.finalize().into()
}

// ─── HealthCompactionLog ──────────────────────────────────────────────────────

pub struct HealthCompactionLog {
    records: Vec<HealthCompactionRecord>,
}

impl HealthCompactionLog {
    pub fn new() -> Self { Self { records: Vec::new() } }

    pub fn len(&self)      -> usize { self.records.len() }
    pub fn is_empty(&self) -> bool  { self.records.is_empty() }
    pub fn records(&self)  -> &[HealthCompactionRecord] { &self.records }

    pub fn record(&mut self, result: &HealthCompactionResult) -> HealthCompactionRecord {
        let prev = self.records.last()
            .map(|r| r.record_hash)
            .unwrap_or(HEALTH_COMPACTOR_GENESIS_HASH);

        let record_hash = compute_record_hash(
            &prev,
            result.compaction_epoch,
            result.pruned_count as u64,
            result.retained_count as u64,
            result.anchor.anchor_epoch,
            &result.anchor.terminal_hash,
            result.anchor.peak_class,
        );

        let rec = HealthCompactionRecord {
            compaction_epoch:  result.compaction_epoch,
            pruned_count:      result.pruned_count as u64,
            retained_count:    result.retained_count as u64,
            anchor_epoch:      result.anchor.anchor_epoch,
            anchor_term_hash:  result.anchor.terminal_hash,
            peak_class:        result.anchor.peak_class,
            record_hash,
            prev_hash:         prev,
        };
        self.records.push(rec.clone());
        rec
    }

    pub fn total_pruned(&self) -> u64 {
        self.records.iter().map(|r| r.pruned_count).sum()
    }

    pub fn latest(&self) -> Option<&HealthCompactionRecord> { self.records.last() }

    pub fn verify_chain(&self) -> (bool, Option<usize>) {
        let mut prev = HEALTH_COMPACTOR_GENESIS_HASH;
        for (i, r) in self.records.iter().enumerate() {
            if r.prev_hash != prev {
                return (false, Some(i));
            }
            let expected = compute_record_hash(
                &prev,
                r.compaction_epoch,
                r.pruned_count,
                r.retained_count,
                r.anchor_epoch,
                &r.anchor_term_hash,
                r.peak_class,
            );
            if r.record_hash != expected {
                return (false, Some(i));
            }
            prev = r.record_hash;
        }
        (true, None)
    }
}

impl Default for HealthCompactionLog {
    fn default() -> Self { Self::new() }
}

// ─── Tests ────────────────────────────────────────────────────────────────────

#[cfg(test)]
mod tests {
    use super::*;

    fn mk_entry(epoch: u64, seed: u8, class: NetworkHealthClass) -> (u64, [u8; 32], NetworkHealthClass) {
        let mut h = [0u8; 32];
        h[0] = seed; h[31] = seed.wrapping_mul(3);
        (epoch, h, class)
    }

    fn mixed_chain(n: u64) -> Vec<(u64, [u8; 32], NetworkHealthClass)> {
        (1..=n).map(|i| {
            let class = match i % 3 {
                0 => NetworkHealthClass::Red,
                1 => NetworkHealthClass::Green,
                _ => NetworkHealthClass::Yellow,
            };
            mk_entry(i, i as u8, class)
        }).collect()
    }

    // ── HealthAnchor ──────────────────────────────────────────────────────────

    #[test]
    fn anchor_empty_is_genesis() {
        let a = HealthAnchor::from_pruned(&[]);
        assert_eq!(a.terminal_hash, HEALTH_COMPACTOR_GENESIS_HASH);
        assert_eq!(a.entry_count, 0);
        assert_eq!(a.anchor_epoch, 0);
        assert_eq!(a.peak_class, NetworkHealthClass::Green);
    }

    #[test]
    fn anchor_single_entry() {
        let entries = vec![mk_entry(1, 10, NetworkHealthClass::Yellow)];
        let a = HealthAnchor::from_pruned(&entries);
        assert_eq!(a.anchor_epoch, 1);
        assert_eq!(a.entry_count, 1);
        assert_eq!(a.peak_class, NetworkHealthClass::Yellow);
        assert_ne!(a.terminal_hash, HEALTH_COMPACTOR_GENESIS_HASH);
    }

    #[test]
    fn anchor_peak_class_tracks_worst() {
        let entries = vec![
            mk_entry(1, 1, NetworkHealthClass::Green),
            mk_entry(2, 2, NetworkHealthClass::Red),
            mk_entry(3, 3, NetworkHealthClass::Yellow),
        ];
        let a = HealthAnchor::from_pruned(&entries);
        assert_eq!(a.peak_class, NetworkHealthClass::Red);
    }

    #[test]
    fn anchor_deterministic() {
        let entries = mixed_chain(5);
        let a1 = HealthAnchor::from_pruned(&entries);
        let a2 = HealthAnchor::from_pruned(&entries);
        assert_eq!(a1.terminal_hash, a2.terminal_hash);
        assert_eq!(a1.peak_class, a2.peak_class);
    }

    #[test]
    fn anchor_order_matters() {
        let e1 = vec![mk_entry(1, 1, NetworkHealthClass::Green), mk_entry(2, 2, NetworkHealthClass::Yellow)];
        let e2 = vec![mk_entry(2, 2, NetworkHealthClass::Yellow), mk_entry(1, 1, NetworkHealthClass::Green)];
        let a1 = HealthAnchor::from_pruned(&e1);
        let a2 = HealthAnchor::from_pruned(&e2);
        assert_ne!(a1.terminal_hash, a2.terminal_hash);
    }

    // ── compact_health() ──────────────────────────────────────────────────────

    #[test]
    fn compact_prunes_prefix() {
        let chain = mixed_chain(10);
        let result = compact_health(HealthCompactionInput {
            reports:          chain,
            retain_count:     4,
            compaction_epoch: 5,
        });
        assert_eq!(result.pruned_count, 6);
        assert_eq!(result.retained_count, 4);
        assert_eq!(result.anchor.anchor_epoch, 6); // epochs 1..6 pruned
        assert_eq!(result.anchor.entry_count, 6);
    }

    #[test]
    fn compact_retain_all_no_pruning() {
        let chain = mixed_chain(5);
        let result = compact_health(HealthCompactionInput {
            reports:          chain,
            retain_count:     10,
            compaction_epoch: 1,
        });
        assert_eq!(result.pruned_count, 0);
        assert_eq!(result.retained_count, 5);
        assert_eq!(result.anchor.terminal_hash, HEALTH_COMPACTOR_GENESIS_HASH);
    }

    #[test]
    fn compact_retain_zero_prunes_all() {
        let chain = mixed_chain(8);
        let result = compact_health(HealthCompactionInput {
            reports:          chain,
            retain_count:     0,
            compaction_epoch: 3,
        });
        assert_eq!(result.pruned_count, 8);
        assert_eq!(result.retained_count, 0);
        assert_eq!(result.anchor.anchor_epoch, 8);
    }

    #[test]
    fn certificate_hash_nonzero() {
        let chain = mixed_chain(5);
        let result = compact_health(HealthCompactionInput {
            reports:          chain,
            retain_count:     2,
            compaction_epoch: 10,
        });
        assert_ne!(result.certificate_hash, [0u8; 32]);
    }

    #[test]
    fn certificate_hash_deterministic() {
        let chain = mixed_chain(6);
        let inp = HealthCompactionInput {
            reports:          chain,
            retain_count:     3,
            compaction_epoch: 7,
        };
        let r1 = compact_health(inp.clone());
        let r2 = compact_health(inp.clone());
        let r3 = compact_health(inp);
        assert_eq!(r1.certificate_hash, r2.certificate_hash);
        assert_eq!(r2.certificate_hash, r3.certificate_hash);
    }

    // ── HealthCompactionLog ───────────────────────────────────────────────────

    #[test]
    fn fresh_log_empty() {
        let l = HealthCompactionLog::new();
        assert!(l.is_empty());
        assert_eq!(l.total_pruned(), 0);
    }

    #[test]
    fn record_chains_correctly() {
        let mut l = HealthCompactionLog::new();
        let r1 = compact_health(HealthCompactionInput { reports: mixed_chain(10), retain_count: 7, compaction_epoch: 1 });
        let r2 = compact_health(HealthCompactionInput { reports: mixed_chain(15), retain_count: 5, compaction_epoch: 2 });
        let rec1 = l.record(&r1);
        let rec2 = l.record(&r2);
        assert_eq!(rec2.prev_hash, rec1.record_hash);
        assert_eq!(l.total_pruned(), 3 + 10);
    }

    #[test]
    fn verify_chain_empty_ok() {
        let l = HealthCompactionLog::new();
        let (ok, idx) = l.verify_chain();
        assert!(ok);
        assert!(idx.is_none());
    }

    #[test]
    fn verify_chain_three_records_ok() {
        let mut l = HealthCompactionLog::new();
        for epoch in 1..=3u64 {
            let r = compact_health(HealthCompactionInput {
                reports:          mixed_chain(10),
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
        let mut l = HealthCompactionLog::new();
        let r = compact_health(HealthCompactionInput { reports: mixed_chain(10), retain_count: 7, compaction_epoch: 1 });
        l.record(&r);
        l.records[0].pruned_count = 99;
        let (ok, idx) = l.verify_chain();
        assert!(!ok);
        assert_eq!(idx, Some(0));
    }

    #[test]
    fn verify_chain_tampered_peak_class() {
        let mut l = HealthCompactionLog::new();
        // All-Green chain so peak_class == Green; tamper to Red to detect change
        let all_green: Vec<_> = (1..=10u64)
            .map(|i| mk_entry(i, i as u8, NetworkHealthClass::Green))
            .collect();
        let r = compact_health(HealthCompactionInput { reports: all_green, retain_count: 7, compaction_epoch: 1 });
        assert_eq!(r.anchor.peak_class, NetworkHealthClass::Green);
        l.record(&r);
        l.records[0].peak_class = NetworkHealthClass::Red; // tamper (was Green)
        let (ok, idx) = l.verify_chain();
        assert!(!ok);
        assert_eq!(idx, Some(0));
    }

    // ── build_input helper ────────────────────────────────────────────────────

    #[test]
    fn build_input_from_reports() {
        use crate::gossip_health_report::{GossipHealthReport};
        let report = GossipHealthReport {
            epoch:          42,
            live_peers:     5,
            degraded_peers: 0,
            suspect_peers:  0,
            dead_peers:     0,
            total_dropped:  0,
            exceeded_epochs: 0,
            sequence_gaps:  0,
            sequence_dups:  0,
            health_class:   NetworkHealthClass::Green,
            report_hash:    [0xABu8; 32],
            prev_hash:      [0u8; 32],
        };
        let inp = build_input(&[report], 1, 1);
        assert_eq!(inp.reports.len(), 1);
        assert_eq!(inp.reports[0].0, 42);
        assert_eq!(inp.reports[0].2, NetworkHealthClass::Green);
    }
}
