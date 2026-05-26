//! Gate 234: Entropy Budget — Constitutional Adaptation Accounting
//! EPISTEMIC TIER: T2 (engineering hypothesis)
//!
//! Implements AdaptivePower(T) ≤ ReplayVerifiability(T) as a concrete numerical
//! constraint: each adaptive event (mutation, evolution, specialization) consumes
//! units from a finite entropy budget; the budget is replenished only through
//! verified replay events (hash-chain-certified state transitions).
//!
//! Budget mechanics:
//!   - Initial budget: INITIAL_ENTROPY_BUDGET (u64, configurable at construction)
//!   - Adaptive event: costs ADAPTIVE_EVENT_COST units
//!   - Replay certification: replenishes REPLAY_REPLENISHMENT units
//!   - Budget never exceeds MAX_ENTROPY_BUDGET (overflow cap)
//!   - Budget never goes below 0 (unsigned — attempts at over-spend are rejected)
//!
//! BudgetEntry: each consume/replenish is a hash-linked record:
//!   entry_hash = SHA-256(prev_hash ‖ delta_i64_be ‖ balance_after_u64_be)
//! The chain of BudgetEntries is the entropy ledger — replay-certifiable.
//!
//! Constitutional law: if budget == 0, adaptive events are BLOCKED (T0_ABORT signal).
//! The system can always observe but cannot adapt without sufficient replay coverage.

use sha2::{Sha256, Digest};

// ─── Constants ────────────────────────────────────────────────────────────

/// Starting entropy budget for a fresh node.
pub const INITIAL_ENTROPY_BUDGET: u64 = 1_000;

/// Units consumed by one adaptive event (mutation, evolution, specialization).
pub const ADAPTIVE_EVENT_COST: u64 = 10;

/// Units replenished by one verified replay certification.
pub const REPLAY_REPLENISHMENT: u64 = 7;

/// Maximum budget cap — prevents unbounded accumulation.
pub const MAX_ENTROPY_BUDGET: u64 = 10_000;

/// Genesis prev_hash for the first budget entry.
pub const ENTROPY_GENESIS_HASH: [u8; 32] = [0u8; 32];

