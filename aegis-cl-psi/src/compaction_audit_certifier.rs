//! Gate 336 — Compaction Audit Certifier (T2)
//! EPISTEMIC TIER: T2 (engineering hypothesis)
//!
//! Certifies a CompactionSealChain (Gate 335) over an epoch window,
//! producing a tamper-evident CompactionAuditCertificate. Analogous to
//! Gate 253 (Constitutional Audit Certifier) for the compaction subsystem.
//!
//! CompactionAuditCertificate:
//!   epoch_start:             u64
//!   epoch_end:               u64
//!   epoch_count:             u64
//!   chains_valid:            bool — CompactionSealChain.verify_chain() passed
//!   total_pruned_certified:  u64  — total_pruned across all seals in window
//!   spsf_pruned_certified:   u64
//!   health_pruned_certified: u64
//!   resonance_pruned_certified: u64
//!   terminal_hash:           [u8;32] — seal chain terminal_hash at epoch_end
//!   certificate_hash:        [u8;32]
//!
//! certificate_hash = SHA-256(epoch_start_be8 ‖ epoch_end_be8 ‖ epoch_count_be8
//!                             ‖ chains_valid_byte ‖ total_pruned_be8
//!                             ‖ spsf_be8 ‖ health_be8 ‖ resonance_be8
//!                             ‖ terminal_hash[32])
//!
//! CertifierLog: hash-chained CompactionAuditCertificates.
//!   certify_window(): takes seals slice + epoch range → certificate.
//!   latest(), all_valid(), verify_chain().

use sha2::{Sha256, Digest};
use crate::compaction_epoch_seal::{CompactionEpochSeal, COMPACTION_SEAL_GENESIS_HASH};

pub const CERTIFIER_GENESIS_HASH: [u8; 32] = [0u8; 32];

// ─── CompactionAuditCertificate ───────────────────────────────────────────────

#[derive(Debug, Clone, PartialEq)]
pub struct CompactionAuditCertificate {
    pub epoch_start:               u64,
    pub epoch_end:                 u64,
    pub epoch_count:               u64,
    pub chains_valid:              bool,
    pub total_pruned_certified:    u64,
    pub spsf_pruned_certified:     u64,
    pub health_pruned_certified:   u64,
    pub resonance_pruned_certified: u64,
    pub terminal_hash:             [u8; 32],
    pub certificate_hash:          [u8; 32],
    pub log_prev_hash:             [u8; 32],
    pub log_record_hash:           [u8; 32],
}

fn compute_certificate_hash(
    epoch_start:    u64,
    epoch_end:      u64,
    epoch_count:    u64,
    chains_valid:   bool,
    total_pruned:   u64,
    spsf:           u64,
    health:         u64,
    resonance:      u64,
    terminal_hash:  &[u8; 32],
) -> [u8; 32] {
    let mut h = Sha256::new();
    h.update(epoch_start.to_be_bytes());
    h.update(epoch_end.to_be_bytes());
    h.update(epoch_count.to_be_bytes());
    h.update([chains_valid as u8]);
    h.update(total_pruned.to_be_bytes());
    h.update(spsf.to_be_bytes());
    h.update(health.to_be_bytes());
    h.update(resonance.to_be_bytes());
    h.update(terminal_hash);
    h.finalize().into()
}

fn compute_log_record_hash(
    prev:            &[u8; 32],
    cert_hash:       &[u8; 32],
    epoch_start:     u64,
    epoch_end:       u64,
    chains_valid:    bool,
) -> [u8; 32] {
    let mut h = Sha256::new();
    h.update(prev);
    h.update(cert_hash);
    h.update(epoch_start.to_be_bytes());
    h.update(epoch_end.to_be_bytes());
    h.update([chains_valid as u8]);
    h.finalize().into()
}

// ─── CertifierLog ─────────────────────────────────────────────────────────────

pub struct CertifierLog {
    entries: Vec<CompactionAuditCertificate>,
}

impl CertifierLog {
    pub fn new() -> Self { Self { entries: Vec::new() } }

    pub fn len(&self)      -> usize { self.entries.len() }
    pub fn is_empty(&self) -> bool  { self.entries.is_empty() }
    pub fn entries(&self)  -> &[CompactionAuditCertificate] { &self.entries }
    pub fn latest(&self)   -> Option<&CompactionAuditCertificate> { self.entries.last() }

