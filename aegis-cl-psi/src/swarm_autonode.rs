//! Gate 232: Swarm Autonode — Multi-Node Constitutional Consensus Layer
//! EPISTEMIC TIER: T2 (engineering hypothesis)
//!
//! Orchestrates N ConstitutionalAutonode instances as a constitutional swarm,
//! applying BFT quorum consensus at the 1/φ threshold:
//!   quorum = coherent_count * 1_000_000 >= node_count * 618_034
//!
//! This is the organism-scale holonic layer: each ConstitutionalAutonode is
//! a molecular-scale entity; the SwarmAutonode is the organism-scale entity
//! that decides whether the constitutional consensus is valid.
//!
//! The consensus_hash is SHA-256 over all nodes' chain_entry_hashes in
//! BTreeMap-ordered (by node index, formatted as zero-padded decimal) iteration —
//! deterministic across all platforms.
//!
//! Constitutional invariant: AdaptivePower(T) ≤ ReplayVerifiability(T) at swarm scale:
//!   swarm_quorum_reached iff ≥ 1/φ of nodes are individually constitutionally coherent.

use sha2::{Sha256, Digest};
use std::collections::BTreeMap;
use crate::constitutional_autonode::{ConstitutionalAutonode, AutonodeTick, AutonodeCycleRecord, AutonodeError};

// ─── Quorum threshold (integer arithmetic, no f64) ────────────────────────

/// 1/φ threshold as integer fraction: 618034 / 1_000_000 ≈ 0.618034
/// Matches DEFAULT_QUORUM_THRESHOLD in swarm.ts and the martingale boundary.
const PHI_QUORUM_NUM: u64 = 618_034;
const PHI_QUORUM_DEN: u64 = 1_000_000;

/// True iff coherent_count / node_count >= 1/φ (integer, no f64).
pub fn phi_quorum_reached(coherent_count: usize, node_count: usize) -> bool {
    if node_count == 0 { return false; }
    (coherent_count as u64) * PHI_QUORUM_DEN >= (node_count as u64) * PHI_QUORUM_NUM
}

// ─── Swarm cycle record ───────────────────────────────────────────────────

/// The output of one swarm tick — all N node cycle records + consensus verdict.
#[derive(Debug)]
pub struct SwarmCycleRecord {
    pub epoch: u64,
    /// One AutonodeCycleRecord per node (in node-index order).
    pub node_records: Vec<AutonodeCycleRecord>,
    /// How many nodes have global_section_exists=true for this epoch.
    pub coherent_count: usize,
    /// How many nodes have is_continuously_coherent=true (all epochs so far).
    pub continuously_coherent_count: usize,
    /// True iff coherent_count / node_count >= 1/φ.
    pub quorum_reached: bool,
    /// True iff continuously_coherent_count / node_count >= 1/φ.
    pub continuous_quorum: bool,
    /// SHA-256 of all node chain_entry_hashes in BTreeMap order (deterministic).
    pub consensus_hash: [u8; 32],
}

impl SwarmCycleRecord {
    pub fn node_count(&self) -> usize { self.node_records.len() }
}

// ─── Swarm autonode error ─────────────────────────────────────────────────

#[derive(Debug)]
pub enum SwarmError {
    NodeError { node_index: usize, error: AutonodeError },
    TickCountMismatch,
    NoNodes,
}

// ─── Swarm autonode ───────────────────────────────────────────────────────

/// Multi-node constitutional swarm — N ConstitutionalAutonode instances
/// synchronized through BFT quorum consensus at the 1/φ threshold.
pub struct SwarmAutonode {
    nodes: Vec<ConstitutionalAutonode>,
}

