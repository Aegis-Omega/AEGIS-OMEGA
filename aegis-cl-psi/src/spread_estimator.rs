//! Gate 272 — Spread Estimator: gossip message propagation reach estimator (T2)
//! EPISTEMIC TIER: T2 (engineering hypothesis)
//!
//! Estimates how many hops and nodes a gossip message will reach given the
//! current routing table state and gossip fanout. Uses purely integer arithmetic.
//!
//! SpreadModel:
//!   fanout        — u8 (number of peers each relay forwards to)
//!   max_ttl       — u8 (maximum hop count, from gossip_router::MAX_TTL)
//!   total_nodes   — usize (known mesh size)
//!
//! SpreadEstimate:
//!   source_node   — u32
//!   fanout        — u8
//!   max_ttl       — u8
//!   estimated_reach — usize (min(fanout^ttl geometric series sum, total_nodes))
//!   reach_pct     — u8 (estimated_reach * 100 / total_nodes, or 100 if empty)
//!   hops_to_quorum — Option<u8> (minimum hops for 1/φ quorum, None if unreachable)
//!   estimate_hash — SHA-256(source_be4 ‖ fanout ‖ max_ttl ‖ total_be8 ‖ prev_hash)
//!   prev_hash     — [u8; 32]
//!
//! EstimateLog: hash-chained SpreadEstimates; max_reach_pct(), quorum_reachable_count().

use sha2::{Sha256, Digest};

// ─── Spread model ─────────────────────────────────────────────────────────────

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub struct SpreadModel {
    pub fanout:      u8,
    pub max_ttl:     u8,
    pub total_nodes: usize,
}

impl SpreadModel {
    pub fn new(fanout: u8, max_ttl: u8, total_nodes: usize) -> Self {
        Self { fanout, max_ttl, total_nodes }
    }
}

/// Estimate reach: sum of geometric series 1 + f + f^2 + ... + f^ttl, capped at total_nodes.
/// Uses saturating integer arithmetic — no f64.
fn estimate_reach(fanout: u8, max_ttl: u8, total_nodes: usize) -> usize {
    if total_nodes == 0 || fanout == 0 { return 0; }
    if fanout == 1 {
        return (max_ttl as usize + 1).min(total_nodes);
    }
    // Sum geometric series iteratively with saturation
    let mut reach: usize = 1; // source node
    let mut layer: usize = 1;
    for _ in 0..max_ttl {
        layer = layer.saturating_mul(fanout as usize);
        reach = reach.saturating_add(layer);
        if reach >= total_nodes {
            return total_nodes;
        }
    }
    reach.min(total_nodes)
}

/// Compute minimum hops needed to reach at least 1/φ of total_nodes.
/// Returns None if unreachable within max_ttl.
fn hops_to_quorum(fanout: u8, max_ttl: u8, total_nodes: usize) -> Option<u8> {
    if total_nodes == 0 || fanout == 0 { return None; }
    // Quorum threshold: total_nodes * 618_034 / 1_000_000 (integer 1/φ)
    let quorum_needed = (total_nodes * 618_034 + 999_999) / 1_000_000; // ceiling
    let mut reach: usize = 1;
    let mut layer: usize = 1;
    for hop in 0..max_ttl {
        if reach >= quorum_needed { return Some(hop); }
        layer = layer.saturating_mul(fanout as usize);
        reach = reach.saturating_add(layer);
        if reach >= quorum_needed { return Some(hop + 1); }
    }
    if reach >= quorum_needed { Some(max_ttl) } else { None }
}

// ─── Spread estimate ──────────────────────────────────────────────────────────

#[derive(Debug, Clone, PartialEq)]
pub struct SpreadEstimate {
    pub source_node:       u32,
    pub fanout:            u8,
    pub max_ttl:           u8,
    pub total_nodes:       usize,
    pub estimated_reach:   usize,
    pub reach_pct:         u8,
    pub hops_to_quorum:    Option<u8>,
    pub estimate_hash:     [u8; 32],
    pub prev_hash:         [u8; 32],
}

pub const SPREAD_GENESIS_HASH: [u8; 32] = [0u8; 32];

