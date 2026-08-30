//! Gate 370 — Compaction Gossip Epoch Ledger (T2)
//! EPISTEMIC TIER: T2 (engineering hypothesis)
//!
//! Tamper-evident per-epoch ledger binding all gossip subsystem terminal
//! hashes into a single hash-chained GossipLedgerEntry per epoch.
//! Mirrors Gate 348 for the gossip subsystem.
//!
//! GossipLedgerEntry:
//!   epoch:               u64
//!   report_hash:         [u8;32]    — GossipEpochReport.report_hash
//!   alert_hash:          [u8;32]    — GossipAlertRecord.alert_hash
//!   sla_hash:            [u8;32]    — GossipSlaRecord.sla_hash
//!   capacity_hash:       [u8;32]    — GossipCapacityProjection.projection_hash
//!   delta_hash:          [u8;32]    — GossipEpochDeltaRecord.delta_hash (or zeros if first)
//!   trend_hash:          [u8;32]    — GossipTrendRecord.trend_hash
//!   dashboard_hash:      [u8;32]    — GossipDashboardFrame.frame_hash
//!   entry_hash:          [u8;32]
//!   prev_hash:           [u8;32]
//!
//! entry_hash = SHA-256(prev[32] ‖ epoch_be8
//!                        ‖ report_hash[32] ‖ alert_hash[32] ‖ sla_hash[32]
//!                        ‖ capacity_hash[32] ‖ delta_hash[32] ‖ trend_hash[32]
//!                        ‖ dashboard_hash[32])
//!
//! GossipEpochLedger: append(...), terminal_hash(), entry_count(),
//!   latest(), verify_chain().

use sha2::{Sha256, Digest};

pub const GOSSIP_LEDGER_GENESIS_HASH: [u8; 32] = [0u8; 32];

// ─── GossipLedgerEntry ────────────────────────────────────────────────────────

#[derive(Debug, Clone, PartialEq)]
pub struct GossipLedgerEntry {
    pub epoch:           u64,
    pub report_hash:     [u8; 32],
    pub alert_hash:      [u8; 32],
    pub sla_hash:        [u8; 32],
    pub capacity_hash:   [u8; 32],
    pub delta_hash:      [u8; 32],
    pub trend_hash:      [u8; 32],
    pub dashboard_hash:  [u8; 32],
    pub entry_hash:      [u8; 32],
    pub prev_hash:       [u8; 32],
}

fn compute_entry_hash(
    prev:            &[u8; 32],
    epoch:           u64,
    report_hash:     &[u8; 32],
    alert_hash:      &[u8; 32],
    sla_hash:        &[u8; 32],
    capacity_hash:   &[u8; 32],
    delta_hash:      &[u8; 32],
    trend_hash:      &[u8; 32],
    dashboard_hash:  &[u8; 32],
) -> [u8; 32] {
    let mut h = Sha256::new();
    h.update(prev);
    h.update(epoch.to_be_bytes());
    h.update(report_hash);
    h.update(alert_hash);
    h.update(sla_hash);
    h.update(capacity_hash);
    h.update(delta_hash);
    h.update(trend_hash);
    h.update(dashboard_hash);
    h.finalize().into()
}

// ─── GossipEpochLedger ────────────────────────────────────────────────────────

pub struct GossipEpochLedger {
    entries: Vec<GossipLedgerEntry>,
}

impl GossipEpochLedger {
    pub fn new() -> Self { Self { entries: Vec::new() } }

    pub fn entry_count(&self)          -> usize { self.entries.len() }
    pub fn is_empty(&self)             -> bool   { self.entries.is_empty() }
    pub fn entries(&self)              -> &[GossipLedgerEntry]     { &self.entries }
    pub fn entries_mut(&mut self)      -> &mut [GossipLedgerEntry] { &mut self.entries }
    pub fn latest(&self)               -> Option<&GossipLedgerEntry> { self.entries.last() }

