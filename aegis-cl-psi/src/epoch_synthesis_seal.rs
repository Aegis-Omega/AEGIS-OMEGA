//! Gate 324 — Epoch Synthesis Seal (T2)
//! EPISTEMIC TIER: T2 (engineering hypothesis)
//!
//! Closes each epoch by producing a tamper-evident SHA-256 seal over all three
//! constitutional synthesis layers introduced in Gates 320–323:
//!   - gossip_health_hash   (terminal hash of GossipHealthMonitor at epoch close)
//!   - resonance_hash       (terminal hash of ResonanceChain at epoch close)
//!   - verdict_hash         (SHA-256 over all NodeVerdictLedger terminal hashes,
//!                           BTreeMap node_id order — deterministic)
//!   - t0_consensus         (bool — were all nodes constitutionally certified?)
//!   - quorum_t0            (bool — did ≥1/φ of nodes hold T0=true?)
//!
//! seal_hash = SHA-256(
//!   prev_seal[32]
//!   ‖ epoch_be8
//!   ‖ gossip_health_hash[32]
//!   ‖ resonance_hash[32]
//!   ‖ verdict_hash[32]
//!   ‖ t0_consensus_byte
//!   ‖ quorum_t0_byte
//! )
//!
//! EpochSynthesisSeal: one record per epoch close.
//! SynthesisSealChain: append(), latest(), consensus_count(), verify_chain().

use sha2::{Sha256, Digest};
use std::collections::BTreeMap;

pub const SEAL_GENESIS_HASH: [u8; 32] = [0u8; 32];

// ─── Epoch Synthesis Seal ─────────────────────────────────────────────────────

/// One hash-chained synthesis seal for one epoch.
#[derive(Debug, Clone, PartialEq)]
pub struct EpochSynthesisSeal {
    pub epoch:               u64,
    pub gossip_health_hash:  [u8; 32],
    pub resonance_hash:      [u8; 32],
    pub verdict_hash:        [u8; 32],
    pub t0_consensus:        bool,
    pub quorum_t0:           bool,
    pub seal_hash:           [u8; 32],
    pub prev_seal:           [u8; 32],
}

// ─── Seal Input ───────────────────────────────────────────────────────────────

/// Input required to produce one epoch synthesis seal.
#[derive(Debug, Clone)]
pub struct SealInput {
    pub epoch:              u64,
    pub gossip_health_hash: [u8; 32],
    pub resonance_hash:     [u8; 32],
    /// Per-node terminal hashes: node_id → terminal_hash.
    /// Sorted by node_id (BTreeMap) before hashing — deterministic.
    pub node_terminal_hashes: BTreeMap<u64, [u8; 32]>,
    pub t0_consensus:       bool,
    pub quorum_t0:          bool,
}

// ─── Verdict hash ─────────────────────────────────────────────────────────────

/// Compute the verdict_hash over all per-node terminal hashes.
///
/// Hash = SHA-256 of BTreeMap-ordered concatenation of:
///   node_id_be8[N] ‖ terminal_hash[32] for each (node_id, hash) pair
///
/// Returns genesis hash if `node_terminal_hashes` is empty.
pub fn compute_verdict_hash(node_terminal_hashes: &BTreeMap<u64, [u8; 32]>) -> [u8; 32] {
    if node_terminal_hashes.is_empty() {
        return SEAL_GENESIS_HASH;
    }
    let mut h = Sha256::new();
    for (node_id, terminal) in node_terminal_hashes {
        h.update(node_id.to_be_bytes());
        h.update(terminal);
    }
    h.finalize().into()
}

// ─── Seal hash ────────────────────────────────────────────────────────────────

fn compute_seal_hash(
    prev:               &[u8; 32],
    epoch:              u64,
    gossip_health_hash: &[u8; 32],
    resonance_hash:     &[u8; 32],
    verdict_hash:       &[u8; 32],
    t0_consensus:       bool,
    quorum_t0:          bool,
) -> [u8; 32] {
    let mut h = Sha256::new();
    h.update(prev);
    h.update(epoch.to_be_bytes());
    h.update(gossip_health_hash);
    h.update(resonance_hash);
    h.update(verdict_hash);
    h.update([t0_consensus as u8]);
    h.update([quorum_t0 as u8]);
    h.finalize().into()
}

// ─── SynthesisSealChain ───────────────────────────────────────────────────────

/// Append-only hash-chained ledger of epoch synthesis seals.
pub struct SynthesisSealChain {
    seals: Vec<EpochSynthesisSeal>,
}

impl SynthesisSealChain {
    pub fn new() -> Self { Self { seals: Vec::new() } }

    pub fn len(&self)      -> usize { self.seals.len() }
    pub fn is_empty(&self) -> bool  { self.seals.is_empty() }
    pub fn seals(&self)    -> &[EpochSynthesisSeal] { &self.seals }

