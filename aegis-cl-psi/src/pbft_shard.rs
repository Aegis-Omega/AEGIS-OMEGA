//! PBFT Merkle Sharding
//! EPISTEMIC TIER: T2
//!
//! Lightweight BFT quorum over shard Merkle roots. Validators cast votes on the
//! root hash of their assigned shard; a root is committed when
//! ≥ ⌊2N/3⌋ + 1 votes agree — the classical PBFT 1/3-fault-tolerance quorum.
//!
//! Invariants:
//!   - `vote_hash = SHA-256(validator_id || shard_root || sequence_be)` — tamper-evident
//!   - Votes are keyed by validator_id in a BTreeMap (deterministic iteration)
//!   - Duplicate vote from same validator: second vote overwrites the first
//!   - PBFT_GENESIS_HASH = [0u8;32] — chain origin for round digests
//!
//! Source: From Metaphysics to Production — PBFT Merkle sharding, T2.

use sha2::{Sha256, Digest};
use std::collections::BTreeMap;

pub const PBFT_GENESIS_HASH: [u8; 32] = [0u8; 32];

/// A single validator's vote on a shard root.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct PbftShardVote {
    pub validator_id: [u8; 32],
    pub shard_root:   [u8; 32],
    pub sequence:     u64,
    pub vote_hash:    [u8; 32],  // SHA-256(validator_id || shard_root || sequence_be)
}

impl PbftShardVote {
    pub fn new(validator_id: [u8; 32], shard_root: [u8; 32], sequence: u64) -> Self {
        let vote_hash = Self::compute_vote_hash(&validator_id, &shard_root, sequence);
        Self { validator_id, shard_root, sequence, vote_hash }
    }

    fn compute_vote_hash(validator_id: &[u8; 32], shard_root: &[u8; 32], sequence: u64) -> [u8; 32] {
        let mut h = Sha256::new();
        h.update(validator_id);
        h.update(shard_root);
        h.update(sequence.to_be_bytes());
        h.finalize().into()
    }
}

/// Outcome of a PBFT tally round.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct PbftTallyResult {
    pub committed_root: [u8; 32],  // the agreed shard root
    pub agreeing_votes: usize,
    pub total_votes:    usize,
    pub round_hash:     [u8; 32],  // SHA-256(committed_root || agreeing_votes_be || sequence_be)
}

/// A round of PBFT shard voting.
pub struct PbftShardRound {
    pub sequence:     u64,
    /// Keyed by validator_id (BTreeMap — deterministic iteration, no HashMap).
    votes: BTreeMap<[u8; 32], PbftShardVote>,
    pub prev_hash:    [u8; 32],
}

impl PbftShardRound {
    pub fn new(sequence: u64, prev_hash: [u8; 32]) -> Self {
        Self { sequence, votes: BTreeMap::new(), prev_hash }
    }

    /// Submit or replace a validator's vote.
    pub fn cast_vote(&mut self, vote: PbftShardVote) {
        self.votes.insert(vote.validator_id, vote);
    }

    /// Returns the number of validators that have voted.
    pub fn vote_count(&self) -> usize { self.votes.len() }

    /// PBFT tally: requires ⌊2N/3⌋ + 1 agreeing votes (1/3-fault tolerance).
    /// `n_validators` is the full declared validator set size (not just those who voted).
    /// Returns `Some(result)` when quorum is met on any single root, `None` otherwise.
    pub fn tally(&self, n_validators: usize) -> Option<PbftTallyResult> {
        if n_validators == 0 || self.votes.is_empty() { return None; }
        let quorum = pbft_quorum(n_validators);

        // Tally votes per shard_root — BTreeMap for deterministic ordering.
        let mut counts: BTreeMap<[u8; 32], usize> = BTreeMap::new();
        for v in self.votes.values() {
            *counts.entry(v.shard_root).or_insert(0) += 1;
        }

        // Find any root that meets quorum.
        for (root, &count) in &counts {
            if count >= quorum {
                let round_hash = Self::compute_round_hash(root, count, self.sequence, &self.prev_hash);
                return Some(PbftTallyResult {
                    committed_root: *root,
                    agreeing_votes: count,
                    total_votes: self.votes.len(),
                    round_hash,
                });
            }
        }
        None
    }

