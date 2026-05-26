//! Gate 281 — Mesh Convergence Certifier: multi-epoch gossip stability proof (T2)
//! EPISTEMIC TIER: T2 (engineering hypothesis)
//!
//! Certifies that the gossip mesh has achieved convergence: stable quorum,
//! stable spread reach, and no blocked peers across a window of epochs.
//!
//! ConvergenceWindow:
//!   Required: CONVERGENCE_WINDOW_SIZE consecutive epochs with:
//!     - quorum_reachable = true
//!     - spread_reach_pct ≥ MIN_REACH_PCT (50)
//!     - blocked_peer_count = 0
//!     - max fanout not at Maximum policy (fanout < 8)
//!
//! ConvergenceCertificate:
//!   epoch_start        — u64 (first epoch in the window)
//!   epoch_end          — u64 (last epoch in the window)
//!   window_size        — u8  (number of epochs certified)
//!   min_reach_pct      — u8  (minimum reach across window)
//!   max_fanout         — u8  (maximum fanout used across window)
//!   is_converged       — bool
//!   certificate_hash   — SHA-256(prev ‖ epoch_start_be8 ‖ epoch_end_be8 ‖ window_size ‖
//!                                 min_reach ‖ max_fanout ‖ converged_byte)
//!   prev_hash          — [u8; 32]
//!
//! ConvergenceCertifier: sliding window over MeshSupervisionRecords.
//!   push_epoch(), latest_certificate(), consecutive_converged_count().

use sha2::{Sha256, Digest};

pub const CONVERGENCE_WINDOW_SIZE: usize = 3;
pub const MIN_REACH_PCT: u8 = 50;
pub const MAX_CONVERGED_FANOUT: u8 = 7; // fanout < 8 (not Maximum policy)

// ─── Epoch snapshot (lightweight view of supervision state) ───────────────────

#[derive(Debug, Clone, Copy)]
pub struct EpochSnapshot {
    pub epoch:              u64,
    pub fanout:             u8,
    pub spread_reach_pct:   u8,
    pub quorum_reachable:   bool,
    pub blocked_peer_count: u16,
}

impl EpochSnapshot {
    /// True if this single epoch satisfies convergence conditions.
    pub fn satisfies_convergence(&self) -> bool {
        self.quorum_reachable
            && self.spread_reach_pct >= MIN_REACH_PCT
            && self.blocked_peer_count == 0
            && self.fanout <= MAX_CONVERGED_FANOUT
    }
}

// ─── Convergence certificate ──────────────────────────────────────────────────

#[derive(Debug, Clone, PartialEq)]
pub struct ConvergenceCertificate {
    pub epoch_start:      u64,
    pub epoch_end:        u64,
    pub window_size:      u8,
    pub min_reach_pct:    u8,
    pub max_fanout:       u8,
    pub is_converged:     bool,
    pub certificate_hash: [u8; 32],
    pub prev_hash:        [u8; 32],
}

pub const CONVERGENCE_GENESIS_HASH: [u8; 32] = [0u8; 32];

fn compute_cert_hash(
    epoch_start:   u64,
    epoch_end:     u64,
    window_size:   u8,
    min_reach_pct: u8,
    max_fanout:    u8,
    is_converged:  bool,
    prev:          &[u8; 32],
) -> [u8; 32] {
    let mut h = Sha256::new();
    h.update(prev);
    h.update(epoch_start.to_be_bytes());
    h.update(epoch_end.to_be_bytes());
    h.update([window_size, min_reach_pct, max_fanout, is_converged as u8]);
    h.finalize().into()
}

// ─── Certifier ────────────────────────────────────────────────────────────────

#[derive(Debug, Clone)]
pub struct ConvergenceCertifier {
    window:       Vec<EpochSnapshot>,   // circular, capped at CONVERGENCE_WINDOW_SIZE
    certificates: Vec<ConvergenceCertificate>,
}

impl ConvergenceCertifier {
    pub fn new() -> Self {
        Self { window: Vec::new(), certificates: Vec::new() }
    }

    pub fn certificate_count(&self) -> usize { self.certificates.len() }
    pub fn certificates(&self) -> &[ConvergenceCertificate] { &self.certificates }
    pub fn latest_certificate(&self) -> Option<&ConvergenceCertificate> {
        self.certificates.last()
    }