impl SwarmAutonode {
    /// Create a swarm of N identical autonodes sharing the same constitutional hash.
    /// Panics if n == 0.
    pub fn new(n: usize, constitutional_hash: [u8; 32], system_version: &'static str) -> Self {
        assert!(n > 0, "SwarmAutonode requires at least 1 node");
        let nodes = (0..n)
            .map(|_| ConstitutionalAutonode::new(constitutional_hash, system_version))
            .collect();
        Self { nodes }
    }

    /// Number of nodes in the swarm.
    pub fn node_count(&self) -> usize { self.nodes.len() }

    /// Run one swarm tick with the same input applied to all N nodes.
    ///
    /// All nodes process the same epoch — individual ticks diverge only if
    /// their per-node state (last_sequence) differs (it won't in the uniform case).
    pub fn tick_uniform(&mut self, tick: AutonodeTick) -> Result<SwarmCycleRecord, SwarmError> {
        if self.nodes.is_empty() { return Err(SwarmError::NoNodes); }
        let epoch = tick.epoch;
        let mut node_records: Vec<AutonodeCycleRecord> = Vec::with_capacity(self.nodes.len());

        for (i, node) in self.nodes.iter_mut().enumerate() {
            let rec = node.tick(tick.clone()).map_err(|e| SwarmError::NodeError {
                node_index: i,
                error: e,
            })?;
            node_records.push(rec);
        }

        Ok(self.build_swarm_record(epoch, node_records))
    }

    /// Run one swarm tick with per-node inputs.
    /// `ticks.len()` must equal `self.node_count()`.
    pub fn tick_per_node(&mut self, ticks: Vec<AutonodeTick>) -> Result<SwarmCycleRecord, SwarmError> {
        if self.nodes.is_empty() { return Err(SwarmError::NoNodes); }
        if ticks.len() != self.nodes.len() { return Err(SwarmError::TickCountMismatch); }

        let epoch = ticks[0].epoch;
        let mut node_records: Vec<AutonodeCycleRecord> = Vec::with_capacity(self.nodes.len());

        for (i, (node, tick)) in self.nodes.iter_mut().zip(ticks.into_iter()).enumerate() {
            let rec = node.tick(tick).map_err(|e| SwarmError::NodeError {
                node_index: i,
                error: e,
            })?;
            node_records.push(rec);
        }

        Ok(self.build_swarm_record(epoch, node_records))
    }

    /// True iff ALL nodes are continuously coherent across their entire chain.
    pub fn all_continuously_coherent(&self) -> bool {
        self.nodes.iter().all(|n| n.is_continuously_coherent())
    }

    /// Number of nodes that are currently continuously coherent.
    pub fn continuously_coherent_count(&self) -> usize {
        self.nodes.iter().filter(|n| n.is_continuously_coherent()).count()
    }

    fn build_swarm_record(&self, epoch: u64, node_records: Vec<AutonodeCycleRecord>) -> SwarmCycleRecord {
        let n = node_records.len();

        let coherent_count = node_records.iter().filter(|r| r.is_fully_coherent).count();
        let continuously_coherent_count = self.nodes.iter().filter(|n| n.is_continuously_coherent()).count();

        let quorum_reached = phi_quorum_reached(coherent_count, n);
        let continuous_quorum = phi_quorum_reached(continuously_coherent_count, n);

        // consensus_hash: SHA-256 over all chain_entry_hashes in index order (BTreeMap sorted)
        let mut ordered: BTreeMap<String, [u8; 32]> = BTreeMap::new();
        for (i, rec) in node_records.iter().enumerate() {
            ordered.insert(format!("{:04}", i), rec.chain_entry_hash);
        }
        let mut hasher = Sha256::new();
        for (_, hash) in &ordered {
            hasher.update(hash);
        }
        let consensus_hash: [u8; 32] = hasher.finalize().into();

        SwarmCycleRecord {
            epoch,
            node_records,
            coherent_count,
            continuously_coherent_count,
            quorum_reached,
            continuous_quorum,
            consensus_hash,
        }
    }
}

// ─── Tests ────────────────────────────────────────────────────────────────

