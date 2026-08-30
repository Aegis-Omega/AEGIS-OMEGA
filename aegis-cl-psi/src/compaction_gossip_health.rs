//! Gate 355 — Compaction Gossip Health Report (T2)
//! EPISTEMIC TIER: T2 (engineering hypothesis)
//!
//! Synthesises the compaction broadcast layer (Gates 350–354) into a single
//! per-epoch health verdict, mirroring Gate 320 for the compaction gossip layer.
//!
//! Inputs (all optional — absent subsystems are treated as healthy):
//!   validator_checksum_fails:  u32  — frames rejected by checksum
//!   validator_epoch_regresss:  u32  — frames with regressed epoch
//!   delivered_count:           u64  — frames successfully dispatched
//!   missed_count:              u64  — frames missed (peer_count - delivered)
//!   lagging_peers:             u32  — peers with lag > 0
//!   diverged_peers:            u32  — peers with acked_epoch > current_epoch
//!   admitted_peers:            u32  — total peers in registry
//!
//! CompactionGossipHealthClass:
//!   Green  — all systems nominal
//!   Yellow — degradation but no critical failure
//!   Red    — critical failure (diverged peers, checksum failures, or zero delivery)
//!
//! Red conditions:
//!   diverged_peers ≥ 1 OR checksum_fails ≥ 3 OR (admitted_peers > 0 AND delivered_count == 0)
//! Yellow conditions:
//!   lagging_peers ≥ 1 OR epoch_regressions ≥ 1 OR missed_count ≥ 1 OR checksum_fails ≥ 1
//!
//! report_hash = SHA-256(prev[32] ‖ epoch_be8 ‖ class_byte
//!                        ‖ checksum_fails_be4 ‖ epoch_regressions_be4
//!                        ‖ delivered_be8 ‖ missed_be8
//!                        ‖ lagging_be4 ‖ diverged_be4 ‖ admitted_be4)

use sha2::{Sha256, Digest};

pub const GOSSIP_HEALTH_GENESIS_HASH: [u8; 32] = [0u8; 32];

// ─── CompactionGossipHealthClass ─────────────────────────────────────────────

#[derive(Debug, Clone, Copy, PartialEq, Eq, PartialOrd, Ord)]
#[repr(u8)]
pub enum CompactionGossipHealthClass {
    Green  = 0,
    Yellow = 1,
    Red    = 2,
}

impl CompactionGossipHealthClass {
    pub fn as_u8(self) -> u8 { self as u8 }
}

// ─── CompactionGossipHealthInput ─────────────────────────────────────────────

#[derive(Debug, Clone, Default)]
pub struct CompactionGossipHealthInput {
    pub epoch:                   u64,
    pub validator_checksum_fails: u32,
    pub validator_epoch_regressions: u32,
    pub delivered_count:         u64,
    pub missed_count:            u64,
    pub lagging_peers:           u32,
    pub diverged_peers:          u32,
    pub admitted_peers:          u32,
}

// ─── CompactionGossipHealthReport ────────────────────────────────────────────

#[derive(Debug, Clone, PartialEq)]
pub struct CompactionGossipHealthReport {
    pub epoch:                   u64,
    pub health_class:            CompactionGossipHealthClass,
    pub validator_checksum_fails: u32,
    pub validator_epoch_regressions: u32,
    pub delivered_count:         u64,
    pub missed_count:            u64,
    pub lagging_peers:           u32,
    pub diverged_peers:          u32,
    pub admitted_peers:          u32,
    pub report_hash:             [u8; 32],
    pub prev_hash:               [u8; 32],
}

fn compute_report_hash(
    prev:              &[u8; 32],
    epoch:             u64,
    class:             CompactionGossipHealthClass,
    checksum_fails:    u32,
    epoch_regressions: u32,
    delivered:         u64,
    missed:            u64,
    lagging:           u32,
    diverged:          u32,
    admitted:          u32,
) -> [u8; 32] {
    let mut h = Sha256::new();
    h.update(prev);
    h.update(epoch.to_be_bytes());
    h.update([class.as_u8()]);
    h.update(checksum_fails.to_be_bytes());
    h.update(epoch_regressions.to_be_bytes());
    h.update(delivered.to_be_bytes());
    h.update(missed.to_be_bytes());
    h.update(lagging.to_be_bytes());
    h.update(diverged.to_be_bytes());
    h.update(admitted.to_be_bytes());
    h.finalize().into()
}

fn classify(input: &CompactionGossipHealthInput) -> CompactionGossipHealthClass {
    // Red: diverged peers, too many checksum failures, or complete delivery blackout
    if input.diverged_peers >= 1
        || input.validator_checksum_fails >= 3
        || (input.admitted_peers > 0 && input.delivered_count == 0)
    {
        return CompactionGossipHealthClass::Red;
    }
    // Yellow: any lagging, any regression, any missed delivery, or partial checksum failures
    if input.lagging_peers >= 1
        || input.validator_epoch_regressions >= 1
        || input.missed_count >= 1
        || input.validator_checksum_fails >= 1
    {
        return CompactionGossipHealthClass::Yellow;
    }
    CompactionGossipHealthClass::Green
}

