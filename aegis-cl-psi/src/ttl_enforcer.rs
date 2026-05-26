//! Gate 286 — Gossip TTL Enforcer: per-message TTL tracking and hop-count enforcement (T2)
//! EPISTEMIC TIER: T2 (engineering hypothesis)
//!
//! Tracks message TTL (time-to-live) hop counts. Each time a gossip message is forwarded,
//! its TTL is decremented. If TTL reaches 0, the message must be dropped.
//! Detects TTL inflation: a forwarded message claiming a TTL higher than its origin record.
//!
//! TtlDecision:
//!   Forward { remaining_ttl: u8 }  — TTL decremented, message can be forwarded
//!   Drop { reason: TtlDropReason } — message must not be forwarded
//!
//! TtlDropReason:
//!   Expired   — TTL reached 0 after decrement
//!   Inflated  — forwarded TTL > origin TTL (violation — counts as TtlViolation reputation event)
//!   TooHigh   — initial TTL exceeds MAX_INITIAL_TTL (15)
//!
//! MessageTtlRecord:
//!   message_id     — u64
//!   origin_ttl     — u8 (set at origin, max MAX_INITIAL_TTL)
//!   current_ttl    — u8 (decremented on each forward hop)
//!   hop_count      — u8 (number of times forwarded)
//!   decision       — TtlDecision (last applied decision)
//!   record_hash    — SHA-256(prev ‖ msg_id_be8 ‖ origin_ttl ‖ current_ttl ‖ hop_count ‖ decision_byte)
//!   prev_hash      — [u8; 32]
//!
//! TtlEnforcer: BTreeMap<message_id, MessageTtlRecord>.
//!   register_origin(message_id, origin_ttl) → Result<(), TtlError>   — register at origin
//!   forward(message_id, claimed_ttl) → TtlDecision                   — apply one forward hop
//!   expired_count(), inflated_count(), active_messages().

use sha2::{Sha256, Digest};
use std::collections::BTreeMap;

pub const MAX_INITIAL_TTL: u8 = 15;

// ─── TTL drop reason ──────────────────────────────────────────────────────────

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum TtlDropReason {
    Expired,
    Inflated,
    TooHigh,
}

// ─── TTL decision ─────────────────────────────────────────────────────────────

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum TtlDecision {
    Forward { remaining_ttl: u8 },
    Drop    { reason: TtlDropReason },
}

impl TtlDecision {
    pub fn decision_byte(self) -> u8 {
        match self {
            Self::Forward { .. }                         => 0,
            Self::Drop { reason: TtlDropReason::Expired }  => 1,
            Self::Drop { reason: TtlDropReason::Inflated } => 2,
            Self::Drop { reason: TtlDropReason::TooHigh }  => 3,
        }
    }

    pub fn is_forward(self) -> bool { matches!(self, Self::Forward { .. }) }
    pub fn is_drop(self)    -> bool { matches!(self, Self::Drop { .. }) }
}

// ─── Message TTL record ───────────────────────────────────────────────────────

#[derive(Debug, Clone, PartialEq)]
pub struct MessageTtlRecord {
    pub message_id:  u64,
    pub origin_ttl:  u8,
    pub current_ttl: u8,
    pub hop_count:   u8,
    pub decision:    TtlDecision,
    pub record_hash: [u8; 32],
    pub prev_hash:   [u8; 32],
}

pub const TTL_GENESIS_HASH: [u8; 32] = [0u8; 32];

fn compute_ttl_hash(
    message_id:  u64,
    origin_ttl:  u8,
    current_ttl: u8,
    hop_count:   u8,
    decision:    TtlDecision,
    prev:        &[u8; 32],
) -> [u8; 32] {
    let mut h = Sha256::new();
    h.update(prev);
    h.update(message_id.to_be_bytes());
    h.update([origin_ttl, current_ttl, hop_count, decision.decision_byte()]);
    h.finalize().into()
}

// ─── Per-message state ────────────────────────────────────────────────────────

#[derive(Debug, Clone)]
struct MessageState {
    origin_ttl:   u8,
    current_ttl:  u8,
    hop_count:    u8,
    last_hash:    [u8; 32],
    drop_reason:  Option<TtlDropReason>,
}

// ─── TTL enforcer ─────────────────────────────────────────────────────────────

#[derive(Debug, Clone)]
pub struct TtlEnforcer {
    messages:        BTreeMap<u64, MessageState>,
    expired_count:   u64,
    inflated_count:  u64,
    forwarded_count: u64,
}

#[derive(Debug)]
pub enum TtlError {
    AlreadyRegistered,
    TtlTooHigh,
    MessageNotFound,
    MessageAlreadyDropped,
}

