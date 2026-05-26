//! Gate 323 — Constitutional Verdict Ledger (T2)
//! EPISTEMIC TIER: T2 (engineering hypothesis)
//!
//! Per-node T0 constitutional verdict tracking with tamper-evident SHA-256
//! hash chain. Aggregates Gate 322 synthesis verdicts across a distributed
//! swarm; enables each node to maintain its own constitutional audit trail
//! and cross-verify peers at epoch boundaries.
//!
//! VerdictEntry fields hashed: prev[32]‖node_id_be8‖epoch_be8‖t0_verdict_byte
//!                              ‖health_class_byte‖resonance_certified_byte
//!
//! NodeVerdictLedger: per-node append-only chain.
//!   append(), latest(), t0_verdict(), verify_chain()
//!
//! SwarmVerdictRegistry: BTreeMap<node_id, NodeVerdictLedger> — deterministic.
//!   record_verdict(), ledger_for(), consensus_t0(), quorum_t0(), verify_all()
//!
//! consensus_t0(): true iff every node in registry has latest t0_verdict=true
//! quorum_t0(threshold): integer 1/φ quorum — true nodes * 1_000_000 >= total * 618_034

use sha2::{Sha256, Digest};
use std::collections::BTreeMap;
use crate::gossip_health_report::NetworkHealthClass;

pub const VERDICT_GENESIS_HASH: [u8; 32] = [0u8; 32];

// ─── VerdictEntry ─────────────────────────────────────────────────────────────

/// One hash-chained T0 constitutional verdict for a single node at one epoch.
#[derive(Debug, Clone, PartialEq)]
pub struct VerdictEntry {
    pub node_id:              u64,
    pub epoch:                u64,
    pub t0_verdict:           bool,
    pub health_class:         NetworkHealthClass,
    pub resonance_certified:  bool,
    pub entry_hash:           [u8; 32],
    pub prev_hash:            [u8; 32],
}

// ─── Input ────────────────────────────────────────────────────────────────────

/// Input for one verdict entry.
#[derive(Debug, Clone, Copy)]
pub struct VerdictInput {
    pub node_id:             u64,
    pub epoch:               u64,
    pub t0_verdict:          bool,
    pub health_class:        NetworkHealthClass,
    pub resonance_certified: bool,
}

// ─── Hash ─────────────────────────────────────────────────────────────────────

fn compute_verdict_hash(
    prev:                &[u8; 32],
    node_id:             u64,
    epoch:               u64,
    t0_verdict:          bool,
    health_class:        NetworkHealthClass,
    resonance_certified: bool,
) -> [u8; 32] {
    let mut h = Sha256::new();
    h.update(prev);
    h.update(node_id.to_be_bytes());
    h.update(epoch.to_be_bytes());
    h.update([t0_verdict as u8]);
    h.update([health_class.class_byte()]);
    h.update([resonance_certified as u8]);
    h.finalize().into()
}

// ─── NodeVerdictLedger ────────────────────────────────────────────────────────

/// Append-only hash-chained ledger of T0 verdicts for a single node.
pub struct NodeVerdictLedger {
    node_id: u64,
    entries: Vec<VerdictEntry>,
}

impl NodeVerdictLedger {
    pub fn new(node_id: u64) -> Self {
        Self { node_id, entries: Vec::new() }
    }

    pub fn node_id(&self)   -> u64   { self.node_id }
    pub fn len(&self)       -> usize { self.entries.len() }
    pub fn is_empty(&self)  -> bool  { self.entries.is_empty() }
    pub fn entries(&self)   -> &[VerdictEntry] { &self.entries }

