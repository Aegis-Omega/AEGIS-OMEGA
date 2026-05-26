//! Gate 269 — Capability Negotiator: peer capability advertisement + intersection (T2)
//! EPISTEMIC TIER: T2 (engineering hypothesis)
//!
//! Negotiates the shared capability set between the local node and a peer node.
//! Uses the bitmask capability system from peer_manifest (GOSSIP/RELAY/AUDIT/CONSENSUS).
//!
//! NegotiationResult:
//!   local_caps     — u8 (local node capabilities bitmask)
//!   peer_caps      — u8 (peer node capabilities bitmask)
//!   shared_caps    — u8 (local_caps & peer_caps — intersection)
//!   gossip_ok      — bool (GOSSIP in shared_caps)
//!   consensus_ok   — bool (CONSENSUS in shared_caps)
//!   relay_ok       — bool (RELAY in shared_caps)
//!   audit_ok       — bool (AUDIT in shared_caps)
//!   negotiation_hash — SHA-256(local_id_be4 ‖ peer_id_be4 ‖ local_caps ‖ peer_caps ‖ epoch_be8)
//!
//! NegotiationLog: ordered log of NegotiationResults per (local_id, peer_id) pair;
//! hash-chained. last_shared_caps(), capability_stable(), verify_chain().

use sha2::{Sha256, Digest};
use crate::peer_manifest::cap;

// ─── Negotiation result ───────────────────────────────────────────────────────

#[derive(Debug, Clone, PartialEq)]
pub struct NegotiationResult {
    pub local_id:          u32,
    pub peer_id:           u32,
    pub epoch:             u64,
    pub local_caps:        u8,
    pub peer_caps:         u8,
    pub shared_caps:       u8,
    pub gossip_ok:         bool,
    pub consensus_ok:      bool,
    pub relay_ok:          bool,
    pub audit_ok:          bool,
    pub negotiation_hash:  [u8; 32],
    pub prev_hash:         [u8; 32],
}

impl NegotiationResult {
    /// True if at least one capability is shared.
    pub fn any_shared(&self) -> bool { self.shared_caps != 0 }

    /// Count of shared capabilities.
    pub fn shared_count(&self) -> u32 { self.shared_caps.count_ones() }

    /// True if full bidirectional gossip + consensus is available.
    pub fn fully_capable(&self) -> bool { self.gossip_ok && self.consensus_ok }
}

pub const NEG_GENESIS_HASH: [u8; 32] = [0u8; 32];

fn compute_neg_hash(
    local_id: u32, peer_id: u32, local_caps: u8, peer_caps: u8, epoch: u64, prev: &[u8; 32],
) -> [u8; 32] {
    let mut h = Sha256::new();
    h.update(prev);
    h.update(local_id.to_be_bytes());
    h.update(peer_id.to_be_bytes());
    h.update([local_caps, peer_caps]);
    h.update(epoch.to_be_bytes());
    h.finalize().into()
}

pub fn negotiate(
    local_id:   u32,
    peer_id:    u32,
    epoch:      u64,
    local_caps: u8,
    peer_caps:  u8,
    prev_hash:  &[u8; 32],
) -> NegotiationResult {
    let shared_caps = local_caps & peer_caps;
    NegotiationResult {
        local_id,
        peer_id,
        epoch,
        local_caps,
        peer_caps,
        shared_caps,
        gossip_ok:    (shared_caps & cap::GOSSIP)    != 0,
        consensus_ok: (shared_caps & cap::CONSENSUS) != 0,
        relay_ok:     (shared_caps & cap::RELAY)     != 0,
        audit_ok:     (shared_caps & cap::AUDIT)     != 0,
        negotiation_hash: compute_neg_hash(
            local_id, peer_id, local_caps, peer_caps, epoch, prev_hash),
        prev_hash: *prev_hash,
    }
}

// ─── Negotiation log ──────────────────────────────────────────────────────────

#[derive(Debug, Clone)]
pub struct NegotiationLog {
    local_id: u32,
    peer_id:  u32,
    results:  Vec<NegotiationResult>,
}

