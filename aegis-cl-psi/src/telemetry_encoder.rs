//! Gate 254 — Constitutional Telemetry Encoder: 32-byte gossip packet (T2)
//! EPISTEMIC TIER: T2 (engineering hypothesis)
//!
//! Encodes a DashboardFrame into a compact 32-byte TelemetryPacket for gossip
//! broadcast. Deterministic encode/decode. SHA-256 of the 24 data bytes gives
//! the last 8 bytes (packet_checksum truncated to 8 bytes).
//!
//! TelemetryPacket layout (32 bytes):
//!   [0..8]   epoch as u64 big-endian
//!   [8]      OverallCondition as u8 (0–4)
//!   [9]      OverallTrend as u8 (0–3)
//!   [10]     AlertSeverity as u8 (0–4)
//!   [11]     ConstitutionalPhase as u8 (0–3)
//!   [12]     MomentumDir as u8 (0–2)
//!   [13]     degraded_count (0–6)
//!   [14..16] momentum_int as i16 big-endian (clamped to i16::MIN..=i16::MAX)
//!   [16..24] SHA-256(bytes[0..16])[:8] — packet integrity check
//!   [24..32] frame_hash[:8] — first 8 bytes of DashboardFrame.frame_hash
//!
//! TelemetryPacket is 32 bytes; encode() is O(1); decode() is O(1).
//! Decode cannot recover full frame_hash but validates integrity via checksum.

use sha2::{Sha256, Digest};
use crate::health_dashboard::{DashboardFrame, OverallTrend};
use crate::health_aggregator::OverallCondition;
use crate::alert_engine::AlertSeverity;
use crate::phase_transition::ConstitutionalPhase;
use crate::momentum_tracker::MomentumDir;

// ─── Telemetry packet ─────────────────────────────────────────────────────────

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub struct TelemetryPacket(pub [u8; 32]);

impl TelemetryPacket {
    pub fn as_bytes(&self) -> &[u8; 32] { &self.0 }

    pub fn epoch(&self) -> u64 {
        u64::from_be_bytes(self.0[0..8].try_into().unwrap())
    }

    pub fn condition(&self) -> Option<OverallCondition> {
        decode_condition(self.0[8])
    }

    pub fn trend(&self) -> Option<OverallTrend> {
        decode_trend(self.0[9])
    }

    pub fn severity(&self) -> Option<AlertSeverity> {
        decode_severity(self.0[10])
    }

    pub fn phase(&self) -> Option<ConstitutionalPhase> {
        decode_phase(self.0[11])
    }

    pub fn momentum_dir(&self) -> Option<MomentumDir> {
        decode_momentum_dir(self.0[12])
    }

    pub fn degraded_count(&self) -> u8 { self.0[13] }

    pub fn momentum_int_clamped(&self) -> i16 {
        i16::from_be_bytes(self.0[14..16].try_into().unwrap())
    }

    /// Verify the 8-byte inline checksum matches SHA-256(bytes[0..16])[:8].
    pub fn is_checksum_valid(&self) -> bool {
        let expected = packet_checksum(&self.0[0..16]);
        self.0[16..24] == expected
    }

    /// First 8 bytes of the originating DashboardFrame.frame_hash.
    pub fn frame_hash_prefix(&self) -> [u8; 8] {
        self.0[24..32].try_into().unwrap()
    }
}

fn packet_checksum(data: &[u8]) -> [u8; 8] {
    let digest = Sha256::digest(data);
    digest[0..8].try_into().unwrap()
}

// ─── Encode ───────────────────────────────────────────────────────────────────

