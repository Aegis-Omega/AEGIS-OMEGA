//! Gate 267 — Health Ticker: epoch-by-epoch condensed health signal (T2)
//! EPISTEMIC TIER: T2 (engineering hypothesis)
//!
//! Produces a compact 3-byte TickerFrame encoding the constitutional health state
//! of the mesh at each epoch. Designed for low-overhead gossip broadcast.
//!
//! TickerFrame (3 bytes):
//!   [0] — quorum_level (0=Healthy, 1=AtThreshold, 2=BelowQuorum, 3=NoNodes)
//!   [1] — health_pct   (0..100, from CensusRecord.health_ratio_pct)
//!   [2] — fault_byte   (fault_class in high nibble, recovery_action_kind in low nibble)
//!         fault_class:   bits 7:4 (FaultClass as u8)
//!         top_action:    bits 3:0 (RecoveryActionKind as u8, or 0xFF if no actions)
//!
//! TickerRecord:
//!   epoch        — u64
//!   frame        — TickerFrame
//!   ticker_hash  — SHA-256(prev_hash ‖ epoch_be8 ‖ frame[3])
//!   prev_hash    — [u8; 32]
//!
//! TickerLog: hash-chained TickerRecords; healthy_count(), alert_count(), verify_chain().

use sha2::{Sha256, Digest};
use crate::quorum_guard::QuorumLevel;
use crate::fault_detector::FaultClass;
use crate::recovery_planner::RecoveryActionKind;

// ─── Ticker frame ─────────────────────────────────────────────────────────────

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub struct TickerFrame(pub [u8; 3]);

impl TickerFrame {
    pub fn quorum_level(self) -> QuorumLevel {
        match self.0[0] {
            0 => QuorumLevel::Healthy,
            1 => QuorumLevel::AtThreshold,
            2 => QuorumLevel::BelowQuorum,
            _ => QuorumLevel::NoNodes,
        }
    }

    pub fn health_pct(self) -> u8 { self.0[1] }

    pub fn fault_class(self) -> FaultClass {
        match self.0[2] >> 4 {
            0 => FaultClass::None,
            1 => FaultClass::Isolated,
            2 => FaultClass::Correlated,
            _ => FaultClass::Cascading,
        }
    }

    pub fn top_action_kind(self) -> Option<RecoveryActionKind> {
        let nibble = self.0[2] & 0x0F;
        match nibble {
            0 => Some(RecoveryActionKind::MonitorOnly),
            1 => Some(RecoveryActionKind::IsolateNode),
            2 => Some(RecoveryActionKind::RestartNode),
            3 => Some(RecoveryActionKind::ReduceLoad),
            4 => Some(RecoveryActionKind::ActivateSpare),
            5 => Some(RecoveryActionKind::PartialQuorumMode),
            6 => Some(RecoveryActionKind::HaltAndReform),
            _ => None, // 0xF = no action
        }
    }

    pub fn is_healthy(self) -> bool {
        self.quorum_level().is_quorum_met() && self.fault_class() == FaultClass::None
    }

    pub fn as_bytes(self) -> [u8; 3] { self.0 }
}

/// Build a TickerFrame from its components.
pub fn build_ticker_frame(
    quorum_level: QuorumLevel,
    health_pct:   u8,
    fault_class:  FaultClass,
    top_action:   Option<RecoveryActionKind>,
) -> TickerFrame {
    let fault_nibble  = (fault_class.as_u8() & 0x0F) << 4;
    let action_nibble = match top_action {
        Some(k) => k.as_u8() & 0x0F,
        None    => 0x0F,
    };
    TickerFrame([
        quorum_level.as_u8(),
        health_pct,
        fault_nibble | action_nibble,
    ])
}

// ─── Ticker record ────────────────────────────────────────────────────────────

#[derive(Debug, Clone, PartialEq)]
pub struct TickerRecord {
    pub epoch:       u64,
    pub frame:       TickerFrame,
    pub ticker_hash: [u8; 32],
    pub prev_hash:   [u8; 32],
}

