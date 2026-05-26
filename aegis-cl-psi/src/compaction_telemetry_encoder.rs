//! Gate 337 — Compaction Telemetry Encoder (T2)
//! EPISTEMIC TIER: T2 (engineering hypothesis)
//!
//! Encodes a CompactionAuditCertificate (Gate 336) into a compact 24-byte
//! frame suitable for peer gossip broadcast. Mirrors Gate 254 (Constitutional
//! Telemetry Encoder) for the compaction subsystem.
//!
//! CompactionTelemetryFrame (24 bytes):
//!   [0..8]    epoch_end          (u64 BE)
//!   [8..16]   total_pruned       (u64 BE)
//!   [16]      chains_valid       (0x01 = valid, 0x00 = invalid)
//!   [17..20]  spsf+health+res pct (each u8, 0-100 = prune share as % of total_pruned)
//!   [20..24]  cert_hash_prefix   (first 4 bytes of certificate_hash)
//!
//! Pct fields encode the share of each compactor:
//!   spsf_pct   = spsf_pruned   * 100 / max(total_pruned, 1)  (integer, saturating at 100)
//!   health_pct = health_pruned * 100 / max(total_pruned, 1)
//!   res_pct    = resonance_pruned * 100 / max(total_pruned, 1)
//!
//! encode() → CompactionTelemetryFrame
//! decode() → (epoch_end, total_pruned, chains_valid, spsf_pct, health_pct, res_pct, cert_prefix[4])
//!
//! CompactionTelemetryLog: hash-chained encode/decode records.
//!   record_hash = SHA-256(prev[32] ‖ frame[24] ‖ epoch_end_be8)
//!   verify_chain(), frame_count(), latest().

use sha2::{Sha256, Digest};
use crate::compaction_audit_certifier::CompactionAuditCertificate;

pub const TELEMETRY_ENCODER_GENESIS_HASH: [u8; 32] = [0u8; 32];
pub const FRAME_SIZE: usize = 24;

// ─── CompactionTelemetryFrame ─────────────────────────────────────────────────

#[derive(Debug, Clone, Copy, PartialEq)]
pub struct CompactionTelemetryFrame {
    pub bytes: [u8; FRAME_SIZE],
}

impl CompactionTelemetryFrame {
    pub fn epoch_end(&self) -> u64 {
        u64::from_be_bytes(self.bytes[0..8].try_into().unwrap())
    }
    pub fn total_pruned(&self) -> u64 {
        u64::from_be_bytes(self.bytes[8..16].try_into().unwrap())
    }
    pub fn chains_valid(&self) -> bool { self.bytes[16] == 0x01 }
    pub fn spsf_pct(&self)    -> u8    { self.bytes[17] }
    pub fn health_pct(&self)  -> u8    { self.bytes[18] }
    pub fn res_pct(&self)     -> u8    { self.bytes[19] }
    pub fn cert_prefix(&self) -> [u8; 4] {
        self.bytes[20..24].try_into().unwrap()
    }
}

/// Encode a CompactionAuditCertificate into a 24-byte telemetry frame.
pub fn encode(cert: &CompactionAuditCertificate) -> CompactionTelemetryFrame {
    let total = cert.total_pruned_certified.max(1);

    let spsf_pct   = ((cert.spsf_pruned_certified   * 100) / total).min(100) as u8;
    let health_pct = ((cert.health_pruned_certified  * 100) / total).min(100) as u8;
    let res_pct    = ((cert.resonance_pruned_certified * 100) / total).min(100) as u8;

    let mut bytes = [0u8; FRAME_SIZE];
    bytes[0..8].copy_from_slice(&cert.epoch_end.to_be_bytes());
    bytes[8..16].copy_from_slice(&cert.total_pruned_certified.to_be_bytes());
    bytes[16] = if cert.chains_valid { 0x01 } else { 0x00 };
    bytes[17] = spsf_pct;
    bytes[18] = health_pct;
    bytes[19] = res_pct;
    bytes[20..24].copy_from_slice(&cert.certificate_hash[0..4]);

    CompactionTelemetryFrame { bytes }
}