    pub fn terminal_hash(&self) -> [u8; 32] {
        self.entries.last()
            .map(|e| e.entry_hash)
            .unwrap_or(GOSSIP_LEDGER_GENESIS_HASH)
    }

    #[allow(clippy::too_many_arguments)]
    pub fn append(
        &mut self,
        epoch:           u64,
        report_hash:     [u8; 32],
        alert_hash:      [u8; 32],
        sla_hash:        [u8; 32],
        capacity_hash:   [u8; 32],
        delta_hash:      [u8; 32],
        trend_hash:      [u8; 32],
        dashboard_hash:  [u8; 32],
    ) -> &GossipLedgerEntry {
        let prev = self.entries.last()
            .map(|e| e.entry_hash)
            .unwrap_or(GOSSIP_LEDGER_GENESIS_HASH);

        let entry_hash = compute_entry_hash(
            &prev, epoch,
            &report_hash, &alert_hash, &sla_hash, &capacity_hash,
            &delta_hash, &trend_hash, &dashboard_hash,
        );

        self.entries.push(GossipLedgerEntry {
            epoch,
            report_hash,
            alert_hash,
            sla_hash,
            capacity_hash,
            delta_hash,
            trend_hash,
            dashboard_hash,
            entry_hash,
            prev_hash: prev,
        });
        self.entries.last().unwrap()
    }

    pub fn verify_chain(&self) -> (bool, Option<usize>) {
        let mut prev = GOSSIP_LEDGER_GENESIS_HASH;
        for (i, e) in self.entries.iter().enumerate() {
            if e.prev_hash != prev {
                return (false, Some(i));
            }
            let expected = compute_entry_hash(
                &prev, e.epoch,
                &e.report_hash, &e.alert_hash, &e.sla_hash, &e.capacity_hash,
                &e.delta_hash, &e.trend_hash, &e.dashboard_hash,
            );
            if e.entry_hash != expected {
                return (false, Some(i));
            }
            prev = e.entry_hash;
        }
        (true, None)
    }
}

impl Default for GossipEpochLedger {
    fn default() -> Self { Self::new() }
}

// ─── Tests ────────────────────────────────────────────────────────────────────

#[cfg(test)]
mod tests {
    use super::*;

    fn rnd_hash(seed: u8) -> [u8; 32] {
        let mut h = [0u8; 32];
        for (i, b) in h.iter_mut().enumerate() {
            *b = seed.wrapping_add(i as u8);
        }
        h
    }

    fn append_entry(ledger: &mut GossipEpochLedger, epoch: u64) -> GossipLedgerEntry {
        ledger.append(
            epoch,
            rnd_hash(epoch as u8),
            rnd_hash(epoch as u8 + 1),
            rnd_hash(epoch as u8 + 2),
            rnd_hash(epoch as u8 + 3),
            rnd_hash(epoch as u8 + 4),
            rnd_hash(epoch as u8 + 5),
            rnd_hash(epoch as u8 + 6),
        ).clone()
    }

    // ── Basic operations ──────────────────────────────────────────────────────

    #[test]
    fn new_ledger_empty() {
        let l = GossipEpochLedger::new();
        assert_eq!(l.entry_count(), 0);
        assert!(l.is_empty());
        assert_eq!(l.terminal_hash(), GOSSIP_LEDGER_GENESIS_HASH);
        assert!(l.latest().is_none());
    }

    #[test]
    fn single_entry_fields() {
        let mut l = GossipEpochLedger::new();
        let e = append_entry(&mut l, 1);
        assert_eq!(e.epoch, 1);
        assert_eq!(l.entry_count(), 1);
        assert_eq!(l.terminal_hash(), e.entry_hash);
    }

    #[test]
    fn entry_hash_is_32_bytes_nonzero() {
        let mut l = GossipEpochLedger::new();
        let e = append_entry(&mut l, 1);
        assert_ne!(e.entry_hash, [0u8; 32]);
    }