    /// Certify a window of seals.
    ///
    /// `seals`: the seals slice to certify (may be an epoch-range subset or the full chain).
    /// `epoch_start` / `epoch_end`: declared range covered by this certificate.
    /// `chains_valid`: caller passes `CompactionSealChain::verify_chain().0` for the full chain.
    pub fn certify_window(
        &mut self,
        seals:         &[CompactionEpochSeal],
        epoch_start:   u64,
        epoch_end:     u64,
        chains_valid:  bool,
    ) -> &CompactionAuditCertificate {
        let epoch_count = seals.len() as u64;

        let spsf     = seals.iter().map(|s| s.spsf_total_pruned).last().unwrap_or(0);
        let health   = seals.iter().map(|s| s.health_total_pruned).last().unwrap_or(0);
        let resonance = seals.iter().map(|s| s.resonance_total_pruned).last().unwrap_or(0);
        let total    = seals.iter().map(|s| s.total_pruned).last().unwrap_or(0);
        let terminal = seals.last().map(|s| s.seal_hash).unwrap_or(COMPACTION_SEAL_GENESIS_HASH);

        let certificate_hash = compute_certificate_hash(
            epoch_start, epoch_end, epoch_count, chains_valid,
            total, spsf, health, resonance, &terminal,
        );

        let prev = self.entries.last()
            .map(|e| e.log_record_hash)
            .unwrap_or(CERTIFIER_GENESIS_HASH);

        let log_record_hash = compute_log_record_hash(
            &prev, &certificate_hash, epoch_start, epoch_end, chains_valid,
        );

        self.entries.push(CompactionAuditCertificate {
            epoch_start,
            epoch_end,
            epoch_count,
            chains_valid,
            total_pruned_certified:     total,
            spsf_pruned_certified:      spsf,
            health_pruned_certified:    health,
            resonance_pruned_certified: resonance,
            terminal_hash:              terminal,
            certificate_hash,
            log_prev_hash:              prev,
            log_record_hash,
        });
        self.entries.last().unwrap()
    }

    /// True iff every certificate in the log has `chains_valid == true`.
    pub fn all_valid(&self) -> bool {
        self.entries.iter().all(|e| e.chains_valid)
    }

    pub fn verify_chain(&self) -> (bool, Option<usize>) {
        let mut prev = CERTIFIER_GENESIS_HASH;
        for (i, e) in self.entries.iter().enumerate() {
            if e.log_prev_hash != prev {
                return (false, Some(i));
            }
            let expected = compute_log_record_hash(
                &prev, &e.certificate_hash, e.epoch_start, e.epoch_end, e.chains_valid,
            );
            if e.log_record_hash != expected {
                return (false, Some(i));
            }
            prev = e.log_record_hash;
        }
        (true, None)
    }
}

impl Default for CertifierLog {
    fn default() -> Self { Self::new() }
}

// ─── Tests ────────────────────────────────────────────────────────────────────

#[cfg(test)]
mod tests {
    use super::*;
    use crate::compaction_epoch_seal::CompactionSealChain;

    fn build_seal_chain(n: u64) -> CompactionSealChain {
        let mut c = CompactionSealChain::new();
        for i in 1..=n {
            let mut uh = [0u8; 32];
            uh[0] = i as u8;
            c.append(i, uh, i * 5, i * 3, i * 2);
        }
        c
    }

    // ── CertifierLog basics ───────────────────────────────────────────────────

    #[test]
    fn log_starts_empty() {
        let l = CertifierLog::new();
        assert!(l.is_empty());
        assert!(l.latest().is_none());
        assert!(l.all_valid());
    }

    #[test]
    fn certify_empty_seals() {
        let mut l = CertifierLog::new();
        let c = l.certify_window(&[], 0, 0, true);
        assert_eq!(c.epoch_count, 0);
        assert_eq!(c.total_pruned_certified, 0);
        assert!(c.chains_valid);
        assert_eq!(c.terminal_hash, COMPACTION_SEAL_GENESIS_HASH);
    }

    #[test]
    fn certify_single_seal_window() {
        let chain = build_seal_chain(1);
        let mut l = CertifierLog::new();
        let (ok, _) = chain.verify_chain();
        let c = l.certify_window(chain.seals(), 1, 1, ok);
        assert_eq!(c.epoch_count, 1);
        assert_eq!(c.epoch_start, 1);
        assert_eq!(c.epoch_end, 1);
        assert!(c.chains_valid);
        // terminal_hash must match the chain's terminal hash
        assert_eq!(c.terminal_hash, chain.terminal_hash());
    }

