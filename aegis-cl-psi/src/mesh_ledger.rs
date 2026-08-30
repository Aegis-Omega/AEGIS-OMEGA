//! Gate 268 — Mesh Ledger: cross-module tamper-evident epoch ledger (T2)
//! EPISTEMIC TIER: T2 (engineering hypothesis)
//!
//! Binds the hashes from census, fault, recovery, quorum, and ticker modules
//! into a single hash-chained MeshEntry per epoch. Provides a unified audit trail
//! across all gossip mesh health subsystems.
//!
//! MeshEntry:
//!   epoch          — u64
//!   census_hash    — [u8; 32] (from CensusRecord.census_hash)
//!   fault_hash     — [u8; 32] (from FaultReport.report_hash)
//!   plan_hash      — [u8; 32] (from RecoveryPlan.plan_hash)
//!   quorum_hash    — [u8; 32] (from QuorumStatus.status_hash)
//!   ticker_hash    — [u8; 32] (from TickerRecord.ticker_hash)
//!   entry_hash     — SHA-256(prev ‖ epoch_be8 ‖ census_hash ‖ fault_hash ‖ plan_hash ‖ quorum_hash ‖ ticker_hash)
//!   prev_hash      — [u8; 32]
//!
//! MeshLedger: hash-chained MeshEntries; entry_count(), verify_chain(), terminal_hash().

use sha2::{Sha256, Digest};

// ─── Mesh entry ───────────────────────────────────────────────────────────────

#[derive(Debug, Clone, PartialEq)]
pub struct MeshEntry {
    pub epoch:       u64,
    pub census_hash: [u8; 32],
    pub fault_hash:  [u8; 32],
    pub plan_hash:   [u8; 32],
    pub quorum_hash: [u8; 32],
    pub ticker_hash: [u8; 32],
    pub entry_hash:  [u8; 32],
    pub prev_hash:   [u8; 32],
}

pub const MESH_GENESIS_HASH: [u8; 32] = [0u8; 32];

fn compute_entry_hash(
    epoch:       u64,
    census_hash: &[u8; 32],
    fault_hash:  &[u8; 32],
    plan_hash:   &[u8; 32],
    quorum_hash: &[u8; 32],
    ticker_hash: &[u8; 32],
    prev:        &[u8; 32],
) -> [u8; 32] {
    let mut h = Sha256::new();
    h.update(prev);
    h.update(epoch.to_be_bytes());
    h.update(census_hash);
    h.update(fault_hash);
    h.update(plan_hash);
    h.update(quorum_hash);
    h.update(ticker_hash);
    h.finalize().into()
}

pub fn build_entry(
    epoch:       u64,
    census_hash: [u8; 32],
    fault_hash:  [u8; 32],
    plan_hash:   [u8; 32],
    quorum_hash: [u8; 32],
    ticker_hash: [u8; 32],
    prev_hash:   &[u8; 32],
) -> MeshEntry {
    let entry_hash = compute_entry_hash(
        epoch, &census_hash, &fault_hash, &plan_hash, &quorum_hash, &ticker_hash, prev_hash);
    MeshEntry {
        epoch, census_hash, fault_hash, plan_hash, quorum_hash, ticker_hash,
        entry_hash, prev_hash: *prev_hash,
    }
}

// ─── Mesh ledger ──────────────────────────────────────────────────────────────

#[derive(Debug, Clone)]
pub struct MeshLedger {
    entries: Vec<MeshEntry>,
}

#[derive(Debug)]
pub enum LedgerError {
    StaleEpoch,
}

impl LedgerError {
    pub fn as_str(&self) -> &'static str { "stale epoch" }
}

impl MeshLedger {
    pub fn new() -> Self { Self { entries: Vec::new() } }