    fn compute_round_hash(
        committed_root: &[u8; 32],
        agreeing_votes: usize,
        sequence: u64,
        prev_hash: &[u8; 32],
    ) -> [u8; 32] {
        let mut h = Sha256::new();
        h.update(prev_hash);
        h.update(committed_root);
        h.update((agreeing_votes as u64).to_be_bytes());
        h.update(sequence.to_be_bytes());
        h.finalize().into()
    }
}

/// PBFT quorum: minimum votes required for 1/3-fault tolerance.
/// Formula: ⌊2N/3⌋ + 1
pub fn pbft_quorum(n_validators: usize) -> usize {
    n_validators * 2 / 3 + 1
}

/// Append-only chain of PBFT tally results.
pub struct PbftShardChain {
    entries: Vec<(PbftTallyResult, [u8; 32])>,  // (result, prev_hash at time of commit)
    terminal_hash: [u8; 32],
}

impl PbftShardChain {
    pub fn new() -> Self {
        Self { entries: Vec::new(), terminal_hash: PBFT_GENESIS_HASH }
    }

    pub fn commit(&mut self, result: PbftTallyResult) {
        self.terminal_hash = result.round_hash;
        self.entries.push((result, self.terminal_hash));
    }

    pub fn terminal_hash(&self) -> [u8; 32] { self.terminal_hash }
    pub fn len(&self) -> usize { self.entries.len() }
    pub fn is_empty(&self) -> bool { self.entries.is_empty() }
}

impl Default for PbftShardChain {
    fn default() -> Self { Self::new() }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn vid(b: u8) -> [u8; 32] { let mut a = [0u8; 32]; a[0] = b; a }
    fn root(b: u8) -> [u8; 32] { let mut a = [0u8; 32]; a[31] = b; a }

    // 1. pbft_quorum(1) = 1
    #[test]
    fn quorum_one_validator() { assert_eq!(pbft_quorum(1), 1); }

    // 2. pbft_quorum(3) = 3  (classic minimal BFT)
    #[test]
    fn quorum_three_validators() { assert_eq!(pbft_quorum(3), 3); }

    // 3. pbft_quorum(4) = 3
    #[test]
    fn quorum_four_validators() { assert_eq!(pbft_quorum(4), 3); }

    // 4. pbft_quorum(10) = 7
    #[test]
    fn quorum_ten_validators() { assert_eq!(pbft_quorum(10), 7); }

    // 5. Empty round → no tally
    #[test]
    fn empty_round_no_tally() {
        let round = PbftShardRound::new(0, PBFT_GENESIS_HASH);
        assert!(round.tally(4).is_none());
    }

    // 6. n_validators=0 → no tally
    #[test]
    fn zero_validators_no_tally() {
        let mut round = PbftShardRound::new(0, PBFT_GENESIS_HASH);
        round.cast_vote(PbftShardVote::new(vid(1), root(1), 0));
        assert!(round.tally(0).is_none());
    }

    // 7. Below quorum → no commit
    #[test]
    fn below_quorum_no_commit() {
        let mut round = PbftShardRound::new(0, PBFT_GENESIS_HASH);
        // 4 validators, quorum=3 — only 2 votes for same root
        round.cast_vote(PbftShardVote::new(vid(1), root(42), 0));
        round.cast_vote(PbftShardVote::new(vid(2), root(42), 0));
        assert!(round.tally(4).is_none());
    }

    // 8. Exact quorum → commit
    #[test]
    fn exact_quorum_commits() {
        let mut round = PbftShardRound::new(0, PBFT_GENESIS_HASH);
        // 4 validators, quorum=3 — 3 votes for same root
        round.cast_vote(PbftShardVote::new(vid(1), root(99), 0));
        round.cast_vote(PbftShardVote::new(vid(2), root(99), 0));
        round.cast_vote(PbftShardVote::new(vid(3), root(99), 0));
        let result = round.tally(4).unwrap();
        assert_eq!(result.committed_root, root(99));
        assert_eq!(result.agreeing_votes, 3);
        assert_eq!(result.total_votes, 3);
    }

    // 9. Unanimous commit
    #[test]
    fn unanimous_commits() {
        let mut round = PbftShardRound::new(1, PBFT_GENESIS_HASH);
        for i in 0u8..5 {
            round.cast_vote(PbftShardVote::new(vid(i), root(77), 1));
        }
        let result = round.tally(5).unwrap();
        assert_eq!(result.committed_root, root(77));
        assert_eq!(result.agreeing_votes, 5);
    }