// ─── CompactionGossipHealthMonitor ───────────────────────────────────────────

pub struct CompactionGossipHealthMonitor {
    reports: Vec<CompactionGossipHealthReport>,
}

impl CompactionGossipHealthMonitor {
    pub fn new() -> Self { Self { reports: Vec::new() } }

    pub fn record_count(&self) -> usize { self.reports.len() }
    pub fn is_empty(&self)     -> bool  { self.reports.is_empty() }
    pub fn reports(&self)      -> &[CompactionGossipHealthReport] { &self.reports }
    pub fn latest(&self)       -> Option<&CompactionGossipHealthReport> { self.reports.last() }

    pub fn health_class(&self) -> Option<CompactionGossipHealthClass> {
        self.reports.last().map(|r| r.health_class)
    }

    pub fn red_count(&self) -> usize {
        self.reports.iter().filter(|r| r.health_class == CompactionGossipHealthClass::Red).count()
    }

    pub fn yellow_count(&self) -> usize {
        self.reports.iter().filter(|r| r.health_class == CompactionGossipHealthClass::Yellow).count()
    }

    pub fn green_count(&self) -> usize {
        self.reports.iter().filter(|r| r.health_class == CompactionGossipHealthClass::Green).count()
    }

    pub fn record(&mut self, input: CompactionGossipHealthInput) -> &CompactionGossipHealthReport {
        let class = classify(&input);
        let prev = self.reports.last()
            .map(|r| r.report_hash)
            .unwrap_or(GOSSIP_HEALTH_GENESIS_HASH);

        let report_hash = compute_report_hash(
            &prev,
            input.epoch,
            class,
            input.validator_checksum_fails,
            input.validator_epoch_regressions,
            input.delivered_count,
            input.missed_count,
            input.lagging_peers,
            input.diverged_peers,
            input.admitted_peers,
        );

        self.reports.push(CompactionGossipHealthReport {
            epoch: input.epoch,
            health_class: class,
            validator_checksum_fails: input.validator_checksum_fails,
            validator_epoch_regressions: input.validator_epoch_regressions,
            delivered_count: input.delivered_count,
            missed_count: input.missed_count,
            lagging_peers: input.lagging_peers,
            diverged_peers: input.diverged_peers,
            admitted_peers: input.admitted_peers,
            report_hash,
            prev_hash: prev,
        });
        self.reports.last().unwrap()
    }

    pub fn verify_chain(&self) -> (bool, Option<usize>) {
        let mut prev = GOSSIP_HEALTH_GENESIS_HASH;
        for (i, r) in self.reports.iter().enumerate() {
            if r.prev_hash != prev {
                return (false, Some(i));
            }
            let expected = compute_report_hash(
                &prev,
                r.epoch,
                r.health_class,
                r.validator_checksum_fails,
                r.validator_epoch_regressions,
                r.delivered_count,
                r.missed_count,
                r.lagging_peers,
                r.diverged_peers,
                r.admitted_peers,
            );
            if r.report_hash != expected {
                return (false, Some(i));
            }
            prev = r.report_hash;
        }
        (true, None)
    }
}

impl Default for CompactionGossipHealthMonitor {
    fn default() -> Self { Self::new() }
}

// ─── Tests ────────────────────────────────────────────────────────────────────

#[cfg(test)]
mod tests {
    use super::*;

    fn healthy(epoch: u64) -> CompactionGossipHealthInput {
        CompactionGossipHealthInput {
            epoch,
            validator_checksum_fails: 0,
            validator_epoch_regressions: 0,
            delivered_count: 10,
            missed_count: 0,
            lagging_peers: 0,
            diverged_peers: 0,
            admitted_peers: 3,
        }
    }

    // ── classification ────────────────────────────────────────────────────────

    #[test]
    fn green_when_all_nominal() {
        let mut m = CompactionGossipHealthMonitor::new();
        let r = m.record(healthy(1));
        assert_eq!(r.health_class, CompactionGossipHealthClass::Green);
    }

    #[test]
    fn yellow_on_lagging_peer() {
        let mut m = CompactionGossipHealthMonitor::new();
        let r = m.record(CompactionGossipHealthInput { lagging_peers: 1, ..healthy(1) });
        assert_eq!(r.health_class, CompactionGossipHealthClass::Yellow);
    }

    #[test]
    fn yellow_on_epoch_regression() {
        let mut m = CompactionGossipHealthMonitor::new();
        let r = m.record(CompactionGossipHealthInput {
            validator_epoch_regressions: 1, ..healthy(1)
        });
        assert_eq!(r.health_class, CompactionGossipHealthClass::Yellow);
    }