fn compute_estimate_hash(
    source:      u32,
    fanout:      u8,
    max_ttl:     u8,
    total_nodes: usize,
    prev:        &[u8; 32],
) -> [u8; 32] {
    let mut h = Sha256::new();
    h.update(prev);
    h.update(source.to_be_bytes());
    h.update([fanout, max_ttl]);
    h.update((total_nodes as u64).to_be_bytes());
    h.finalize().into()
}

pub fn build_estimate(
    source_node: u32,
    model:       &SpreadModel,
    prev_hash:   &[u8; 32],
) -> SpreadEstimate {
    let estimated_reach = estimate_reach(model.fanout, model.max_ttl, model.total_nodes);
    let reach_pct = if model.total_nodes == 0 {
        100u8
    } else {
        ((estimated_reach * 100) / model.total_nodes).min(100) as u8
    };
    let hops = hops_to_quorum(model.fanout, model.max_ttl, model.total_nodes);
    let estimate_hash = compute_estimate_hash(
        source_node, model.fanout, model.max_ttl, model.total_nodes, prev_hash);

    SpreadEstimate {
        source_node,
        fanout:          model.fanout,
        max_ttl:         model.max_ttl,
        total_nodes:     model.total_nodes,
        estimated_reach,
        reach_pct,
        hops_to_quorum:  hops,
        estimate_hash,
        prev_hash:       *prev_hash,
    }
}

impl SpreadEstimate {
    pub fn quorum_reachable(&self) -> bool { self.hops_to_quorum.is_some() }
}

// ─── Estimate log ─────────────────────────────────────────────────────────────

#[derive(Debug, Clone)]
pub struct EstimateLog {
    estimates: Vec<SpreadEstimate>,
}

#[derive(Debug)]
pub enum EstimateError {
    EmptyLog,
}

impl EstimateLog {
    pub fn new() -> Self { Self { estimates: Vec::new() } }

    pub fn len(&self) -> usize { self.estimates.len() }
    pub fn is_empty(&self) -> bool { self.estimates.is_empty() }
    pub fn estimates(&self) -> &[SpreadEstimate] { &self.estimates }
    pub fn latest(&self) -> Option<&SpreadEstimate> { self.estimates.last() }

    pub fn last_hash(&self) -> [u8; 32] {
        self.estimates.last().map(|e| e.estimate_hash).unwrap_or(SPREAD_GENESIS_HASH)
    }

    pub fn record(&mut self, source_node: u32, model: &SpreadModel) -> &SpreadEstimate {
        let prev_hash = self.last_hash();
        let est = build_estimate(source_node, model, &prev_hash);
        self.estimates.push(est);
        self.estimates.last().unwrap()
    }

    pub fn max_reach_pct(&self) -> u8 {
        self.estimates.iter().map(|e| e.reach_pct).max().unwrap_or(0)
    }

    pub fn quorum_reachable_count(&self) -> usize {
        self.estimates.iter().filter(|e| e.quorum_reachable()).count()
    }

    pub fn verify_chain(&self) -> (bool, Option<usize>) {
        let mut expected_prev = SPREAD_GENESIS_HASH;
        for (i, est) in self.estimates.iter().enumerate() {
            if est.prev_hash != expected_prev {
                return (false, Some(i));
            }
            let recomputed = compute_estimate_hash(
                est.source_node, est.fanout, est.max_ttl, est.total_nodes, &est.prev_hash);
            if recomputed != est.estimate_hash {
                return (false, Some(i));
            }
            expected_prev = est.estimate_hash;
        }
        (true, None)
    }
}

impl Default for EstimateLog {
    fn default() -> Self { Self::new() }
}

// ─── Tests ───────────────────────────────────────────────────────────────────

#[cfg(test)]
mod tests {
    use super::*;

    // ── estimate_reach ────────────────────────────────────────────────────────

    #[test]
    fn fanout_2_ttl_3_capped() {
        // 1 + 2 + 4 + 8 = 15; capped at total_nodes if < 15
        assert_eq!(estimate_reach(2, 3, 10), 10); // capped at 10
        assert_eq!(estimate_reach(2, 3, 20), 15); // not capped
    }