    // 10. Split vote — neither root reaches quorum
    #[test]
    fn split_vote_no_commit() {
        let mut round = PbftShardRound::new(0, PBFT_GENESIS_HASH);
        // 6 validators, quorum=5 — 3 for each root
        for i in 0u8..3 { round.cast_vote(PbftShardVote::new(vid(i), root(10), 0)); }
        for i in 3u8..6 { round.cast_vote(PbftShardVote::new(vid(i), root(20), 0)); }
        assert!(round.tally(6).is_none());
    }

    // 11. Duplicate vote (same validator) overwrites — counted once
    #[test]
    fn duplicate_vote_overwrites() {
        let mut round = PbftShardRound::new(0, PBFT_GENESIS_HASH);
        // Validator 1 votes twice for different roots
        round.cast_vote(PbftShardVote::new(vid(1), root(10), 0));
        round.cast_vote(PbftShardVote::new(vid(1), root(20), 0)); // overwrites
        round.cast_vote(PbftShardVote::new(vid(2), root(20), 0));
        round.cast_vote(PbftShardVote::new(vid(3), root(20), 0));
        // 3 validators declared, quorum=3 — all 3 must agree on root(20)
        let result = round.tally(3).unwrap();
        assert_eq!(result.committed_root, root(20));
        assert_eq!(result.agreeing_votes, 3);
    }

    // 12. vote_hash is deterministic
    #[test]
    fn vote_hash_determinism() {
        let v1 = PbftShardVote::new(vid(5), root(7), 42);
        let v2 = PbftShardVote::new(vid(5), root(7), 42);
        assert_eq!(v1.vote_hash, v2.vote_hash);
    }

    // 13. vote_hash differs when sequence differs
    #[test]
    fn vote_hash_differs_by_sequence() {
        let v1 = PbftShardVote::new(vid(5), root(7), 1);
        let v2 = PbftShardVote::new(vid(5), root(7), 2);
        assert_ne!(v1.vote_hash, v2.vote_hash);
    }

    // 14. round_hash differs when committed_root differs
    #[test]
    fn tally_hash_differs_by_root() {
        let mut r1 = PbftShardRound::new(0, PBFT_GENESIS_HASH);
        let mut r2 = PbftShardRound::new(0, PBFT_GENESIS_HASH);
        for i in 0u8..3 {
            r1.cast_vote(PbftShardVote::new(vid(i), root(1), 0));
            r2.cast_vote(PbftShardVote::new(vid(i), root(2), 0));
        }
        let h1 = r1.tally(3).unwrap().round_hash;
        let h2 = r2.tally(3).unwrap().round_hash;
        assert_ne!(h1, h2);
    }

    // 15. PBFT_GENESIS_HASH is all zeros
    #[test]
    fn genesis_hash_is_all_zeros() {
        assert_eq!(PBFT_GENESIS_HASH, [0u8; 32]);
    }

    // 16. Chain: commit advances terminal_hash
    #[test]
    fn chain_advances_terminal_hash() {
        let mut chain = PbftShardChain::new();
        assert_eq!(chain.terminal_hash(), PBFT_GENESIS_HASH);

        let mut round = PbftShardRound::new(0, PBFT_GENESIS_HASH);
        for i in 0u8..3 { round.cast_vote(PbftShardVote::new(vid(i), root(5), 0)); }
        let result = round.tally(3).unwrap();
        chain.commit(result);

        assert_ne!(chain.terminal_hash(), PBFT_GENESIS_HASH);
        assert_eq!(chain.len(), 1);
    }

    // 17. Determinism ×3: identical rounds produce identical tally
    #[test]
    fn tally_determinism_triple() {
        let make_result = || {
            let mut round = PbftShardRound::new(7, [0xABu8; 32]);
            for i in 0u8..4 { round.cast_vote(PbftShardVote::new(vid(i), root(3), 7)); }
            round.tally(5).unwrap()
        };
        let r1 = make_result();
        let r2 = make_result();
        let r3 = make_result();
        assert_eq!(r1, r2);
        assert_eq!(r2, r3);
    }
}