    /// Append a new verdict, chaining from the previous (or genesis).
    ///
    /// Returns `Err` if `inp.node_id != self.node_id` (cross-node contamination).
    pub fn append(&mut self, inp: VerdictInput) -> Result<VerdictEntry, VerdictLedgerError> {
        if inp.node_id != self.node_id {
            return Err(VerdictLedgerError("[VERDICT] node_id mismatch"));
        }
        let prev = self.entries.last()
            .map(|e| e.entry_hash)
            .unwrap_or(VERDICT_GENESIS_HASH);

        let entry_hash = compute_verdict_hash(
            &prev,
            inp.node_id,
            inp.epoch,
            inp.t0_verdict,
            inp.health_class,
            inp.resonance_certified,
        );

        let entry = VerdictEntry {
            node_id:             inp.node_id,
            epoch:               inp.epoch,
            t0_verdict:          inp.t0_verdict,
            health_class:        inp.health_class,
            resonance_certified: inp.resonance_certified,
            entry_hash,
            prev_hash:           prev,
        };
        self.entries.push(entry.clone());
        Ok(entry)
    }

    /// Most recent verdict entry, or `None` if empty.
    pub fn latest(&self) -> Option<&VerdictEntry> {
        self.entries.last()
    }

    /// T0 verdict of the most recent entry, or `None` if empty.
    pub fn t0_verdict(&self) -> Option<bool> {
        self.latest().map(|e| e.t0_verdict)
    }

    /// Terminal hash (most recent entry_hash) or genesis hash if empty.
    pub fn terminal_hash(&self) -> [u8; 32] {
        self.entries.last()
            .map(|e| e.entry_hash)
            .unwrap_or(VERDICT_GENESIS_HASH)
    }

    /// Count of entries where t0_verdict == true.
    pub fn certified_count(&self) -> usize {
        self.entries.iter().filter(|e| e.t0_verdict).count()
    }

    /// Verify hash chain integrity.
    /// Returns `(true, None)` when valid; `(false, Some(idx))` at first broken link.
    pub fn verify_chain(&self) -> (bool, Option<usize>) {
        let mut prev = VERDICT_GENESIS_HASH;
        for (i, e) in self.entries.iter().enumerate() {
            if e.prev_hash != prev {
                return (false, Some(i));
            }
            let expected = compute_verdict_hash(
                &prev,
                e.node_id,
                e.epoch,
                e.t0_verdict,
                e.health_class,
                e.resonance_certified,
            );
            if e.entry_hash != expected {
                return (false, Some(i));
            }
            prev = e.entry_hash;
        }
        (true, None)
    }
}

// ─── SwarmVerdictRegistry ─────────────────────────────────────────────────────

/// BTreeMap-keyed per-node verdict ledger registry for the swarm.
///
/// Deterministic: BTreeMap iteration order is sorted by node_id.
pub struct SwarmVerdictRegistry {
    ledgers: BTreeMap<u64, NodeVerdictLedger>,
}

impl SwarmVerdictRegistry {
    pub fn new() -> Self { Self { ledgers: BTreeMap::new() } }

    pub fn node_count(&self) -> usize { self.ledgers.len() }

    /// Record a verdict for a node, creating a ledger if one does not yet exist.
    pub fn record_verdict(&mut self, inp: VerdictInput) -> Result<VerdictEntry, VerdictLedgerError> {
        let ledger = self.ledgers
            .entry(inp.node_id)
            .or_insert_with(|| NodeVerdictLedger::new(inp.node_id));
        ledger.append(inp)
    }

    /// Get the ledger for a specific node, or `None` if never registered.
    pub fn ledger_for(&self, node_id: u64) -> Option<&NodeVerdictLedger> {
        self.ledgers.get(&node_id)
    }

    /// Iterate all ledgers in node_id order.
    pub fn all_ledgers(&self) -> impl Iterator<Item = (&u64, &NodeVerdictLedger)> {
        self.ledgers.iter()
    }

    /// `true` iff every registered node has latest t0_verdict == true.
    ///
    /// Returns `false` if no nodes are registered (empty swarm = not certified).
    pub fn consensus_t0(&self) -> bool {
        if self.ledgers.is_empty() {
            return false;
        }
        self.ledgers.values().all(|l| l.t0_verdict() == Some(true))
    }

