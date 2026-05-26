//! Gate 279 — Gossip Mesh Supervisor: epoch-level gossip subsystem snapshot (T2)
//! EPISTEMIC TIER: T2 (engineering hypothesis)
//!
//! Binds the outputs of the gossip mesh subsystems into a single per-epoch
//! supervision record. Provides a tamper-evident hash over all subsystem
//! states at epoch boundary.
//!
//! MeshSupervisionRecord:
//!   epoch               — u64
//!   fanout              — u8  (from fanout_controller)
//!   drop_count          — u32 (global backpressure drops this epoch)
//!   spread_reach_pct    — u8  (estimated reach percentage from spread_estimator)
//!   quorum_reachable    — bool
//!   avg_reputation      — u8  (ledger average_score)
//!   blocked_peer_count  — u16
//!   trusted_peer_count  — u16
//!   pending_queue_len   — u32 (messages in priority queue at epoch end)
//!   supervision_hash    — SHA-256(prev ‖ epoch_be8 ‖ fanout ‖ drop_count_be4 ‖
//!                                 spread_reach_pct ‖ quorum_byte ‖ avg_rep ‖
//!                                 blocked_be2 ‖ trusted_be2 ‖ queue_be4)
//!   prev_hash           — [u8; 32]
//!
//! MeshSupervisionLog: hash-chained records.
//!   append(), min_reach_pct(), max_drop_count(), quorum_loss_epochs(), verify_chain().

use sha2::{Sha256, Digest};

// ─── Supervision record ───────────────────────────────────────────────────────

#[derive(Debug, Clone, PartialEq)]
pub struct MeshSupervisionRecord {
    pub epoch:              u64,
    pub fanout:             u8,
    pub drop_count:         u32,
    pub spread_reach_pct:   u8,
    pub quorum_reachable:   bool,
    pub avg_reputation:     u8,
    pub blocked_peer_count: u16,
    pub trusted_peer_count: u16,
    pub pending_queue_len:  u32,
    pub supervision_hash:   [u8; 32],
    pub prev_hash:          [u8; 32],
}

pub const SUPERVISOR_GENESIS_HASH: [u8; 32] = [0u8; 32];

fn compute_supervision_hash(
    epoch:              u64,
    fanout:             u8,
    drop_count:         u32,
    spread_reach_pct:   u8,
    quorum_reachable:   bool,
    avg_reputation:     u8,
    blocked_peer_count: u16,
    trusted_peer_count: u16,
    pending_queue_len:  u32,
    prev:               &[u8; 32],
) -> [u8; 32] {
    let mut h = Sha256::new();
    h.update(prev);
    h.update(epoch.to_be_bytes());
    h.update([fanout]);
    h.update(drop_count.to_be_bytes());
    h.update([spread_reach_pct, quorum_reachable as u8, avg_reputation]);
    h.update(blocked_peer_count.to_be_bytes());
    h.update(trusted_peer_count.to_be_bytes());
    h.update(pending_queue_len.to_be_bytes());
    h.finalize().into()
}

#[allow(clippy::too_many_arguments)]
pub fn build_supervision_record(
    epoch:              u64,
    fanout:             u8,
    drop_count:         u32,
    spread_reach_pct:   u8,
    quorum_reachable:   bool,
    avg_reputation:     u8,
    blocked_peer_count: u16,
    trusted_peer_count: u16,
    pending_queue_len:  u32,
    prev_hash:          &[u8; 32],
) -> MeshSupervisionRecord {
    let supervision_hash = compute_supervision_hash(
        epoch, fanout, drop_count, spread_reach_pct,
        quorum_reachable, avg_reputation,
        blocked_peer_count, trusted_peer_count, pending_queue_len, prev_hash,
    );
    MeshSupervisionRecord {
        epoch, fanout, drop_count, spread_reach_pct, quorum_reachable,
        avg_reputation, blocked_peer_count, trusted_peer_count, pending_queue_len,
        supervision_hash, prev_hash: *prev_hash,
    }
}

impl MeshSupervisionRecord {
    /// True if the mesh state is considered healthy:
    /// quorum reachable AND spread reach ≥ 50% AND no blocked peers.
    pub fn mesh_healthy(&self) -> bool {
        self.quorum_reachable && self.spread_reach_pct >= 50 && self.blocked_peer_count == 0
    }

