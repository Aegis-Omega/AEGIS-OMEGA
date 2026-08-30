//! Gate 361 — Compaction Gossip Momentum Tracker (T2)
//! EPISTEMIC TIER: T2 (engineering hypothesis)
//!
//! Rolling directional trend signal for GossipJointCondition (Gate 360) across
//! a sliding observation window. Mirrors Gate 339 for the gossip subsystem.
//!
//! GOSSIP_MOMENTUM_WINDOW = 4 observations
//!
//! GossipMomentumDir:
//!   Improving — latest_score < earliest_score (lower ordinal = better)
//!   Stable    — latest_score == earliest_score
//!   Declining — latest_score > earliest_score
//!
//! Score = GossipJointCondition::as_u8() (0=Optimal … 3=Critical)
//! momentum_int = latest_score as i16 - earliest_score as i16
//!
//! GossipMomentumRecord:
//!   epoch:           u64
//!   joint_condition: GossipJointCondition
//!   score:           u8
//!   direction:       GossipMomentumDir
//!   momentum_int:    i16
//!   window_size:     u16
//!   record_hash:     [u8;32]
//!   prev_hash:       [u8;32]
//!
//! record_hash = SHA-256(prev[32] ‖ epoch_be8 ‖ score_byte ‖ dir_byte
//!                        ‖ momentum_int_be2 ‖ window_size_be2)
//!
//! GossipMomentumLog: append(), direction_count(), improving_epochs(),
//! declining_epochs(), verify_chain().

use sha2::{Sha256, Digest};
use crate::compaction_gossip_health_aggregator::GossipJointCondition;

pub const GOSSIP_MOMENTUM_GENESIS_HASH: [u8; 32] = [0u8; 32];
pub const GOSSIP_MOMENTUM_WINDOW: usize = 4;

// ─── GossipMomentumDir ────────────────────────────────────────────────────────

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
#[repr(u8)]
pub enum GossipMomentumDir {
    Improving = 0,
    Stable    = 1,
    Declining = 2,
}

impl GossipMomentumDir {
    pub fn as_u8(self) -> u8 { self as u8 }

    fn from_delta(delta: i16) -> Self {
        match delta.cmp(&0) {
            std::cmp::Ordering::Less    => Self::Improving,
            std::cmp::Ordering::Equal   => Self::Stable,
            std::cmp::Ordering::Greater => Self::Declining,
        }
    }
}

// ─── GossipMomentumRecord ─────────────────────────────────────────────────────

#[derive(Debug, Clone, PartialEq)]
pub struct GossipMomentumRecord {
    pub epoch:           u64,
    pub joint_condition: GossipJointCondition,
    pub score:           u8,
    pub direction:       GossipMomentumDir,
    pub momentum_int:    i16,
    pub window_size:     u16,
    pub prev_hash:       [u8; 32],
    pub record_hash:     [u8; 32],
}

fn compute_record_hash(
    prev:         &[u8; 32],
    epoch:        u64,
    score:        u8,
    dir:          GossipMomentumDir,
    momentum_int: i16,
    window_size:  u16,
) -> [u8; 32] {
    let mut h = Sha256::new();
    h.update(prev);
    h.update(epoch.to_be_bytes());
    h.update([score]);
    h.update([dir.as_u8()]);
    h.update(momentum_int.to_be_bytes());
    h.update(window_size.to_be_bytes());
    h.finalize().into()
}

// ─── GossipMomentumLog ────────────────────────────────────────────────────────

pub struct GossipMomentumLog {
    records: Vec<GossipMomentumRecord>,
    window:  [u8; GOSSIP_MOMENTUM_WINDOW], // ring buffer of recent scores
    w_len:   usize,
    w_head:  usize,
}

impl GossipMomentumLog {
    pub fn new() -> Self {
        Self { records: Vec::new(), window: [0u8; GOSSIP_MOMENTUM_WINDOW], w_len: 0, w_head: 0 }
    }

    pub fn record_count(&self)   -> usize { self.records.len() }
    pub fn is_empty(&self)       -> bool  { self.records.is_empty() }
    pub fn records(&self)        -> &[GossipMomentumRecord] { &self.records }
    pub fn latest(&self)         -> Option<&GossipMomentumRecord> { self.records.last() }

    pub fn improving_epochs(&self) -> usize {
        self.direction_count(GossipMomentumDir::Improving)
    }
    pub fn declining_epochs(&self) -> usize {
        self.direction_count(GossipMomentumDir::Declining)
    }
    pub fn direction_count(&self, dir: GossipMomentumDir) -> usize {
        self.records.iter().filter(|r| r.direction == dir).count()
    }

    pub fn append(&mut self, epoch: u64, jc: GossipJointCondition) -> &GossipMomentumRecord {
        let score = jc.as_u8();

        // Update ring buffer
        let slot = self.w_head % GOSSIP_MOMENTUM_WINDOW;
        self.window[slot] = score;
        self.w_head += 1;
        if self.w_len < GOSSIP_MOMENTUM_WINDOW { self.w_len += 1; }

        // Compute direction from window
        let window_size = self.w_len;
        let (earliest, latest) = if window_size == 1 {
            (score, score)
        } else {
            let oldest_slot = if self.w_len < GOSSIP_MOMENTUM_WINDOW {
                0
            } else {
                self.w_head % GOSSIP_MOMENTUM_WINDOW
            };
            let newest_slot = (self.w_head - 1) % GOSSIP_MOMENTUM_WINDOW;
            (self.window[oldest_slot], self.window[newest_slot])
        };

        let momentum_int = latest as i16 - earliest as i16;
        let direction    = GossipMomentumDir::from_delta(momentum_int);

        let prev = self.records.last().map(|r| r.record_hash)
            .unwrap_or(GOSSIP_MOMENTUM_GENESIS_HASH);
        let record_hash = compute_record_hash(&prev, epoch, score, direction, momentum_int, window_size as u16);

        self.records.push(GossipMomentumRecord {
            epoch, joint_condition: jc, score, direction,
            momentum_int, window_size: window_size as u16,
            prev_hash: prev, record_hash,
        });
        self.records.last().unwrap()
    }