    fn last_cert_hash(&self) -> [u8; 32] {
        self.certificates.last()
            .map(|c| c.certificate_hash)
            .unwrap_or(CONVERGENCE_GENESIS_HASH)
    }

    /// Push a new epoch snapshot and produce a certificate if window is full.
    pub fn push_epoch(&mut self, snapshot: EpochSnapshot) -> Option<&ConvergenceCertificate> {
        // Maintain window up to CONVERGENCE_WINDOW_SIZE
        if self.window.len() >= CONVERGENCE_WINDOW_SIZE {
            self.window.remove(0);
        }
        self.window.push(snapshot);

        if self.window.len() < CONVERGENCE_WINDOW_SIZE {
            return None; // window not yet full
        }

        let epoch_start  = self.window[0].epoch;
        let epoch_end    = self.window[self.window.len() - 1].epoch;
        let window_size  = self.window.len() as u8;
        let min_reach    = self.window.iter().map(|s| s.spread_reach_pct).min().unwrap_or(0);
        let max_fanout   = self.window.iter().map(|s| s.fanout).max().unwrap_or(0);
        let is_converged = self.window.iter().all(|s| s.satisfies_convergence());

        let prev = self.last_cert_hash();
        let certificate_hash = compute_cert_hash(
            epoch_start, epoch_end, window_size, min_reach, max_fanout, is_converged, &prev,
        );
        let cert = ConvergenceCertificate {
            epoch_start, epoch_end, window_size, min_reach_pct: min_reach,
            max_fanout, is_converged, certificate_hash, prev_hash: prev,
        };
        self.certificates.push(cert);
        self.certificates.last()
    }

    /// Number of consecutive certificates where is_converged = true (from the end).
    pub fn consecutive_converged_count(&self) -> usize {
        self.certificates.iter().rev()
            .take_while(|c| c.is_converged)
            .count()
    }

    pub fn verify_chain(&self) -> (bool, Option<usize>) {
        let mut expected_prev = CONVERGENCE_GENESIS_HASH;
        for (i, c) in self.certificates.iter().enumerate() {
            if c.prev_hash != expected_prev {
                return (false, Some(i));
            }
            let recomputed = compute_cert_hash(
                c.epoch_start, c.epoch_end, c.window_size,
                c.min_reach_pct, c.max_fanout, c.is_converged, &c.prev_hash,
            );
            if recomputed != c.certificate_hash {
                return (false, Some(i));
            }
            expected_prev = c.certificate_hash;
        }
        (true, None)
    }
}

impl Default for ConvergenceCertifier {
    fn default() -> Self { Self::new() }
}

// ─── Tests ───────────────────────────────────────────────────────────────────

#[cfg(test)]
mod tests {
    use super::*;

    fn good(epoch: u64) -> EpochSnapshot {
        EpochSnapshot { epoch, fanout: 3, spread_reach_pct: 80, quorum_reachable: true, blocked_peer_count: 0 }
    }

    fn bad_quorum(epoch: u64) -> EpochSnapshot {
        EpochSnapshot { epoch, fanout: 8, spread_reach_pct: 80, quorum_reachable: false, blocked_peer_count: 0 }
    }

    fn bad_reach(epoch: u64) -> EpochSnapshot {
        EpochSnapshot { epoch, fanout: 3, spread_reach_pct: 30, quorum_reachable: true, blocked_peer_count: 0 }
    }

    fn bad_blocked(epoch: u64) -> EpochSnapshot {
        EpochSnapshot { epoch, fanout: 3, spread_reach_pct: 80, quorum_reachable: true, blocked_peer_count: 2 }
    }

    // ── EpochSnapshot ─────────────────────────────────────────────────────────

    #[test]
    fn good_snapshot_satisfies_convergence() {
        assert!(good(1).satisfies_convergence());
    }

    #[test]
    fn bad_quorum_fails() {
        assert!(!bad_quorum(1).satisfies_convergence());
    }

    #[test]
    fn bad_reach_fails() {
        assert!(!bad_reach(1).satisfies_convergence());
    }

