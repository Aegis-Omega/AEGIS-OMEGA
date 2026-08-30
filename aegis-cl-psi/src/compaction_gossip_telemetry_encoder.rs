//! Gate 359 — Compaction Gossip Telemetry Encoder (T2)
//! EPISTEMIC TIER: T2 (engineering hypothesis)
//!
//! Encodes a GossipAuditCertificate (Gate 358) into a compact 24-byte frame
//! suitable for peer gossip broadcast. Mirrors Gate 337 for the gossip subsystem.
//!
//! GossipTelemetryFrame (24 bytes):
//!   [0..8]   epoch_end         (u64 BE)
//!   [8..16]  total_delivered   (u64 BE)
//!   [16]     chains_valid      (0x01 = valid, 0x00 = invalid)
//!   [17]     red_pct           (u8, red_epochs * 100 / max(epoch_count, 1), sat. 100)
//!   [18]     yellow_pct        (u8, yellow_epochs * 100 / max(epoch_count, 1), sat. 100)
//!   [19]     green_pct         (u8, green_epochs * 100 / max(epoch_count, 1), sat. 100)
//!   [20..24] cert_hash_prefix  (first 4 bytes of certificate_hash)
//!
//! encode() → GossipTelemetryFrame
//! decode() → GossipTelemetryDecoded (all extracted fields)
//!
//! GossipTelemetryLog: hash-chained encode records.
//!   record_hash = SHA-256(prev[32] ‖ frame[24] ‖ epoch_end_be8)
//!   verify_chain(), frame_count(), latest().

use sha2::{Sha256, Digest};
use crate::compaction_gossip_audit_certifier::GossipAuditCertificate;

pub const GOSSIP_TELEMETRY_GENESIS_HASH: [u8; 32] = [0u8; 32];
pub const GOSSIP_FRAME_SIZE: usize = 24;

// ─── GossipTelemetryFrame ─────────────────────────────────────────────────────

#[derive(Debug, Clone, Copy, PartialEq)]
pub struct GossipTelemetryFrame {
    pub bytes: [u8; GOSSIP_FRAME_SIZE],
}

impl GossipTelemetryFrame {
    pub fn epoch_end(&self)       -> u64  { u64::from_be_bytes(self.bytes[0..8].try_into().unwrap()) }
    pub fn total_delivered(&self) -> u64  { u64::from_be_bytes(self.bytes[8..16].try_into().unwrap()) }
    pub fn chains_valid(&self)    -> bool { self.bytes[16] == 0x01 }
    pub fn red_pct(&self)         -> u8   { self.bytes[17] }
    pub fn yellow_pct(&self)      -> u8   { self.bytes[18] }
    pub fn green_pct(&self)       -> u8   { self.bytes[19] }
    pub fn cert_prefix(&self)     -> [u8; 4] { self.bytes[20..24].try_into().unwrap() }
}

// ─── encode / decode ──────────────────────────────────────────────────────────

pub fn encode(cert: &GossipAuditCertificate) -> GossipTelemetryFrame {
    let epoch_count = cert.epoch_count.max(1);
    let red_pct    = ((cert.red_epochs    as u64 * 100) / epoch_count).min(100) as u8;
    let yellow_pct = ((cert.yellow_epochs as u64 * 100) / epoch_count).min(100) as u8;
    let green_pct  = ((cert.green_epochs  as u64 * 100) / epoch_count).min(100) as u8;

    let mut bytes = [0u8; GOSSIP_FRAME_SIZE];
    bytes[0..8].copy_from_slice(&cert.epoch_end.to_be_bytes());
    bytes[8..16].copy_from_slice(&cert.total_delivered.to_be_bytes());
    bytes[16] = cert.chains_valid as u8;
    bytes[17] = red_pct;
    bytes[18] = yellow_pct;
    bytes[19] = green_pct;
    bytes[20..24].copy_from_slice(&cert.certificate_hash[..4]);
    GossipTelemetryFrame { bytes }
}

#[derive(Debug, Clone, Copy, PartialEq)]
pub struct GossipTelemetryDecoded {
    pub epoch_end:       u64,
    pub total_delivered: u64,
    pub chains_valid:    bool,
    pub red_pct:         u8,
    pub yellow_pct:      u8,
    pub green_pct:       u8,
    pub cert_prefix:     [u8; 4],
}

