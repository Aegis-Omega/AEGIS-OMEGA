//! Gate 283 — Mesh Partition Detector: network partition detection from probe evidence (T2)
//! EPISTEMIC TIER: T2 (engineering hypothesis)
//!
//! Analyzes gossip probe reachability data to classify the mesh topology into
//! partition states. Uses integer-only arithmetic. BTreeMap for deterministic iteration.
//!
//! PartitionClass:
//!   Unified       — all registered nodes reach each other (symmetric reachability)
//!   Asymmetric    — some one-way reachability gaps exist (A→B ok, B→A failed)
//!   Clustered     — two or more disconnected reachability groups detected
//!   Isolated(u32) — specific node cannot reach any other node
//!   Unknown       — insufficient probe data (<2 nodes probed)
//!
//! PartitionReport:
//!   epoch            — u64
//!   class            — PartitionClass
//!   reachable_pairs  — u32 (number of (a,b) pairs where a can reach b)
//!   total_pairs      — u32 (number of registered (a,b) pairs)
//!   reachability_pct — u8  (reachable_pairs * 100 / total_pairs; 0 if total=0)
//!   report_hash      — SHA-256(prev ‖ epoch_be8 ‖ class_byte ‖ reachable_be4 ‖ total_be4)
//!   prev_hash        — [u8; 32]
//!
//! PartitionLog: hash-chained PartitionReports.
//!   record(), partition_count_by_class(), longest_non_unified_run(), verify_chain().
//!
//! detect_partition(node_ids, reachability_fn) → PartitionClass
//!   Given a set of node IDs and a closure mapping (from, to) → bool,
//!   classifies the current mesh partition state.

use sha2::{Sha256, Digest};
use std::collections::BTreeSet;

// ─── Partition class ──────────────────────────────────────────────────────────

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum PartitionClass {
    Unified,
    Asymmetric,
    Clustered,
    Isolated(u32),
    Unknown,
}

impl PartitionClass {
    pub fn class_byte(self) -> u8 {
        match self {
            Self::Unified      => 0,
            Self::Asymmetric   => 1,
            Self::Clustered    => 2,
            Self::Isolated(_)  => 3,
            Self::Unknown      => 4,
        }
    }

    pub fn is_healthy(self) -> bool { matches!(self, Self::Unified) }
}

// ─── Partition detection algorithm ───────────────────────────────────────────

/// Classify partition state given a set of nodes and a reachability oracle.
///
/// Algorithm (integer arithmetic, no floats, BTreeSet for determinism):
/// 1. If fewer than 2 nodes → Unknown
/// 2. For each ordered pair (a, b) where a != b, call reachability_fn(a, b)
/// 3. Check symmetry: if any (a→b)==true && (b→a)==false → Asymmetric
/// 4. Find isolated nodes: a node where NO outgoing probe (a→x) is true → Isolated(first found)
/// 5. Compute reachable component sets via BFS using only reachability_fn;
///    if number of distinct components > 1 → Clustered
/// 6. All pairs reachable → Unified
pub fn detect_partition<F>(node_ids: &BTreeSet<u32>, reachability_fn: F) -> PartitionClass
where
    F: Fn(u32, u32) -> bool,
{
    if node_ids.len() < 2 {
        return PartitionClass::Unknown;
    }

    let nodes: Vec<u32> = node_ids.iter().copied().collect();

    // Check for isolated nodes (no outgoing reachability at all)
    for &a in &nodes {
        let any_out = nodes.iter().any(|&b| b != a && reachability_fn(a, b));
        if !any_out {
            return PartitionClass::Isolated(a);
        }
    }

    // Check symmetry: a→b but not b→a
    for &a in &nodes {
        for &b in &nodes {
            if a == b { continue; }
            if reachability_fn(a, b) && !reachability_fn(b, a) {
                return PartitionClass::Asymmetric;
            }
        }
    }

    // BFS component analysis (undirected: (a,b) edge if reachability_fn(a,b))
    let mut visited: BTreeSet<u32> = BTreeSet::new();
    let mut component_count = 0usize;

    for &start in &nodes {
        if visited.contains(&start) { continue; }
        component_count += 1;
        if component_count > 1 { return PartitionClass::Clustered; }
        let mut queue: Vec<u32> = vec![start];
        visited.insert(start);
        while let Some(curr) = queue.pop() {
            for &neighbor in &nodes {
                if !visited.contains(&neighbor) && reachability_fn(curr, neighbor) {
                    visited.insert(neighbor);
                    queue.push(neighbor);
                }
            }
        }
    }

    PartitionClass::Unified
}

