//! Gate 266 — Quorum Guard: real-time quorum health monitoring with alert levels (T2)
//! EPISTEMIC TIER: T2 (engineering hypothesis)
//!
//! Tracks quorum health epoch-by-epoch from TopologySnapshot + CensusRecord data.
//! Produces a QuorumStatus record with alert level and quorum delta.
//!
//! QuorumLevel:
//!   Healthy      — quorum firmly above 1/φ (≥ 70% operational)
//!   AtThreshold  — quorum near 1/φ (≥ 61.8% < 70%)
//!   BelowQuorum  — quorum below 1/φ but non-zero
//!   NoNodes      — zero nodes in mesh
//!
//! QuorumStatus:
//!   epoch              — u64
//!   total_nodes        — usize
//!   operational_nodes  — usize
//!   quorum_level       — QuorumLevel
//!   quorum_pct         — u8 (operational * 100 / total, or 0)
//!   quorum_delta       — i16 (quorum_pct change from previous status, signed)
//!   status_hash        — SHA-256(epoch_be8 ‖ total_be8 ‖ operational_be8 ‖ level_byte ‖ prev_hash)
//!   prev_hash          — [u8; 32]
//!
//! QuorumGuard: hash-chained QuorumStatus records. alert_epochs(), longest_outage().

use sha2::{Sha256, Digest};

// ─── Quorum level ─────────────────────────────────────────────────────────────

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum QuorumLevel {
    Healthy     = 0,
    AtThreshold = 1,
    BelowQuorum = 2,
    NoNodes     = 3,
}

impl QuorumLevel {
    pub fn as_u8(self) -> u8 { self as u8 }

    pub fn as_str(self) -> &'static str {
        match self {
            Self::Healthy     => "healthy",
            Self::AtThreshold => "at_threshold",
            Self::BelowQuorum => "below_quorum",
            Self::NoNodes     => "no_nodes",
        }
    }

    pub fn is_quorum_met(self) -> bool {
        matches!(self, Self::Healthy | Self::AtThreshold)
    }

    pub fn requires_alert(self) -> bool {
        matches!(self, Self::BelowQuorum | Self::NoNodes)
    }
}

fn classify_quorum(total: usize, operational: usize) -> QuorumLevel {
    if total == 0 { return QuorumLevel::NoNodes; }
    // Healthy ≥ 70% (700_000/1_000_000)
    if operational * 1_000_000 >= total * 700_000 {
        return QuorumLevel::Healthy;
    }
    // AtThreshold ≥ 1/φ (618_034/1_000_000)
    if operational * 1_000_000 >= total * 618_034 {
        return QuorumLevel::AtThreshold;
    }
    QuorumLevel::BelowQuorum
}

// ─── Quorum status ────────────────────────────────────────────────────────────

#[derive(Debug, Clone, PartialEq)]
pub struct QuorumStatus {
    pub epoch:             u64,
    pub total_nodes:       usize,
    pub operational_nodes: usize,
    pub quorum_level:      QuorumLevel,
    pub quorum_pct:        u8,
    pub quorum_delta:      i16,  // signed difference from previous quorum_pct
    pub status_hash:       [u8; 32],
    pub prev_hash:         [u8; 32],
}

pub const QUORUM_GENESIS_HASH: [u8; 32] = [0u8; 32];

fn compute_status_hash(
    epoch:       u64,
    total:       usize,
    operational: usize,
    level:       QuorumLevel,
    prev:        &[u8; 32],
) -> [u8; 32] {
    let mut h = Sha256::new();
    h.update(prev);
    h.update(epoch.to_be_bytes());
    h.update((total       as u64).to_be_bytes());
    h.update((operational as u64).to_be_bytes());
    h.update([level.as_u8()]);
    h.finalize().into()
}

pub fn build_status(
    epoch:       u64,
    total:       usize,
    operational: usize,
    prev_pct:    u8,
    prev_hash:   &[u8; 32],
) -> QuorumStatus {
    let level = classify_quorum(total, operational);
    let quorum_pct = if total == 0 {
        0u8
    } else {
        ((operational * 100) / total).min(100) as u8
    };
    let quorum_delta = quorum_pct as i16 - prev_pct as i16;
    let status_hash = compute_status_hash(epoch, total, operational, level, prev_hash);

    QuorumStatus {
        epoch,
        total_nodes: total,
        operational_nodes: operational,
        quorum_level: level,
        quorum_pct,
        quorum_delta,
        status_hash,
        prev_hash: *prev_hash,
    }
}

// ─── Quorum guard ─────────────────────────────────────────────────────────────