#[cfg(test)]
mod tests {
    use super::*;
    use crate::chord_network::NetworkVerdict;
    use crate::self_certification::NetworkSnapshot;

    fn const_hash(v: u8) -> [u8; 32] {
        let mut h = [0u8; 32]; h[0] = v; h
    }

    fn ring5(seed: u8) -> Vec<[u8; 32]> {
        // [A, B, C, B, A] — valid ring
        vec![const_hash(seed), const_hash(seed+1), const_hash(seed+2), const_hash(seed+1), const_hash(seed)]
    }

    fn unified_net() -> NetworkSnapshot {
        NetworkSnapshot { verdict: NetworkVerdict::Unified, peer_count: 3, above_phi_count: 0, quorum_triadic: true }
    }

    fn good_tick(epoch: u64, seq: u64) -> AutonodeTick {
        AutonodeTick {
            epoch,
            sequence_id: seq,
            divergence_risk: 0.12,
            start_rank: 3,
            end_rank: 9,
            ring_hashes: ring5(1),
            network: unified_net(),
            mutation_authority_active: true,
        }
    }

    // ── phi_quorum_reached ────────────────────────────────────────────────

    #[test]
    fn quorum_zero_nodes_false() {
        assert!(!phi_quorum_reached(0, 0));
    }

    #[test]
    fn quorum_all_coherent_true() {
        assert!(phi_quorum_reached(5, 5));
    }

    #[test]
    fn quorum_61_of_100_true() {
        // 61/100 = 0.61 < 0.618034 → false (below phi)
        assert!(!phi_quorum_reached(61, 100));
    }

    #[test]
    fn quorum_62_of_100_true() {
        // 62/100 = 0.62 >= 0.618034 → true
        assert!(phi_quorum_reached(62, 100));
    }

    #[test]
    fn quorum_1_of_1_true() {
        assert!(phi_quorum_reached(1, 1));
    }

    #[test]
    fn quorum_0_of_5_false() {
        assert!(!phi_quorum_reached(0, 5));
    }

    // ── SwarmAutonode creation ─────────────────────────────────────────────

    #[test]
    fn new_swarm_has_correct_node_count() {
        let swarm = SwarmAutonode::new(5, const_hash(1), "1.0.0");
        assert_eq!(swarm.node_count(), 5);
    }

    #[test]
    fn new_swarm_all_continuously_coherent() {
        let swarm = SwarmAutonode::new(3, const_hash(1), "1.0.0");
        assert!(swarm.all_continuously_coherent());
        assert_eq!(swarm.continuously_coherent_count(), 3);
    }

    // ── tick_uniform ─────────────────────────────────────────────────────

    #[test]
    fn tick_uniform_all_coherent() {
        let mut swarm = SwarmAutonode::new(5, const_hash(1), "1.0.0");
        let rec = swarm.tick_uniform(good_tick(1, 100)).unwrap();
        assert_eq!(rec.coherent_count, 5);
        assert!(rec.quorum_reached);
        assert_eq!(rec.node_count(), 5);
    }

    #[test]
    fn tick_uniform_epoch_preserved() {
        let mut swarm = SwarmAutonode::new(3, const_hash(1), "1.0.0");
        let rec = swarm.tick_uniform(good_tick(42, 100)).unwrap();
        assert_eq!(rec.epoch, 42);
    }

    #[test]
    fn tick_uniform_consensus_hash_nonzero() {
        let mut swarm = SwarmAutonode::new(3, const_hash(1), "1.0.0");
        let rec = swarm.tick_uniform(good_tick(1, 100)).unwrap();
        assert_ne!(rec.consensus_hash, [0u8; 32]);
    }

