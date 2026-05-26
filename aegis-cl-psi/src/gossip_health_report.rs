//! Gate 320 — Gossip Network Health Report: constitutional health synthesis (T2)
//! EPISTEMIC TIER: T2 (engineering hypothesis)
//!
//! Aggregates signals from the gossip layer (liveness, rate accounting, sequence
//! integrity) into a single `GossipHealthReport` with a `NetworkHealthClass` verdict.
//! Reports are hash-chained for audit replay.
//!
//! Classification rules (top-to-bottom, first match):
//!   Red    — dead_peers ≥ 1
//!             OR exceeded_epochs ≥ RED_EXCEEDED_THRESHOLD (3)
//!             OR sequence_gaps  ≥ RED_GAP_THRESHOLD (10)
//!   Yellow — degraded_peers ≥ 1
//!             OR suspect_peers  ≥ 1
//!             OR total_dropped  ≥ YELLOW_DROP_THRESHOLD (100)
//!             OR sequence_gaps  ≥ 1
//!   Green  — all other cases
//!
//! report_hash = SHA-256(prev_hash[32] ‖ epoch_be8 ‖ live_be4 ‖ degraded_be4
//!               ‖ suspect_be4 ‖ dead_be4 ‖ dropped_be8 ‖ exceeded_be4
//!               ‖ gaps_be8 ‖ dups_be8 ‖ class_byte)
//!
//! GossipHealthMonitor: record(), latest(), health_class(), verify_chain().
//! verify_chain() → (bool, Option<usize>) — index of first invalid record.

use sha2::{Sha256, Digest};

pub const HEALTH_REPORT_GENESIS_HASH: [u8; 32] = [0u8; 32];

pub const RED_EXCEEDED_THRESHOLD: u32 = 3;
pub const RED_GAP_THRESHOLD:      u64 = 10;
pub const YELLOW_DROP_THRESHOLD:  u64 = 100;

// ─── Network health class ─────────────────────────────────────────────────────

#[derive(Debug, Clone, Copy, PartialEq, Eq, PartialOrd, Ord)]
pub enum NetworkHealthClass {
    Green  = 0,
    Yellow = 1,
    Red    = 2,
}

impl NetworkHealthClass {
    pub fn class_byte(self) -> u8 { self as u8 }

    pub fn classify(
        dead_peers:      u32,
        degraded_peers:  u32,
        suspect_peers:   u32,
        total_dropped:   u64,
        exceeded_epochs: u32,
        sequence_gaps:   u64,
    ) -> Self {
        if dead_peers >= 1
            || exceeded_epochs >= RED_EXCEEDED_THRESHOLD
            || sequence_gaps  >= RED_GAP_THRESHOLD
        {
            return NetworkHealthClass::Red;
        }
        if degraded_peers >= 1
            || suspect_peers  >= 1
            || total_dropped  >= YELLOW_DROP_THRESHOLD
            || sequence_gaps  >= 1
        {
            return NetworkHealthClass::Yellow;
        }
        NetworkHealthClass::Green
    }
}

// ─── Report input ─────────────────────────────────────────────────────────────

#[derive(Debug, Clone, Copy)]
pub struct HealthReportInput {
    pub epoch:           u64,
    pub live_peers:      u32,
    pub degraded_peers:  u32,
    pub suspect_peers:   u32,
    pub dead_peers:      u32,
    pub total_dropped:   u64,
    pub exceeded_epochs: u32,
    pub sequence_gaps:   u64,
    pub sequence_dups:   u64,
}

// ─── Gossip health report ─────────────────────────────────────────────────────

#[derive(Debug, Clone, PartialEq)]
pub struct GossipHealthReport {
    pub epoch:           u64,
    pub health_class:    NetworkHealthClass,
    pub live_peers:      u32,
    pub degraded_peers:  u32,
    pub suspect_peers:   u32,
    pub dead_peers:      u32,
    pub total_dropped:   u64,
    pub exceeded_epochs: u32,
    pub sequence_gaps:   u64,
    pub sequence_dups:   u64,
    pub report_hash:     [u8; 32],
    pub prev_hash:       [u8; 32],
}