    /// True if backpressure drops exceeded a threshold (>10).
    pub fn backpressure_alert(&self) -> bool { self.drop_count > 10 }
}

// ─── Supervision log ──────────────────────────────────────────────────────────

#[derive(Debug, Clone)]
pub struct MeshSupervisionLog {
    records: Vec<MeshSupervisionRecord>,
}

#[derive(Debug)]
pub enum SupervisionError {
    StaleEpoch,
}

impl MeshSupervisionLog {
    pub fn new() -> Self { Self { records: Vec::new() } }

    pub fn len(&self)      -> usize { self.records.len() }
    pub fn is_empty(&self) -> bool  { self.records.is_empty() }
    pub fn records(&self)  -> &[MeshSupervisionRecord] { &self.records }
    pub fn latest(&self)   -> Option<&MeshSupervisionRecord> { self.records.last() }

    pub fn last_hash(&self) -> [u8; 32] {
        self.records.last().map(|r| r.supervision_hash).unwrap_or(SUPERVISOR_GENESIS_HASH)
    }

    #[allow(clippy::too_many_arguments)]
    pub fn append(
        &mut self,
        epoch:              u64,
        fanout:             u8,
        drop_count:         u32,
        spread_reach_pct:   u8,
        quorum_reachable:   bool,
        avg_reputation:     u8,
        blocked_peer_count: u16,
        trusted_peer_count: u16,
        pending_queue_len:  u32,
    ) -> Result<&MeshSupervisionRecord, SupervisionError> {
        if let Some(last) = self.records.last() {
            if epoch <= last.epoch {
                return Err(SupervisionError::StaleEpoch);
            }
        }
        let prev_hash = self.last_hash();
        let r = build_supervision_record(
            epoch, fanout, drop_count, spread_reach_pct, quorum_reachable,
            avg_reputation, blocked_peer_count, trusted_peer_count, pending_queue_len, &prev_hash,
        );
        self.records.push(r);
        Ok(self.records.last().unwrap())
    }

    pub fn min_reach_pct(&self) -> u8 {
        self.records.iter().map(|r| r.spread_reach_pct).min().unwrap_or(0)
    }

    pub fn max_drop_count(&self) -> u32 {
        self.records.iter().map(|r| r.drop_count).max().unwrap_or(0)
    }

    /// Number of epochs where quorum was not reachable.
    pub fn quorum_loss_epochs(&self) -> usize {
        self.records.iter().filter(|r| !r.quorum_reachable).count()
    }

    /// Number of epochs where mesh was fully healthy.
    pub fn healthy_epoch_count(&self) -> usize {
        self.records.iter().filter(|r| r.mesh_healthy()).count()
    }

    pub fn verify_chain(&self) -> (bool, Option<usize>) {
        let mut expected_prev = SUPERVISOR_GENESIS_HASH;
        for (i, r) in self.records.iter().enumerate() {
            if r.prev_hash != expected_prev {
                return (false, Some(i));
            }
            let recomputed = compute_supervision_hash(
                r.epoch, r.fanout, r.drop_count, r.spread_reach_pct,
                r.quorum_reachable, r.avg_reputation,
                r.blocked_peer_count, r.trusted_peer_count, r.pending_queue_len,
                &r.prev_hash,
            );
            if recomputed != r.supervision_hash {
                return (false, Some(i));
            }
            expected_prev = r.supervision_hash;
        }
        (true, None)
    }
}

impl Default for MeshSupervisionLog {
    fn default() -> Self { Self::new() }
}

// ─── Tests ───────────────────────────────────────────────────────────────────

#[cfg(test)]
mod tests {
    use super::*;

    fn record(epoch: u64, reach: u8, quorum: bool, drops: u32, blocked: u16)
        -> MeshSupervisionRecord
    {
        build_supervision_record(epoch, 3, drops, reach, quorum, 60, blocked, 2, 0,
            &SUPERVISOR_GENESIS_HASH)
    }

    // ── build_supervision_record ──────────────────────────────────────────────

    #[test]
    fn supervision_hash_nonzero() {
        let r = record(1, 80, true, 0, 0);
        assert_ne!(r.supervision_hash, [0u8; 32]);
    }