    #[test]
    fn tick_uniform_chain_grows() {
        let mut swarm = SwarmAutonode::new(3, const_hash(1), "1.0.0");
        swarm.tick_uniform(good_tick(1, 100)).unwrap();
        swarm.tick_uniform(good_tick(2, 101)).unwrap();
        let rec = swarm.tick_uniform(good_tick(3, 102)).unwrap();
        assert_eq!(rec.node_records[0].chain_length, 3);
    }

    // ── tick_per_node ─────────────────────────────────────────────────────

    #[test]
    fn tick_per_node_mismatch_is_err() {
        let mut swarm = SwarmAutonode::new(3, const_hash(1), "1.0.0");
        let ticks = vec![good_tick(1, 100), good_tick(1, 101)]; // only 2 for 3-node swarm
        assert!(matches!(swarm.tick_per_node(ticks), Err(SwarmError::TickCountMismatch)));
    }

    #[test]
    fn tick_per_node_heterogeneous_divergence() {
        let mut swarm = SwarmAutonode::new(3, const_hash(1), "1.0.0");
        let ticks = vec![
            good_tick(1, 100),                                               // coherent
            { let mut t = good_tick(1, 100); t.divergence_risk = 0.99; t }, // above-phi → incoherent
            good_tick(1, 100),                                               // coherent
        ];
        let rec = swarm.tick_per_node(ticks).unwrap();
        assert_eq!(rec.coherent_count, 2);       // 2/3 coherent
        assert!(rec.quorum_reached);             // 2/3 = 0.667 > 0.618 → quorum
    }

    #[test]
    fn tick_per_node_below_quorum() {
        let mut swarm = SwarmAutonode::new(5, const_hash(1), "1.0.0");
        // Only 2/5 = 0.40 < 0.618 → no quorum
        let ticks: Vec<AutonodeTick> = (0..5).map(|i| {
            let mut t = good_tick(1, 100 + i as u64);
            if i >= 2 { t.divergence_risk = 0.99; }
            t
        }).collect();
        let rec = swarm.tick_per_node(ticks).unwrap();
        assert_eq!(rec.coherent_count, 2);
        assert!(!rec.quorum_reached);
    }

    // ── Continuous coherence tracking ──────────────────────────────────────

    #[test]
    fn continuous_quorum_after_breach() {
        let mut swarm = SwarmAutonode::new(3, const_hash(1), "1.0.0");
        swarm.tick_uniform(good_tick(1, 100)).unwrap(); // all coherent
        // Node 0 breaches on epoch 2
        let ticks = vec![
            { let mut t = good_tick(2, 101); t.divergence_risk = 0.99; t },
            good_tick(2, 101),
            good_tick(2, 101),
        ];
        swarm.tick_per_node(ticks).unwrap();
        // Node 0 has breached, nodes 1 and 2 are still continuously coherent: 2/3 = 0.667 > 0.618
        assert_eq!(swarm.continuously_coherent_count(), 2);
    }

    // ── Determinism ────────────────────────────────────────────────────────

    #[test]
    fn determinism_same_inputs_same_consensus_hash() {
        let build = || {
            let mut s = SwarmAutonode::new(4, const_hash(7), "1.0.0");
            let r1 = s.tick_uniform(good_tick(1, 100)).unwrap();
            let r2 = s.tick_uniform(good_tick(2, 101)).unwrap();
            (r1.consensus_hash, r2.consensus_hash)
        };
        let (a1, a2) = build();
        let (b1, b2) = build();
        let (c1, c2) = build();
        assert_eq!(a1, b1); assert_eq!(b1, c1);
        assert_eq!(a2, b2); assert_eq!(b2, c2);
    }

    #[test]
    fn consensus_hash_changes_between_epochs() {
        let mut swarm = SwarmAutonode::new(3, const_hash(1), "1.0.0");
        let r1 = swarm.tick_uniform(good_tick(1, 100)).unwrap();
        let r2 = swarm.tick_uniform(good_tick(2, 101)).unwrap();
        assert_ne!(r1.consensus_hash, r2.consensus_hash);
    }
}