fn compute_report_hash(prev: &[u8; 32], inp: &HealthReportInput, class: NetworkHealthClass) -> [u8; 32] {
    let mut h = Sha256::new();
    h.update(prev);
    h.update(inp.epoch.to_be_bytes());
    h.update(inp.live_peers.to_be_bytes());
    h.update(inp.degraded_peers.to_be_bytes());
    h.update(inp.suspect_peers.to_be_bytes());
    h.update(inp.dead_peers.to_be_bytes());
    h.update(inp.total_dropped.to_be_bytes());
    h.update(inp.exceeded_epochs.to_be_bytes());
    h.update(inp.sequence_gaps.to_be_bytes());
    h.update(inp.sequence_dups.to_be_bytes());
    h.update([class.class_byte()]);
    h.finalize().into()
}

// ─── Monitor ──────────────────────────────────────────────────────────────────

pub struct GossipHealthMonitor {
    reports: Vec<GossipHealthReport>,
}

impl GossipHealthMonitor {
    pub fn new() -> Self { Self { reports: Vec::new() } }

    pub fn len(&self)      -> usize { self.reports.len() }
    pub fn is_empty(&self) -> bool  { self.reports.is_empty() }
    pub fn reports(&self)  -> &[GossipHealthReport] { &self.reports }

    pub fn record(&mut self, inp: HealthReportInput) -> GossipHealthReport {
        let prev = self.reports.last()
            .map(|r| r.report_hash)
            .unwrap_or(HEALTH_REPORT_GENESIS_HASH);

        let class = NetworkHealthClass::classify(
            inp.dead_peers, inp.degraded_peers, inp.suspect_peers,
            inp.total_dropped, inp.exceeded_epochs, inp.sequence_gaps,
        );

        let report_hash = compute_report_hash(&prev, &inp, class);

        let r = GossipHealthReport {
            epoch:           inp.epoch,
            health_class:    class,
            live_peers:      inp.live_peers,
            degraded_peers:  inp.degraded_peers,
            suspect_peers:   inp.suspect_peers,
            dead_peers:      inp.dead_peers,
            total_dropped:   inp.total_dropped,
            exceeded_epochs: inp.exceeded_epochs,
            sequence_gaps:   inp.sequence_gaps,
            sequence_dups:   inp.sequence_dups,
            report_hash,
            prev_hash: prev,
        };
        self.reports.push(r.clone());
        r
    }

    pub fn latest(&self) -> Option<&GossipHealthReport> {
        self.reports.last()
    }

    pub fn health_class(&self) -> Option<NetworkHealthClass> {
        self.latest().map(|r| r.health_class)
    }

    /// Verifies hash chain integrity.
    /// Returns (true, None) if all links are valid.
    /// Returns (false, Some(idx)) where idx is the first broken record index.
    pub fn verify_chain(&self) -> (bool, Option<usize>) {
        let mut prev = HEALTH_REPORT_GENESIS_HASH;
        for (i, r) in self.reports.iter().enumerate() {
            if r.prev_hash != prev { return (false, Some(i)); }
            let expected = compute_report_hash(&prev, &HealthReportInput {
                epoch:           r.epoch,
                live_peers:      r.live_peers,
                degraded_peers:  r.degraded_peers,
                suspect_peers:   r.suspect_peers,
                dead_peers:      r.dead_peers,
                total_dropped:   r.total_dropped,
                exceeded_epochs: r.exceeded_epochs,
                sequence_gaps:   r.sequence_gaps,
                sequence_dups:   r.sequence_dups,
            }, r.health_class);
            if r.report_hash != expected { return (false, Some(i)); }
            prev = r.report_hash;
        }
        (true, None)
    }
}

impl Default for GossipHealthMonitor {
    fn default() -> Self { Self::new() }
}

// ─── Tests ────────────────────────────────────────────────────────────────────

#[cfg(test)]
mod tests {
    use super::*;

    fn all_live(epoch: u64) -> HealthReportInput {
        HealthReportInput { epoch, live_peers: 4, degraded_peers: 0, suspect_peers: 0,
            dead_peers: 0, total_dropped: 0, exceeded_epochs: 0, sequence_gaps: 0, sequence_dups: 0 }
    }

    #[test]
    fn fresh_monitor_no_reports() {
        let m = GossipHealthMonitor::new();
        assert!(m.is_empty());
        assert!(m.latest().is_none());
        assert!(m.health_class().is_none());
    }