pub const TICKER_GENESIS_HASH: [u8; 32] = [0u8; 32];

fn compute_ticker_hash(
    epoch: u64,
    frame: &TickerFrame,
    prev:  &[u8; 32],
) -> [u8; 32] {
    let mut h = Sha256::new();
    h.update(prev);
    h.update(epoch.to_be_bytes());
    h.update(frame.0);
    h.finalize().into()
}

// ─── Ticker log ───────────────────────────────────────────────────────────────

#[derive(Debug, Clone)]
pub struct TickerLog {
    records: Vec<TickerRecord>,
}

#[derive(Debug)]
pub enum TickerError {
    StaleEpoch,
}

impl TickerError {
    pub fn as_str(&self) -> &'static str { "stale epoch" }
}

impl TickerLog {
    pub fn new() -> Self { Self { records: Vec::new() } }

    pub fn len(&self) -> usize { self.records.len() }
    pub fn is_empty(&self) -> bool { self.records.is_empty() }
    pub fn records(&self) -> &[TickerRecord] { &self.records }
    pub fn latest(&self) -> Option<&TickerRecord> { self.records.last() }

    pub fn last_hash(&self) -> [u8; 32] {
        self.records.last().map(|r| r.ticker_hash).unwrap_or(TICKER_GENESIS_HASH)
    }

    pub fn append(
        &mut self,
        epoch: u64,
        frame: TickerFrame,
    ) -> Result<&TickerRecord, TickerError> {
        if let Some(last) = self.records.last() {
            if epoch <= last.epoch {
                return Err(TickerError::StaleEpoch);
            }
        }
        let prev_hash   = self.last_hash();
        let ticker_hash = compute_ticker_hash(epoch, &frame, &prev_hash);
        self.records.push(TickerRecord { epoch, frame, ticker_hash, prev_hash });
        Ok(self.records.last().unwrap())
    }

    /// Count of epochs where the mesh is fully healthy (quorum met + no fault).
    pub fn healthy_count(&self) -> usize {
        self.records.iter().filter(|r| r.frame.is_healthy()).count()
    }

    /// Count of epochs with quorum alerts.
    pub fn alert_count(&self) -> usize {
        self.records.iter().filter(|r| r.frame.quorum_level().requires_alert()).count()
    }

    pub fn verify_chain(&self) -> (bool, Option<usize>) {
        let mut expected_prev = TICKER_GENESIS_HASH;
        for (i, rec) in self.records.iter().enumerate() {
            if rec.prev_hash != expected_prev {
                return (false, Some(i));
            }
            let recomputed = compute_ticker_hash(rec.epoch, &rec.frame, &rec.prev_hash);
            if recomputed != rec.ticker_hash {
                return (false, Some(i));
            }
            expected_prev = rec.ticker_hash;
        }
        (true, None)
    }
}

impl Default for TickerLog {
    fn default() -> Self { Self::new() }
}

// ─── Tests ───────────────────────────────────────────────────────────────────

#[cfg(test)]
mod tests {
    use super::*;

    fn healthy_frame() -> TickerFrame {
        build_ticker_frame(
            QuorumLevel::Healthy, 85, FaultClass::None,
            Some(RecoveryActionKind::MonitorOnly),
        )
    }

    fn alert_frame() -> TickerFrame {
        build_ticker_frame(
            QuorumLevel::BelowQuorum, 40, FaultClass::Cascading,
            Some(RecoveryActionKind::HaltAndReform),
        )
    }

    // ── TickerFrame encoding ───────────────────────────────────────────────────

    #[test]
    fn healthy_frame_roundtrip() {
        let f = healthy_frame();
        assert_eq!(f.quorum_level(), QuorumLevel::Healthy);
        assert_eq!(f.health_pct(), 85);
        assert_eq!(f.fault_class(), FaultClass::None);
        assert_eq!(f.top_action_kind(), Some(RecoveryActionKind::MonitorOnly));
    }