impl TtlEnforcer {
    pub fn new() -> Self {
        Self {
            messages:        BTreeMap::new(),
            expired_count:   0,
            inflated_count:  0,
            forwarded_count: 0,
        }
    }

    pub fn message_count(&self) -> usize { self.messages.len() }
    pub fn expired_count(&self)  -> u64  { self.expired_count }
    pub fn inflated_count(&self) -> u64  { self.inflated_count }
    pub fn forwarded_count(&self) -> u64 { self.forwarded_count }

    /// Register a message at its origin with the given initial TTL.
    pub fn register_origin(
        &mut self,
        message_id: u64,
        origin_ttl: u8,
    ) -> Result<MessageTtlRecord, TtlError> {
        if self.messages.contains_key(&message_id) {
            return Err(TtlError::AlreadyRegistered);
        }
        if origin_ttl > MAX_INITIAL_TTL {
            return Err(TtlError::TtlTooHigh);
        }

        let decision = TtlDecision::Forward { remaining_ttl: origin_ttl };
        let record_hash = compute_ttl_hash(
            message_id, origin_ttl, origin_ttl, 0, decision, &TTL_GENESIS_HASH,
        );
        let state = MessageState {
            origin_ttl,
            current_ttl:  origin_ttl,
            hop_count:    0,
            last_hash:    record_hash,
            drop_reason:  None,
        };
        self.messages.insert(message_id, state);
        Ok(MessageTtlRecord {
            message_id, origin_ttl, current_ttl: origin_ttl, hop_count: 0,
            decision, record_hash, prev_hash: TTL_GENESIS_HASH,
        })
    }

    /// Apply one forward hop to a registered message.
    /// claimed_ttl: the TTL value the forwarding peer claims; must equal current_ttl - 1.
    /// If claimed_ttl > current_ttl - 1 → Inflated (TTL violation).
    pub fn forward(
        &mut self,
        message_id: u64,
        claimed_ttl: u8,
    ) -> Result<(MessageTtlRecord, TtlDecision), TtlError> {
        let state = self.messages.get_mut(&message_id)
            .ok_or(TtlError::MessageNotFound)?;
        if state.drop_reason.is_some() {
            return Err(TtlError::MessageAlreadyDropped);
        }

        let prev_hash = state.last_hash;
        let expected_ttl = state.current_ttl.saturating_sub(1);

        let decision = if claimed_ttl > expected_ttl {
            // TTL inflation: peer claims higher TTL than allowed
            self.inflated_count += 1;
            state.drop_reason = Some(TtlDropReason::Inflated);
            TtlDecision::Drop { reason: TtlDropReason::Inflated }
        } else if expected_ttl == 0 {
            self.expired_count += 1;
            state.drop_reason = Some(TtlDropReason::Expired);
            TtlDecision::Drop { reason: TtlDropReason::Expired }
        } else {
            self.forwarded_count += 1;
            state.current_ttl = expected_ttl;
            state.hop_count   = state.hop_count.saturating_add(1);
            TtlDecision::Forward { remaining_ttl: expected_ttl }
        };

        let record_hash = compute_ttl_hash(
            message_id, state.origin_ttl, state.current_ttl,
            state.hop_count, decision, &prev_hash,
        );
        state.last_hash = record_hash;

        let record = MessageTtlRecord {
            message_id,
            origin_ttl:  state.origin_ttl,
            current_ttl: state.current_ttl,
            hop_count:   state.hop_count,
            decision,
            record_hash,
            prev_hash,
        };
        Ok((record, decision))
    }

    /// All message IDs with an active (non-dropped) TTL.
    pub fn active_messages(&self) -> Vec<u64> {
        self.messages.iter()
            .filter(|(_, s)| s.drop_reason.is_none() && s.current_ttl > 0)
            .map(|(&id, _)| id)
            .collect()
    }
}

impl Default for TtlEnforcer {
    fn default() -> Self { Self::new() }
}

// ─── Tests ───────────────────────────────────────────────────────────────────

#[cfg(test)]
mod tests {
    use super::*;

    // ── TtlDecision ───────────────────────────────────────────────────────────

    #[test]
    fn decision_bytes() {
        assert_eq!(TtlDecision::Forward { remaining_ttl: 5 }.decision_byte(), 0);
        assert_eq!(TtlDecision::Drop { reason: TtlDropReason::Expired }.decision_byte(), 1);
        assert_eq!(TtlDecision::Drop { reason: TtlDropReason::Inflated }.decision_byte(), 2);
        assert_eq!(TtlDecision::Drop { reason: TtlDropReason::TooHigh }.decision_byte(), 3);
    }

    #[test]
    fn is_forward_and_drop() {
        assert!(TtlDecision::Forward { remaining_ttl: 3 }.is_forward());
        assert!(TtlDecision::Drop { reason: TtlDropReason::Expired }.is_drop());
    }