#[derive(Debug, Clone)]
pub struct QuorumGuard {
    statuses: Vec<QuorumStatus>,
}

#[derive(Debug)]
pub enum GuardError {
    StaleEpoch,
}

impl GuardError {
    pub fn as_str(&self) -> &'static str { "stale epoch" }
}

impl QuorumGuard {
    pub fn new() -> Self { Self { statuses: Vec::new() } }

    pub fn len(&self) -> usize { self.statuses.len() }
    pub fn is_empty(&self) -> bool { self.statuses.is_empty() }
    pub fn statuses(&self) -> &[QuorumStatus] { &self.statuses }
    pub fn latest(&self) -> Option<&QuorumStatus> { self.statuses.last() }

    pub fn last_hash(&self) -> [u8; 32] {
        self.statuses.last().map(|s| s.status_hash).unwrap_or(QUORUM_GENESIS_HASH)
    }

    fn prev_pct(&self) -> u8 {
        self.statuses.last().map(|s| s.quorum_pct).unwrap_or(0)
    }

    pub fn observe(
        &mut self,
        epoch:       u64,
        total:       usize,
        operational: usize,
    ) -> Result<&QuorumStatus, GuardError> {
        if let Some(last) = self.statuses.last() {
            if epoch <= last.epoch {
                return Err(GuardError::StaleEpoch);
            }
        }
        let prev_pct  = self.prev_pct();
        let prev_hash = self.last_hash();
        let status = build_status(epoch, total, operational, prev_pct, &prev_hash);
        self.statuses.push(status);
        Ok(self.statuses.last().unwrap())
    }

    /// Count of epochs where quorum was not met (BelowQuorum or NoNodes).
    pub fn alert_epochs(&self) -> usize {
        self.statuses.iter().filter(|s| s.quorum_level.requires_alert()).count()
    }

    /// Longest consecutive run of alert epochs.
    pub fn longest_outage(&self) -> usize {
        let mut longest = 0usize;
        let mut current = 0usize;
        for s in &self.statuses {
            if s.quorum_level.requires_alert() {
                current += 1;
                if current > longest { longest = current; }
            } else {
                current = 0;
            }
        }
        longest
    }

    /// Most recent quorum_delta (0 if no records).
    pub fn latest_delta(&self) -> i16 {
        self.statuses.last().map(|s| s.quorum_delta).unwrap_or(0)
    }

    pub fn verify_chain(&self) -> (bool, Option<usize>) {
        let mut expected_prev = QUORUM_GENESIS_HASH;
        for (i, s) in self.statuses.iter().enumerate() {
            if s.prev_hash != expected_prev {
                return (false, Some(i));
            }
            let recomputed = compute_status_hash(
                s.epoch, s.total_nodes, s.operational_nodes, s.quorum_level, &s.prev_hash);
            if recomputed != s.status_hash {
                return (false, Some(i));
            }
            expected_prev = s.status_hash;
        }
        (true, None)
    }
}

impl Default for QuorumGuard {
    fn default() -> Self { Self::new() }
}

// ─── Tests ───────────────────────────────────────────────────────────────────

#[cfg(test)]
mod tests {
    use super::*;

    // ── QuorumLevel ────────────────────────────────────────────────────────────

    #[test]
    fn level_as_str() {
        assert_eq!(QuorumLevel::Healthy.as_str(),     "healthy");
        assert_eq!(QuorumLevel::AtThreshold.as_str(), "at_threshold");
        assert_eq!(QuorumLevel::BelowQuorum.as_str(), "below_quorum");
        assert_eq!(QuorumLevel::NoNodes.as_str(),     "no_nodes");
    }

    #[test]
    fn quorum_met_flags() {
        assert!(QuorumLevel::Healthy.is_quorum_met());
        assert!(QuorumLevel::AtThreshold.is_quorum_met());
        assert!(!QuorumLevel::BelowQuorum.is_quorum_met());
        assert!(!QuorumLevel::NoNodes.is_quorum_met());
    }

    #[test]
    fn requires_alert_flags() {
        assert!(!QuorumLevel::Healthy.requires_alert());
        assert!(!QuorumLevel::AtThreshold.requires_alert());
        assert!(QuorumLevel::BelowQuorum.requires_alert());
        assert!(QuorumLevel::NoNodes.requires_alert());
    }

    // ── classify_quorum ────────────────────────────────────────────────────────

    #[test]
    fn no_nodes_classified() {
        assert_eq!(classify_quorum(0, 0), QuorumLevel::NoNodes);
    }