    #[test]
    fn first_entry_prev_hash_is_genesis() {
        let mut l = GossipEpochLedger::new();
        let e = append_entry(&mut l, 1);
        assert_eq!(e.prev_hash, GOSSIP_LEDGER_GENESIS_HASH);
    }

    #[test]
    fn second_entry_prev_hash_links_first() {
        let mut l = GossipEpochLedger::new();
        let e1 = append_entry(&mut l, 1);
        let e2 = append_entry(&mut l, 2);
        assert_eq!(e2.prev_hash, e1.entry_hash);
    }

    #[test]
    fn terminal_hash_updates_on_each_append() {
        let mut l = GossipEpochLedger::new();
        append_entry(&mut l, 1);
        let h1 = l.terminal_hash();
        append_entry(&mut l, 2);
        let h2 = l.terminal_hash();
        assert_ne!(h1, h2);
    }

    // ── Cross-subsystem hash binding ──────────────────────────────────────────

    #[test]
    fn all_sub_hashes_stored() {
        let mut l = GossipEpochLedger::new();
        let rh  = rnd_hash(10);
        let ah  = rnd_hash(20);
        let sh  = rnd_hash(30);
        let ch  = rnd_hash(40);
        let dh  = rnd_hash(50);
        let th  = rnd_hash(60);
        let dbh = rnd_hash(70);
        let e = l.append(7, rh, ah, sh, ch, dh, th, dbh).clone();
        assert_eq!(e.report_hash,     rh);
        assert_eq!(e.alert_hash,      ah);
        assert_eq!(e.sla_hash,        sh);
        assert_eq!(e.capacity_hash,   ch);
        assert_eq!(e.delta_hash,      dh);
        assert_eq!(e.trend_hash,      th);
        assert_eq!(e.dashboard_hash,  dbh);
    }

    #[test]
    fn different_sub_hashes_yield_different_entry_hash() {
        let mut l1 = GossipEpochLedger::new();
        let mut l2 = GossipEpochLedger::new();
        l1.append(1, rnd_hash(1), [0u8;32], [0u8;32], [0u8;32], [0u8;32], [0u8;32], [0u8;32]);
        l2.append(1, rnd_hash(9), [0u8;32], [0u8;32], [0u8;32], [0u8;32], [0u8;32], [0u8;32]);
        assert_ne!(l1.entries[0].entry_hash, l2.entries[0].entry_hash);
    }

    // ── Chain integrity ───────────────────────────────────────────────────────

    #[test]
    fn verify_chain_empty_ok() {
        let l = GossipEpochLedger::new();
        let (ok, idx) = l.verify_chain();
        assert!(ok);
        assert!(idx.is_none());
    }

    #[test]
    fn verify_chain_five_entries_ok() {
        let mut l = GossipEpochLedger::new();
        for i in 1u64..=5 { append_entry(&mut l, i); }
        let (ok, idx) = l.verify_chain();
        assert!(ok);
        assert!(idx.is_none());
    }

    #[test]
    fn verify_chain_detects_tamper_entry_hash() {
        let mut l = GossipEpochLedger::new();
        for i in 1u64..=3 { append_entry(&mut l, i); }
        l.entries[1].entry_hash[0] ^= 0xFF;
        let (ok, idx) = l.verify_chain();
        assert!(!ok);
        assert_eq!(idx, Some(1));
    }

    #[test]
    fn verify_chain_detects_tamper_sub_hash() {
        let mut l = GossipEpochLedger::new();
        append_entry(&mut l, 1);
        l.entries[0].alert_hash[3] ^= 0xAB;
        let (ok, idx) = l.verify_chain();
        assert!(!ok);
        assert_eq!(idx, Some(0));
    }

    #[test]
    fn entry_hash_deterministic() {
        let mut l1 = GossipEpochLedger::new();
        let mut l2 = GossipEpochLedger::new();
        append_entry(&mut l1, 5);
        append_entry(&mut l2, 5);
        assert_eq!(l1.entries[0].entry_hash, l2.entries[0].entry_hash);
    }
}