    /// `true` iff the fraction of nodes with latest t0_verdict == true
    /// meets the 1/φ quorum threshold.
    ///
    /// Integer arithmetic: `true_count * 1_000_000 >= total * 618_034`.
    /// Returns `false` if no nodes are registered.
    pub fn quorum_t0(&self) -> bool {
        let total = self.ledgers.len();
        if total == 0 { return false; }
        let true_count = self.ledgers.values()
            .filter(|l| l.t0_verdict() == Some(true))
            .count();
        true_count * 1_000_000 >= total * 618_034
    }

    /// Verify chain integrity for all ledgers.
    ///
    /// Returns `(true, BTreeMap::new())` when all chains are valid.
    /// Returns `(false, map)` where `map` contains `node_id → first_invalid_idx`
    /// for each ledger with a broken chain.
    pub fn verify_all(&self) -> (bool, BTreeMap<u64, usize>) {
        let mut failures: BTreeMap<u64, usize> = BTreeMap::new();
        for (&node_id, ledger) in &self.ledgers {
            let (ok, idx) = ledger.verify_chain();
            if !ok {
                failures.insert(node_id, idx.unwrap_or(0));
            }
        }
        (failures.is_empty(), failures)
    }
}

impl Default for SwarmVerdictRegistry {
    fn default() -> Self { Self::new() }
}

// ─── Error ────────────────────────────────────────────────────────────────────

#[derive(Debug)]
pub struct VerdictLedgerError(pub &'static str);

impl std::fmt::Display for VerdictLedgerError {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        f.write_str(self.0)
    }
}

// ─── Tests ────────────────────────────────────────────────────────────────────

#[cfg(test)]
mod tests {
    use super::*;
    use crate::gossip_health_report::NetworkHealthClass;

    fn green_t0(node_id: u64, epoch: u64) -> VerdictInput {
        VerdictInput {
            node_id,
            epoch,
            t0_verdict:          true,
            health_class:        NetworkHealthClass::Green,
            resonance_certified: true,
        }
    }

    fn red_false(node_id: u64, epoch: u64) -> VerdictInput {
        VerdictInput {
            node_id,
            epoch,
            t0_verdict:          false,
            health_class:        NetworkHealthClass::Red,
            resonance_certified: false,
        }
    }

    // ── Genesis ───────────────────────────────────────────────────────────────

    #[test]
    fn genesis_hash_is_zero() {
        assert_eq!(VERDICT_GENESIS_HASH, [0u8; 32]);
    }

    #[test]
    fn fresh_ledger_empty() {
        let l = NodeVerdictLedger::new(1);
        assert!(l.is_empty());
        assert!(l.latest().is_none());
        assert!(l.t0_verdict().is_none());
        assert_eq!(l.terminal_hash(), VERDICT_GENESIS_HASH);
    }

    // ── NodeVerdictLedger ─────────────────────────────────────────────────────

    #[test]
    fn append_returns_correct_fields() {
        let mut l = NodeVerdictLedger::new(7);
        let e = l.append(green_t0(7, 1)).unwrap();
        assert_eq!(e.node_id, 7);
        assert_eq!(e.epoch, 1);
        assert!(e.t0_verdict);
        assert_eq!(e.prev_hash, VERDICT_GENESIS_HASH);
        assert_ne!(e.entry_hash, [0u8; 32]);
    }

    #[test]
    fn append_node_id_mismatch_errors() {
        let mut l = NodeVerdictLedger::new(1);
        let r = l.append(green_t0(2, 1));
        assert!(r.is_err());
    }

    #[test]
    fn second_entry_chains_to_first() {
        let mut l = NodeVerdictLedger::new(3);
        let e1 = l.append(green_t0(3, 1)).unwrap();
        let e2 = l.append(green_t0(3, 2)).unwrap();
        assert_eq!(e2.prev_hash, e1.entry_hash);
    }