    /// Seal one epoch, chaining from the previous seal (or genesis).
    pub fn append(&mut self, inp: SealInput) -> EpochSynthesisSeal {
        let prev = self.seals.last()
            .map(|s| s.seal_hash)
            .unwrap_or(SEAL_GENESIS_HASH);

        let verdict_hash = compute_verdict_hash(&inp.node_terminal_hashes);

        let seal_hash = compute_seal_hash(
            &prev,
            inp.epoch,
            &inp.gossip_health_hash,
            &inp.resonance_hash,
            &verdict_hash,
            inp.t0_consensus,
            inp.quorum_t0,
        );

        let seal = EpochSynthesisSeal {
            epoch:              inp.epoch,
            gossip_health_hash: inp.gossip_health_hash,
            resonance_hash:     inp.resonance_hash,
            verdict_hash,
            t0_consensus:       inp.t0_consensus,
            quorum_t0:          inp.quorum_t0,
            seal_hash,
            prev_seal:          prev,
        };
        self.seals.push(seal.clone());
        seal
    }

    /// Most recent seal, or `None` if empty.
    pub fn latest(&self) -> Option<&EpochSynthesisSeal> {
        self.seals.last()
    }

    /// Terminal seal_hash (most recent) or SEAL_GENESIS_HASH if empty.
    pub fn terminal_hash(&self) -> [u8; 32] {
        self.seals.last()
            .map(|s| s.seal_hash)
            .unwrap_or(SEAL_GENESIS_HASH)
    }

    /// Count of epochs where both t0_consensus and quorum_t0 were true.
    pub fn consensus_count(&self) -> usize {
        self.seals.iter().filter(|s| s.t0_consensus && s.quorum_t0).count()
    }

    /// Count of epochs where t0_consensus was false.
    pub fn violation_count(&self) -> usize {
        self.seals.iter().filter(|s| !s.t0_consensus).count()
    }

    /// Verify the seal hash chain.
    /// Returns `(true, None)` when valid; `(false, Some(idx))` at first broken seal.
    pub fn verify_chain(&self) -> (bool, Option<usize>) {
        let mut prev = SEAL_GENESIS_HASH;
        for (i, s) in self.seals.iter().enumerate() {
            if s.prev_seal != prev {
                return (false, Some(i));
            }
            let expected = compute_seal_hash(
                &prev,
                s.epoch,
                &s.gossip_health_hash,
                &s.resonance_hash,
                &s.verdict_hash,
                s.t0_consensus,
                s.quorum_t0,
            );
            if s.seal_hash != expected {
                return (false, Some(i));
            }
            prev = s.seal_hash;
        }
        (true, None)
    }
}

impl Default for SynthesisSealChain {
    fn default() -> Self { Self::new() }
}

// ─── Tests ────────────────────────────────────────────────────────────────────

#[cfg(test)]
mod tests {
    use super::*;

    fn dummy_hash(seed: u8) -> [u8; 32] {
        let mut h = [0u8; 32];
        h[0] = seed;
        h[31] = seed.wrapping_mul(7);
        h
    }

    fn clean_input(epoch: u64) -> SealInput {
        let mut nodes = BTreeMap::new();
        nodes.insert(1u64, dummy_hash(1));
        nodes.insert(2u64, dummy_hash(2));
        SealInput {
            epoch,
            gossip_health_hash:    dummy_hash(10),
            resonance_hash:        dummy_hash(20),
            node_terminal_hashes:  nodes,
            t0_consensus:          true,
            quorum_t0:             true,
        }
    }

    // ── Genesis ───────────────────────────────────────────────────────────────

    #[test]
    fn genesis_hash_is_zero() {
        assert_eq!(SEAL_GENESIS_HASH, [0u8; 32]);
    }

    #[test]
    fn fresh_chain_empty() {
        let c = SynthesisSealChain::new();
        assert!(c.is_empty());
        assert!(c.latest().is_none());
        assert_eq!(c.terminal_hash(), SEAL_GENESIS_HASH);
    }

    // ── Single seal ───────────────────────────────────────────────────────────

    #[test]
    fn first_seal_prev_is_genesis() {
        let mut c = SynthesisSealChain::new();
        let s = c.append(clean_input(1));
        assert_eq!(s.prev_seal, SEAL_GENESIS_HASH);
        assert_ne!(s.seal_hash, [0u8; 32]);
    }

    #[test]
    fn seal_fields_preserved() {
        let mut c = SynthesisSealChain::new();
        let s = c.append(clean_input(5));
        assert_eq!(s.epoch, 5);
        assert!(s.t0_consensus);
        assert!(s.quorum_t0);
    }

    #[test]
    fn second_seal_chains_to_first() {
        let mut c = SynthesisSealChain::new();
        let s1 = c.append(clean_input(1));
        let s2 = c.append(clean_input(2));
        assert_eq!(s2.prev_seal, s1.seal_hash);
    }

    #[test]
    fn terminal_hash_tracks_latest() {
        let mut c = SynthesisSealChain::new();
        let s = c.append(clean_input(1));
        assert_eq!(c.terminal_hash(), s.seal_hash);
    }

    // ── verdict_hash ──────────────────────────────────────────────────────────

