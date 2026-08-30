//! Gate 349 — Compaction Audit Seal (T2)
//! EPISTEMIC TIER: T2 (engineering hypothesis)
//!
//! Certifies a window of CompactionEpochLedger entries (Gate 348) into a
//! tamper-evident CompactionAuditSeal. Analogous to Gate 336 for the full
//! compaction subsystem (gates 338–348).
//!
//! CompactionAuditSeal:
//!   epoch_start:        u64
//!   epoch_end:          u64
//!   epoch_count:        u64
//!   chains_valid:       bool           — verify_chain() result for the window
//!   terminal_hash:      [u8;32]        — LedgerEntry.entry_hash of last entry
//!   seal_hash:          [u8;32]
//!   prev_hash:          [u8;32]
//!
//! seal_hash = SHA-256(prev[32] ‖ epoch_start_be8 ‖ epoch_end_be8
//!                       ‖ epoch_count_be8 ‖ chains_valid_byte
//!                       ‖ terminal_hash[32])
//!
//! CompactionAuditSealLog: certify(ledger_entries), all_valid(),
//!   seal_count(), verify_chain().

use sha2::{Sha256, Digest};
use crate::compaction_epoch_ledger::{CompactionEpochLedger, LedgerEntry};

pub const AUDIT_SEAL_GENESIS_HASH: [u8; 32] = [0u8; 32];

// ─── CompactionAuditSeal ──────────────────────────────────────────────────────

#[derive(Debug, Clone, PartialEq)]
pub struct CompactionAuditSeal {
    pub epoch_start:   u64,
    pub epoch_end:     u64,
    pub epoch_count:   u64,
    pub chains_valid:  bool,
    pub terminal_hash: [u8; 32],
    pub seal_hash:     [u8; 32],
    pub prev_hash:     [u8; 32],
}

fn compute_seal_hash(
    prev:          &[u8; 32],
    epoch_start:   u64,
    epoch_end:     u64,
    epoch_count:   u64,
    chains_valid:  bool,
    terminal_hash: &[u8; 32],
) -> [u8; 32] {
    let mut h = Sha256::new();
    h.update(prev);
    h.update(epoch_start.to_be_bytes());
    h.update(epoch_end.to_be_bytes());
    h.update(epoch_count.to_be_bytes());
    h.update([chains_valid as u8]);
    h.update(terminal_hash);
    h.finalize().into()
}

// ─── CompactionAuditSealLog ───────────────────────────────────────────────────

pub struct CompactionAuditSealLog {
    seals: Vec<CompactionAuditSeal>,
}

impl CompactionAuditSealLog {
    pub fn new() -> Self { Self { seals: Vec::new() } }

    pub fn seal_count(&self) -> usize { self.seals.len() }
    pub fn is_empty(&self)   -> bool  { self.seals.is_empty() }
    pub fn seals(&self)      -> &[CompactionAuditSeal] { &self.seals }
    pub fn latest(&self)     -> Option<&CompactionAuditSeal> { self.seals.last() }

    /// Certify a slice of LedgerEntries as a single audit window.
    /// Returns Err if entries is empty.
    pub fn certify(&mut self, entries: &[LedgerEntry]) -> Result<&CompactionAuditSeal, &'static str> {
        if entries.is_empty() {
            return Err("[AUDIT_SEAL] Cannot certify empty entry window");
        }

        let epoch_start = entries.first().unwrap().epoch;
        let epoch_end   = entries.last().unwrap().epoch;
        let epoch_count = entries.len() as u64;

        // Verify the internal chain within this window
        let chains_valid = {
            let mut valid = true;
            let mut prev = entries[0].prev_hash;
            for (i, e) in entries.iter().enumerate() {
                if e.prev_hash != prev {
                    valid = false;
                    break;
                }
                // Recompute entry_hash using stored fields
                use sha2::Digest as _;
                let mut hh = Sha256::new();
                hh.update(&prev);
                hh.update(e.epoch.to_be_bytes());
                hh.update(&e.report_hash);
                hh.update(&e.alert_hash);
                hh.update(&e.sla_hash);
                hh.update(&e.capacity_hash);
                hh.update(&e.delta_hash);
                hh.update(&e.trend_hash);
                hh.update(&e.dashboard_hash);
                let expected: [u8; 32] = hh.finalize().into();
                if e.entry_hash != expected {
                    valid = false;
                    break;
                }
                let _ = i;
                prev = e.entry_hash;
            }
            valid
        };

        let terminal_hash = entries.last().unwrap().entry_hash;

        let prev = self.seals.last()
            .map(|s| s.seal_hash)
            .unwrap_or(AUDIT_SEAL_GENESIS_HASH);

        let seal_hash = compute_seal_hash(
            &prev, epoch_start, epoch_end, epoch_count, chains_valid, &terminal_hash,
        );

        self.seals.push(CompactionAuditSeal {
            epoch_start,
            epoch_end,
            epoch_count,
            chains_valid,
            terminal_hash,
            seal_hash,
            prev_hash: prev,
        });
        Ok(self.seals.last().unwrap())
    }

    /// Convenience: certify the entire contents of a CompactionEpochLedger.
    pub fn certify_ledger(&mut self, ledger: &CompactionEpochLedger) -> Result<&CompactionAuditSeal, &'static str> {
        self.certify(ledger.entries())
    }

    /// True if every seal in this log has chains_valid == true.
    pub fn all_valid(&self) -> bool {
        self.seals.iter().all(|s| s.chains_valid)
    }

    pub fn verify_chain(&self) -> (bool, Option<usize>) {
        let mut prev = AUDIT_SEAL_GENESIS_HASH;
        for (i, s) in self.seals.iter().enumerate() {
            if s.prev_hash != prev {
                return (false, Some(i));
            }
            let expected = compute_seal_hash(
                &prev,
                s.epoch_start,
                s.epoch_end,
                s.epoch_count,
                s.chains_valid,
                &s.terminal_hash,
            );
            if s.seal_hash != expected {
                return (false, Some(i));
            }
            prev = s.seal_hash;
        }
        (true, None)
    }
}