/// Count reachable (a,b) pairs in node set.
pub fn count_reachable_pairs<F>(node_ids: &BTreeSet<u32>, reachability_fn: F) -> (u32, u32)
where
    F: Fn(u32, u32) -> bool,
{
    let nodes: Vec<u32> = node_ids.iter().copied().collect();
    let n = nodes.len() as u32;
    if n < 2 { return (0, 0); }
    let total = n * (n - 1);
    let mut reachable = 0u32;
    for &a in &nodes {
        for &b in &nodes {
            if a != b && reachability_fn(a, b) { reachable += 1; }
        }
    }
    (reachable, total)
}

// ─── Partition report ─────────────────────────────────────────────────────────

#[derive(Debug, Clone, PartialEq)]
pub struct PartitionReport {
    pub epoch:            u64,
    pub class:            PartitionClass,
    pub reachable_pairs:  u32,
    pub total_pairs:      u32,
    pub reachability_pct: u8,
    pub report_hash:      [u8; 32],
    pub prev_hash:        [u8; 32],
}

pub const PARTITION_GENESIS_HASH: [u8; 32] = [0u8; 32];

fn compute_report_hash(
    epoch:           u64,
    class:           PartitionClass,
    reachable_pairs: u32,
    total_pairs:     u32,
    prev:            &[u8; 32],
) -> [u8; 32] {
    let mut h = Sha256::new();
    h.update(prev);
    h.update(epoch.to_be_bytes());
    h.update([class.class_byte()]);
    h.update(reachable_pairs.to_be_bytes());
    h.update(total_pairs.to_be_bytes());
    h.finalize().into()
}

pub fn build_partition_report(
    epoch:           u64,
    class:           PartitionClass,
    reachable_pairs: u32,
    total_pairs:     u32,
    prev_hash:       &[u8; 32],
) -> PartitionReport {
    let reachability_pct = if total_pairs == 0 {
        0
    } else {
        ((reachable_pairs as u64 * 100) / total_pairs as u64).min(100) as u8
    };
    let report_hash = compute_report_hash(epoch, class, reachable_pairs, total_pairs, prev_hash);
    PartitionReport {
        epoch, class, reachable_pairs, total_pairs, reachability_pct,
        report_hash, prev_hash: *prev_hash,
    }
}

// ─── Partition log ────────────────────────────────────────────────────────────

#[derive(Debug, Clone)]
pub struct PartitionLog {
    records: Vec<PartitionReport>,
}

#[derive(Debug)]
pub enum PartitionError {
    StaleEpoch,
}

impl PartitionLog {
    pub fn new() -> Self { Self { records: Vec::new() } }

    pub fn len(&self)     -> usize { self.records.len() }
    pub fn is_empty(&self) -> bool { self.records.is_empty() }
    pub fn records(&self) -> &[PartitionReport] { &self.records }

    pub fn last_hash(&self) -> [u8; 32] {
        self.records.last().map(|r| r.report_hash).unwrap_or(PARTITION_GENESIS_HASH)
    }

    pub fn record(
        &mut self,
        epoch:           u64,
        class:           PartitionClass,
        reachable_pairs: u32,
        total_pairs:     u32,
    ) -> Result<&PartitionReport, PartitionError> {
        if let Some(last) = self.records.last() {
            if epoch <= last.epoch {
                return Err(PartitionError::StaleEpoch);
            }
        }
        let prev = self.last_hash();
        let r = build_partition_report(epoch, class, reachable_pairs, total_pairs, &prev);
        self.records.push(r);
        Ok(self.records.last().unwrap())
    }