    #[test]
    fn bad_blocked_fails() {
        assert!(!bad_blocked(1).satisfies_convergence());
    }

    #[test]
    fn max_fanout_8_fails() {
        let s = EpochSnapshot { epoch: 1, fanout: 8, spread_reach_pct: 80,
            quorum_reachable: true, blocked_peer_count: 0 };
        assert!(!s.satisfies_convergence());
    }

    // ── ConvergenceCertifier ──────────────────────────────────────────────────

    #[test]
    fn no_certificate_before_window_full() {
        let mut c = ConvergenceCertifier::new();
        assert!(c.push_epoch(good(1)).is_none());
        assert!(c.push_epoch(good(2)).is_none());
        assert_eq!(c.certificate_count(), 0);
    }

    #[test]
    fn certificate_produced_on_third_epoch() {
        let mut c = ConvergenceCertifier::new();
        c.push_epoch(good(1));
        c.push_epoch(good(2));
        let cert = c.push_epoch(good(3)).unwrap();
        assert!(cert.is_converged);
        assert_eq!(cert.epoch_start, 1);
        assert_eq!(cert.epoch_end,   3);
        assert_eq!(cert.window_size, 3);
    }

    #[test]
    fn not_converged_when_any_bad() {
        let mut c = ConvergenceCertifier::new();
        c.push_epoch(good(1));
        c.push_epoch(bad_quorum(2));
        let cert = c.push_epoch(good(3)).unwrap();
        assert!(!cert.is_converged);
    }

    #[test]
    fn min_reach_tracked_in_cert() {
        let mut c = ConvergenceCertifier::new();
        c.push_epoch(EpochSnapshot { epoch: 1, fanout: 3, spread_reach_pct: 60, quorum_reachable: true, blocked_peer_count: 0 });
        c.push_epoch(EpochSnapshot { epoch: 2, fanout: 3, spread_reach_pct: 90, quorum_reachable: true, blocked_peer_count: 0 });
        let cert = c.push_epoch(good(3)).unwrap();
        assert_eq!(cert.min_reach_pct, 60);
    }

    #[test]
    fn window_slides_correctly() {
        let mut c = ConvergenceCertifier::new();
        c.push_epoch(bad_quorum(1)); // will be evicted
        c.push_epoch(good(2));
        c.push_epoch(good(3));
        // Now epoch 1 is evicted; window = [2, 3, 4]
        let cert = c.push_epoch(good(4)).unwrap();
        assert!(cert.is_converged); // all good now
        assert_eq!(cert.epoch_start, 2);
    }

    #[test]
    fn certificate_hash_nonzero() {
        let mut c = ConvergenceCertifier::new();
        c.push_epoch(good(1));
        c.push_epoch(good(2));
        let cert = c.push_epoch(good(3)).unwrap();
        assert_ne!(cert.certificate_hash, [0u8; 32]);
    }

    #[test]
    fn certificate_hash_deterministic() {
        let mut c1 = ConvergenceCertifier::new();
        let mut c2 = ConvergenceCertifier::new();
        for i in 1..=3u64 {
            c1.push_epoch(good(i));
            c2.push_epoch(good(i));
        }
        assert_eq!(c1.certificates()[0].certificate_hash, c2.certificates()[0].certificate_hash);
    }

    #[test]
    fn consecutive_converged_count() {
        let mut c = ConvergenceCertifier::new();
        // First window [1,2,3]: bad (bad_quorum at epoch 2)
        c.push_epoch(good(1));
        c.push_epoch(bad_quorum(2));
        c.push_epoch(good(3));
        // Second window [2,3,4]: still bad (bad_quorum(2) still in window)
        c.push_epoch(good(4));
        // Third window [3,4,5]: good (all satisfy convergence)
        c.push_epoch(good(5));
        // Fourth window [4,5,6]: good (all satisfy convergence)
        c.push_epoch(good(6));
        assert_eq!(c.consecutive_converged_count(), 2);
    }

    #[test]
    fn verify_chain_valid() {
        let mut c = ConvergenceCertifier::new();
        for i in 1..=8u64 {
            c.push_epoch(good(i));
        }
        let (valid, broken) = c.verify_chain();
        assert!(valid);
        assert!(broken.is_none());
    }
}