#[derive(Debug)]
pub enum NegLogError {
    StaleEpoch,
    PeerMismatch,
}

impl NegLogError {
    pub fn as_str(&self) -> &'static str {
        match self {
            Self::StaleEpoch   => "stale epoch",
            Self::PeerMismatch => "peer id mismatch",
        }
    }
}

impl NegotiationLog {
    pub fn new(local_id: u32, peer_id: u32) -> Self {
        Self { local_id, peer_id, results: Vec::new() }
    }

    pub fn local_id(&self) -> u32 { self.local_id }
    pub fn peer_id(&self)  -> u32 { self.peer_id }
    pub fn len(&self)      -> usize { self.results.len() }
    pub fn is_empty(&self) -> bool  { self.results.is_empty() }
    pub fn results(&self)  -> &[NegotiationResult] { &self.results }
    pub fn latest(&self)   -> Option<&NegotiationResult> { self.results.last() }

    pub fn last_hash(&self) -> [u8; 32] {
        self.results.last().map(|r| r.negotiation_hash).unwrap_or(NEG_GENESIS_HASH)
    }

    pub fn record(
        &mut self,
        epoch:      u64,
        local_caps: u8,
        peer_caps:  u8,
    ) -> Result<&NegotiationResult, NegLogError> {
        if let Some(last) = self.results.last() {
            if epoch <= last.epoch {
                return Err(NegLogError::StaleEpoch);
            }
        }
        let prev_hash = self.last_hash();
        let result = negotiate(
            self.local_id, self.peer_id, epoch, local_caps, peer_caps, &prev_hash);
        self.results.push(result);
        Ok(self.results.last().unwrap())
    }

    /// The shared capability bitmask from the latest negotiation (0 if empty).
    pub fn last_shared_caps(&self) -> u8 {
        self.results.last().map(|r| r.shared_caps).unwrap_or(0)
    }

    /// True if all negotiation results have identical shared_caps (capability stable).
    pub fn capability_stable(&self) -> bool {
        if self.results.len() < 2 { return true; }
        let first = self.results[0].shared_caps;
        self.results.iter().all(|r| r.shared_caps == first)
    }

    pub fn verify_chain(&self) -> (bool, Option<usize>) {
        let mut expected_prev = NEG_GENESIS_HASH;
        for (i, r) in self.results.iter().enumerate() {
            if r.prev_hash != expected_prev {
                return (false, Some(i));
            }
            let recomputed = compute_neg_hash(
                r.local_id, r.peer_id, r.local_caps, r.peer_caps, r.epoch, &r.prev_hash);
            if recomputed != r.negotiation_hash {
                return (false, Some(i));
            }
            expected_prev = r.negotiation_hash;
        }
        (true, None)
    }
}

// ─── Tests ───────────────────────────────────────────────────────────────────

#[cfg(test)]
mod tests {
    use super::*;
    use crate::peer_manifest::cap;

    // ── negotiate ─────────────────────────────────────────────────────────────

    #[test]
    fn full_caps_both_sides() {
        let r = negotiate(1, 2, 1, cap::ALL, cap::ALL, &NEG_GENESIS_HASH);
        assert_eq!(r.shared_caps, cap::ALL);
        assert!(r.gossip_ok);
        assert!(r.consensus_ok);
        assert!(r.relay_ok);
        assert!(r.audit_ok);
        assert!(r.fully_capable());
    }

    #[test]
    fn no_shared_caps() {
        let local = cap::GOSSIP | cap::RELAY;
        let peer  = cap::AUDIT  | cap::CONSENSUS;
        let r = negotiate(1, 2, 1, local, peer, &NEG_GENESIS_HASH);
        assert_eq!(r.shared_caps, 0);
        assert!(!r.any_shared());
        assert!(!r.fully_capable());
    }