    #[test]
    fn verdict_hash_empty_is_genesis() {
        let map: BTreeMap<u64, [u8; 32]> = BTreeMap::new();
        assert_eq!(compute_verdict_hash(&map), SEAL_GENESIS_HASH);
    }

    #[test]
    fn verdict_hash_deterministic() {
        let mut m = BTreeMap::new();
        m.insert(1u64, dummy_hash(1));
        m.insert(2u64, dummy_hash(2));
        let h1 = compute_verdict_hash(&m);
        let h2 = compute_verdict_hash(&m);
        let h3 = compute_verdict_hash(&m);
        assert_eq!(h1, h2);
        assert_eq!(h2, h3);
    }

    #[test]
    fn verdict_hash_order_independent() {
        // BTreeMap always sorts by key — different insertion order → same hash
        let mut m1 = BTreeMap::new();
        m1.insert(1u64, dummy_hash(1));
        m1.insert(2u64, dummy_hash(2));

        let mut m2 = BTreeMap::new();
        m2.insert(2u64, dummy_hash(2));
        m2.insert(1u64, dummy_hash(1));

        assert_eq!(compute_verdict_hash(&m1), compute_verdict_hash(&m2));
    }

    #[test]
    fn verdict_hash_different_nodes_different_hash() {
        let mut m1 = BTreeMap::new(); m1.insert(1u64, dummy_hash(1));
        let mut m2 = BTreeMap::new(); m2.insert(2u64, dummy_hash(1));
        assert_ne!(compute_verdict_hash(&m1), compute_verdict_hash(&m2));
    }

    // ── Counters ──────────────────────────────────────────────────────────────

    #[test]
    fn consensus_count_only_full_passes() {
        let mut c = SynthesisSealChain::new();
        c.append(clean_input(1)); // consensus=true, quorum=true
        c.append(SealInput { t0_consensus: false, quorum_t0: true, ..clean_input(2) });
        c.append(clean_input(3));
        assert_eq!(c.consensus_count(), 2);
        assert_eq!(c.violation_count(), 1);
    }

    // ── verify_chain ──────────────────────────────────────────────────────────

    #[test]
    fn verify_chain_empty_ok() {
        let c = SynthesisSealChain::new();
        let (ok, idx) = c.verify_chain();
        assert!(ok);
        assert!(idx.is_none());
    }

    #[test]
    fn verify_chain_three_seals_ok() {
        let mut c = SynthesisSealChain::new();
        c.append(clean_input(1));
        c.append(clean_input(2));
        c.append(SealInput { t0_consensus: false, ..clean_input(3) });
        let (ok, idx) = c.verify_chain();
        assert!(ok);
        assert!(idx.is_none());
    }

    #[test]
    fn verify_chain_tampered_seal_hash() {
        let mut c = SynthesisSealChain::new();
        c.append(clean_input(1));
        c.append(clean_input(2));
        c.seals[1].seal_hash[0] ^= 0xFF;
        let (ok, idx) = c.verify_chain();
        assert!(!ok);
        assert_eq!(idx, Some(1));
    }

    #[test]
    fn verify_chain_tampered_prev_seal() {
        let mut c = SynthesisSealChain::new();
        c.append(clean_input(1));
        c.append(clean_input(2));
        c.seals[1].prev_seal[0] ^= 0x01;
        let (ok, idx) = c.verify_chain();
        assert!(!ok);
        assert_eq!(idx, Some(1));
    }

    #[test]
    fn verify_chain_tampered_consensus_field() {
        let mut c = SynthesisSealChain::new();
        c.append(clean_input(1));
        c.seals[0].t0_consensus = false;
        let (ok, idx) = c.verify_chain();
        assert!(!ok);
        assert_eq!(idx, Some(0));
    }

    // ── Determinism ───────────────────────────────────────────────────────────

    #[test]
    fn determinism_same_input_three_times() {
        let inp = clean_input(42);
        let mut c1 = SynthesisSealChain::new(); let s1 = c1.append(inp.clone());
        let mut c2 = SynthesisSealChain::new(); let s2 = c2.append(inp.clone());
        let mut c3 = SynthesisSealChain::new(); let s3 = c3.append(inp.clone());
        assert_eq!(s1.seal_hash, s2.seal_hash);
        assert_eq!(s2.seal_hash, s3.seal_hash);
    }

    #[test]
    fn different_epoch_different_seal_hash() {
        let mut c1 = SynthesisSealChain::new(); let s1 = c1.append(clean_input(1));
        let mut c2 = SynthesisSealChain::new(); let s2 = c2.append(clean_input(2));
        assert_ne!(s1.seal_hash, s2.seal_hash);
    }

    #[test]
    fn different_gossip_hash_different_seal() {
        let mut inp1 = clean_input(1); inp1.gossip_health_hash = dummy_hash(10);
        let mut inp2 = clean_input(1); inp2.gossip_health_hash = dummy_hash(99);
        let mut c1 = SynthesisSealChain::new(); let s1 = c1.append(inp1);
        let mut c2 = SynthesisSealChain::new(); let s2 = c2.append(inp2);
        assert_ne!(s1.seal_hash, s2.seal_hash);
    }
}
