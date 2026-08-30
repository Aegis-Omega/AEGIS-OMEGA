//! Gate 358 — Compaction Gossip Audit Certifier (T2)
//! EPISTEMIC TIER: T2 (engineering hypothesis)
//!
//! Certifies a GossipEpochSealChain (Gate 357) over an epoch window,
//! producing a tamper-evident GossipAuditCertificate. Mirrors Gate 336
//! (Compaction Audit Certifier) for the compaction gossip subsystem.
//!
//! GossipAuditCertificate:
//!   epoch_start:       u64
//!   epoch_end:         u64
//!   epoch_count:       u64
//!   chains_valid:      bool — GossipEpochSealChain.verify_chain() passed
//!   total_delivered:   u64  — sum of delivered across window
//!   total_missed:      u64  — sum of missed across window
//!   red_epochs:        u32  — sum of red_epochs across window
//!   yellow_epochs:     u32  — sum of yellow_epochs across window
//!   green_epochs:      u32  — sum of green_epochs across window
//!   terminal_hash:     [u8;32] — seal chain terminal_hash at epoch_end
//!   certificate_hash:  [u8;32]
//!
//! certificate_hash = SHA-256(epoch_start_be8 ‖ epoch_end_be8 ‖ epoch_count_be8
//!                             ‖ chains_valid_byte ‖ total_delivered_be8 ‖ total_missed_be8
//!                             ‖ red_be4 ‖ yellow_be4 ‖ green_be4 ‖ terminal_hash[32])
//!
//! GossipCertifierLog: hash-chained certificates.
//!   certify_window(), latest(), all_valid(), verify_chain().

use sha2::{Sha256, Digest};
use crate::compaction_gossip_epoch_seal::GossipEpochSeal;

pub const GOSSIP_CERTIFIER_GENESIS_HASH: [u8; 32] = [0u8; 32];

// ─── GossipAuditCertificate ───────────────────────────────────────────────────

#[derive(Debug, Clone, PartialEq)]
pub struct GossipAuditCertificate {
    pub epoch_start:      u64,
    pub epoch_end:        u64,
    pub epoch_count:      u64,
    pub chains_valid:     bool,
    pub total_delivered:  u64,
    pub total_missed:     u64,
    pub red_epochs:       u32,
    pub yellow_epochs:    u32,
    pub green_epochs:     u32,
    pub terminal_hash:    [u8; 32],
    pub certificate_hash: [u8; 32],
    pub log_prev_hash:    [u8; 32],
    pub log_record_hash:  [u8; 32],
}

fn compute_certificate_hash(
    epoch_start:     u64,
    epoch_end:       u64,
    epoch_count:     u64,
    chains_valid:    bool,
    total_delivered: u64,
    total_missed:    u64,
    red:             u32,
    yellow:          u32,
    green:           u32,
    terminal_hash:   &[u8; 32],
) -> [u8; 32] {
    let mut h = Sha256::new();
    h.update(epoch_start.to_be_bytes());
    h.update(epoch_end.to_be_bytes());
    h.update(epoch_count.to_be_bytes());
    h.update([chains_valid as u8]);
    h.update(total_delivered.to_be_bytes());
    h.update(total_missed.to_be_bytes());
    h.update(red.to_be_bytes());
    h.update(yellow.to_be_bytes());
    h.update(green.to_be_bytes());
    h.update(terminal_hash);
    h.finalize().into()
}

fn compute_log_record_hash(
    prev:        &[u8; 32],
    cert_hash:   &[u8; 32],
    epoch_start: u64,
    epoch_end:   u64,
) -> [u8; 32] {
    let mut h = Sha256::new();
    h.update(prev);
    h.update(cert_hash);
    h.update(epoch_start.to_be_bytes());
    h.update(epoch_end.to_be_bytes());
    h.finalize().into()
}

// ─── GossipCertifierLog ───────────────────────────────────────────────────────