    #[test]
    fn partial_intersection() {
        let r = negotiate(1, 2, 1, cap::GOSSIP | cap::CONSENSUS, cap::GOSSIP | cap::RELAY, &NEG_GENESIS_HASH);
        assert_eq!(r.shared_caps, cap::GOSSIP);
        assert!(r.gossip_ok);
        assert!(!r.consensus_ok);
        assert_eq!(r.shared_count(), 1);
    }

    #[test]
    fn gossip_only_not_fully_capable() {
        let r = negotiate(1, 2, 1, cap::GOSSIP, cap::GOSSIP, &NEG_GENESIS_HASH);
        assert!(r.gossip_ok);
        assert!(!r.consensus_ok);
        assert!(!r.fully_capable());
    }

    #[test]
    fn hash_nonzero() {
        let r = negotiate(1, 2, 1, cap::ALL, cap::ALL, &NEG_GENESIS_HASH);
        assert_ne!(r.negotiation_hash, [0u8; 32]);
    }

    #[test]
    fn hash_deterministic() {
        let r1 = negotiate(1, 2, 1, cap::ALL, cap::ALL, &NEG_GENESIS_HASH);
        let r2 = negotiate(1, 2, 1, cap::ALL, cap::ALL, &NEG_GENESIS_HASH);
        assert_eq!(r1.negotiation_hash, r2.negotiation_hash);
    }

    #[test]
    fn different_peer_caps_different_hash() {
        let r1 = negotiate(1, 2, 1, cap::ALL, cap::ALL,   &NEG_GENESIS_HASH);
        let r2 = negotiate(1, 2, 1, cap::ALL, cap::GOSSIP, &NEG_GENESIS_HASH);
        assert_ne!(r1.negotiation_hash, r2.negotiation_hash);
    }

    // ── NegotiationLog ────────────────────────────────────────────────────────

    #[test]
    fn new_log_empty() {
        let l = NegotiationLog::new(1, 2);
        assert!(l.is_empty());
        assert_eq!(l.last_hash(), NEG_GENESIS_HASH);
        assert_eq!(l.last_shared_caps(), 0);
        assert!(l.capability_stable());
    }

    #[test]
    fn record_appends() {
        let mut l = NegotiationLog::new(1, 2);
        l.record(1, cap::ALL, cap::ALL).unwrap();
        l.record(2, cap::ALL, cap::ALL).unwrap();
        assert_eq!(l.len(), 2);
    }

    #[test]
    fn stale_epoch_rejected() {
        let mut l = NegotiationLog::new(1, 2);
        l.record(5, cap::ALL, cap::ALL).unwrap();
        assert!(matches!(l.record(5, cap::ALL, cap::ALL), Err(NegLogError::StaleEpoch)));
        assert!(matches!(l.record(4, cap::ALL, cap::ALL), Err(NegLogError::StaleEpoch)));
    }

    #[test]
    fn last_shared_caps_updates() {
        let mut l = NegotiationLog::new(1, 2);
        l.record(1, cap::ALL, cap::GOSSIP).unwrap();
        assert_eq!(l.last_shared_caps(), cap::GOSSIP);
    }

    #[test]
    fn capability_stable_true_when_same() {
        let mut l = NegotiationLog::new(1, 2);
        l.record(1, cap::ALL, cap::ALL).unwrap();
        l.record(2, cap::ALL, cap::ALL).unwrap();
        l.record(3, cap::ALL, cap::ALL).unwrap();
        assert!(l.capability_stable());
    }

    #[test]
    fn capability_stable_false_when_changed() {
        let mut l = NegotiationLog::new(1, 2);
        l.record(1, cap::ALL, cap::ALL).unwrap();
        l.record(2, cap::ALL, cap::GOSSIP).unwrap(); // different shared
        assert!(!l.capability_stable());
    }

    #[test]
    fn verify_chain_valid() {
        let mut l = NegotiationLog::new(1, 2);
        for e in 1..=4u64 {
            l.record(e, cap::ALL, cap::ALL).unwrap();
        }
        let (valid, broken) = l.verify_chain();
        assert!(valid);
        assert!(broken.is_none());
    }
}