    #[test]
    fn alert_frame_roundtrip() {
        let f = alert_frame();
        assert_eq!(f.quorum_level(), QuorumLevel::BelowQuorum);
        assert_eq!(f.health_pct(), 40);
        assert_eq!(f.fault_class(), FaultClass::Cascading);
        assert_eq!(f.top_action_kind(), Some(RecoveryActionKind::HaltAndReform));
    }

    #[test]
    fn no_action_encodes_none() {
        let f = build_ticker_frame(QuorumLevel::Healthy, 100, FaultClass::None, None);
        assert_eq!(f.top_action_kind(), None);
    }

    #[test]
    fn is_healthy_true() {
        assert!(healthy_frame().is_healthy());
    }

    #[test]
    fn is_healthy_false_on_fault() {
        let f = build_ticker_frame(
            QuorumLevel::Healthy, 80, FaultClass::Isolated,
            Some(RecoveryActionKind::RestartNode),
        );
        assert!(!f.is_healthy());
    }

    #[test]
    fn is_healthy_false_on_below_quorum() {
        assert!(!alert_frame().is_healthy());
    }

    #[test]
    fn at_threshold_quorum_met() {
        let f = build_ticker_frame(
            QuorumLevel::AtThreshold, 62, FaultClass::None,
            Some(RecoveryActionKind::MonitorOnly),
        );
        assert!(f.quorum_level().is_quorum_met());
        assert!(f.is_healthy());
    }

    #[test]
    fn frame_bytes_3_bytes() {
        let f = healthy_frame();
        assert_eq!(f.as_bytes().len(), 3);
    }

    // ── TickerLog ──────────────────────────────────────────────────────────────

    #[test]
    fn new_log_empty() {
        let l = TickerLog::new();
        assert!(l.is_empty());
        assert_eq!(l.last_hash(), TICKER_GENESIS_HASH);
        assert_eq!(l.healthy_count(), 0);
        assert_eq!(l.alert_count(), 0);
    }

    #[test]
    fn append_sequential() {
        let mut l = TickerLog::new();
        l.append(1, healthy_frame()).unwrap();
        l.append(2, healthy_frame()).unwrap();
        assert_eq!(l.len(), 2);
    }

    #[test]
    fn stale_epoch_rejected() {
        let mut l = TickerLog::new();
        l.append(5, healthy_frame()).unwrap();
        assert!(matches!(l.append(5, healthy_frame()), Err(TickerError::StaleEpoch)));
        assert!(matches!(l.append(4, healthy_frame()), Err(TickerError::StaleEpoch)));
    }

    #[test]
    fn healthy_count_tracked() {
        let mut l = TickerLog::new();
        l.append(1, healthy_frame()).unwrap();
        l.append(2, alert_frame()).unwrap();
        l.append(3, healthy_frame()).unwrap();
        assert_eq!(l.healthy_count(), 2);
    }

    #[test]
    fn alert_count_tracked() {
        let mut l = TickerLog::new();
        l.append(1, healthy_frame()).unwrap();
        l.append(2, alert_frame()).unwrap();
        l.append(3, alert_frame()).unwrap();
        assert_eq!(l.alert_count(), 2);
    }

    #[test]
    fn ticker_hash_nonzero() {
        let mut l = TickerLog::new();
        let r = l.append(1, healthy_frame()).unwrap();
        assert_ne!(r.ticker_hash, [0u8; 32]);
    }

    #[test]
    fn ticker_hash_deterministic() {
        let mut l1 = TickerLog::new();
        let mut l2 = TickerLog::new();
        let r1 = l1.append(1, healthy_frame()).unwrap();
        let r2 = l2.append(1, healthy_frame()).unwrap();
        assert_eq!(r1.ticker_hash, r2.ticker_hash);
    }

    #[test]
    fn verify_chain_valid() {
        let mut l = TickerLog::new();
        for e in 1..=5u64 {
            l.append(e, healthy_frame()).unwrap();
        }
        let (valid, broken) = l.verify_chain();
        assert!(valid);
        assert!(broken.is_none());
    }
}
