//! Gate 262 — Node State Machine: per-node lifecycle automaton (T2)
//! EPISTEMIC TIER: T2 (engineering hypothesis)
//!
//! Models the constitutional lifecycle of a single gossip mesh node.
//! State transitions are deterministic and hash-linked for replay.
//!
//! NodeState:
//!   Initializing — node booting; no gossip or consensus participation
//!   Active       — fully operational; all capabilities enabled
//!   Degraded     — reduced capability; gossip continues, no consensus
//!   Recovery     — returning to Active from Degraded
//!   Halted       — terminal; no participation
//!
//! Valid transitions (adjacency):
//!   Initializing → Active
//!   Active       → Degraded | Halted
//!   Degraded     → Recovery | Halted
//!   Recovery     → Active   | Degraded
//!   Halted       → (none — terminal)
//!
//! NodeRecord: one entry per transition; hash-chained.
//!   node_id, from_state, to_state, epoch, reason, record_hash
//!   record_hash = SHA-256(prev ‖ node_id_be4 ‖ from_byte ‖ to_byte ‖ epoch_be8)
//!
//! NodeHistory: ordered log of NodeRecords for one node.

use sha2::{Sha256, Digest};

// ─── Node state ───────────────────────────────────────────────────────────────

#[derive(Debug, Clone, Copy, PartialEq, Eq, PartialOrd, Ord)]
pub enum NodeState {
    Initializing = 0,
    Active       = 1,
    Degraded     = 2,
    Recovery     = 3,
    Halted       = 4,
}

impl NodeState {
    pub fn as_u8(self) -> u8 { self as u8 }

    pub fn as_str(self) -> &'static str {
        match self {
            Self::Initializing => "initializing",
            Self::Active       => "active",
            Self::Degraded     => "degraded",
            Self::Recovery     => "recovery",
            Self::Halted       => "halted",
        }
    }

    pub fn is_terminal(self) -> bool { self == Self::Halted }

    pub fn is_operational(self) -> bool {
        matches!(self, Self::Active | Self::Recovery)
    }

    /// Returns true if transition to `next` is allowed.
    pub fn can_transition_to(self, next: NodeState) -> bool {
        match (self, next) {
            (Self::Initializing, Self::Active)    => true,
            (Self::Active,       Self::Degraded)  => true,
            (Self::Active,       Self::Halted)    => true,
            (Self::Degraded,     Self::Recovery)  => true,
            (Self::Degraded,     Self::Halted)    => true,
            (Self::Recovery,     Self::Active)    => true,
            (Self::Recovery,     Self::Degraded)  => true,
            _ => false,
        }
    }
}

fn decode_state(b: u8) -> Option<NodeState> {
    match b {
        0 => Some(NodeState::Initializing),
        1 => Some(NodeState::Active),
        2 => Some(NodeState::Degraded),
        3 => Some(NodeState::Recovery),
        4 => Some(NodeState::Halted),
        _ => None,
    }
}

// ─── Node record ─────────────────────────────────────────────────────────────

#[derive(Debug, Clone, PartialEq)]
pub struct NodeRecord {
    pub node_id:     u32,
    pub from_state:  NodeState,
    pub to_state:    NodeState,
    pub epoch:       u64,
    pub reason:      &'static str,
    pub record_hash: [u8; 32],
    pub prev_hash:   [u8; 32],
}

pub const NODE_GENESIS_HASH: [u8; 32] = [0u8; 32];

fn compute_record_hash(
    prev:       &[u8; 32],
    node_id:    u32,
    from_state: NodeState,
    to_state:   NodeState,
    epoch:      u64,
) -> [u8; 32] {
    let mut h = Sha256::new();
    h.update(prev);
    h.update(node_id.to_be_bytes());
    h.update([from_state.as_u8()]);
    h.update([to_state.as_u8()]);
    h.update(epoch.to_be_bytes());
    h.finalize().into()
}

// ─── Node history ─────────────────────────────────────────────────────────────

#[derive(Debug, Clone)]
pub struct NodeHistory {
    node_id:       u32,
    current_state: NodeState,
    records:       Vec<NodeRecord>,
}

#[derive(Debug)]
pub enum TransitionError {
    InvalidTransition { from: NodeState, to: NodeState },
    TerminalState,
    StaleEpoch,
}

impl TransitionError {
    pub fn as_str(&self) -> &'static str {
        match self {
            Self::InvalidTransition { .. } => "invalid transition",
            Self::TerminalState            => "terminal state",
            Self::StaleEpoch               => "stale epoch",
        }
    }
}

impl NodeHistory {
    pub fn new(node_id: u32) -> Self {
        Self {
            node_id,
            current_state: NodeState::Initializing,
            records: Vec::new(),
        }
    }

