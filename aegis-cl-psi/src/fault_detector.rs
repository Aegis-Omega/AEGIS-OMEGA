//! Gate 263 — Fault Detector: mesh-wide fault pattern classifier (T2)
//! EPISTEMIC TIER: T2 (engineering hypothesis)
//!
//! Analyses NodeHistory records across the mesh to classify fault patterns.
//! Fault classification helps triage whether degradations are isolated or systemic.
//!
//! FaultClass:
//!   None       — no degradations detected
//!   Isolated   — 1 node degraded (local fault)
//!   Correlated — 2+ nodes degraded within same epoch window
//!   Cascading  — degradation count increasing monotonically over window
//!
//! FaultReport:
//!   epoch              — u64 (epoch at assessment time)
//!   degraded_nodes     — Vec<u32> (node_ids currently in Degraded or Halted state)
//!   fault_class        — FaultClass
//!   window_epochs      — u8 (how many epochs back were analysed)
//!   report_hash        — SHA-256(epoch_be8 ‖ degraded_count_be8 ‖ fault_class_byte ‖ prev_hash)
//!
//! FaultLog: hash-chained FaultReports.
//! assess(epoch, histories) → FaultReport

use sha2::{Sha256, Digest};
use std::collections::BTreeMap;
use crate::node_state_machine::{NodeHistory, NodeState};

// ─── Fault class ──────────────────────────────────────────────────────────────

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum FaultClass {
    None       = 0,
    Isolated   = 1,
    Correlated = 2,
    Cascading  = 3,
}

impl FaultClass {
    pub fn as_u8(self) -> u8 { self as u8 }

    pub fn as_str(self) -> &'static str {
        match self {
            Self::None       => "none",
            Self::Isolated   => "isolated",
            Self::Correlated => "correlated",
            Self::Cascading  => "cascading",
        }
    }

    pub fn is_systemic(self) -> bool {
        matches!(self, Self::Correlated | Self::Cascading)
    }

    pub fn requires_intervention(self) -> bool {
        self == Self::Cascading
    }
}

// ─── Fault report ─────────────────────────────────────────────────────────────

#[derive(Debug, Clone, PartialEq)]
pub struct FaultReport {
    pub epoch:          u64,
    pub degraded_nodes: Vec<u32>,
    pub fault_class:    FaultClass,
    pub window_epochs:  u8,
    pub report_hash:    [u8; 32],
    pub prev_hash:      [u8; 32],
}

impl FaultReport {
    pub fn degraded_count(&self) -> usize { self.degraded_nodes.len() }
    pub fn is_clean(&self) -> bool { self.fault_class == FaultClass::None }
}

pub const FAULT_GENESIS_HASH: [u8; 32] = [0u8; 32];

fn compute_report_hash(
    epoch:          u64,
    degraded_count: usize,
    fault_class:    FaultClass,
    prev:           &[u8; 32],
) -> [u8; 32] {
    let mut h = Sha256::new();
    h.update(prev);
    h.update(epoch.to_be_bytes());
    h.update((degraded_count as u64).to_be_bytes());
    h.update([fault_class.as_u8()]);
    h.finalize().into()
}

// ─── Assessment logic ─────────────────────────────────────────────────────────

/// Count nodes currently in Degraded or Halted state.
fn count_degraded(histories: &[&NodeHistory]) -> Vec<u32> {
    let mut degraded: Vec<u32> = histories.iter()
        .filter(|h| matches!(h.current_state(), NodeState::Degraded | NodeState::Halted))
        .map(|h| h.node_id())
        .collect();
    degraded.sort(); // BTreeMap-style: deterministic order
    degraded
}

/// Count degraded events per epoch within [epoch - window, epoch].
fn epoch_degradation_counts(
    histories: &[&NodeHistory],
    epoch:     u64,
    window:    u8,
) -> BTreeMap<u64, usize> {
    let start_epoch = epoch.saturating_sub(window as u64);
    let mut counts: BTreeMap<u64, usize> = BTreeMap::new();
    for h in histories {
        for rec in h.records() {
            if rec.to_state == NodeState::Degraded
                && rec.epoch >= start_epoch
                && rec.epoch <= epoch
            {
                *counts.entry(rec.epoch).or_insert(0) += 1;
            }
        }
    }
    counts
}

fn classify_fault(
    degraded_count: usize,
    epoch_counts:   &BTreeMap<u64, usize>,
) -> FaultClass {
    if degraded_count == 0 {
        return FaultClass::None;
    }
    if degraded_count == 1 {
        return FaultClass::Isolated;
    }
    // Check for cascading: is the degradation count monotonically increasing?
    let values: Vec<usize> = epoch_counts.values().copied().collect();
    if values.len() >= 2 {
        let monotone = values.windows(2).all(|w| w[1] >= w[0]);
        if monotone {
            return FaultClass::Cascading;
        }
    }
    FaultClass::Correlated
}

