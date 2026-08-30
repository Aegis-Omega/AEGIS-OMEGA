//! Gate 261 — Consensus Ledger: distributed vote log with quorum certification (T2)
//! EPISTEMIC TIER: T2 (engineering hypothesis)
//!
//! Collects votes from multiple nodes on a proposed value (represented as [u8;32]).
//! Certifies quorum at the 1/φ threshold (integer arithmetic).
//!
//! VoteEntry:
//!   voter_id       — u32 (node casting the vote)
//!   proposal_hash  — [u8; 32] (the value being voted on)
//!   epoch          — u64
//!   vote_hash      — SHA-256(voter_id_be4 ‖ proposal_hash ‖ epoch_be8)
//!
//! ConsensusRound:
//!   round_id       — u64 (monotone round counter)
//!   proposal_hash  — [u8; 32] (the proposed value)
//!   votes          — BTreeMap<u32, VoteEntry> (one vote per voter_id)
//!   voter_count    — usize (size of known voter set)
//!   quorum_reached — bool = vote_count * 1_000_000 >= voter_count * 618_034
//!   round_hash     — SHA-256(round_id_be8 ‖ proposal_hash ‖ vote_count_be8 ‖ voter_count_be8)
//!
//! ConsensusCertificate:
//!   round_id, proposal_hash, vote_count, voter_count, quorum_reached
//!   cert_hash = SHA-256(round_hash ‖ prev_cert_hash)
//!
//! ConsensusLedger: hash-chained certificates across rounds.

use sha2::{Sha256, Digest};
use std::collections::BTreeMap;

// ─── Vote entry ───────────────────────────────────────────────────────────────

#[derive(Debug, Clone, PartialEq)]
pub struct VoteEntry {
    pub voter_id:      u32,
    pub proposal_hash: [u8; 32],
    pub epoch:         u64,
    pub vote_hash:     [u8; 32],
}

impl VoteEntry {
    pub fn is_hash_valid(&self) -> bool {
        compute_vote_hash(self.voter_id, &self.proposal_hash, self.epoch) == self.vote_hash
    }
}

fn compute_vote_hash(voter_id: u32, proposal_hash: &[u8; 32], epoch: u64) -> [u8; 32] {
    let mut h = Sha256::new();
    h.update(voter_id.to_be_bytes());
    h.update(proposal_hash);
    h.update(epoch.to_be_bytes());
    h.finalize().into()
}

pub fn build_vote(voter_id: u32, proposal_hash: [u8; 32], epoch: u64) -> VoteEntry {
    let vote_hash = compute_vote_hash(voter_id, &proposal_hash, epoch);
    VoteEntry { voter_id, proposal_hash, epoch, vote_hash }
}

// ─── Consensus round ─────────────────────────────────────────────────────────

#[derive(Debug, Clone)]
pub struct ConsensusRound {
    pub round_id:       u64,
    pub proposal_hash:  [u8; 32],
    pub votes:          BTreeMap<u32, VoteEntry>,
    pub voter_count:    usize,
    pub round_hash:     [u8; 32],
}

impl ConsensusRound {
    pub fn vote_count(&self) -> usize { self.votes.len() }

    pub fn quorum_reached(&self) -> bool {
        if self.voter_count == 0 { return false; }
        self.vote_count() * 1_000_000 >= self.voter_count * 618_034
    }

    /// Cast or replace a vote. Validates vote_hash; rejects mismatched proposal_hash.
    pub fn cast_vote(&mut self, vote: VoteEntry) -> Result<(), RoundError> {
        if !vote.is_hash_valid() {
            return Err(RoundError::InvalidVoteHash);
        }
        if vote.proposal_hash != self.proposal_hash {
            return Err(RoundError::ProposalMismatch);
        }
        self.votes.insert(vote.voter_id, vote);
        self.round_hash = compute_round_hash(
            self.round_id, &self.proposal_hash,
            self.votes.len(), self.voter_count);
        Ok(())
    }
}

fn compute_round_hash(
    round_id:    u64,
    proposal:    &[u8; 32],
    vote_count:  usize,
    voter_count: usize,
) -> [u8; 32] {
    let mut h = Sha256::new();
    h.update(round_id.to_be_bytes());
    h.update(proposal);
    h.update((vote_count as u64).to_be_bytes());
    h.update((voter_count as u64).to_be_bytes());
    h.finalize().into()
}

pub fn build_round(
    round_id:      u64,
    proposal_hash: [u8; 32],
    voter_count:   usize,
) -> ConsensusRound {
    let round_hash = compute_round_hash(round_id, &proposal_hash, 0, voter_count);
    ConsensusRound {
        round_id,
        proposal_hash,
        votes: BTreeMap::new(),
        voter_count,
        round_hash,
    }
}

#[derive(Debug)]
pub enum RoundError {
    InvalidVoteHash,
    ProposalMismatch,
}