    // ── register_origin ───────────────────────────────────────────────────────

    #[test]
    fn register_origin_ok() {
        let mut e = TtlEnforcer::new();
        let r = e.register_origin(1, 5).unwrap();
        assert_eq!(r.origin_ttl, 5);
        assert_eq!(r.current_ttl, 5);
        assert_eq!(r.hop_count, 0);
        assert!(r.decision.is_forward());
        assert_ne!(r.record_hash, [0u8; 32]);
    }

    #[test]
    fn register_too_high_ttl_rejected() {
        let mut e = TtlEnforcer::new();
        assert!(matches!(e.register_origin(1, 16), Err(TtlError::TtlTooHigh)));
    }

    #[test]
    fn max_ttl_accepted() {
        let mut e = TtlEnforcer::new();
        assert!(e.register_origin(1, MAX_INITIAL_TTL).is_ok());
    }

    #[test]
    fn duplicate_registration_rejected() {
        let mut e = TtlEnforcer::new();
        e.register_origin(1, 5).unwrap();
        assert!(matches!(e.register_origin(1, 3), Err(TtlError::AlreadyRegistered)));
    }

    // ── forward ───────────────────────────────────────────────────────────────

    #[test]
    fn forward_decrements_ttl() {
        let mut e = TtlEnforcer::new();
        e.register_origin(1, 5).unwrap();
        let (r, d) = e.forward(1, 4).unwrap();
        assert_eq!(r.current_ttl, 4);
        assert_eq!(r.hop_count, 1);
        assert_eq!(d, TtlDecision::Forward { remaining_ttl: 4 });
    }

    #[test]
    fn forward_chain_hash_links() {
        let mut e = TtlEnforcer::new();
        let r0 = e.register_origin(1, 5).unwrap();
        let (r1, _) = e.forward(1, 4).unwrap();
        assert_eq!(r1.prev_hash, r0.record_hash);
    }

    #[test]
    fn expire_at_zero_ttl() {
        let mut e = TtlEnforcer::new();
        e.register_origin(1, 1).unwrap();
        // After 1 forward, remaining_ttl would be 0 → expired on next hop
        let (r, d) = e.forward(1, 0).unwrap(); // expected_ttl = 0 → expired
        assert_eq!(d, TtlDecision::Drop { reason: TtlDropReason::Expired });
        assert!(r.decision.is_drop());
        assert_eq!(e.expired_count(), 1);
    }

    #[test]
    fn inflated_ttl_detected() {
        let mut e = TtlEnforcer::new();
        e.register_origin(1, 5).unwrap();
        // Claim ttl=5 but should be 4 (5-1)
        let (_, d) = e.forward(1, 5).unwrap();
        assert_eq!(d, TtlDecision::Drop { reason: TtlDropReason::Inflated });
        assert_eq!(e.inflated_count(), 1);
    }

    #[test]
    fn forward_after_drop_errors() {
        let mut e = TtlEnforcer::new();
        e.register_origin(1, 1).unwrap();
        e.forward(1, 0).unwrap(); // expired
        assert!(matches!(e.forward(1, 0), Err(TtlError::MessageAlreadyDropped)));
    }

    #[test]
    fn unknown_message_errors() {
        let mut e = TtlEnforcer::new();
        assert!(matches!(e.forward(99, 5), Err(TtlError::MessageNotFound)));
    }

    #[test]
    fn multiple_hops() {
        let mut e = TtlEnforcer::new();
        e.register_origin(1, 5).unwrap();
        let (_, d1) = e.forward(1, 4).unwrap();
        let (_, d2) = e.forward(1, 3).unwrap();
        let (_, d3) = e.forward(1, 2).unwrap();
        assert_eq!(d1, TtlDecision::Forward { remaining_ttl: 4 });
        assert_eq!(d2, TtlDecision::Forward { remaining_ttl: 3 });
        assert_eq!(d3, TtlDecision::Forward { remaining_ttl: 2 });
        assert_eq!(e.forwarded_count(), 3);
    }

    #[test]
    fn active_messages_excludes_dropped() {
        let mut e = TtlEnforcer::new();
        e.register_origin(1, 3).unwrap();
        e.register_origin(2, 1).unwrap();
        e.forward(2, 0).unwrap(); // expire message 2
        let active = e.active_messages();
        assert_eq!(active, vec![1]);
    }

    #[test]
    fn record_hash_deterministic() {
        let mut e1 = TtlEnforcer::new();
        let mut e2 = TtlEnforcer::new();
        let r1 = e1.register_origin(42, 5).unwrap();
        let r2 = e2.register_origin(42, 5).unwrap();
        assert_eq!(r1.record_hash, r2.record_hash);
    }
}