    #[test]
    fn terminal_hash_tracks_latest() {
        let mut l = NodeVerdictLedger::new(5);
        let e = l.append(green_t0(5, 1)).unwrap();
        assert_eq!(l.terminal_hash(), e.entry_hash);
    }

    #[test]
    fn certified_count_only_true_entries() {
        let mut l = NodeVerdictLedger::new(9);
        l.append(green_t0(9, 1)).unwrap();
        l.append(red_false(9, 2)).unwrap();
        l.append(green_t0(9, 3)).unwrap();
        assert_eq!(l.certified_count(), 2);
    }

    // ── verify_chain (NodeVerdictLedger) ──────────────────────────────────────

    #[test]
    fn verify_chain_empty_ok() {
        let l = NodeVerdictLedger::new(1);
        let (ok, idx) = l.verify_chain();
        assert!(ok);
        assert!(idx.is_none());
    }

    #[test]
    fn verify_chain_three_ok() {
        let mut l = NodeVerdictLedger::new(1);
        l.append(green_t0(1, 1)).unwrap();
        l.append(red_false(1, 2)).unwrap();
        l.append(green_t0(1, 3)).unwrap();
        let (ok, idx) = l.verify_chain();
        assert!(ok);
        assert!(idx.is_none());
    }

    #[test]
    fn verify_chain_tampered_entry_hash() {
        let mut l = NodeVerdictLedger::new(1);
        l.append(green_t0(1, 1)).unwrap();
        l.append(green_t0(1, 2)).unwrap();
        l.entries[1].entry_hash[0] ^= 0xFF;
        let (ok, idx) = l.verify_chain();
        assert!(!ok);
        assert_eq!(idx, Some(1));
    }

    #[test]
    fn verify_chain_tampered_prev_hash() {
        let mut l = NodeVerdictLedger::new(1);
        l.append(green_t0(1, 1)).unwrap();
        l.append(green_t0(1, 2)).unwrap();
        l.entries[1].prev_hash[0] ^= 0x01;
        let (ok, idx) = l.verify_chain();
        assert!(!ok);
        assert_eq!(idx, Some(1));
    }

    #[test]
    fn verify_chain_tampered_t0_field() {
        let mut l = NodeVerdictLedger::new(1);
        l.append(green_t0(1, 1)).unwrap();
        l.entries[0].t0_verdict = false;
        let (ok, idx) = l.verify_chain();
        assert!(!ok);
        assert_eq!(idx, Some(0));
    }

    // ── Determinism ───────────────────────────────────────────────────────────

    #[test]
    fn determinism_same_input_three_times() {
        let inp = green_t0(42, 1);
        let mut l1 = NodeVerdictLedger::new(42); let e1 = l1.append(inp).unwrap();
        let mut l2 = NodeVerdictLedger::new(42); let e2 = l2.append(inp).unwrap();
        let mut l3 = NodeVerdictLedger::new(42); let e3 = l3.append(inp).unwrap();
        assert_eq!(e1.entry_hash, e2.entry_hash);
        assert_eq!(e2.entry_hash, e3.entry_hash);
    }

    #[test]
    fn different_node_id_different_hash() {
        let mut l1 = NodeVerdictLedger::new(1);
        let mut l2 = NodeVerdictLedger::new(2);
        let e1 = l1.append(VerdictInput { node_id: 1, epoch: 1, t0_verdict: true, health_class: NetworkHealthClass::Green, resonance_certified: true }).unwrap();
        let e2 = l2.append(VerdictInput { node_id: 2, epoch: 1, t0_verdict: true, health_class: NetworkHealthClass::Green, resonance_certified: true }).unwrap();
        assert_ne!(e1.entry_hash, e2.entry_hash);
    }

    // ── SwarmVerdictRegistry ──────────────────────────────────────────────────

    #[test]
    fn fresh_registry_empty() {
        let r = SwarmVerdictRegistry::new();
        assert_eq!(r.node_count(), 0);
        assert!(!r.consensus_t0());
        assert!(!r.quorum_t0());
    }