    #[test]
    fn yellow_on_missed_delivery() {
        let mut m = CompactionGossipHealthMonitor::new();
        let r = m.record(CompactionGossipHealthInput { missed_count: 1, ..healthy(1) });
        assert_eq!(r.health_class, CompactionGossipHealthClass::Yellow);
    }

    #[test]
    fn red_on_diverged_peer() {
        let mut m = CompactionGossipHealthMonitor::new();
        let r = m.record(CompactionGossipHealthInput { diverged_peers: 1, ..healthy(1) });
        assert_eq!(r.health_class, CompactionGossipHealthClass::Red);
    }

    #[test]
    fn red_on_three_checksum_fails() {
        let mut m = CompactionGossipHealthMonitor::new();
        let r = m.record(CompactionGossipHealthInput {
            validator_checksum_fails: 3, ..healthy(1)
        });
        assert_eq!(r.health_class, CompactionGossipHealthClass::Red);
    }

    #[test]
    fn two_checksum_fails_is_yellow_not_red() {
        let mut m = CompactionGossipHealthMonitor::new();
        let r = m.record(CompactionGossipHealthInput {
            validator_checksum_fails: 2, ..healthy(1)
        });
        assert_eq!(r.health_class, CompactionGossipHealthClass::Yellow);
    }

    #[test]
    fn red_on_delivery_blackout() {
        let mut m = CompactionGossipHealthMonitor::new();
        let r = m.record(CompactionGossipHealthInput {
            delivered_count: 0,
            admitted_peers: 2,
            ..healthy(1)
        });
        assert_eq!(r.health_class, CompactionGossipHealthClass::Red);
    }

    #[test]
    fn zero_admitted_zero_delivered_is_green() {
        let mut m = CompactionGossipHealthMonitor::new();
        let r = m.record(CompactionGossipHealthInput {
            delivered_count: 0,
            admitted_peers: 0,
            missed_count: 0,
            ..healthy(1)
        });
        assert_eq!(r.health_class, CompactionGossipHealthClass::Green);
    }

    // ── aggregate counts ──────────────────────────────────────────────────────

    #[test]
    fn aggregate_counts_correct() {
        let mut m = CompactionGossipHealthMonitor::new();
        m.record(healthy(1));
        m.record(CompactionGossipHealthInput { lagging_peers: 1, ..healthy(2) });
        m.record(CompactionGossipHealthInput { diverged_peers: 1, ..healthy(3) });
        assert_eq!(m.green_count(), 1);
        assert_eq!(m.yellow_count(), 1);
        assert_eq!(m.red_count(), 1);
    }

    // ── hash chain ────────────────────────────────────────────────────────────

    #[test]
    fn first_report_prev_hash_is_genesis() {
        let mut m = CompactionGossipHealthMonitor::new();
        let r = m.record(healthy(1));
        assert_eq!(r.prev_hash, GOSSIP_HEALTH_GENESIS_HASH);
    }

    #[test]
    fn report_hash_nonzero() {
        let mut m = CompactionGossipHealthMonitor::new();
        let r = m.record(healthy(1));
        assert_ne!(r.report_hash, [0u8; 32]);
    }

    #[test]
    fn prev_hash_links_correctly() {
        let mut m = CompactionGossipHealthMonitor::new();
        m.record(healthy(1));
        let h0 = m.reports()[0].report_hash;
        m.record(healthy(2));
        assert_eq!(m.reports()[1].prev_hash, h0);
    }

    #[test]
    fn verify_chain_empty_ok() {
        let m = CompactionGossipHealthMonitor::new();
        let (ok, idx) = m.verify_chain();
        assert!(ok);
        assert!(idx.is_none());
    }

    #[test]
    fn verify_chain_three_records_ok() {
        let mut m = CompactionGossipHealthMonitor::new();
        for i in 1u64..=3 { m.record(healthy(i)); }
        let (ok, idx) = m.verify_chain();
        assert!(ok);
        assert!(idx.is_none());
    }

    #[test]
    fn verify_chain_detects_tamper() {
        let mut m = CompactionGossipHealthMonitor::new();
        m.record(healthy(1));
        m.record(healthy(2));
        m.reports[0].report_hash[0] ^= 0xFF;
        let (ok, idx) = m.verify_chain();
        assert!(!ok);
        assert_eq!(idx, Some(0));
    }

    // ── determinism ───────────────────────────────────────────────────────────

    #[test]
    fn report_hash_deterministic() {
        let mut m1 = CompactionGossipHealthMonitor::new();
        let mut m2 = CompactionGossipHealthMonitor::new();
        let h1 = m1.record(healthy(5)).report_hash;
        let h2 = m2.record(healthy(5)).report_hash;
        assert_eq!(h1, h2);
    }
}