impl RoundError {
    pub fn as_str(&self) -> &'static str {
        match self {
            Self::InvalidVoteHash  => "invalid vote hash",
            Self::ProposalMismatch => "proposal mismatch",
        }
    }
}

// ─── Consensus certificate ────────────────────────────────────────────────────

#[derive(Debug, Clone, PartialEq)]
pub struct ConsensusCertificate {
    pub round_id:       u64,
    pub proposal_hash:  [u8; 32],
    pub vote_count:     usize,
    pub voter_count:    usize,
    pub quorum_reached: bool,
    pub cert_hash:      [u8; 32],
    pub prev_cert_hash: [u8; 32],
}

pub const CERT_GENESIS_HASH: [u8; 32] = [0u8; 32];

fn compute_cert_hash(round_hash: &[u8; 32], prev: &[u8; 32]) -> [u8; 32] {
    let mut h = Sha256::new();
    h.update(prev);
    h.update(round_hash);
    h.finalize().into()
}

pub fn certify_round(round: &ConsensusRound, prev_cert_hash: &[u8; 32]) -> ConsensusCertificate {
    let cert_hash = compute_cert_hash(&round.round_hash, prev_cert_hash);
    ConsensusCertificate {
        round_id:       round.round_id,
        proposal_hash:  round.proposal_hash,
        vote_count:     round.vote_count(),
        voter_count:    round.voter_count,
        quorum_reached: round.quorum_reached(),
        cert_hash,
        prev_cert_hash: *prev_cert_hash,
    }
}

// ─── Consensus ledger ─────────────────────────────────────────────────────────

#[derive(Debug, Clone)]
pub struct ConsensusLedger {
    certs: Vec<ConsensusCertificate>,
}

#[derive(Debug)]
pub enum LedgerError {
    StaleRound,
}

impl LedgerError {
    pub fn as_str(&self) -> &'static str { "stale round" }
}

impl ConsensusLedger {
    pub fn new() -> Self { Self { certs: Vec::new() } }

    pub fn len(&self) -> usize { self.certs.len() }
    pub fn is_empty(&self) -> bool { self.certs.is_empty() }
    pub fn certs(&self) -> &[ConsensusCertificate] { &self.certs }
    pub fn latest(&self) -> Option<&ConsensusCertificate> { self.certs.last() }

    pub fn last_hash(&self) -> [u8; 32] {
        self.certs.last().map(|c| c.cert_hash).unwrap_or(CERT_GENESIS_HASH)
    }

    /// Append a certified round. round_id must be strictly increasing.
    pub fn append(&mut self, round: &ConsensusRound) -> Result<&ConsensusCertificate, LedgerError> {
        if let Some(last) = self.certs.last() {
            if round.round_id <= last.round_id {
                return Err(LedgerError::StaleRound);
            }
        }
        let prev = self.last_hash();
        let cert = certify_round(round, &prev);
        self.certs.push(cert);
        Ok(self.certs.last().unwrap())
    }

    /// Count of certified rounds where quorum was reached.
    pub fn quorum_count(&self) -> usize {
        self.certs.iter().filter(|c| c.quorum_reached).count()
    }

    /// Verify hash chain integrity.
    pub fn verify_chain(&self) -> (bool, Option<usize>) {
        let mut expected_prev = CERT_GENESIS_HASH;
        for (i, cert) in self.certs.iter().enumerate() {
            if cert.prev_cert_hash != expected_prev {
                return (false, Some(i));
            }
            expected_prev = cert.cert_hash;
        }
        (true, None)
    }
}

impl Default for ConsensusLedger {
    fn default() -> Self { Self::new() }
}

// ─── Tests ───────────────────────────────────────────────────────────────────

#[cfg(test)]
mod tests {
    use super::*;

    fn proposal() -> [u8; 32] { [0xAB; 32] }

    fn vote(voter: u32) -> VoteEntry {
        build_vote(voter, proposal(), 1)
    }

    fn round_with_votes(n_votes: u32, voter_count: usize) -> ConsensusRound {
        let mut r = build_round(1, proposal(), voter_count);
        for i in 0..n_votes {
            r.cast_vote(vote(i)).unwrap();
        }
        r
    }

    // ── VoteEntry ────────────────────────────────────────────────────────────

    #[test]
    fn vote_hash_valid() {
        let v = vote(1);
        assert!(v.is_hash_valid());
    }

    #[test]
    fn tampered_voter_id_fails() {
        let mut v = vote(1);
        v.voter_id = 99;
        assert!(!v.is_hash_valid());
    }

    #[test]
    fn vote_hash_deterministic() {
        let v1 = vote(7);
        let v2 = vote(7);
        assert_eq!(v1.vote_hash, v2.vote_hash);
    }

    // ── ConsensusRound ────────────────────────────────────────────────────────