    #[test]
    fn record_verdict_creates_ledger() {
        let mut r = SwarmVerdictRegistry::new();
        r.record_verdict(green_t0(1, 1)).unwrap();
        assert_eq!(r.node_count(), 1);
        assert!(r.ledger_for(1).is_some());
    }

    #[test]
    fn consensus_t0_all_true() {
        let mut r = SwarmVerdictRegistry::new();
        r.record_verdict(green_t0(1, 1)).unwrap();
        r.record_verdict(green_t0(2, 1)).unwrap();
        r.record_verdict(green_t0(3, 1)).unwrap();
        assert!(r.consensus_t0());
    }

    #[test]
    fn consensus_t0_one_false() {
        let mut r = SwarmVerdictRegistry::new();
        r.record_verdict(green_t0(1, 1)).unwrap();
        r.record_verdict(red_false(2, 1)).unwrap();
        assert!(!r.consensus_t0());
    }

    #[test]
    fn quorum_t0_five_of_eight_meets_phi() {
        // 5/8 = 0.625 >= 0.618034
        let mut r = SwarmVerdictRegistry::new();
        for id in 1..=5u64 { r.record_verdict(green_t0(id, 1)).unwrap(); }
        for id in 6..=8u64 { r.record_verdict(red_false(id, 1)).unwrap(); }
        assert!(r.quorum_t0());
    }

    #[test]
    fn quorum_t0_four_of_eight_below_phi() {
        // 4/8 = 0.500 < 0.618034
        let mut r = SwarmVerdictRegistry::new();
        for id in 1..=4u64 { r.record_verdict(green_t0(id, 1)).unwrap(); }
        for id in 5..=8u64 { r.record_verdict(red_false(id, 1)).unwrap(); }
        assert!(!r.quorum_t0());
    }

    #[test]
    fn verify_all_clean_registry() {
        let mut r = SwarmVerdictRegistry::new();
        r.record_verdict(green_t0(1, 1)).unwrap();
        r.record_verdict(green_t0(2, 1)).unwrap();
        let (ok, failures) = r.verify_all();
        assert!(ok);
        assert!(failures.is_empty());
    }

    #[test]
    fn verify_all_tampered_one_ledger() {
        let mut r = SwarmVerdictRegistry::new();
        r.record_verdict(green_t0(1, 1)).unwrap();
        r.record_verdict(green_t0(2, 1)).unwrap();
        // Tamper node 1's ledger
        r.ledgers.get_mut(&1).unwrap().entries[0].t0_verdict = false;
        let (ok, failures) = r.verify_all();
        assert!(!ok);
        assert!(failures.contains_key(&1));
        assert!(!failures.contains_key(&2));
    }

    #[test]
    fn ledger_for_unknown_node_is_none() {
        let r = SwarmVerdictRegistry::new();
        assert!(r.ledger_for(99).is_none());
    }

    // ── Multi-epoch sequence ──────────────────────────────────────────────────

    #[test]
    fn multi_epoch_chain_valid() {
        let mut r = SwarmVerdictRegistry::new();
        for epoch in 1..=5u64 {
            r.record_verdict(green_t0(1, epoch)).unwrap();
        }
        let (ok, _) = r.verify_all();
        assert!(ok);
        assert_eq!(r.ledger_for(1).unwrap().len(), 5);
    }

    #[test]
    fn quorum_boundary_exactly_at_phi() {
        // 618034 / 1000000 exactly at threshold — should satisfy >= condition
        // Need N such that true_count * 1_000_000 == total * 618_034
        // Simplest: 309017 / 500000. Use 3/5 = 600000 < 618034 → false
        //           5/8 = 625000 >= 618034 → true (tested above)
        //           618034 * 1 = 618034, 1000000 >= 618034 — 1/1 = true
        let mut r = SwarmVerdictRegistry::new();
        r.record_verdict(green_t0(1, 1)).unwrap();
        assert!(r.quorum_t0()); // 1/1 = 100%
    }
}