    pub fn len(&self) -> usize { self.entries.len() }
    pub fn is_empty(&self) -> bool { self.entries.is_empty() }
    pub fn entries(&self) -> &[MeshEntry] { &self.entries }
    pub fn latest(&self) -> Option<&MeshEntry> { self.entries.last() }

    pub fn last_hash(&self) -> [u8; 32] {
        self.entries.last().map(|e| e.entry_hash).unwrap_or(MESH_GENESIS_HASH)
    }

    /// Terminal hash of the ledger (same as last_hash, named for certification).
    pub fn terminal_hash(&self) -> [u8; 32] { self.last_hash() }

    pub fn append(
        &mut self,
        epoch:       u64,
        census_hash: [u8; 32],
        fault_hash:  [u8; 32],
        plan_hash:   [u8; 32],
        quorum_hash: [u8; 32],
        ticker_hash: [u8; 32],
    ) -> Result<&MeshEntry, LedgerError> {
        if let Some(last) = self.entries.last() {
            if epoch <= last.epoch {
                return Err(LedgerError::StaleEpoch);
            }
        }
        let prev_hash = self.last_hash();
        let entry = build_entry(
            epoch, census_hash, fault_hash, plan_hash, quorum_hash, ticker_hash, &prev_hash);
        self.entries.push(entry);
        Ok(self.entries.last().unwrap())
    }

    pub fn entry_count(&self) -> usize { self.entries.len() }

    pub fn verify_chain(&self) -> (bool, Option<usize>) {
        let mut expected_prev = MESH_GENESIS_HASH;
        for (i, entry) in self.entries.iter().enumerate() {
            if entry.prev_hash != expected_prev {
                return (false, Some(i));
            }
            let recomputed = compute_entry_hash(
                entry.epoch,
                &entry.census_hash,
                &entry.fault_hash,
                &entry.plan_hash,
                &entry.quorum_hash,
                &entry.ticker_hash,
                &entry.prev_hash,
            );
            if recomputed != entry.entry_hash {
                return (false, Some(i));
            }
            expected_prev = entry.entry_hash;
        }
        (true, None)
    }
}

impl Default for MeshLedger {
    fn default() -> Self { Self::new() }
}

// ─── Tests ───────────────────────────────────────────────────────────────────

#[cfg(test)]
mod tests {
    use super::*;

    fn dummy_hash(seed: u8) -> [u8; 32] { [seed; 32] }

    fn append_epoch(ledger: &mut MeshLedger, epoch: u64, seed: u8) {
        ledger.append(
            epoch,
            dummy_hash(seed),
            dummy_hash(seed.wrapping_add(1)),
            dummy_hash(seed.wrapping_add(2)),
            dummy_hash(seed.wrapping_add(3)),
            dummy_hash(seed.wrapping_add(4)),
        ).unwrap();
    }

    // ── build_entry ───────────────────────────────────────────────────────────

    #[test]
    fn entry_hash_nonzero() {
        let e = build_entry(1, dummy_hash(1), dummy_hash(2), dummy_hash(3),
                             dummy_hash(4), dummy_hash(5), &MESH_GENESIS_HASH);
        assert_ne!(e.entry_hash, [0u8; 32]);
    }

    #[test]
    fn entry_hash_deterministic() {
        let e1 = build_entry(1, dummy_hash(1), dummy_hash(2), dummy_hash(3),
                              dummy_hash(4), dummy_hash(5), &MESH_GENESIS_HASH);
        let e2 = build_entry(1, dummy_hash(1), dummy_hash(2), dummy_hash(3),
                              dummy_hash(4), dummy_hash(5), &MESH_GENESIS_HASH);
        assert_eq!(e1.entry_hash, e2.entry_hash);
    }

    #[test]
    fn different_census_hash_produces_different_entry_hash() {
        let e1 = build_entry(1, dummy_hash(1), dummy_hash(2), dummy_hash(3),
                              dummy_hash(4), dummy_hash(5), &MESH_GENESIS_HASH);
        let e2 = build_entry(1, dummy_hash(9), dummy_hash(2), dummy_hash(3),
                              dummy_hash(4), dummy_hash(5), &MESH_GENESIS_HASH);
        assert_ne!(e1.entry_hash, e2.entry_hash);
    }

