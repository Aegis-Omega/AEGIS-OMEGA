//! Gate 356 — Compaction Gossip Health Compactor (T2)
//! EPISTEMIC TIER: T2 (engineering hypothesis)
//!
//! Applies proof-preserving compaction (Gate 328 pattern) to the
//! CompactionGossipHealthMonitor chain (Gate 355). Long-running epoch sequences
//! cause the health report chain to grow without bound; this gate prunes old
//! reports while sealing them in a GossipHealthAnchor.
//!
//! GossipHealthAnchor:
//!   anchor_epoch:  u64   — highest epoch in the pruned prefix
//!   terminal_hash: [u8;32] — rolling SHA-256 chain over pruned records
//!   entry_count:   u64   — number of pruned entries sealed into anchor
//!   peak_class:    CompactionGossipHealthClass — worst class in pruned set
//!
//! terminal_hash chain: acc[i] = SHA-256(acc[i-1] ‖ epoch_be8 ‖ report_hash[32] ‖ class_byte)
//!
//! GossipHealthCompactionResult:
//!   compaction_epoch, pruned_count, retained_count, anchor, certificate_hash
//!   certificate_hash = SHA-256(compaction_epoch_be8 ‖ pruned_be8 ‖ retained_be8
//!                               ‖ anchor.terminal_hash ‖ anchor_epoch_be8
//!                               ‖ anchor.peak_class_byte)
//!
//! GossipHealthCompactionLog: hash-chained audit. verify_chain(), total_pruned().

use sha2::{Sha256, Digest};
use crate::compaction_gossip_health::{CompactionGossipHealthReport, CompactionGossipHealthClass};

pub const GOSSIP_HEALTH_COMPACTOR_GENESIS_HASH: [u8; 32] = [0u8; 32];

// ─── helpers ─────────────────────────────────────────────────────────────────

fn class_byte(c: CompactionGossipHealthClass) -> u8 { c.as_u8() }

fn worse(a: CompactionGossipHealthClass, b: CompactionGossipHealthClass) -> CompactionGossipHealthClass {
    if b > a { b } else { a }
}

// ─── GossipHealthAnchor ───────────────────────────────────────────────────────

#[derive(Debug, Clone, PartialEq)]
pub struct GossipHealthAnchor {
    pub anchor_epoch:  u64,
    pub terminal_hash: [u8; 32],
    pub entry_count:   u64,
    pub peak_class:    CompactionGossipHealthClass,
}

impl GossipHealthAnchor {
    pub fn from_pruned(pruned: &[(u64, [u8; 32], CompactionGossipHealthClass)]) -> Self {
        if pruned.is_empty() {
            return GossipHealthAnchor {
                anchor_epoch:  0,
                terminal_hash: GOSSIP_HEALTH_COMPACTOR_GENESIS_HASH,
                entry_count:   0,
                peak_class:    CompactionGossipHealthClass::Green,
            };
        }
        let mut acc  = GOSSIP_HEALTH_COMPACTOR_GENESIS_HASH;
        let mut peak = CompactionGossipHealthClass::Green;
        for (epoch, report_hash, class) in pruned {
            let mut h = Sha256::new();
            h.update(acc);
            h.update(epoch.to_be_bytes());
            h.update(report_hash);
            h.update([class_byte(*class)]);
            acc = h.finalize().into();
            peak = worse(peak, *class);
        }
        GossipHealthAnchor {
            anchor_epoch:  pruned.last().unwrap().0,
            terminal_hash: acc,
            entry_count:   pruned.len() as u64,
            peak_class:    peak,
        }
    }

    pub fn peak_class_byte(&self) -> u8 { class_byte(self.peak_class) }
}

// ─── GossipHealthCompactionResult ────────────────────────────────────────────

#[derive(Debug, Clone, PartialEq)]
pub struct GossipHealthCompactionResult {
    pub compaction_epoch: u64,
    pub pruned_count:     u64,
    pub retained_count:   u64,
    pub anchor:           GossipHealthAnchor,
    pub certificate_hash: [u8; 32],
}

fn compute_certificate(
    compaction_epoch: u64,
    pruned_count:     u64,
    retained_count:   u64,
    anchor:           &GossipHealthAnchor,
) -> [u8; 32] {
    let mut h = Sha256::new();
    h.update(compaction_epoch.to_be_bytes());
    h.update(pruned_count.to_be_bytes());
    h.update(retained_count.to_be_bytes());
    h.update(anchor.terminal_hash);
    h.update(anchor.anchor_epoch.to_be_bytes());
    h.update([anchor.peak_class_byte()]);
    h.finalize().into()
}