    pub fn node_id(&self) -> u32            { self.node_id }
    pub fn current_state(&self) -> NodeState { self.current_state }
    pub fn records(&self) -> &[NodeRecord]  { &self.records }
    pub fn len(&self) -> usize              { self.records.len() }
    pub fn is_empty(&self) -> bool          { self.records.is_empty() }

    pub fn last_hash(&self) -> [u8; 32] {
        self.records.last().map(|r| r.record_hash).unwrap_or(NODE_GENESIS_HASH)
    }

    /// Attempt a state transition. Validates adjacency, terminal guard, epoch.
    pub fn transition(
        &mut self,
        to_state: NodeState,
        epoch:    u64,
        reason:   &'static str,
    ) -> Result<&NodeRecord, TransitionError> {
        if self.current_state.is_terminal() {
            return Err(TransitionError::TerminalState);
        }
        if !self.current_state.can_transition_to(to_state) {
            return Err(TransitionError::InvalidTransition {
                from: self.current_state,
                to:   to_state,
            });
        }
        // Epoch must not regress (same epoch allowed for rapid state changes)
        if let Some(last) = self.records.last() {
            if epoch < last.epoch {
                return Err(TransitionError::StaleEpoch);
            }
        }

        let prev_hash   = self.last_hash();
        let record_hash = compute_record_hash(&prev_hash, self.node_id,
                                              self.current_state, to_state, epoch);
        let record = NodeRecord {
            node_id:     self.node_id,
            from_state:  self.current_state,
            to_state,
            epoch,
            reason,
            record_hash,
            prev_hash,
        };
        self.current_state = to_state;
        self.records.push(record);
        Ok(self.records.last().unwrap())
    }

    /// Count of times the node entered Degraded state.
    pub fn degraded_count(&self) -> usize {
        self.records.iter().filter(|r| r.to_state == NodeState::Degraded).count()
    }

    /// Count of times the node returned to Active.
    pub fn recovery_count(&self) -> usize {
        self.records.iter()
            .filter(|r| r.to_state == NodeState::Active && r.from_state == NodeState::Recovery)
            .count()
    }

    /// Verify hash chain.
    pub fn verify_chain(&self) -> (bool, Option<usize>) {
        let mut expected_prev = NODE_GENESIS_HASH;
        for (i, rec) in self.records.iter().enumerate() {
            if rec.prev_hash != expected_prev {
                return (false, Some(i));
            }
            let recomputed = compute_record_hash(
                &rec.prev_hash, rec.node_id, rec.from_state, rec.to_state, rec.epoch);
            if recomputed != rec.record_hash {
                return (false, Some(i));
            }
            expected_prev = rec.record_hash;
        }
        (true, None)
    }
}

// ─── Tests ───────────────────────────────────────────────────────────────────

#[cfg(test)]
mod tests {
    use super::*;

    // ── NodeState ────────────────────────────────────────────────────────────

    #[test]
    fn state_as_str() {
        assert_eq!(NodeState::Initializing.as_str(), "initializing");
        assert_eq!(NodeState::Active.as_str(),       "active");
        assert_eq!(NodeState::Degraded.as_str(),     "degraded");
        assert_eq!(NodeState::Recovery.as_str(),     "recovery");
        assert_eq!(NodeState::Halted.as_str(),       "halted");
    }

    #[test]
    fn terminal_and_operational() {
        assert!(NodeState::Halted.is_terminal());
        assert!(!NodeState::Active.is_terminal());
        assert!(NodeState::Active.is_operational());
        assert!(NodeState::Recovery.is_operational());
        assert!(!NodeState::Degraded.is_operational());
        assert!(!NodeState::Halted.is_operational());
    }

    #[test]
    fn valid_transitions() {
        assert!(NodeState::Initializing.can_transition_to(NodeState::Active));
        assert!(NodeState::Active.can_transition_to(NodeState::Degraded));
        assert!(NodeState::Active.can_transition_to(NodeState::Halted));
        assert!(NodeState::Degraded.can_transition_to(NodeState::Recovery));
        assert!(NodeState::Degraded.can_transition_to(NodeState::Halted));
        assert!(NodeState::Recovery.can_transition_to(NodeState::Active));
        assert!(NodeState::Recovery.can_transition_to(NodeState::Degraded));
    }

    #[test]
    fn invalid_transitions() {
        assert!(!NodeState::Initializing.can_transition_to(NodeState::Degraded));
        assert!(!NodeState::Active.can_transition_to(NodeState::Initializing));
        assert!(!NodeState::Active.can_transition_to(NodeState::Recovery));
        assert!(!NodeState::Halted.can_transition_to(NodeState::Active));
        assert!(!NodeState::Halted.can_transition_to(NodeState::Initializing));
    }