pub fn assess(
    epoch:     u64,
    histories: &[&NodeHistory],
    window:    u8,
    prev_hash: &[u8; 32],
) -> FaultReport {
    let degraded_nodes = count_degraded(histories);
    let epoch_counts   = epoch_degradation_counts(histories, epoch, window);
    let fault_class    = classify_fault(degraded_nodes.len(), &epoch_counts);
    let report_hash    = compute_report_hash(epoch, degraded_nodes.len(), fault_class, prev_hash);

    FaultReport {
        epoch,
        degraded_nodes,
        fault_class,
        window_epochs: window,
        report_hash,
        prev_hash: *prev_hash,
    }
}

// ─── Fault log ────────────────────────────────────────────────────────────────

#[derive(Debug, Clone)]
pub struct FaultLog {
    reports: Vec<FaultReport>,
}

#[derive(Debug)]
pub enum FaultLogError {
    StaleEpoch,
}

impl FaultLogError {
    pub fn as_str(&self) -> &'static str { "stale epoch" }
}

impl FaultLog {
    pub fn new() -> Self { Self { reports: Vec::new() } }

    pub fn len(&self) -> usize { self.reports.len() }
    pub fn is_empty(&self) -> bool { self.reports.is_empty() }
    pub fn reports(&self) -> &[FaultReport] { &self.reports }
    pub fn latest(&self) -> Option<&FaultReport> { self.reports.last() }

    pub fn last_hash(&self) -> [u8; 32] {
        self.reports.last().map(|r| r.report_hash).unwrap_or(FAULT_GENESIS_HASH)
    }

    pub fn record(
        &mut self,
        epoch:     u64,
        histories: &[&NodeHistory],
        window:    u8,
    ) -> Result<&FaultReport, FaultLogError> {
        if let Some(last) = self.reports.last() {
            if epoch < last.epoch {
                return Err(FaultLogError::StaleEpoch);
            }
        }
        let prev_hash = self.last_hash();
        let report = assess(epoch, histories, window, &prev_hash);
        self.reports.push(report);
        Ok(self.reports.last().unwrap())
    }

    pub fn cascading_count(&self) -> usize {
        self.reports.iter().filter(|r| r.fault_class == FaultClass::Cascading).count()
    }

    pub fn max_degraded_count(&self) -> usize {
        self.reports.iter().map(|r| r.degraded_count()).max().unwrap_or(0)
    }

    pub fn verify_chain(&self) -> (bool, Option<usize>) {
        let mut expected_prev = FAULT_GENESIS_HASH;
        for (i, rep) in self.reports.iter().enumerate() {
            if rep.prev_hash != expected_prev {
                return (false, Some(i));
            }
            let recomputed = compute_report_hash(
                rep.epoch, rep.degraded_count(), rep.fault_class, &rep.prev_hash);
            if recomputed != rep.report_hash {
                return (false, Some(i));
            }
            expected_prev = rep.report_hash;
        }
        (true, None)
    }
}

impl Default for FaultLog {
    fn default() -> Self { Self::new() }
}

// ─── Tests ───────────────────────────────────────────────────────────────────

#[cfg(test)]
mod tests {
    use super::*;
    use crate::node_state_machine::NodeHistory;

    fn active_node(id: u32) -> NodeHistory {
        let mut h = NodeHistory::new(id);
        h.transition(NodeState::Active, 1, "boot").unwrap();
        h
    }

    fn degraded_node(id: u32, epoch: u64) -> NodeHistory {
        let mut h = NodeHistory::new(id);
        h.transition(NodeState::Active, 1, "boot").unwrap();
        h.transition(NodeState::Degraded, epoch, "fault").unwrap();
        h
    }

    // ── FaultClass ───────────────────────────────────────────────────────────

    #[test]
    fn fault_class_as_str() {
        assert_eq!(FaultClass::None.as_str(),       "none");
        assert_eq!(FaultClass::Isolated.as_str(),   "isolated");
        assert_eq!(FaultClass::Correlated.as_str(), "correlated");
        assert_eq!(FaultClass::Cascading.as_str(),  "cascading");
    }

    #[test]
    fn systemic_and_intervention_flags() {
        assert!(!FaultClass::None.is_systemic());
        assert!(!FaultClass::Isolated.is_systemic());
        assert!(FaultClass::Correlated.is_systemic());
        assert!(FaultClass::Cascading.is_systemic());
        assert!(FaultClass::Cascading.requires_intervention());
        assert!(!FaultClass::Correlated.requires_intervention());
    }

    // ── assess ───────────────────────────────────────────────────────────────

    #[test]
    fn no_degraded_nodes_none_class() {
        let a = active_node(1);
        let b = active_node(2);
        let r = assess(5, &[&a, &b], 3, &FAULT_GENESIS_HASH);
        assert_eq!(r.fault_class, FaultClass::None);
        assert_eq!(r.degraded_count(), 0);
        assert!(r.is_clean());
    }