pub fn decode(frame: &GossipTelemetryFrame) -> GossipTelemetryDecoded {
    GossipTelemetryDecoded {
        epoch_end:       frame.epoch_end(),
        total_delivered: frame.total_delivered(),
        chains_valid:    frame.chains_valid(),
        red_pct:         frame.red_pct(),
        yellow_pct:      frame.yellow_pct(),
        green_pct:       frame.green_pct(),
        cert_prefix:     frame.cert_prefix(),
    }
}

// ─── GossipTelemetryLog ───────────────────────────────────────────────────────

#[derive(Debug, Clone, PartialEq)]
pub struct GossipTelemetryRecord {
    pub frame:       GossipTelemetryFrame,
    pub prev_hash:   [u8; 32],
    pub record_hash: [u8; 32],
}

fn compute_record_hash(prev: &[u8; 32], frame: &GossipTelemetryFrame) -> [u8; 32] {
    let mut h = Sha256::new();
    h.update(prev);
    h.update(frame.bytes);
    h.update(frame.epoch_end().to_be_bytes());
    h.finalize().into()
}

pub struct GossipTelemetryLog {
    records: Vec<GossipTelemetryRecord>,
}

impl GossipTelemetryLog {
    pub fn new() -> Self { Self { records: Vec::new() } }

    pub fn frame_count(&self) -> usize { self.records.len() }
    pub fn is_empty(&self)    -> bool  { self.records.is_empty() }
    pub fn records(&self)     -> &[GossipTelemetryRecord] { &self.records }
    pub fn latest(&self)      -> Option<&GossipTelemetryRecord> { self.records.last() }

    pub fn push(&mut self, frame: GossipTelemetryFrame) -> &GossipTelemetryRecord {
        let prev = self.records.last()
            .map(|r| r.record_hash)
            .unwrap_or(GOSSIP_TELEMETRY_GENESIS_HASH);
        let record_hash = compute_record_hash(&prev, &frame);
        self.records.push(GossipTelemetryRecord { frame, prev_hash: prev, record_hash });
        self.records.last().unwrap()
    }

    pub fn verify_chain(&self) -> (bool, Option<usize>) {
        let mut prev = GOSSIP_TELEMETRY_GENESIS_HASH;
        for (i, r) in self.records.iter().enumerate() {
            if r.prev_hash != prev { return (false, Some(i)); }
            let expected = compute_record_hash(&prev, &r.frame);
            if r.record_hash != expected { return (false, Some(i)); }
            prev = r.record_hash;
        }
        (true, None)
    }
}

impl Default for GossipTelemetryLog {
    fn default() -> Self { Self::new() }
}

// ─── Tests ────────────────────────────────────────────────────────────────────

#[cfg(test)]
mod tests {
    use super::*;
    use crate::compaction_gossip_epoch_seal::GossipEpochSealChain;
    use crate::compaction_gossip_audit_certifier::GossipCertifierLog;

    fn make_cert(red: u32, yellow: u32, green: u32, delivered: u64) -> GossipAuditCertificate {
        let mut chain = GossipEpochSealChain::new();
        let n = (red + yellow + green) as u64;
        for i in 1..=n.max(1) {
            chain.append(i, [0xAAu8; 32], [0xBBu8; 32], delivered, 0, red, yellow, green);
        }
        let mut log = GossipCertifierLog::new();
        let (valid, _) = chain.verify_chain();
        let seals = chain.seals();
        let start = seals.first().map(|s| s.epoch).unwrap_or(0);
        let end   = seals.last().map(|s| s.epoch).unwrap_or(0);
        log.certify_window(seals, start, end, valid, chain.terminal_hash());
        log.certs()[0].clone()
    }

    // ── encode ────────────────────────────────────────────────────────────────

    #[test]
    fn encode_epoch_end_roundtrips() {
        let cert = make_cert(0, 0, 5, 100);
        let frame = encode(&cert);
        assert_eq!(frame.epoch_end(), cert.epoch_end);
    }

    #[test]
    fn encode_total_delivered_roundtrips() {
        let cert = make_cert(0, 0, 3, 250);
        let frame = encode(&cert);
        // total_delivered is summed across seals in certify_window
        assert_eq!(frame.total_delivered(), cert.total_delivered);
    }