    #[test]
    fn supervision_hash_deterministic() {
        let r1 = record(1, 80, true, 0, 0);
        let r2 = record(1, 80, true, 0, 0);
        assert_eq!(r1.supervision_hash, r2.supervision_hash);
    }

    #[test]
    fn different_fanout_different_hash() {
        let r1 = build_supervision_record(1, 3, 0, 80, true, 60, 0, 2, 0, &SUPERVISOR_GENESIS_HASH);
        let r2 = build_supervision_record(1, 5, 0, 80, true, 60, 0, 2, 0, &SUPERVISOR_GENESIS_HASH);
        assert_ne!(r1.supervision_hash, r2.supervision_hash);
    }

    // ── mesh_healthy / backpressure_alert ─────────────────────────────────────

    #[test]
    fn mesh_healthy_all_good() {
        let r = record(1, 80, true, 0, 0);
        assert!(r.mesh_healthy());
    }

    #[test]
    fn mesh_unhealthy_no_quorum() {
        let r = record(1, 80, false, 0, 0);
        assert!(!r.mesh_healthy());
    }

    #[test]
    fn mesh_unhealthy_low_reach() {
        let r = record(1, 40, true, 0, 0);
        assert!(!r.mesh_healthy());
    }

    #[test]
    fn mesh_unhealthy_blocked_peers() {
        let r = record(1, 80, true, 0, 2); // blocked_peer_count=2
        assert!(!r.mesh_healthy());
    }

    #[test]
    fn backpressure_alert_when_drops_exceed_10() {
        let high = record(1, 80, true, 11, 0);
        let low  = record(2, 80, true, 5,  0);
        assert!(high.backpressure_alert());
        assert!(!low.backpressure_alert());
    }

    // ── MeshSupervisionLog ────────────────────────────────────────────────────

    #[test]
    fn new_log_empty() {
        let l = MeshSupervisionLog::new();
        assert!(l.is_empty());
        assert_eq!(l.min_reach_pct(), 0);
        assert_eq!(l.max_drop_count(), 0);
        assert_eq!(l.quorum_loss_epochs(), 0);
    }

    #[test]
    fn append_chains_hashes() {
        let mut l = MeshSupervisionLog::new();
        l.append(1, 3, 0, 80, true, 60, 0, 2, 0).unwrap();
        l.append(2, 3, 0, 70, true, 60, 0, 2, 0).unwrap();
        assert_eq!(l.records()[1].prev_hash, l.records()[0].supervision_hash);
    }

    #[test]
    fn stale_epoch_rejected() {
        let mut l = MeshSupervisionLog::new();
        l.append(5, 3, 0, 80, true, 60, 0, 2, 0).unwrap();
        assert!(matches!(l.append(5, 3, 0, 80, true, 60, 0, 2, 0), Err(SupervisionError::StaleEpoch)));
    }

    #[test]
    fn min_reach_pct_tracks() {
        let mut l = MeshSupervisionLog::new();
        l.append(1, 3, 0, 80, true, 60, 0, 2, 0).unwrap();
        l.append(2, 3, 0, 40, true, 60, 0, 2, 0).unwrap();
        assert_eq!(l.min_reach_pct(), 40);
    }

    #[test]
    fn max_drop_count_tracks() {
        let mut l = MeshSupervisionLog::new();
        l.append(1, 3, 5, 80, true, 60, 0, 2, 0).unwrap();
        l.append(2, 3, 20, 80, true, 60, 0, 2, 0).unwrap();
        assert_eq!(l.max_drop_count(), 20);
    }

    #[test]
    fn quorum_loss_epochs_counts() {
        let mut l = MeshSupervisionLog::new();
        l.append(1, 3, 0, 80, true,  60, 0, 2, 0).unwrap();
        l.append(2, 3, 0, 80, false, 60, 0, 2, 0).unwrap();
        l.append(3, 3, 0, 80, false, 60, 0, 2, 0).unwrap();
        assert_eq!(l.quorum_loss_epochs(), 2);
    }

    #[test]
    fn verify_chain_valid() {
        let mut l = MeshSupervisionLog::new();
        for i in 1..=5u64 {
            l.append(i, 3, 0, 80, true, 60, 0, 2, 0).unwrap();
        }
        let (valid, broken) = l.verify_chain();
        assert!(valid);
        assert!(broken.is_none());
    }
}