    #[test]
    fn single_degraded_isolated() {
        let a = active_node(1);
        let d = degraded_node(2, 3);
        let r = assess(5, &[&a, &d], 3, &FAULT_GENESIS_HASH);
        assert_eq!(r.fault_class, FaultClass::Isolated);
        assert_eq!(r.degraded_count(), 1);
        assert_eq!(r.degraded_nodes, vec![2]);
    }

    #[test]
    fn two_degraded_same_epoch_correlated() {
        let d1 = degraded_node(1, 3);
        let d2 = degraded_node(2, 3);
        let r = assess(5, &[&d1, &d2], 4, &FAULT_GENESIS_HASH);
        assert_eq!(r.fault_class, FaultClass::Correlated);
        assert_eq!(r.degraded_count(), 2);
    }

    #[test]
    fn increasing_degradations_cascading() {
        // epoch 3: 1 node, epoch 4: 1 more, epoch 5: 1 more → monotone increasing
        let mut h1 = NodeHistory::new(1);
        h1.transition(NodeState::Active, 1, "boot").unwrap();
        h1.transition(NodeState::Degraded, 3, "fault").unwrap();

        let mut h2 = NodeHistory::new(2);
        h2.transition(NodeState::Active, 1, "boot").unwrap();
        h2.transition(NodeState::Degraded, 4, "fault").unwrap();

        let mut h3 = NodeHistory::new(3);
        h3.transition(NodeState::Active, 1, "boot").unwrap();
        h3.transition(NodeState::Degraded, 5, "fault").unwrap();

        let r = assess(5, &[&h1, &h2, &h3], 5, &FAULT_GENESIS_HASH);
        assert_eq!(r.fault_class, FaultClass::Cascading);
    }

    #[test]
    fn degraded_nodes_sorted() {
        let d3 = degraded_node(3, 2);
        let d1 = degraded_node(1, 2);
        let d2 = degraded_node(2, 2);
        let r = assess(5, &[&d3, &d1, &d2], 4, &FAULT_GENESIS_HASH);
        assert_eq!(r.degraded_nodes, vec![1, 2, 3]);
    }

    #[test]
    fn report_hash_nonzero() {
        let d = degraded_node(1, 3);
        let r = assess(5, &[&d], 4, &FAULT_GENESIS_HASH);
        assert_ne!(r.report_hash, [0u8; 32]);
    }

    #[test]
    fn report_hash_deterministic() {
        let d = degraded_node(1, 3);
        let r1 = assess(5, &[&d], 4, &FAULT_GENESIS_HASH);
        let r2 = assess(5, &[&d], 4, &FAULT_GENESIS_HASH);
        assert_eq!(r1.report_hash, r2.report_hash);
    }

    // ── FaultLog ─────────────────────────────────────────────────────────────

    #[test]
    fn new_log_empty() {
        let l = FaultLog::new();
        assert!(l.is_empty());
        assert_eq!(l.last_hash(), FAULT_GENESIS_HASH);
    }

    #[test]
    fn record_tracks() {
        let mut l = FaultLog::new();
        let a = active_node(1);
        l.record(1, &[&a], 3).unwrap();
        l.record(2, &[&a], 3).unwrap();
        assert_eq!(l.len(), 2);
    }

    #[test]
    fn stale_epoch_rejected() {
        let mut l = FaultLog::new();
        let a = active_node(1);
        l.record(5, &[&a], 3).unwrap();
        assert!(matches!(l.record(4, &[&a], 3), Err(FaultLogError::StaleEpoch)));
    }

    #[test]
    fn cascading_count_tracked() {
        let mut l = FaultLog::new();
        let a = active_node(1);
        // build a cascading scenario
        let mut h1 = NodeHistory::new(10);
        h1.transition(NodeState::Active, 1, "boot").unwrap();
        h1.transition(NodeState::Degraded, 1, "f1").unwrap();
        let mut h2 = NodeHistory::new(11);
        h2.transition(NodeState::Active, 1, "boot").unwrap();
        h2.transition(NodeState::Degraded, 2, "f2").unwrap();
        let mut h3 = NodeHistory::new(12);
        h3.transition(NodeState::Active, 1, "boot").unwrap();
        h3.transition(NodeState::Degraded, 3, "f3").unwrap();
        l.record(1, &[&a], 3).unwrap(); // none
        l.record(5, &[&h1, &h2, &h3], 5).unwrap(); // cascading
        assert_eq!(l.cascading_count(), 1);
        assert_eq!(l.max_degraded_count(), 3);
    }

    #[test]
    fn verify_chain_valid() {
        let mut l = FaultLog::new();
        let a = active_node(1);
        for e in 1..=4u64 {
            l.record(e, &[&a], 3).unwrap();
        }
        let (valid, broken) = l.verify_chain();
        assert!(valid);
        assert!(broken.is_none());
    }
}