pub struct GossipCertifierLog {
    certs: Vec<GossipAuditCertificate>,
}

impl GossipCertifierLog {
    pub fn new() -> Self { Self { certs: Vec::new() } }

    pub fn cert_count(&self) -> usize { self.certs.len() }
    pub fn is_empty(&self)   -> bool  { self.certs.is_empty() }
    pub fn certs(&self)      -> &[GossipAuditCertificate] { &self.certs }
    pub fn latest(&self)     -> Option<&GossipAuditCertificate> { self.certs.last() }

    pub fn all_valid(&self) -> bool {
        self.certs.iter().all(|c| c.chains_valid)
    }

    /// Certify a window of seals. `chains_valid` is the caller's verify_chain() result
    /// over the full seal chain (passed in to avoid re-walking the entire chain each time).
    pub fn certify_window(
        &mut self,
        seals:        &[GossipEpochSeal],
        epoch_start:  u64,
        epoch_end:    u64,
        chains_valid: bool,
        terminal_hash: [u8; 32],
    ) -> &GossipAuditCertificate {
        let epoch_count     = seals.len() as u64;
        let total_delivered = seals.iter().map(|s| s.total_delivered).sum();
        let total_missed    = seals.iter().map(|s| s.total_missed).sum();
        let red_epochs      = seals.iter().map(|s| s.red_epochs).sum();
        let yellow_epochs   = seals.iter().map(|s| s.yellow_epochs).sum();
        let green_epochs    = seals.iter().map(|s| s.green_epochs).sum();

        let certificate_hash = compute_certificate_hash(
            epoch_start, epoch_end, epoch_count,
            chains_valid, total_delivered, total_missed,
            red_epochs, yellow_epochs, green_epochs,
            &terminal_hash,
        );

        let prev = self.certs.last()
            .map(|c| c.log_record_hash)
            .unwrap_or(GOSSIP_CERTIFIER_GENESIS_HASH);
        let log_record_hash = compute_log_record_hash(&prev, &certificate_hash, epoch_start, epoch_end);

        self.certs.push(GossipAuditCertificate {
            epoch_start, epoch_end, epoch_count,
            chains_valid, total_delivered, total_missed,
            red_epochs, yellow_epochs, green_epochs,
            terminal_hash, certificate_hash,
            log_prev_hash: prev, log_record_hash,
        });
        self.certs.last().unwrap()
    }

    pub fn verify_chain(&self) -> (bool, Option<usize>) {
        let mut prev = GOSSIP_CERTIFIER_GENESIS_HASH;
        for (i, c) in self.certs.iter().enumerate() {
            if c.log_prev_hash != prev { return (false, Some(i)); }
            let expected = compute_log_record_hash(&prev, &c.certificate_hash, c.epoch_start, c.epoch_end);
            if c.log_record_hash != expected { return (false, Some(i)); }
            prev = c.log_record_hash;
        }
        (true, None)
    }
}

impl Default for GossipCertifierLog {
    fn default() -> Self { Self::new() }
}

// ─── Tests ────────────────────────────────────────────────────────────────────

#[cfg(test)]
mod tests {
    use super::*;
    use crate::compaction_gossip_epoch_seal::GossipEpochSealChain;

    fn build_seals(n: u64) -> GossipEpochSealChain {
        let mut c = GossipEpochSealChain::new();
        for i in 1..=n {
            c.append(i, [0xAAu8; 32], [0xBBu8; 32], 100 * i, 2 * i, 0, 0, i as u32);
        }
        c
    }

    fn certify(log: &mut GossipCertifierLog, chain: &GossipEpochSealChain) -> () {
        let (valid, _) = chain.verify_chain();
        let seals = chain.seals();
        if seals.is_empty() { return; }
        let start = seals.first().unwrap().epoch;
        let end   = seals.last().unwrap().epoch;
        log.certify_window(seals, start, end, valid, chain.terminal_hash());
    }

    // ── certificate fields ────────────────────────────────────────────────────