/// Compact `reports`: prune the first `prune_count` records into an anchor,
/// retain the remainder. `compaction_epoch` is the caller's current epoch.
pub fn compact_gossip_health(
    reports:          &[CompactionGossipHealthReport],
    prune_count:      usize,
    compaction_epoch: u64,
) -> GossipHealthCompactionResult {
    let prune_count  = prune_count.min(reports.len());
    let pruned_slice = &reports[..prune_count];
    let retained     = (reports.len() - prune_count) as u64;

    let triples: Vec<(u64, [u8; 32], CompactionGossipHealthClass)> = pruned_slice
        .iter()
        .map(|r| (r.epoch, r.report_hash, r.health_class))
        .collect();

    let anchor           = GossipHealthAnchor::from_pruned(&triples);
    let certificate_hash = compute_certificate(compaction_epoch, prune_count as u64, retained, &anchor);

    GossipHealthCompactionResult {
        compaction_epoch,
        pruned_count: prune_count as u64,
        retained_count: retained,
        anchor,
        certificate_hash,
    }
}

// ─── GossipHealthCompactionLog ───────────────────────────────────────────────

#[derive(Debug, Clone, PartialEq)]
pub struct GossipHealthCompactionLogEntry {
    pub result:     GossipHealthCompactionResult,
    pub prev_hash:  [u8; 32],
    pub entry_hash: [u8; 32],
}

fn compute_entry_hash(prev: &[u8; 32], r: &GossipHealthCompactionResult) -> [u8; 32] {
    let mut h = Sha256::new();
    h.update(prev);
    h.update(r.compaction_epoch.to_be_bytes());
    h.update(r.pruned_count.to_be_bytes());
    h.update(r.retained_count.to_be_bytes());
    h.update(r.certificate_hash);
    h.finalize().into()
}

pub struct GossipHealthCompactionLog {
    entries: Vec<GossipHealthCompactionLogEntry>,
}

impl GossipHealthCompactionLog {
    pub fn new() -> Self { Self { entries: Vec::new() } }

    pub fn append(&mut self, result: GossipHealthCompactionResult) -> &GossipHealthCompactionLogEntry {
        let prev = self.entries.last()
            .map(|e| e.entry_hash)
            .unwrap_or(GOSSIP_HEALTH_COMPACTOR_GENESIS_HASH);
        let entry_hash = compute_entry_hash(&prev, &result);
        self.entries.push(GossipHealthCompactionLogEntry { result, prev_hash: prev, entry_hash });
        self.entries.last().unwrap()
    }

    pub fn total_pruned(&self) -> u64 {
        self.entries.iter().map(|e| e.result.pruned_count).sum()
    }

    pub fn entry_count(&self) -> usize { self.entries.len() }
    pub fn is_empty(&self)    -> bool  { self.entries.is_empty() }
    pub fn entries(&self)     -> &[GossipHealthCompactionLogEntry] { &self.entries }

    pub fn verify_chain(&self) -> (bool, Option<usize>) {
        let mut prev = GOSSIP_HEALTH_COMPACTOR_GENESIS_HASH;
        for (i, e) in self.entries.iter().enumerate() {
            if e.prev_hash != prev { return (false, Some(i)); }
            let expected = compute_entry_hash(&prev, &e.result);
            if e.entry_hash != expected { return (false, Some(i)); }
            prev = e.entry_hash;
        }
        (true, None)
    }
}

impl Default for GossipHealthCompactionLog {
    fn default() -> Self { Self::new() }
}

// ─── Tests ────────────────────────────────────────────────────────────────────

#[cfg(test)]
mod tests {
    use super::*;
    use crate::compaction_gossip_health::{CompactionGossipHealthInput, CompactionGossipHealthMonitor};

    fn make_reports(n: u64) -> Vec<CompactionGossipHealthReport> {
        let mut m = CompactionGossipHealthMonitor::new();
        for i in 1..=n {
            m.record(CompactionGossipHealthInput {
                epoch: i,
                validator_checksum_fails: 0,
                validator_epoch_regressions: 0,
                delivered_count: 10,
                missed_count: 0,
                lagging_peers: 0,
                diverged_peers: 0,
                admitted_peers: 3,
            });
        }
        m.reports().to_vec()
    }

    // ── anchor ────────────────────────────────────────────────────────────────

    #[test]
    fn anchor_empty_is_genesis() {
        let a = GossipHealthAnchor::from_pruned(&[]);
        assert_eq!(a.terminal_hash, GOSSIP_HEALTH_COMPACTOR_GENESIS_HASH);
        assert_eq!(a.entry_count, 0);
        assert_eq!(a.peak_class, CompactionGossipHealthClass::Green);
    }

    #[test]
    fn anchor_nonzero_terminal_hash() {
        let reports = make_reports(3);
        let triples: Vec<_> = reports.iter().map(|r| (r.epoch, r.report_hash, r.health_class)).collect();
        let a = GossipHealthAnchor::from_pruned(&triples);
        assert_ne!(a.terminal_hash, [0u8; 32]);
        assert_eq!(a.entry_count, 3);
        assert_eq!(a.anchor_epoch, 3);
    }