pub fn encode(frame: &DashboardFrame, severity: AlertSeverity) -> TelemetryPacket {
    let mut buf = [0u8; 32];

    // [0..8] epoch
    buf[0..8].copy_from_slice(&frame.epoch.to_be_bytes());
    // [8] condition
    buf[8]  = frame.vector.condition.as_u8();
    // [9] trend
    buf[9]  = frame.overall_trend.as_u8();
    // [10] severity
    buf[10] = severity.as_u8();
    // [11] phase
    buf[11] = frame.phase.as_u8();
    // [12] momentum_dir
    buf[12] = frame.momentum_dir.as_u8();
    // [13] degraded_count
    buf[13] = frame.vector.degraded_count;
    // [14..16] momentum_int clamped to i16
    let clamped = frame.momentum_int.clamp(i16::MIN as i64, i16::MAX as i64) as i16;
    buf[14..16].copy_from_slice(&clamped.to_be_bytes());
    // [16..24] checksum of first 16 bytes
    let checksum = packet_checksum(&buf[0..16]);
    buf[16..24].copy_from_slice(&checksum);
    // [24..32] first 8 bytes of frame_hash
    buf[24..32].copy_from_slice(&frame.frame_hash[0..8]);

    TelemetryPacket(buf)
}

// ─── Decode helpers ───────────────────────────────────────────────────────────

fn decode_condition(b: u8) -> Option<OverallCondition> {
    match b {
        0 => Some(OverallCondition::Optimal),
        1 => Some(OverallCondition::Good),
        2 => Some(OverallCondition::Caution),
        3 => Some(OverallCondition::Alert),
        4 => Some(OverallCondition::Emergency),
        _ => None,
    }
}

fn decode_trend(b: u8) -> Option<OverallTrend> {
    match b {
        0 => Some(OverallTrend::Thriving),
        1 => Some(OverallTrend::Stable),
        2 => Some(OverallTrend::Concerning),
        3 => Some(OverallTrend::Critical),
        _ => None,
    }
}

fn decode_severity(b: u8) -> Option<AlertSeverity> {
    match b {
        0 => Some(AlertSeverity::None),
        1 => Some(AlertSeverity::Info),
        2 => Some(AlertSeverity::Warn),
        3 => Some(AlertSeverity::Critical),
        4 => Some(AlertSeverity::Emergency),
        _ => None,
    }
}

fn decode_phase(b: u8) -> Option<ConstitutionalPhase> {
    match b {
        0 => Some(ConstitutionalPhase::Nominal),
        1 => Some(ConstitutionalPhase::Degraded),
        2 => Some(ConstitutionalPhase::Recovery),
        3 => Some(ConstitutionalPhase::Critical),
        _ => None,
    }
}

fn decode_momentum_dir(b: u8) -> Option<MomentumDir> {
    match b {
        0 => Some(MomentumDir::Improving),
        1 => Some(MomentumDir::Stable),
        2 => Some(MomentumDir::Declining),
        _ => None,
    }
}