    #[test]
    fn green_all_healthy() {
        let mut m = GossipHealthMonitor::new();
        let r = m.record(all_live(1));
        assert_eq!(r.health_class, NetworkHealthClass::Green);
        assert_eq!(m.health_class(), Some(NetworkHealthClass::Green));
    }

    #[test]
    fn yellow_degraded_peer() {
        let mut m = GossipHealthMonitor::new();
        let inp = HealthReportInput { degraded_peers: 1, ..all_live(1) };
        let r = m.record(inp);
        assert_eq!(r.health_class, NetworkHealthClass::Yellow);
    }

    #[test]
    fn yellow_suspect_peer() {
        let mut m = GossipHealthMonitor::new();
        let inp = HealthReportInput { suspect_peers: 1, ..all_live(1) };
        assert_eq!(m.record(inp).health_class, NetworkHealthClass::Yellow);
    }

    #[test]
    fn yellow_high_drop_count() {
        let mut m = GossipHealthMonitor::new();
        let inp = HealthReportInput { total_dropped: YELLOW_DROP_THRESHOLD, ..all_live(1) };
        assert_eq!(m.record(inp).health_class, NetworkHealthClass::Yellow);
    }

    #[test]
    fn yellow_one_sequence_gap() {
        let mut m = GossipHealthMonitor::new();
        let inp = HealthReportInput { sequence_gaps: 1, ..all_live(1) };
        assert_eq!(m.record(inp).health_class, NetworkHealthClass::Yellow);
    }

    #[test]
    fn red_dead_peer() {
        let mut m = GossipHealthMonitor::new();
        let inp = HealthReportInput { dead_peers: 1, live_peers: 3, ..all_live(1) };
        assert_eq!(m.record(inp).health_class, NetworkHealthClass::Red);
    }

    #[test]
    fn red_exceeded_epochs_threshold() {
        let mut m = GossipHealthMonitor::new();
        let inp = HealthReportInput { exceeded_epochs: RED_EXCEEDED_THRESHOLD, ..all_live(1) };
        assert_eq!(m.record(inp).health_class, NetworkHealthClass::Red);
    }

    #[test]
    fn red_sequence_gap_threshold() {
        let mut m = GossipHealthMonitor::new();
        let inp = HealthReportInput { sequence_gaps: RED_GAP_THRESHOLD, ..all_live(1) };
        assert_eq!(m.record(inp).health_class, NetworkHealthClass::Red);
    }

    #[test]
    fn hash_chain_links_correctly() {
        let mut m = GossipHealthMonitor::new();
        let r1 = m.record(all_live(1));
        let r2 = m.record(all_live(2));
        assert_eq!(r1.prev_hash, HEALTH_REPORT_GENESIS_HASH);
        assert_eq!(r2.prev_hash, r1.report_hash);
    }

    #[test]
    fn verify_chain_three_records() {
        let mut m = GossipHealthMonitor::new();
        m.record(all_live(1));
        m.record(HealthReportInput { degraded_peers: 1, ..all_live(2) });
        m.record(HealthReportInput { dead_peers: 1, live_peers: 3, ..all_live(3) });
        let (ok, idx) = m.verify_chain();
        assert!(ok);
        assert!(idx.is_none());
    }

    #[test]
    fn verify_chain_tampered() {
        let mut m = GossipHealthMonitor::new();
        m.record(all_live(1));
        m.record(all_live(2));
        m.reports[1].report_hash[0] ^= 0xff;
        let (ok, idx) = m.verify_chain();
        assert!(!ok);
        assert_eq!(idx, Some(1));
    }

    #[test]
    fn determinism_same_input_three_times() {
        let inp = all_live(42);
        let mut m1 = GossipHealthMonitor::new(); let r1 = m1.record(inp);
        let mut m2 = GossipHealthMonitor::new(); let r2 = m2.record(inp);
        let mut m3 = GossipHealthMonitor::new(); let r3 = m3.record(inp);
        assert_eq!(r1.report_hash, r2.report_hash);
        assert_eq!(r2.report_hash, r3.report_hash);
    }

    #[test]
    fn class_ordering_green_lt_red() {
        assert!(NetworkHealthClass::Green < NetworkHealthClass::Yellow);
        assert!(NetworkHealthClass::Yellow < NetworkHealthClass::Red);
    }
}