    // ── NodeHistory ──────────────────────────────────────────────────────────

    #[test]
    fn new_history_initializing() {
        let h = NodeHistory::new(42);
        assert_eq!(h.current_state(), NodeState::Initializing);
        assert_eq!(h.node_id(), 42);
        assert!(h.is_empty());
        assert_eq!(h.last_hash(), NODE_GENESIS_HASH);
    }

    #[test]
    fn valid_transition_recorded() {
        let mut h = NodeHistory::new(1);
        h.transition(NodeState::Active, 1, "boot").unwrap();
        assert_eq!(h.current_state(), NodeState::Active);
        assert_eq!(h.len(), 1);
    }

    #[test]
    fn invalid_transition_rejected() {
        let mut h = NodeHistory::new(1);
        // Can't go Initializing → Degraded
        assert!(matches!(
            h.transition(NodeState::Degraded, 1, "test"),
            Err(TransitionError::InvalidTransition { .. })
        ));
    }

    #[test]
    fn terminal_transition_rejected() {
        let mut h = NodeHistory::new(1);
        h.transition(NodeState::Active, 1, "boot").unwrap();
        h.transition(NodeState::Halted, 2, "halt").unwrap();
        assert!(matches!(
            h.transition(NodeState::Active, 3, "restart"),
            Err(TransitionError::TerminalState)
        ));
    }

    #[test]
    fn stale_epoch_rejected() {
        let mut h = NodeHistory::new(1);
        h.transition(NodeState::Active, 5, "boot").unwrap();
        assert!(matches!(
            h.transition(NodeState::Degraded, 4, "degrade"),
            Err(TransitionError::StaleEpoch)
        ));
    }

    #[test]
    fn same_epoch_allowed() {
        let mut h = NodeHistory::new(1);
        h.transition(NodeState::Active, 5, "boot").unwrap();
        h.transition(NodeState::Degraded, 5, "rapid degrade").unwrap();
        assert_eq!(h.len(), 2);
    }

    #[test]
    fn full_lifecycle() {
        let mut h = NodeHistory::new(1);
        h.transition(NodeState::Active,   1, "boot").unwrap();
        h.transition(NodeState::Degraded, 2, "fault").unwrap();
        h.transition(NodeState::Recovery, 3, "recover").unwrap();
        h.transition(NodeState::Active,   4, "ok").unwrap();
        h.transition(NodeState::Halted,   5, "shutdown").unwrap();
        assert_eq!(h.current_state(), NodeState::Halted);
        assert_eq!(h.degraded_count(), 1);
        assert_eq!(h.recovery_count(), 1);
    }

    #[test]
    fn chain_links_correctly() {
        let mut h = NodeHistory::new(1);
        h.transition(NodeState::Active, 1, "boot").unwrap();
        h.transition(NodeState::Degraded, 2, "fault").unwrap();
        assert_eq!(h.records()[1].prev_hash, h.records()[0].record_hash);
    }

    #[test]
    fn verify_chain_valid() {
        let mut h = NodeHistory::new(1);
        h.transition(NodeState::Active, 1, "boot").unwrap();
        h.transition(NodeState::Degraded, 2, "fault").unwrap();
        h.transition(NodeState::Recovery, 3, "recover").unwrap();
        let (valid, broken) = h.verify_chain();
        assert!(valid);
        assert!(broken.is_none());
    }

    #[test]
    fn tampered_record_fails_chain() {
        let mut h = NodeHistory::new(1);
        h.transition(NodeState::Active, 1, "boot").unwrap();
        h.transition(NodeState::Degraded, 2, "fault").unwrap();
        h.records[0].record_hash[0] ^= 0xFF;
        let (valid, broken) = h.verify_chain();
        assert!(!valid);
        assert_eq!(broken, Some(0));
    }

    #[test]
    fn record_hash_deterministic() {
        let mut h1 = NodeHistory::new(5);
        let mut h2 = NodeHistory::new(5);
        h1.transition(NodeState::Active, 1, "boot").unwrap();
        h2.transition(NodeState::Active, 1, "boot").unwrap();
        assert_eq!(h1.records()[0].record_hash, h2.records()[0].record_hash);
    }

    #[test]
    fn transition_error_as_str() {
        let e = TransitionError::InvalidTransition {
            from: NodeState::Active,
            to:   NodeState::Initializing,
        };
        assert_eq!(e.as_str(), "invalid transition");
        assert_eq!(TransitionError::TerminalState.as_str(), "terminal state");
        assert_eq!(TransitionError::StaleEpoch.as_str(), "stale epoch");
    }
}