    #[test]
    fn encode_chains_valid_true() {
        let cert = make_cert(0, 0, 4, 100);
        let frame = encode(&cert);
        assert!(frame.chains_valid());
    }

    #[test]
    fn encode_chains_valid_false() {
        let chain = GossipEpochSealChain::new();
        let mut log = GossipCertifierLog::new();
        let seals: &[_] = &[];
        log.certify_window(seals, 0, 0, false, [0u8; 32]);
        let cert = log.certs()[0].clone();
        let frame = encode(&cert);
        assert!(!frame.chains_valid());
    }

    #[test]
    fn cert_prefix_matches() {
        let cert = make_cert(1, 2, 7, 100);
        let frame = encode(&cert);
        assert_eq!(frame.cert_prefix(), cert.certificate_hash[..4]);
    }

    #[test]
    fn green_pct_all_green() {
        // epoch_count=1, green_epochs=1 → green_pct=100
        let cert = make_cert(0, 0, 1, 100);
        let frame = encode(&cert);
        assert_eq!(frame.green_pct(), 100);
    }

    #[test]
    fn red_pct_saturates_at_100() {
        let cert = make_cert(5, 0, 0, 100);
        let frame = encode(&cert);
        assert!(frame.red_pct() <= 100);
    }

    #[test]
    fn encode_deterministic() {
        let cert = make_cert(1, 2, 3, 500);
        let f1 = encode(&cert);
        let f2 = encode(&cert);
        assert_eq!(f1, f2);
    }

    // ── decode ────────────────────────────────────────────────────────────────

    #[test]
    fn decode_roundtrips_all_fields() {
        let cert = make_cert(1, 2, 7, 300);
        let frame = encode(&cert);
        let d = decode(&frame);
        assert_eq!(d.epoch_end,       frame.epoch_end());
        assert_eq!(d.total_delivered, frame.total_delivered());
        assert_eq!(d.chains_valid,    frame.chains_valid());
        assert_eq!(d.red_pct,         frame.red_pct());
        assert_eq!(d.yellow_pct,      frame.yellow_pct());
        assert_eq!(d.green_pct,       frame.green_pct());
        assert_eq!(d.cert_prefix,     frame.cert_prefix());
    }

    // ── log ───────────────────────────────────────────────────────────────────

    #[test]
    fn log_empty_ok() {
        let log = GossipTelemetryLog::new();
        assert!(log.is_empty());
        let (ok, idx) = log.verify_chain();
        assert!(ok);
        assert!(idx.is_none());
    }

    #[test]
    fn log_first_prev_is_genesis() {
        let mut log = GossipTelemetryLog::new();
        let frame = encode(&make_cert(0, 0, 1, 100));
        let r = log.push(frame);
        assert_eq!(r.prev_hash, GOSSIP_TELEMETRY_GENESIS_HASH);
    }

    #[test]
    fn log_record_hash_nonzero() {
        let mut log = GossipTelemetryLog::new();
        let frame = encode(&make_cert(0, 1, 2, 50));
        let r = log.push(frame);
        assert_ne!(r.record_hash, [0u8; 32]);
    }

    #[test]
    fn log_verify_chain_three_ok() {
        let mut log = GossipTelemetryLog::new();
        for i in 0..3u32 {
            log.push(encode(&make_cert(i, i, i + 1, 100)));
        }
        let (ok, idx) = log.verify_chain();
        assert!(ok);
        assert!(idx.is_none());
    }

    #[test]
    fn log_verify_chain_detects_tamper() {
        let mut log = GossipTelemetryLog::new();
        for i in 0..3u32 {
            log.push(encode(&make_cert(i, i, i + 1, 100)));
        }
        log.records[0].record_hash[0] ^= 0xFF;
        let (ok, idx) = log.verify_chain();
        assert!(!ok);
        assert_eq!(idx, Some(0));
    }

    #[test]
    fn log_frame_count() {
        let mut log = GossipTelemetryLog::new();
        assert_eq!(log.frame_count(), 0);
        log.push(encode(&make_cert(0, 0, 1, 10)));
        log.push(encode(&make_cert(0, 1, 0, 20)));
        assert_eq!(log.frame_count(), 2);
    }
}