// ─── Entry type ───────────────────────────────────────────────────────────

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum EntryKind {
    AdaptiveEvent,      // consume ADAPTIVE_EVENT_COST
    ReplayCertification, // replenish REPLAY_REPLENISHMENT
    Custom,             // arbitrary delta (signed)
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct BudgetEntry {
    /// Kind of budget event.
    pub kind: EntryKind,
    /// Signed delta (negative = consume, positive = replenish).
    pub delta: i64,
    /// Budget balance after this entry.
    pub balance_after: u64,
    /// SHA-256(prev_entry_hash ‖ delta_i64_be ‖ balance_after_u64_be).
    pub entry_hash: [u8; 32],
    /// Hash of the previous entry (ENTROPY_GENESIS_HASH for first).
    pub prev_entry_hash: [u8; 32],
}

// ─── Error ────────────────────────────────────────────────────────────────

#[derive(Debug, PartialEq, Eq)]
pub enum BudgetError {
    InsufficientBudget { available: u64, required: u64 },
    InvalidCustomDelta, // delta == 0
}

// ─── Entropy budget ───────────────────────────────────────────────────────

/// Hash-linked entropy budget ledger.
#[derive(Debug, Clone)]
pub struct EntropyBudget {
    balance:  u64,
    entries:  Vec<BudgetEntry>,
}

impl EntropyBudget {
    /// Create a fresh budget with INITIAL_ENTROPY_BUDGET.
    pub fn new() -> Self {
        Self { balance: INITIAL_ENTROPY_BUDGET, entries: Vec::new() }
    }

    /// Create a budget with a custom initial balance (capped at MAX_ENTROPY_BUDGET).
    pub fn with_balance(balance: u64) -> Self {
        Self { balance: balance.min(MAX_ENTROPY_BUDGET), entries: Vec::new() }
    }

    /// Current balance.
    pub fn balance(&self) -> u64 { self.balance }

    /// True iff adaptive events are permitted (balance >= ADAPTIVE_EVENT_COST).
    pub fn can_adapt(&self) -> bool { self.balance >= ADAPTIVE_EVENT_COST }

    /// Number of budget entries (ledger length).
    pub fn len(&self) -> usize { self.entries.len() }

    /// True iff no entries have been recorded.
    pub fn is_empty(&self) -> bool { self.entries.is_empty() }

    /// All ledger entries.
    pub fn entries(&self) -> &[BudgetEntry] { &self.entries }

    /// Last entry hash (ENTROPY_GENESIS_HASH if empty).
    pub fn last_hash(&self) -> [u8; 32] {
        self.entries.last().map(|e| e.entry_hash).unwrap_or(ENTROPY_GENESIS_HASH)
    }

    /// Consume ADAPTIVE_EVENT_COST units for an adaptive event.
    /// Returns Err(InsufficientBudget) if balance < ADAPTIVE_EVENT_COST.
    pub fn consume_adaptive(&mut self) -> Result<&BudgetEntry, BudgetError> {
        if self.balance < ADAPTIVE_EVENT_COST {
            return Err(BudgetError::InsufficientBudget {
                available: self.balance,
                required: ADAPTIVE_EVENT_COST,
            });
        }
        self.balance -= ADAPTIVE_EVENT_COST;
        let entry = self.push_entry(EntryKind::AdaptiveEvent, -(ADAPTIVE_EVENT_COST as i64));
        Ok(entry)
    }

    /// Replenish REPLAY_REPLENISHMENT units for a verified replay certification.
    /// Balance is capped at MAX_ENTROPY_BUDGET.
    pub fn replenish_replay(&mut self) -> &BudgetEntry {
        let added = REPLAY_REPLENISHMENT.min(MAX_ENTROPY_BUDGET - self.balance);
        self.balance += added;
        self.push_entry(EntryKind::ReplayCertification, added as i64)
    }

    /// Apply a custom signed delta (non-zero only).
    /// Positive = replenish (capped at MAX_ENTROPY_BUDGET).
    /// Negative = consume (Err if would underflow).
    pub fn apply_custom(&mut self, delta: i64) -> Result<&BudgetEntry, BudgetError> {
        if delta == 0 { return Err(BudgetError::InvalidCustomDelta); }
        if delta < 0 {
            let cost = (-delta) as u64;
            if self.balance < cost {
                return Err(BudgetError::InsufficientBudget {
                    available: self.balance,
                    required: cost,
                });
            }
            self.balance -= cost;
        } else {
            let add = (delta as u64).min(MAX_ENTROPY_BUDGET - self.balance);
            self.balance += add;
        }
        Ok(self.push_entry(EntryKind::Custom, delta))
    }

    /// Verify the full hash chain integrity of the ledger.
    /// Returns (is_valid, first_broken_index) where None means valid.
    pub fn verify_chain(&self) -> (bool, Option<usize>) {
        let mut prev = ENTROPY_GENESIS_HASH;
        for (i, entry) in self.entries.iter().enumerate() {
            if entry.prev_entry_hash != prev {
                return (false, Some(i));
            }
            let expected = compute_entry_hash(entry.delta, entry.balance_after, &prev);
            if expected != entry.entry_hash {
                return (false, Some(i));
            }
            prev = entry.entry_hash;
        }
        (true, None)
    }

    // ── Private helpers ───────────────────────────────────────────────────

    fn push_entry(&mut self, kind: EntryKind, delta: i64) -> &BudgetEntry {
        let prev = self.last_hash();
        let hash = compute_entry_hash(delta, self.balance, &prev);
        self.entries.push(BudgetEntry {
            kind,
            delta,
            balance_after: self.balance,
            entry_hash: hash,
            prev_entry_hash: prev,
        });
        self.entries.last().unwrap()
    }
}

impl Default for EntropyBudget {
    fn default() -> Self { Self::new() }
}

fn compute_entry_hash(delta: i64, balance_after: u64, prev: &[u8; 32]) -> [u8; 32] {
    let mut h = Sha256::new();
    h.update(prev);
    h.update(delta.to_be_bytes());
    h.update(balance_after.to_be_bytes());
    h.finalize().into()
}

// ─── Tests ────────────────────────────────────────────────────────────────

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn constants_sane() {
        assert_eq!(INITIAL_ENTROPY_BUDGET, 1_000);
        assert_eq!(ADAPTIVE_EVENT_COST, 10);
        assert_eq!(REPLAY_REPLENISHMENT, 7);
        assert_eq!(MAX_ENTROPY_BUDGET, 10_000);
        assert_eq!(ENTROPY_GENESIS_HASH, [0u8; 32]);
    }

    #[test]
    fn new_has_initial_balance() {
        let b = EntropyBudget::new();
        assert_eq!(b.balance(), INITIAL_ENTROPY_BUDGET);
        assert!(b.is_empty());
    }

    #[test]
    fn can_adapt_true_on_fresh_budget() {
        assert!(EntropyBudget::new().can_adapt());
    }

    #[test]
    fn consume_adaptive_reduces_balance() {
        let mut b = EntropyBudget::new();
        b.consume_adaptive().unwrap();
        assert_eq!(b.balance(), INITIAL_ENTROPY_BUDGET - ADAPTIVE_EVENT_COST);
    }

    #[test]
    fn consume_adaptive_insufficient_budget() {
        let mut b = EntropyBudget::with_balance(5); // less than ADAPTIVE_EVENT_COST=10
        let err = b.consume_adaptive().unwrap_err();
        assert_eq!(err, BudgetError::InsufficientBudget { available: 5, required: 10 });
    }

    #[test]
    fn replenish_replay_increases_balance() {
        let mut b = EntropyBudget::with_balance(100);
        b.replenish_replay();
        assert_eq!(b.balance(), 100 + REPLAY_REPLENISHMENT);
    }

    #[test]
    fn replenish_capped_at_max() {
        let mut b = EntropyBudget::with_balance(MAX_ENTROPY_BUDGET);
        b.replenish_replay();
        assert_eq!(b.balance(), MAX_ENTROPY_BUDGET);
    }

    #[test]
    fn with_balance_capped_at_max() {
        let b = EntropyBudget::with_balance(u64::MAX);
        assert_eq!(b.balance(), MAX_ENTROPY_BUDGET);
    }

    #[test]
    fn entry_hash_is_32_bytes_nonzero() {
        let mut b = EntropyBudget::new();
        let e = b.consume_adaptive().unwrap();
        assert_ne!(e.entry_hash, [0u8; 32]);
    }

    #[test]
    fn first_entry_prev_is_genesis() {
        let mut b = EntropyBudget::new();
        let e = b.consume_adaptive().unwrap();
        assert_eq!(e.prev_entry_hash, ENTROPY_GENESIS_HASH);
    }

    #[test]
    fn second_entry_prev_matches_first_hash() {
        let mut b = EntropyBudget::new();
        b.consume_adaptive().unwrap();
        b.replenish_replay();
        let entries = b.entries();
        assert_eq!(entries[1].prev_entry_hash, entries[0].entry_hash);
    }

    #[test]
    fn verify_chain_clean() {
        let mut b = EntropyBudget::new();
        for _ in 0..5 { b.consume_adaptive().unwrap(); }
        for _ in 0..5 { b.replenish_replay(); }
        let (valid, broken) = b.verify_chain();
        assert!(valid);
        assert!(broken.is_none());
    }

    #[test]
    fn verify_empty_chain() {
        let b = EntropyBudget::new();
        let (valid, broken) = b.verify_chain();
        assert!(valid);
        assert!(broken.is_none());
    }

    #[test]
    fn custom_positive_delta() {
        let mut b = EntropyBudget::with_balance(100);
        b.apply_custom(50).unwrap();
        assert_eq!(b.balance(), 150);
    }

    #[test]
    fn custom_negative_delta() {
        let mut b = EntropyBudget::with_balance(100);
        b.apply_custom(-30).unwrap();
        assert_eq!(b.balance(), 70);
    }

    #[test]
    fn custom_zero_delta_is_err() {
        let mut b = EntropyBudget::new();
        assert_eq!(b.apply_custom(0).unwrap_err(), BudgetError::InvalidCustomDelta);
    }

    #[test]
    fn determinism_same_sequence_same_hashes() {
        let build = || {
            let mut b = EntropyBudget::new();
            b.consume_adaptive().unwrap();
            b.consume_adaptive().unwrap();
            b.replenish_replay();
            b.entries()[2].entry_hash
        };
        assert_eq!(build(), build());
        assert_eq!(build(), build());
    }

    #[test]
    fn can_adapt_false_when_exhausted() {
        let mut b = EntropyBudget::with_balance(5); // below ADAPTIVE_EVENT_COST
        assert!(!b.can_adapt());
    }

    #[test]
    fn ledger_grows_with_each_entry() {
        let mut b = EntropyBudget::new();
        assert_eq!(b.len(), 0);
        b.consume_adaptive().unwrap();
        assert_eq!(b.len(), 1);
        b.replenish_replay();
        assert_eq!(b.len(), 2);
    }
}