/// Decode a telemetry frame back to its constituent fields.
pub fn decode(frame: &CompactionTelemetryFrame)
    -> (u64, u64, bool, u8, u8, u8, [u8; 4])
{
    (
        frame.epoch_end(),
        frame.total_pruned(),
        frame.chains_valid(),
        frame.spsf_pct(),
        frame.health_pct(),
        frame.res_pct(),
        frame.cert_prefix(),
    )
}

// ─── CompactionTelemetryRecord ────────────────────────────────────────────────

#[derive(Debug, Clone, PartialEq)]
pub struct CompactionTelemetryRecord {
    pub epoch_end:    u64,
    pub frame:        [u8; FRAME_SIZE],
    pub record_hash:  [u8; 32],
    pub prev_hash:    [u8; 32],
}

fn compute_record_hash(
    prev:      &[u8; 32],
    frame:     &[u8; FRAME_SIZE],
    epoch_end: u64,
) -> [u8; 32] {
    let mut h = Sha256::new();
    h.update(prev);
    h.update(frame.as_slice());
    h.update(epoch_end.to_be_bytes());
    h.finalize().into()
}

// ─── CompactionTelemetryLog ───────────────────────────────────────────────────

pub struct CompactionTelemetryLog {
    records: Vec<CompactionTelemetryRecord>,
}

impl CompactionTelemetryLog {
    pub fn new() -> Self { Self { records: Vec::new() } }

    pub fn frame_count(&self) -> usize { self.records.len() }
    pub fn is_empty(&self)    -> bool  { self.records.is_empty() }
    pub fn records(&self)     -> &[CompactionTelemetryRecord] { &self.records }
    pub fn latest(&self)      -> Option<&CompactionTelemetryRecord> { self.records.last() }

    /// Encode a certificate and append the resulting frame to the log.
    pub fn record_frame(&mut self, cert: &CompactionAuditCertificate) -> CompactionTelemetryRecord {
        let frame = encode(cert);
        let prev  = self.records.last()
            .map(|r| r.record_hash)
            .unwrap_or(TELEMETRY_ENCODER_GENESIS_HASH);

        let record_hash = compute_record_hash(&prev, &frame.bytes, cert.epoch_end);

        let rec = CompactionTelemetryRecord {
            epoch_end:   cert.epoch_end,
            frame:       frame.bytes,
            record_hash,
            prev_hash:   prev,
        };
        self.records.push(rec.clone());
        rec
    }

    pub fn verify_chain(&self) -> (bool, Option<usize>) {
        let mut prev = TELEMETRY_ENCODER_GENESIS_HASH;
        for (i, r) in self.records.iter().enumerate() {
            if r.prev_hash != prev {
                return (false, Some(i));
            }
            let expected = compute_record_hash(&prev, &r.frame, r.epoch_end);
            if r.record_hash != expected {
                return (false, Some(i));
            }
            prev = r.record_hash;
        }
        (true, None)
    }
}

impl Default for CompactionTelemetryLog {
    fn default() -> Self { Self::new() }
}

// ─── Tests ────────────────────────────────────────────────────────────────────

#[cfg(test)]
mod tests {
    use super::*;
    use crate::compaction_epoch_seal::CompactionSealChain;
    use crate::compaction_audit_certifier::CertifierLog;

    fn build_cert(epoch_end: u64, spsf: u64, health: u64, resonance: u64) -> CompactionAuditCertificate {
        let mut chain = CompactionSealChain::new();
        for i in 1..=epoch_end {
            let mut uh = [0u8; 32];
            uh[0] = i as u8;
            chain.append(i, uh, spsf, health, resonance);
        }
        let (ok, _) = chain.verify_chain();
        let mut log = CertifierLog::new();
        log.certify_window(chain.seals(), 1, epoch_end, ok).clone()
    }

    // ── encode / decode ───────────────────────────────────────────────────────

    #[test]
    fn encode_epoch_end_roundtrip() {
        let c = build_cert(7, 50, 30, 20);
        let f = encode(&c);
        let (ep, _, _, _, _, _, _) = decode(&f);
        assert_eq!(ep, 7);
    }

    #[test]
    fn encode_total_pruned_roundtrip() {
        let c = build_cert(5, 40, 30, 30);
        let f = encode(&c);
        let (_, tp, _, _, _, _, _) = decode(&f);
        assert_eq!(tp, c.total_pruned_certified);
    }