#[derive(Debug)]
pub struct EncoderError(pub &'static str);

// ─── Tests ───────────────────────────────────────────────────────────────────

#[cfg(test)]
mod tests {
    use super::*;
    use crate::health_aggregator::{build_vector, VECTOR_GENESIS_HASH};
    use crate::health_dashboard::{build_frame, DASHBOARD_GENESIS_HASH};
    use crate::swarm_health::HealthVerdict;
    use crate::resilience_watchdog::ResilienceVerdict;
    use crate::constitutional_pulse::PulseVerdict;
    use crate::coherence_stability::StabilityGrade;

    fn good_frame() -> DashboardFrame {
        let v = build_vector(7,
            HealthVerdict::Pass, ResilienceVerdict::Stable,
            PulseVerdict::Green, StabilityGrade::A,
            MomentumDir::Improving, ConstitutionalPhase::Nominal,
            &VECTOR_GENESIS_HASH);
        build_frame(7, v, ConstitutionalPhase::Nominal,
                    MomentumDir::Improving, 15, &DASHBOARD_GENESIS_HASH)
    }

    fn emergency_frame() -> DashboardFrame {
        let v = build_vector(3,
            HealthVerdict::Fail, ResilienceVerdict::Oscillating,
            PulseVerdict::Red, StabilityGrade::F,
            MomentumDir::Declining, ConstitutionalPhase::Critical,
            &VECTOR_GENESIS_HASH);
        build_frame(3, v, ConstitutionalPhase::Critical,
                    MomentumDir::Declining, -500, &DASHBOARD_GENESIS_HASH)
    }

    // ── encode ────────────────────────────────────────────────────────────────

    #[test]
    fn packet_is_32_bytes() {
        let p = encode(&good_frame(), AlertSeverity::None);
        assert_eq!(p.as_bytes().len(), 32);
    }

    #[test]
    fn epoch_roundtrips() {
        let p = encode(&good_frame(), AlertSeverity::None);
        assert_eq!(p.epoch(), 7);
    }

    #[test]
    fn condition_roundtrips() {
        let p = encode(&good_frame(), AlertSeverity::None);
        assert_eq!(p.condition(), Some(OverallCondition::Optimal));
    }

    #[test]
    fn trend_roundtrips() {
        let p = encode(&good_frame(), AlertSeverity::None);
        assert_eq!(p.trend(), Some(OverallTrend::Thriving));
    }

    #[test]
    fn severity_roundtrips() {
        let p = encode(&good_frame(), AlertSeverity::Info);
        assert_eq!(p.severity(), Some(AlertSeverity::Info));
    }

    #[test]
    fn phase_roundtrips() {
        let p = encode(&good_frame(), AlertSeverity::None);
        assert_eq!(p.phase(), Some(ConstitutionalPhase::Nominal));
    }

    #[test]
    fn momentum_dir_roundtrips() {
        let p = encode(&good_frame(), AlertSeverity::None);
        assert_eq!(p.momentum_dir(), Some(MomentumDir::Improving));
    }

    #[test]
    fn degraded_count_roundtrips() {
        let p = encode(&good_frame(), AlertSeverity::None);
        assert_eq!(p.degraded_count(), 0); // all optimal
    }

    #[test]
    fn momentum_int_clamped_roundtrips() {
        let p = encode(&good_frame(), AlertSeverity::None);
        assert_eq!(p.momentum_int_clamped(), 15);
    }

    #[test]
    fn large_momentum_int_clamped_to_i16() {
        let p = encode(&emergency_frame(), AlertSeverity::Emergency);
        // -500 fits in i16 (-32768..=32767)
        assert_eq!(p.momentum_int_clamped(), -500);
    }

    #[test]
    fn checksum_valid_for_good_frame() {
        let p = encode(&good_frame(), AlertSeverity::None);
        assert!(p.is_checksum_valid());
    }

    #[test]
    fn checksum_valid_for_emergency_frame() {
        let p = encode(&emergency_frame(), AlertSeverity::Emergency);
        assert!(p.is_checksum_valid());
    }

    #[test]
    fn frame_hash_prefix_matches() {
        let f = good_frame();
        let expected: [u8; 8] = f.frame_hash[0..8].try_into().unwrap();
        let p = encode(&f, AlertSeverity::None);
        assert_eq!(p.frame_hash_prefix(), expected);
    }

    #[test]
    fn encode_is_deterministic() {
        let f1 = good_frame();
        let f2 = good_frame();
        let f3 = good_frame();
        let p1 = encode(&f1, AlertSeverity::None);
        let p2 = encode(&f2, AlertSeverity::None);
        let p3 = encode(&f3, AlertSeverity::None);
        assert_eq!(p1, p2);
        assert_eq!(p2, p3);
    }

    #[test]
    fn different_severity_different_packet() {
        let f1 = good_frame();
        let f2 = good_frame();
        let p1 = encode(&f1, AlertSeverity::None);
        let p2 = encode(&f2, AlertSeverity::Emergency);
        assert_ne!(p1, p2);
    }

    #[test]
    fn tampered_checksum_detected() {
        let mut p = encode(&good_frame(), AlertSeverity::None);
        p.0[16] ^= 0xFF; // flip bits in checksum area
        assert!(!p.is_checksum_valid());
    }

    #[test]
    fn emergency_condition_encoded() {
        let p = encode(&emergency_frame(), AlertSeverity::Emergency);
        assert_eq!(p.condition(), Some(OverallCondition::Emergency));
        assert_eq!(p.trend(), Some(OverallTrend::Critical));
        assert_eq!(p.severity(), Some(AlertSeverity::Emergency));
    }

    #[test]
    fn decode_out_of_range_gives_none() {
        assert_eq!(decode_condition(99), None);
        assert_eq!(decode_trend(99), None);
        assert_eq!(decode_severity(99), None);
        assert_eq!(decode_phase(99), None);
        assert_eq!(decode_momentum_dir(99), None);
    }
}