    /// Number of epochs where class == Unified.
    pub fn unified_count(&self) -> usize {
        self.records.iter().filter(|r| r.class == PartitionClass::Unified).count()
    }

    /// Number of epochs where class != Unified.
    pub fn partition_count(&self) -> usize {
        self.records.iter().filter(|r| r.class != PartitionClass::Unified).count()
    }

    /// Longest consecutive run of non-Unified epochs.
    pub fn longest_non_unified_run(&self) -> usize {
        let mut max_run = 0usize;
        let mut run = 0usize;
        for r in &self.records {
            if r.class != PartitionClass::Unified {
                run += 1;
                if run > max_run { max_run = run; }
            } else {
                run = 0;
            }
        }
        max_run
    }

    pub fn latest(&self) -> Option<&PartitionReport> { self.records.last() }

    pub fn verify_chain(&self) -> (bool, Option<usize>) {
        let mut expected_prev = PARTITION_GENESIS_HASH;
        for (i, r) in self.records.iter().enumerate() {
            if r.prev_hash != expected_prev {
                return (false, Some(i));
            }
            let recomputed = compute_report_hash(
                r.epoch, r.class, r.reachable_pairs, r.total_pairs, &r.prev_hash,
            );
            if recomputed != r.report_hash {
                return (false, Some(i));
            }
            expected_prev = r.report_hash;
        }
        (true, None)
    }
}

impl Default for PartitionLog {
    fn default() -> Self { Self::new() }
}

// ─── Tests ───────────────────────────────────────────────────────────────────

#[cfg(test)]
mod tests {
    use super::*;

    fn nodes(ids: &[u32]) -> BTreeSet<u32> { ids.iter().copied().collect() }

    // ── detect_partition ──────────────────────────────────────────────────────

    #[test]
    fn single_node_unknown() {
        let n = nodes(&[1]);
        assert_eq!(detect_partition(&n, |_, _| true), PartitionClass::Unknown);
    }

    #[test]
    fn two_nodes_unified() {
        let n = nodes(&[1, 2]);
        assert_eq!(detect_partition(&n, |_, _| true), PartitionClass::Unified);
    }

    #[test]
    fn three_nodes_unified() {
        let n = nodes(&[1, 2, 3]);
        assert_eq!(detect_partition(&n, |_, _| true), PartitionClass::Unified);
    }

    #[test]
    fn isolated_node_detected() {
        // node 3 cannot reach anything
        let n = nodes(&[1, 2, 3]);
        let r = detect_partition(&n, |a, _b| a != 3);
        // node 3 has no outgoing → Isolated(3)
        assert_eq!(r, PartitionClass::Isolated(3));
    }

    #[test]
    fn asymmetric_detected() {
        // 1→2 ok, 2→1 not ok, 3 symmetric with others
        let n = nodes(&[1, 2, 3]);
        let r = detect_partition(&n, |a, b| {
            if a == 2 && b == 1 { false } else { true }
        });
        assert_eq!(r, PartitionClass::Asymmetric);
    }

    #[test]
    fn clustered_detected() {
        // {1,2} can reach each other; {3,4} can reach each other; no cross-cluster reachability
        let n = nodes(&[1, 2, 3, 4]);
        let r = detect_partition(&n, |a, b| {
            (a <= 2 && b <= 2) || (a >= 3 && b >= 3)
        });
        assert_eq!(r, PartitionClass::Clustered);
    }

    #[test]
    fn unified_is_healthy() {
        assert!(PartitionClass::Unified.is_healthy());
        assert!(!PartitionClass::Clustered.is_healthy());
        assert!(!PartitionClass::Isolated(1).is_healthy());
    }

    // ── count_reachable_pairs ─────────────────────────────────────────────────