    #[test]
    fn encode_chains_valid_true() {
        let c = build_cert(3, 10, 5, 5);
        let f = encode(&c);
        assert!(f.chains_valid());
    }

    #[test]
    fn encode_chains_invalid_byte() {
        // Build a cert with chains_valid=false by using certify_window directly
        let mut log = CertifierLog::new();
        let c = log.certify_window(&[], 0, 0, false).clone();
        let f = encode(&c);
        assert!(!f.chains_valid());
        assert_eq!(f.bytes[16], 0x00);
    }

    #[test]
    fn pct_fields_sum_approximately_100() {
        let c = build_cert(4, 60, 30, 10);
        let f = encode(&c);
        // spsf+health+res pct of 100 total: 60%, 30%, 10%
        assert_eq!(f.spsf_pct(), 60);
        assert_eq!(f.health_pct(), 30);
        assert_eq!(f.res_pct(), 10);
    }

    #[test]
    fn pct_fields_zero_when_total_zero() {
        let mut log = CertifierLog::new();
        let c = log.certify_window(&[], 0, 0, true).clone();
        let f = encode(&c);
        assert_eq!(f.spsf_pct(), 0);
        assert_eq!(f.health_pct(), 0);
        assert_eq!(f.res_pct(), 0);
    }

    #[test]
    fn cert_prefix_matches_certificate_hash() {
        let c = build_cert(2, 10, 5, 5);
        let f = encode(&c);
        assert_eq!(f.cert_prefix(), c.certificate_hash[0..4]);
    }

    #[test]
    fn frame_size_is_24() {
        let c = build_cert(1, 5, 3, 2);
        let f = encode(&c);
        assert_eq!(f.bytes.len(), FRAME_SIZE);
        assert_eq!(FRAME_SIZE, 24);
    }

    #[test]
    fn encode_deterministic() {
        let c = build_cert(3, 20, 15, 10);
        let f1 = encode(&c);
        let f2 = encode(&c);
        assert_eq!(f1.bytes, f2.bytes);
    }

    #[test]
    fn different_epochs_different_frames() {
        let c1 = build_cert(1, 10, 5, 5);
        let c2 = build_cert(2, 10, 5, 5);
        let f1 = encode(&c1);
        let f2 = encode(&c2);
        assert_ne!(f1.bytes, f2.bytes);
    }

    // ── CompactionTelemetryLog ────────────────────────────────────────────────

    #[test]
    fn log_starts_empty() {
        let l = CompactionTelemetryLog::new();
        assert!(l.is_empty());
        assert_eq!(l.frame_count(), 0);
        assert!(l.latest().is_none());
    }

    #[test]
    fn record_frame_appends() {
        let mut l = CompactionTelemetryLog::new();
        let c = build_cert(1, 5, 3, 2);
        let rec = l.record_frame(&c);
        assert_eq!(l.frame_count(), 1);
        assert_eq!(rec.epoch_end, 1);
        assert_eq!(rec.frame.len(), FRAME_SIZE);
    }

    #[test]
    fn prev_hash_links_correctly() {
        let mut l = CompactionTelemetryLog::new();
        let c1 = build_cert(1, 5, 3, 2);
        let c2 = build_cert(2, 8, 4, 3);
        let r1 = l.record_frame(&c1);
        let r2 = l.record_frame(&c2);
        assert_eq!(r2.prev_hash, r1.record_hash);
    }

    #[test]
    fn verify_chain_empty_ok() {
        let l = CompactionTelemetryLog::new();
        let (ok, idx) = l.verify_chain();
        assert!(ok);
        assert!(idx.is_none());
    }

    #[test]
    fn verify_chain_three_records_ok() {
        let mut l = CompactionTelemetryLog::new();
        for i in 1u64..=3 {
            let c = build_cert(i, i * 5, i * 3, i * 2);
            l.record_frame(&c);
        }
        let (ok, idx) = l.verify_chain();
        assert!(ok);
        assert!(idx.is_none());
    }

    #[test]
    fn verify_chain_detects_tamper() {
        let mut l = CompactionTelemetryLog::new();
        let c = build_cert(1, 5, 3, 2);
        l.record_frame(&c);
        l.records[0].record_hash[0] ^= 0xFF;
        let (ok, idx) = l.verify_chain();
        assert!(!ok);
        assert_eq!(idx, Some(0));
    }
}