    #[test]
    fn certify_five_seal_window() {
        let chain = build_seal_chain(5);
        let (ok, _) = chain.verify_chain();
        let mut l = CertifierLog::new();
        let c = l.certify_window(chain.seals(), 1, 5, ok);
        assert_eq!(c.epoch_count, 5);
        assert!(c.chains_valid);
        assert_ne!(c.certificate_hash, [0u8; 32]);
    }

    #[test]
    fn chains_invalid_when_chain_invalid() {
        let mut chain = build_seal_chain(3);
        chain.seals_mut()[1].seal_hash[0] ^= 0xFF; // tamper
        let (ok, _) = chain.verify_chain();
        let mut l = CertifierLog::new();
        let c = l.certify_window(chain.seals(), 1, 3, ok);
        assert!(!c.chains_valid);
    }

    // ── Certifier log chaining ────────────────────────────────────────────────

    #[test]
    fn two_certifications_chain_correctly() {
        let chain = build_seal_chain(4);
        let (ok, _) = chain.verify_chain();
        let mut l = CertifierLog::new();
        l.certify_window(chain.seals(), 1, 2, ok);
        l.certify_window(chain.seals(), 3, 4, ok);
        assert_eq!(l.len(), 2);
        assert_eq!(
            l.entries()[1].log_prev_hash,
            l.entries()[0].log_record_hash,
        );
    }

    #[test]
    fn verify_chain_empty_ok() {
        let l = CertifierLog::new();
        let (ok, idx) = l.verify_chain();
        assert!(ok);
        assert!(idx.is_none());
    }

    #[test]
    fn verify_chain_three_entries_ok() {
        let chain = build_seal_chain(3);
        let (ok, _) = chain.verify_chain();
        let mut l = CertifierLog::new();
        for _ in 0..3 {
            l.certify_window(chain.seals(), 1, 3, ok);
        }
        let (v_ok, idx) = l.verify_chain();
        assert!(v_ok);
        assert!(idx.is_none());
    }

    #[test]
    fn verify_chain_detects_tampered_log_record_hash() {
        let chain = build_seal_chain(2);
        let (ok, _) = chain.verify_chain();
        let mut l = CertifierLog::new();
        l.certify_window(chain.seals(), 1, 2, ok);
        l.certify_window(chain.seals(), 1, 2, ok);
        l.entries[0].log_record_hash[0] ^= 0xFF;
        let (v_ok, idx) = l.verify_chain();
        assert!(!v_ok);
        assert_eq!(idx, Some(0));
    }

    #[test]
    fn verify_chain_detects_tampered_certificate_hash() {
        let chain = build_seal_chain(2);
        let (ok, _) = chain.verify_chain();
        let mut l = CertifierLog::new();
        l.certify_window(chain.seals(), 1, 2, ok);
        l.entries[0].certificate_hash[0] ^= 0xFF;
        let (v_ok, idx) = l.verify_chain();
        assert!(!v_ok);
        assert_eq!(idx, Some(0));
    }

    // ── all_valid ─────────────────────────────────────────────────────────────

    #[test]
    fn all_valid_true_when_all_chains_valid() {
        let chain = build_seal_chain(3);
        let (ok, _) = chain.verify_chain();
        let mut l = CertifierLog::new();
        l.certify_window(chain.seals(), 1, 3, ok);
        assert!(l.all_valid());
    }

    #[test]
    fn all_valid_false_when_one_invalid() {
        let chain = build_seal_chain(3);
        let mut l = CertifierLog::new();
        l.certify_window(chain.seals(), 1, 3, true);
        l.certify_window(chain.seals(), 1, 3, false); // inject invalid
        assert!(!l.all_valid());
    }

    // ── Determinism ───────────────────────────────────────────────────────────

    #[test]
    fn certificate_hash_deterministic() {
        let chain = build_seal_chain(4);
        let (ok, _) = chain.verify_chain();
        let mut l1 = CertifierLog::new();
        let mut l2 = CertifierLog::new();
        let c1 = l1.certify_window(chain.seals(), 1, 4, ok);
        let c2 = l2.certify_window(chain.seals(), 1, 4, ok);
        assert_eq!(c1.certificate_hash, c2.certificate_hash);
    }

    #[test]
    fn different_epoch_range_different_hash() {
        let chain = build_seal_chain(4);
        let (ok, _) = chain.verify_chain();
        let mut l1 = CertifierLog::new();
        let mut l2 = CertifierLog::new();
        let c1 = l1.certify_window(chain.seals(), 1, 4, ok);
        let c2 = l2.certify_window(chain.seals(), 2, 5, ok);
        assert_ne!(c1.certificate_hash, c2.certificate_hash);
    }
}