    #[test]
    fn certificate_hash_nonzero() {
        let chain = build_seals(3);
        let mut log = GossipCertifierLog::new();
        certify(&mut log, &chain);
        assert_ne!(log.latest().unwrap().certificate_hash, [0u8; 32]);
    }

    #[test]
    fn chains_valid_true_for_intact_chain() {
        let chain = build_seals(4);
        let mut log = GossipCertifierLog::new();
        certify(&mut log, &chain);
        assert!(log.latest().unwrap().chains_valid);
        assert!(log.all_valid());
    }

    #[test]
    fn chains_valid_false_when_flagged() {
        let chain = build_seals(2);
        let mut log = GossipCertifierLog::new();
        let seals = chain.seals();
        log.certify_window(seals, 1, 2, false, chain.terminal_hash());
        assert!(!log.latest().unwrap().chains_valid);
        assert!(!log.all_valid());
    }

    #[test]
    fn epoch_count_matches_seals() {
        let chain = build_seals(5);
        let mut log = GossipCertifierLog::new();
        certify(&mut log, &chain);
        assert_eq!(log.latest().unwrap().epoch_count, 5);
    }

    #[test]
    fn totals_summed_correctly() {
        let chain = build_seals(3); // epochs 1,2,3 → delivered 100,200,300 → 600
        let mut log = GossipCertifierLog::new();
        certify(&mut log, &chain);
        assert_eq!(log.latest().unwrap().total_delivered, 600);
        assert_eq!(log.latest().unwrap().total_missed, 2 + 4 + 6);
    }

    #[test]
    fn terminal_hash_matches_chain() {
        let chain = build_seals(3);
        let mut log = GossipCertifierLog::new();
        certify(&mut log, &chain);
        assert_eq!(log.latest().unwrap().terminal_hash, chain.terminal_hash());
    }

    #[test]
    fn certificate_deterministic() {
        let chain = build_seals(3);
        let mut log1 = GossipCertifierLog::new();
        let mut log2 = GossipCertifierLog::new();
        certify(&mut log1, &chain);
        certify(&mut log2, &chain);
        assert_eq!(
            log1.latest().unwrap().certificate_hash,
            log2.latest().unwrap().certificate_hash
        );
    }

    // ── log chain ─────────────────────────────────────────────────────────────

    #[test]
    fn log_empty_ok() {
        let log = GossipCertifierLog::new();
        assert!(log.is_empty());
        let (ok, idx) = log.verify_chain();
        assert!(ok);
        assert!(idx.is_none());
    }

    #[test]
    fn log_first_prev_is_genesis() {
        let chain = build_seals(2);
        let mut log = GossipCertifierLog::new();
        certify(&mut log, &chain);
        assert_eq!(log.certs()[0].log_prev_hash, GOSSIP_CERTIFIER_GENESIS_HASH);
    }

    #[test]
    fn log_record_hash_links() {
        let mut log = GossipCertifierLog::new();
        let c1 = build_seals(2);
        let c2 = build_seals(3);
        certify(&mut log, &c1);
        let h0 = log.certs()[0].log_record_hash;
        certify(&mut log, &c2);
        assert_eq!(log.certs()[1].log_prev_hash, h0);
    }

    #[test]
    fn verify_chain_three_certs_ok() {
        let mut log = GossipCertifierLog::new();
        for _ in 0..3 {
            let chain = build_seals(2);
            certify(&mut log, &chain);
        }
        let (ok, idx) = log.verify_chain();
        assert!(ok);
        assert!(idx.is_none());
    }

    #[test]
    fn verify_chain_detects_tamper() {
        let mut log = GossipCertifierLog::new();
        for _ in 0..3 {
            let chain = build_seals(2);
            certify(&mut log, &chain);
        }
        log.certs[0].log_record_hash[0] ^= 0xFF;
        let (ok, idx) = log.verify_chain();
        assert!(!ok);
        assert_eq!(idx, Some(0));
    }
}