    #[test]
    fn count_pairs_all_reachable() {
        let n = nodes(&[1, 2, 3]);
        let (r, t) = count_reachable_pairs(&n, |_, _| true);
        assert_eq!(t, 6); // 3*(3-1)
        assert_eq!(r, 6);
    }

    #[test]
    fn count_pairs_none_reachable() {
        let n = nodes(&[1, 2, 3]);
        let (r, t) = count_reachable_pairs(&n, |_, _| false);
        assert_eq!(r, 0);
        assert_eq!(t, 6);
    }

    // ── build_partition_report ────────────────────────────────────────────────

    #[test]
    fn report_hash_nonzero() {
        let r = build_partition_report(1, PartitionClass::Unified, 4, 4, &PARTITION_GENESIS_HASH);
        assert_ne!(r.report_hash, [0u8; 32]);
    }

    #[test]
    fn report_hash_deterministic() {
        let r1 = build_partition_report(1, PartitionClass::Unified, 4, 4, &PARTITION_GENESIS_HASH);
        let r2 = build_partition_report(1, PartitionClass::Unified, 4, 4, &PARTITION_GENESIS_HASH);
        assert_eq!(r1.report_hash, r2.report_hash);
    }

    #[test]
    fn reachability_pct_computed() {
        let r = build_partition_report(1, PartitionClass::Clustered, 2, 4, &PARTITION_GENESIS_HASH);
        assert_eq!(r.reachability_pct, 50);
    }

    #[test]
    fn zero_total_pct_zero() {
        let r = build_partition_report(1, PartitionClass::Unknown, 0, 0, &PARTITION_GENESIS_HASH);
        assert_eq!(r.reachability_pct, 0);
    }

    // ── PartitionLog ──────────────────────────────────────────────────────────

    #[test]
    fn new_log_empty() {
        let l = PartitionLog::new();
        assert!(l.is_empty());
        assert_eq!(l.unified_count(), 0);
        assert_eq!(l.partition_count(), 0);
    }

    #[test]
    fn record_and_classify() {
        let mut l = PartitionLog::new();
        l.record(1, PartitionClass::Unified, 6, 6).unwrap();
        l.record(2, PartitionClass::Clustered, 2, 6).unwrap();
        l.record(3, PartitionClass::Unified, 6, 6).unwrap();
        assert_eq!(l.unified_count(), 2);
        assert_eq!(l.partition_count(), 1);
    }

    #[test]
    fn stale_epoch_rejected() {
        let mut l = PartitionLog::new();
        l.record(5, PartitionClass::Unified, 4, 4).unwrap();
        assert!(matches!(l.record(4, PartitionClass::Unified, 4, 4), Err(PartitionError::StaleEpoch)));
    }

    #[test]
    fn hash_chain_links() {
        let mut l = PartitionLog::new();
        l.record(1, PartitionClass::Unified, 4, 4).unwrap();
        l.record(2, PartitionClass::Clustered, 2, 4).unwrap();
        assert_eq!(l.records()[1].prev_hash, l.records()[0].report_hash);
    }

    #[test]
    fn longest_non_unified_run() {
        let mut l = PartitionLog::new();
        l.record(1, PartitionClass::Unified,   4, 4).unwrap();
        l.record(2, PartitionClass::Clustered, 2, 4).unwrap();
        l.record(3, PartitionClass::Asymmetric,3, 4).unwrap();
        l.record(4, PartitionClass::Unified,   4, 4).unwrap();
        l.record(5, PartitionClass::Clustered, 2, 4).unwrap();
        assert_eq!(l.longest_non_unified_run(), 2);
    }

    #[test]
    fn verify_chain_valid() {
        let mut l = PartitionLog::new();
        for e in 1..=6u64 {
            l.record(e, PartitionClass::Unified, 4, 4).unwrap();
        }
        let (valid, broken) = l.verify_chain();
        assert!(valid);
        assert!(broken.is_none());
    }
}