impl Default for CompactionAuditSealLog {
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

    fn build_ledger(n: u64) -> CompactionEpochLedger {
        let mut l = CompactionEpochLedger::new();
        for i in 1u64..=n {
            l.append(i, rnd_hash(i as u8), rnd_hash(i as u8+1), rnd_hash(i as u8+2),
                     rnd_hash(i as u8+3), rnd_hash(i as u8+4), rnd_hash(i as u8+5), rnd_hash(i as u8+6));
        }
        l
    }

    // ── certify() ─────────────────────────────────────────────────────────────

    #[test]
    fn certify_empty_returns_err() {
        let mut log = CompactionAuditSealLog::new();
        assert!(log.certify(&[]).is_err());
    }

    #[test]
    fn certify_single_entry_valid() {
        let ledger = build_ledger(1);
        let mut log = CompactionAuditSealLog::new();
        let seal = log.certify_ledger(&ledger).unwrap().clone();
        assert_eq!(seal.epoch_start, 1);
        assert_eq!(seal.epoch_end, 1);
        assert_eq!(seal.epoch_count, 1);
        assert!(seal.chains_valid);
    }

    #[test]
    fn certify_five_entry_ledger_valid() {
        let ledger = build_ledger(5);
        let mut log = CompactionAuditSealLog::new();
        let seal = log.certify_ledger(&ledger).unwrap().clone();
        assert_eq!(seal.epoch_start, 1);
        assert_eq!(seal.epoch_end, 5);
        assert_eq!(seal.epoch_count, 5);
        assert!(seal.chains_valid);
    }

    #[test]
    fn terminal_hash_matches_ledger_terminal() {
        let ledger = build_ledger(3);
        let mut log = CompactionAuditSealLog::new();
        let seal = log.certify_ledger(&ledger).unwrap().clone();
        assert_eq!(seal.terminal_hash, ledger.terminal_hash());
    }

    #[test]
    fn tampered_entry_hash_detected() {
        let mut ledger = build_ledger(3);
        ledger.entries_mut()[1].entry_hash[0] ^= 0xFF;
        let mut log = CompactionAuditSealLog::new();
        let seal = log.certify_ledger(&ledger).unwrap().clone();
        assert!(!seal.chains_valid);
    }

    #[test]
    fn all_valid_true_when_all_seals_valid() {
        let ledger = build_ledger(3);
        let mut log = CompactionAuditSealLog::new();
        log.certify_ledger(&ledger).unwrap();
        assert!(log.all_valid());
    }

    #[test]
    fn all_valid_false_when_one_seal_invalid() {
        let mut ledger = build_ledger(3);
        let mut log = CompactionAuditSealLog::new();
        log.certify_ledger(&ledger).unwrap(); // valid seal
        // Tamper and certify again
        ledger.entries_mut()[0].entry_hash[0] ^= 0xFF;
        log.certify_ledger(&ledger).unwrap(); // invalid seal
        assert!(!log.all_valid());
    }

    // ── Seal hash determinism ─────────────────────────────────────────────────

    #[test]
    fn seal_hash_deterministic() {
        let ledger = build_ledger(4);
        let mut log1 = CompactionAuditSealLog::new();
        let mut log2 = CompactionAuditSealLog::new();
        let s1 = log1.certify_ledger(&ledger).unwrap().clone();
        let s2 = log2.certify_ledger(&ledger).unwrap().clone();
        assert_eq!(s1.seal_hash, s2.seal_hash);
    }

    // ── Seal log chain integrity ───────────────────────────────────────────────

    #[test]
    fn verify_chain_empty_ok() {
        let log = CompactionAuditSealLog::new();
        let (ok, idx) = log.verify_chain();
        assert!(ok);
        assert!(idx.is_none());
    }

    #[test]
    fn verify_chain_three_seals_ok() {
        let mut log = CompactionAuditSealLog::new();
        for _ in 0..3 {
            let ledger = build_ledger(2);
            log.certify_ledger(&ledger).unwrap();
        }
        let (ok, idx) = log.verify_chain();
        assert!(ok);
        assert!(idx.is_none());
    }

    #[test]
    fn verify_chain_detects_tamper() {
        let mut log = CompactionAuditSealLog::new();
        log.certify_ledger(&build_ledger(2)).unwrap();
        log.certify_ledger(&build_ledger(2)).unwrap();
        log.seals[0].seal_hash[0] ^= 0xFF;
        let (ok, idx) = log.verify_chain();
        assert!(!ok);
        assert_eq!(idx, Some(0));
    }

    #[test]
    fn prev_hash_links_correctly() {
        let mut log = CompactionAuditSealLog::new();
        log.certify_ledger(&build_ledger(1)).unwrap();
        let h0 = log.seals[0].seal_hash;
        log.certify_ledger(&build_ledger(1)).unwrap();
        assert_eq!(log.seals[1].prev_hash, h0);
    }
}