    #[test]
    fn empty_round_no_quorum() {
        let r = build_round(1, proposal(), 5);
        assert_eq!(r.vote_count(), 0);
        assert!(!r.quorum_reached());
    }

    #[test]
    fn quorum_at_phi_threshold() {
        // 5/8 = 0.625 > 0.618034 → quorum
        let r = round_with_votes(5, 8);
        assert!(r.quorum_reached());
    }

    #[test]
    fn no_quorum_below_phi() {
        // 4/8 = 0.5 < 0.618034
        let r = round_with_votes(4, 8);
        assert!(!r.quorum_reached());
    }

    #[test]
    fn proposal_mismatch_rejected() {
        let mut r = build_round(1, proposal(), 3);
        let bad = build_vote(1, [0xFF; 32], 1); // wrong proposal
        assert!(matches!(r.cast_vote(bad), Err(RoundError::ProposalMismatch)));
    }

    #[test]
    fn invalid_vote_hash_rejected() {
        let mut r = build_round(1, proposal(), 3);
        let mut bad = vote(1);
        bad.vote_hash[0] ^= 0xFF;
        assert!(matches!(r.cast_vote(bad), Err(RoundError::InvalidVoteHash)));
    }

    #[test]
    fn round_hash_changes_on_vote() {
        let mut r = build_round(1, proposal(), 3);
        let before = r.round_hash;
        r.cast_vote(vote(1)).unwrap();
        assert_ne!(r.round_hash, before);
    }

    #[test]
    fn duplicate_vote_replaces() {
        let mut r = build_round(1, proposal(), 3);
        r.cast_vote(vote(1)).unwrap();
        r.cast_vote(vote(1)).unwrap(); // same voter_id
        assert_eq!(r.vote_count(), 1);
    }

    // ── ConsensusCertificate / ConsensusLedger ────────────────────────────────

    #[test]
    fn certify_quorum_round() {
        let r = round_with_votes(5, 8);
        let cert = certify_round(&r, &CERT_GENESIS_HASH);
        assert!(cert.quorum_reached);
        assert_eq!(cert.vote_count, 5);
        assert_eq!(cert.voter_count, 8);
    }

    #[test]
    fn cert_hash_nonzero() {
        let r = round_with_votes(3, 5);
        let cert = certify_round(&r, &CERT_GENESIS_HASH);
        assert_ne!(cert.cert_hash, [0u8; 32]);
    }

    #[test]
    fn cert_hash_deterministic() {
        let r1 = round_with_votes(5, 8);
        let r2 = round_with_votes(5, 8);
        let c1 = certify_round(&r1, &CERT_GENESIS_HASH);
        let c2 = certify_round(&r2, &CERT_GENESIS_HASH);
        assert_eq!(c1.cert_hash, c2.cert_hash);
    }

    #[test]
    fn ledger_new_empty() {
        let l = ConsensusLedger::new();
        assert!(l.is_empty());
        assert_eq!(l.last_hash(), CERT_GENESIS_HASH);
    }

    #[test]
    fn ledger_appends_rounds() {
        let mut l = ConsensusLedger::new();
        let r1 = round_with_votes(5, 8);
        let mut r2 = build_round(2, [0xCD; 32], 8);
        r2.cast_vote(build_vote(1, [0xCD; 32], 2)).unwrap();
        l.append(&r1).unwrap();
        l.append(&r2).unwrap();
        assert_eq!(l.len(), 2);
    }

    #[test]
    fn stale_round_rejected() {
        let mut l = ConsensusLedger::new();
        l.append(&round_with_votes(5, 8)).unwrap();
        let mut stale = build_round(1, proposal(), 8); // same round_id
        stale.cast_vote(vote(1)).unwrap();
        assert!(matches!(l.append(&stale), Err(LedgerError::StaleRound)));
    }

    #[test]
    fn quorum_count_tracked() {
        let mut l = ConsensusLedger::new();
        l.append(&round_with_votes(5, 8)).unwrap(); // quorum
        let r2 = build_round(2, [0x01; 32], 8);    // no votes → no quorum
        l.append(&r2).unwrap();
        assert_eq!(l.quorum_count(), 1);
    }

    #[test]
    fn verify_chain_valid() {
        let mut l = ConsensusLedger::new();
        l.append(&round_with_votes(5, 8)).unwrap();
        let mut r2 = build_round(2, [0xCD; 32], 8);
        r2.cast_vote(build_vote(0, [0xCD; 32], 2)).unwrap();
        l.append(&r2).unwrap();
        let (valid, broken) = l.verify_chain();
        assert!(valid);
        assert!(broken.is_none());
    }

    #[test]
    fn round_error_as_str() {
        assert_eq!(RoundError::InvalidVoteHash.as_str(),  "invalid vote hash");
        assert_eq!(RoundError::ProposalMismatch.as_str(), "proposal mismatch");
    }
}