    #[test]
    fn different_epoch_produces_different_entry_hash() {
        let e1 = build_entry(1, dummy_hash(1), dummy_hash(2), dummy_hash(3),
                              dummy_hash(4), dummy_hash(5), &MESH_GENESIS_HASH);
        let e2 = build_entry(2, dummy_hash(1), dummy_hash(2), dummy_hash(3),
                              dummy_hash(4), dummy_hash(5), &MESH_GENESIS_HASH);
        assert_ne!(e1.entry_hash, e2.entry_hash);
    }

    // ── MeshLedger ────────────────────────────────────────────────────────────

    #[test]
    fn new_ledger_empty() {
        let l = MeshLedger::new();
        assert!(l.is_empty());
        assert_eq!(l.last_hash(), MESH_GENESIS_HASH);
        assert_eq!(l.terminal_hash(), MESH_GENESIS_HASH);
    }

    #[test]
    fn append_chains_entries() {
        let mut l = MeshLedger::new();
        append_epoch(&mut l, 1, 10);
        append_epoch(&mut l, 2, 20);
        assert_eq!(l.len(), 2);
        assert_eq!(l.entries()[1].prev_hash, l.entries()[0].entry_hash);
    }

    #[test]
    fn stale_epoch_rejected() {
        let mut l = MeshLedger::new();
        append_epoch(&mut l, 5, 10);
        let r = l.append(5, dummy_hash(1), dummy_hash(2), dummy_hash(3),
                          dummy_hash(4), dummy_hash(5));
        assert!(matches!(r, Err(LedgerError::StaleEpoch)));
    }

    #[test]
    fn terminal_hash_matches_last_entry() {
        let mut l = MeshLedger::new();
        append_epoch(&mut l, 1, 10);
        append_epoch(&mut l, 2, 20);
        assert_eq!(l.terminal_hash(), l.entries().last().unwrap().entry_hash);
    }

    #[test]
    fn entry_count_correct() {
        let mut l = MeshLedger::new();
        for e in 1..=6u64 {
            append_epoch(&mut l, e, e as u8 * 10);
        }
        assert_eq!(l.entry_count(), 6);
    }

    #[test]
    fn verify_chain_valid() {
        let mut l = MeshLedger::new();
        for e in 1..=5u64 {
            append_epoch(&mut l, e, e as u8 * 5);
        }
        let (valid, broken) = l.verify_chain();
        assert!(valid);
        assert!(broken.is_none());
    }

    #[test]
    fn tampered_entry_fails_chain() {
        let mut l = MeshLedger::new();
        append_epoch(&mut l, 1, 10);
        append_epoch(&mut l, 2, 20);
        append_epoch(&mut l, 3, 30);
        l.entries[1].entry_hash[0] ^= 0xFF;
        let (valid, broken) = l.verify_chain();
        assert!(!valid);
        assert_eq!(broken, Some(1));
    }

    #[test]
    fn fields_preserved() {
        let mut l = MeshLedger::new();
        let ch = dummy_hash(0xAA);
        let fh = dummy_hash(0xBB);
        let ph = dummy_hash(0xCC);
        let qh = dummy_hash(0xDD);
        let th = dummy_hash(0xEE);
        l.append(7, ch, fh, ph, qh, th).unwrap();
        let entry = l.latest().unwrap();
        assert_eq!(entry.epoch, 7);
        assert_eq!(entry.census_hash, ch);
        assert_eq!(entry.fault_hash, fh);
        assert_eq!(entry.plan_hash, ph);
        assert_eq!(entry.quorum_hash, qh);
        assert_eq!(entry.ticker_hash, th);
    }
}