    pub fn verify_chain(&self) -> (bool, Option<usize>) {
        let mut prev = GOSSIP_MOMENTUM_GENESIS_HASH;
        for (i, r) in self.records.iter().enumerate() {
            if r.prev_hash != prev { return (false, Some(i)); }
            let expected = compute_record_hash(
                &prev, r.epoch, r.score, r.direction, r.momentum_int, r.window_size,
            );
            if r.record_hash != expected { return (false, Some(i)); }
            prev = r.record_hash;
        }
        (true, None)
    }
}

impl Default for GossipMomentumLog {
    fn default() -> Self { Self::new() }
}

// ─── Tests ────────────────────────────────────────────────────────────────────

#[cfg(test)]
mod tests {
    use super::*;
    use GossipJointCondition as JC;

    #[test]
    fn single_entry_stable() {
        let mut log = GossipMomentumLog::new();
        let r = log.append(1, JC::Optimal);
        assert_eq!(r.direction, GossipMomentumDir::Stable);
        assert_eq!(r.momentum_int, 0);
        assert_eq!(r.window_size, 1);
    }

    #[test]
    fn improving_when_score_drops() {
        let mut log = GossipMomentumLog::new();
        log.append(1, JC::Critical); // score 3
        let r = log.append(2, JC::Optimal); // score 0; delta = 0-3 = -3
        assert_eq!(r.direction, GossipMomentumDir::Improving);
        assert!(r.momentum_int < 0);
    }

    #[test]
    fn declining_when_score_rises() {
        let mut log = GossipMomentumLog::new();
        log.append(1, JC::Optimal);   // score 0
        let r = log.append(2, JC::Critical); // score 3; delta=3
        assert_eq!(r.direction, GossipMomentumDir::Declining);
        assert!(r.momentum_int > 0);
    }

    #[test]
    fn stable_same_scores() {
        let mut log = GossipMomentumLog::new();
        log.append(1, JC::Nominal);
        let r = log.append(2, JC::Nominal);
        assert_eq!(r.direction, GossipMomentumDir::Stable);
        assert_eq!(r.momentum_int, 0);
    }

    #[test]
    fn window_caps_at_four() {
        let mut log = GossipMomentumLog::new();
        for i in 1..=6 {
            log.append(i, JC::Nominal);
        }
        assert_eq!(log.latest().unwrap().window_size, GOSSIP_MOMENTUM_WINDOW as u16);
    }

    #[test]
    fn direction_counts_correct() {
        let mut log = GossipMomentumLog::new();
        log.append(1, JC::Critical);  // score=3, stable (window size 1)
        log.append(2, JC::Optimal);   // score=0, improving (delta 0-3 = -3)
        log.append(3, JC::Critical);  // score=3, stable (earliest=3, latest=3 in window)
        log.append(4, JC::Critical);  // score=3, stable
        assert_eq!(log.declining_epochs(), 0);
        assert_eq!(log.improving_epochs(), 1);
    }

    #[test]
    fn record_hash_nonzero() {
        let mut log = GossipMomentumLog::new();
        let r = log.append(1, JC::Nominal);
        assert_ne!(r.record_hash, [0u8; 32]);
    }

    #[test]
    fn first_prev_is_genesis() {
        let mut log = GossipMomentumLog::new();
        let r = log.append(1, JC::Optimal);
        assert_eq!(r.prev_hash, GOSSIP_MOMENTUM_GENESIS_HASH);
    }

    #[test]
    fn hash_chain_links() {
        let mut log = GossipMomentumLog::new();
        log.append(1, JC::Optimal);
        let h0 = log.records()[0].record_hash;
        log.append(2, JC::Nominal);
        assert_eq!(log.records()[1].prev_hash, h0);
    }

    #[test]
    fn verify_chain_five_records_ok() {
        let mut log = GossipMomentumLog::new();
        let classes = [JC::Optimal, JC::Nominal, JC::Degraded, JC::Critical, JC::Optimal];
        for (i, &jc) in classes.iter().enumerate() { log.append(i as u64 + 1, jc); }
        let (ok, idx) = log.verify_chain();
        assert!(ok);
        assert!(idx.is_none());
    }

    #[test]
    fn verify_chain_detects_tamper() {
        let mut log = GossipMomentumLog::new();
        log.append(1, JC::Optimal);
        log.append(2, JC::Nominal);
        log.records[0].record_hash[0] ^= 0xFF;
        let (ok, idx) = log.verify_chain();
        assert!(!ok);
        assert_eq!(idx, Some(0));
    }

    #[test]
    fn record_hash_deterministic() {
        let mut l1 = GossipMomentumLog::new();
        let mut l2 = GossipMomentumLog::new();
        let h1 = l1.append(7, JC::Degraded).record_hash;
        let h2 = l2.append(7, JC::Degraded).record_hash;
        assert_eq!(h1, h2);
    }
}