    #[test]
    fn healthy_at_70_pct() {
        // 7/10 = 70% → Healthy
        assert_eq!(classify_quorum(10, 7), QuorumLevel::Healthy);
    }

    #[test]
    fn at_threshold_62_pct() {
        // 5/8 = 62.5% → AtThreshold (≥61.8%, <70%)
        assert_eq!(classify_quorum(8, 5), QuorumLevel::AtThreshold);
    }

    #[test]
    fn below_quorum_50_pct() {
        // 4/8 = 50% → BelowQuorum
        assert_eq!(classify_quorum(8, 4), QuorumLevel::BelowQuorum);
    }

    #[test]
    fn all_operational_healthy() {
        assert_eq!(classify_quorum(5, 5), QuorumLevel::Healthy);
    }

    // ── build_status ───────────────────────────────────────────────────────────

    #[test]
    fn status_hash_nonzero() {
        let s = build_status(1, 8, 6, 0, &QUORUM_GENESIS_HASH);
        assert_ne!(s.status_hash, [0u8; 32]);
    }

    #[test]
    fn status_hash_deterministic() {
        let s1 = build_status(1, 8, 6, 0, &QUORUM_GENESIS_HASH);
        let s2 = build_status(1, 8, 6, 0, &QUORUM_GENESIS_HASH);
        assert_eq!(s1.status_hash, s2.status_hash);
    }

    #[test]
    fn quorum_pct_correct() {
        let s = build_status(1, 8, 6, 0, &QUORUM_GENESIS_HASH);
        assert_eq!(s.quorum_pct, 75); // 6/8 * 100 = 75
    }

    #[test]
    fn quorum_delta_computed() {
        let s = build_status(2, 8, 6, 50, &QUORUM_GENESIS_HASH);
        assert_eq!(s.quorum_delta, 25); // 75 - 50
    }

    #[test]
    fn zero_nodes_pct_zero() {
        let s = build_status(1, 0, 0, 0, &QUORUM_GENESIS_HASH);
        assert_eq!(s.quorum_pct, 0);
        assert_eq!(s.quorum_level, QuorumLevel::NoNodes);
    }

    // ── QuorumGuard ────────────────────────────────────────────────────────────

    #[test]
    fn new_guard_empty() {
        let g = QuorumGuard::new();
        assert!(g.is_empty());
        assert_eq!(g.last_hash(), QUORUM_GENESIS_HASH);
        assert_eq!(g.alert_epochs(), 0);
        assert_eq!(g.longest_outage(), 0);
    }

    #[test]
    fn observe_appends() {
        let mut g = QuorumGuard::new();
        g.observe(1, 8, 6).unwrap();
        g.observe(2, 8, 6).unwrap();
        assert_eq!(g.len(), 2);
    }

    #[test]
    fn stale_epoch_rejected() {
        let mut g = QuorumGuard::new();
        g.observe(5, 8, 6).unwrap();
        assert!(matches!(g.observe(5, 8, 5), Err(GuardError::StaleEpoch)));
        assert!(matches!(g.observe(4, 8, 5), Err(GuardError::StaleEpoch)));
    }

    #[test]
    fn alert_epochs_count() {
        let mut g = QuorumGuard::new();
        g.observe(1, 8, 6).unwrap(); // healthy
        g.observe(2, 8, 4).unwrap(); // below quorum
        g.observe(3, 8, 3).unwrap(); // below quorum
        g.observe(4, 8, 7).unwrap(); // healthy
        assert_eq!(g.alert_epochs(), 2);
    }

    #[test]
    fn longest_outage_tracks() {
        let mut g = QuorumGuard::new();
        g.observe(1, 8, 6).unwrap(); // healthy
        g.observe(2, 8, 4).unwrap(); // alert
        g.observe(3, 8, 3).unwrap(); // alert
        g.observe(4, 8, 2).unwrap(); // alert
        g.observe(5, 8, 7).unwrap(); // healthy
        g.observe(6, 8, 3).unwrap(); // alert
        assert_eq!(g.longest_outage(), 3);
    }

    #[test]
    fn delta_tracks_change() {
        let mut g = QuorumGuard::new();
        g.observe(1, 8, 4).unwrap(); // 50%
        g.observe(2, 8, 6).unwrap(); // 75%
        assert_eq!(g.latest_delta(), 25);
    }

    #[test]
    fn verify_chain_valid() {
        let mut g = QuorumGuard::new();
        for e in 1..=5u64 {
            g.observe(e, 10, 7).unwrap();
        }
        let (valid, broken) = g.verify_chain();
        assert!(valid);
        assert!(broken.is_none());
    }
}