    #[test]
    fn fanout_0_reach_0() {
        assert_eq!(estimate_reach(0, 5, 100), 0);
    }

    #[test]
    fn empty_mesh_reach_0() {
        assert_eq!(estimate_reach(3, 4, 0), 0);
    }

    #[test]
    fn fanout_1_linear_reach() {
        // fanout=1: source + 1 per hop = ttl+1
        assert_eq!(estimate_reach(1, 3, 100), 4); // 1+3 hops
    }

    #[test]
    fn fanout_3_ttl_2_capped() {
        // 1 + 3 + 9 = 13; capped at total
        assert_eq!(estimate_reach(3, 2, 8), 8);
    }

    // ── hops_to_quorum ────────────────────────────────────────────────────────

    #[test]
    fn quorum_reachable_with_high_fanout() {
        // 10 nodes, 1/φ quorum = 7; fanout=3: 1+3+9=13 >= 7 in 2 hops
        let h = hops_to_quorum(3, 5, 10);
        assert!(h.is_some());
        assert!(h.unwrap() <= 3);
    }

    #[test]
    fn quorum_unreachable_low_fanout() {
        // 100 nodes, quorum ~62; fanout=1, ttl=4: reach=5 — never reaches quorum
        let h = hops_to_quorum(1, 4, 100);
        assert!(h.is_none());
    }

    #[test]
    fn quorum_empty_mesh_none() {
        assert_eq!(hops_to_quorum(3, 5, 0), None);
    }

    // ── build_estimate ────────────────────────────────────────────────────────

    #[test]
    fn estimate_hash_nonzero() {
        let m = SpreadModel::new(3, 4, 50);
        let e = build_estimate(1, &m, &SPREAD_GENESIS_HASH);
        assert_ne!(e.estimate_hash, [0u8; 32]);
    }

    #[test]
    fn estimate_hash_deterministic() {
        let m = SpreadModel::new(3, 4, 50);
        let e1 = build_estimate(1, &m, &SPREAD_GENESIS_HASH);
        let e2 = build_estimate(1, &m, &SPREAD_GENESIS_HASH);
        assert_eq!(e1.estimate_hash, e2.estimate_hash);
    }

    #[test]
    fn reach_pct_capped_at_100() {
        let m = SpreadModel::new(10, 8, 5); // easily saturates
        let e = build_estimate(0, &m, &SPREAD_GENESIS_HASH);
        assert_eq!(e.reach_pct, 100);
    }

    #[test]
    fn quorum_reachable_flag() {
        let m = SpreadModel::new(3, 8, 20);
        let e = build_estimate(0, &m, &SPREAD_GENESIS_HASH);
        assert!(e.quorum_reachable());
    }

    // ── EstimateLog ───────────────────────────────────────────────────────────

    #[test]
    fn new_log_empty() {
        let l = EstimateLog::new();
        assert!(l.is_empty());
        assert_eq!(l.max_reach_pct(), 0);
        assert_eq!(l.quorum_reachable_count(), 0);
    }

    #[test]
    fn record_appends() {
        let mut l = EstimateLog::new();
        let m = SpreadModel::new(3, 4, 20);
        l.record(1, &m);
        l.record(2, &m);
        assert_eq!(l.len(), 2);
    }

    #[test]
    fn max_reach_pct_tracks() {
        let mut l = EstimateLog::new();
        l.record(0, &SpreadModel::new(1, 2, 100)); // low reach
        l.record(1, &SpreadModel::new(5, 5, 20));  // full reach
        assert_eq!(l.max_reach_pct(), 100);
    }

    #[test]
    fn quorum_reachable_count() {
        let mut l = EstimateLog::new();
        l.record(0, &SpreadModel::new(3, 6, 20));    // reachable
        l.record(1, &SpreadModel::new(1, 2, 10000)); // not reachable
        assert_eq!(l.quorum_reachable_count(), 1);
    }

    #[test]
    fn verify_chain_valid() {
        let mut l = EstimateLog::new();
        let m = SpreadModel::new(3, 4, 30);
        for i in 0..5u32 {
            l.record(i, &m);
        }
        let (valid, broken) = l.verify_chain();
        assert!(valid);
        assert!(broken.is_none());
    }
}