    #[test]
    fn anchor_peak_class_red() {
        let mut m = CompactionGossipHealthMonitor::new();
        m.record(CompactionGossipHealthInput { epoch: 1, diverged_peers: 0, validator_checksum_fails: 0,
            validator_epoch_regressions: 0, delivered_count: 10, missed_count: 0,
            lagging_peers: 0, admitted_peers: 3 });
        m.record(CompactionGossipHealthInput { epoch: 2, diverged_peers: 1, validator_checksum_fails: 0,
            validator_epoch_regressions: 0, delivered_count: 10, missed_count: 0,
            lagging_peers: 0, admitted_peers: 3 });
        let reports = m.reports().to_vec();
        let triples: Vec<_> = reports.iter().map(|r| (r.epoch, r.report_hash, r.health_class)).collect();
        let a = GossipHealthAnchor::from_pruned(&triples);
        assert_eq!(a.peak_class, CompactionGossipHealthClass::Red);
    }

    #[test]
    fn anchor_deterministic() {
        let reports = make_reports(5);
        let triples: Vec<_> = reports.iter().map(|r| (r.epoch, r.report_hash, r.health_class)).collect();
        let a1 = GossipHealthAnchor::from_pruned(&triples);
        let a2 = GossipHealthAnchor::from_pruned(&triples);
        assert_eq!(a1.terminal_hash, a2.terminal_hash);
    }

    // ── compact ───────────────────────────────────────────────────────────────

    #[test]
    fn compact_prune_all() {
        let reports = make_reports(5);
        let r = compact_gossip_health(&reports, 5, 100);
        assert_eq!(r.pruned_count, 5);
        assert_eq!(r.retained_count, 0);
        assert_ne!(r.certificate_hash, [0u8; 32]);
    }

    #[test]
    fn compact_prune_partial() {
        let reports = make_reports(6);
        let r = compact_gossip_health(&reports, 4, 100);
        assert_eq!(r.pruned_count, 4);
        assert_eq!(r.retained_count, 2);
    }

    #[test]
    fn compact_prune_zero() {
        let reports = make_reports(3);
        let r = compact_gossip_health(&reports, 0, 10);
        assert_eq!(r.pruned_count, 0);
        assert_eq!(r.retained_count, 3);
        assert_eq!(r.anchor.entry_count, 0);
    }

    #[test]
    fn compact_prune_beyond_len_clamped() {
        let reports = make_reports(3);
        let r = compact_gossip_health(&reports, 100, 50);
        assert_eq!(r.pruned_count, 3);
        assert_eq!(r.retained_count, 0);
    }

    #[test]
    fn compact_certificate_deterministic() {
        let reports = make_reports(4);
        let r1 = compact_gossip_health(&reports, 2, 99);
        let r2 = compact_gossip_health(&reports, 2, 99);
        assert_eq!(r1.certificate_hash, r2.certificate_hash);
    }

    // ── log ───────────────────────────────────────────────────────────────────

    #[test]
    fn log_empty_ok() {
        let log = GossipHealthCompactionLog::new();
        assert!(log.is_empty());
        assert_eq!(log.total_pruned(), 0);
        let (ok, idx) = log.verify_chain();
        assert!(ok);
        assert!(idx.is_none());
    }

    #[test]
    fn log_first_prev_is_genesis() {
        let mut log = GossipHealthCompactionLog::new();
        let reports = make_reports(3);
        let r = compact_gossip_health(&reports, 3, 1);
        let e = log.append(r);
        assert_eq!(e.prev_hash, GOSSIP_HEALTH_COMPACTOR_GENESIS_HASH);
    }

    #[test]
    fn log_entry_hash_nonzero() {
        let mut log = GossipHealthCompactionLog::new();
        let reports = make_reports(3);
        let r = compact_gossip_health(&reports, 3, 1);
        let e = log.append(r);
        assert_ne!(e.entry_hash, [0u8; 32]);
    }

    #[test]
    fn log_chain_links() {
        let mut log = GossipHealthCompactionLog::new();
        let reports = make_reports(6);
        log.append(compact_gossip_health(&reports[..3], 3, 1));
        let h0 = log.entries()[0].entry_hash;
        log.append(compact_gossip_health(&reports[3..], 3, 2));
        assert_eq!(log.entries()[1].prev_hash, h0);
    }

    #[test]
    fn log_total_pruned() {
        let mut log = GossipHealthCompactionLog::new();
        let reports = make_reports(8);
        log.append(compact_gossip_health(&reports[..4], 4, 1));
        log.append(compact_gossip_health(&reports[4..], 3, 2));
        assert_eq!(log.total_pruned(), 7);
    }

    #[test]
    fn log_verify_chain_three_ok() {
        let mut log = GossipHealthCompactionLog::new();
        let reports = make_reports(9);
        for i in 0..3 {
            log.append(compact_gossip_health(&reports[i*3..(i+1)*3], 3, i as u64 + 1));
        }
        let (ok, idx) = log.verify_chain();
        assert!(ok);
        assert!(idx.is_none());
    }

    #[test]
    fn log_verify_chain_detects_tamper() {
        let mut log = GossipHealthCompactionLog::new();
        let reports = make_reports(4);
        log.append(compact_gossip_health(&reports[..2], 2, 1));
        log.append(compact_gossip_health(&reports[2..], 2, 2));
        log.entries.first_mut().unwrap().entry_hash[0] ^= 0xFF;
        let (ok, idx) = log.verify_chain();
        assert!(!ok);
        assert_eq!(idx, Some(0));
    }
}
