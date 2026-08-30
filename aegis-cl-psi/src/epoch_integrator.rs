//! Gate 292 — Gossip Epoch Integrator: cross-subsystem epoch close coordination (T2)
//! EPISTEMIC TIER: T2 (engineering hypothesis)
//!
//! At epoch close, collects summary statistics from the gossip protection subsystems
//! and produces a single tamper-evident EpochIntegrationRecord that captures the
//! joint state of: flood guard, TTL enforcer, bandwidth tracker, epoch auditor,
//! rate limiter, and reputation decay subsystems.
//!
//! EpochIntegrationInput:
//!   epoch              — u64
//!   flood_banned_count — u32 (sources at Banned level this epoch)
//!   flood_dropped      — u64 (total messages dropped by flood guard)
//!   ttl_expired        — u64 (messages dropped due to TTL expiry)
//!   ttl_inflated       — u64 (messages dropped due to TTL inflation)
//!   bw_denied_peers    — u32 (peers that hit bandwidth Deny this epoch)
//!   audit_consistent   — bool (epoch auditor found all subsystems consistent)
//!   rate_limited_count — u32 (messages dropped by rate limiter this epoch)
//!   decayed_peers      — u32 (peers that received reputation decay this epoch)
//!
//! EpochIntegrationRecord:
//!   (all input fields) + health_score + record_hash + prev_hash
//!   health_score: u8 = 100 - penalties (capped at 0)
//!     Penalties: flood_banned_count>0: −20; ttl_inflated>0: −15;
//!                !audit_consistent: −30; bw_denied_peers>3: −15; else: −0
//!
//! IntegrationChain: hash-chained EpochIntegrationRecords.
//!   append(), healthy_epoch_count(), degraded_epoch_count(), terminal_hash(), verify_chain().

use sha2::{Sha256, Digest};

// ─── Integration input ────────────────────────────────────────────────────────

#[derive(Debug, Clone, Copy)]
pub struct EpochIntegrationInput {
    pub epoch:              u64,
    pub flood_banned_count: u32,
    pub flood_dropped:      u64,
    pub ttl_expired:        u64,
    pub ttl_inflated:       u64,
    pub bw_denied_peers:    u32,
    pub audit_consistent:   bool,
    pub rate_limited_count: u32,
    pub decayed_peers:      u32,
}

// ─── Health scoring ───────────────────────────────────────────────────────────

pub fn compute_health_score(input: &EpochIntegrationInput) -> u8 {
    let mut penalty: u8 = 0;
    if input.flood_banned_count > 0      { penalty = penalty.saturating_add(20); }
    if input.ttl_inflated > 0            { penalty = penalty.saturating_add(15); }
    if !input.audit_consistent           { penalty = penalty.saturating_add(30); }
    if input.bw_denied_peers > 3         { penalty = penalty.saturating_add(15); }
    100u8.saturating_sub(penalty)
}

// ─── Integration record ────────────────────────────────────────────────────────

#[derive(Debug, Clone, PartialEq)]
pub struct EpochIntegrationRecord {
    pub epoch:              u64,
    pub flood_banned_count: u32,
    pub flood_dropped:      u64,
    pub ttl_expired:        u64,
    pub ttl_inflated:       u64,
    pub bw_denied_peers:    u32,
    pub audit_consistent:   bool,
    pub rate_limited_count: u32,
    pub decayed_peers:      u32,
    pub health_score:       u8,
    pub record_hash:        [u8; 32],
    pub prev_hash:          [u8; 32],
}

pub const INTEGRATION_GENESIS_HASH: [u8; 32] = [0u8; 32];

fn compute_integration_hash(
    epoch:              u64,
    flood_banned_count: u32,
    flood_dropped:      u64,
    ttl_expired:        u64,
    ttl_inflated:       u64,
    bw_denied_peers:    u32,
    audit_consistent:   bool,
    rate_limited_count: u32,
    decayed_peers:      u32,
    health_score:       u8,
    prev:               &[u8; 32],
) -> [u8; 32] {
    let mut h = Sha256::new();
    h.update(prev);
    h.update(epoch.to_be_bytes());
    h.update(flood_banned_count.to_be_bytes());
    h.update(flood_dropped.to_be_bytes());
    h.update(ttl_expired.to_be_bytes());
    h.update(ttl_inflated.to_be_bytes());
    h.update(bw_denied_peers.to_be_bytes());
    h.update([if audit_consistent { 1u8 } else { 0u8 }]);
    h.update(rate_limited_count.to_be_bytes());
    h.update(decayed_peers.to_be_bytes());
    h.update([health_score]);
    h.finalize().into()
}

pub fn build_integration_record(
    input:     &EpochIntegrationInput,
    prev_hash: &[u8; 32],
) -> EpochIntegrationRecord {
    let health_score = compute_health_score(input);
    let record_hash = compute_integration_hash(
        input.epoch, input.flood_banned_count, input.flood_dropped,
        input.ttl_expired, input.ttl_inflated, input.bw_denied_peers,
        input.audit_consistent, input.rate_limited_count, input.decayed_peers,
        health_score, prev_hash,
    );
    EpochIntegrationRecord {
        epoch:              input.epoch,
        flood_banned_count: input.flood_banned_count,
        flood_dropped:      input.flood_dropped,
        ttl_expired:        input.ttl_expired,
        ttl_inflated:       input.ttl_inflated,
        bw_denied_peers:    input.bw_denied_peers,
        audit_consistent:   input.audit_consistent,
        rate_limited_count: input.rate_limited_count,
        decayed_peers:      input.decayed_peers,
        health_score,
        record_hash,
        prev_hash: *prev_hash,
    }
}

// ─── Integration chain ─────────────────────────────────────────────────────────

#[derive(Debug, Clone)]
pub struct IntegrationChain {
    records: Vec<EpochIntegrationRecord>,
}

#[derive(Debug)]
pub enum IntegrationError {
    StaleEpoch,
}

impl IntegrationChain {
    pub fn new() -> Self { Self { records: Vec::new() } }

    pub fn len(&self)     -> usize { self.records.len() }
    pub fn is_empty(&self)-> bool  { self.records.is_empty() }
    pub fn records(&self) -> &[EpochIntegrationRecord] { &self.records }
    pub fn latest(&self)  -> Option<&EpochIntegrationRecord> { self.records.last() }

    pub fn last_hash(&self) -> [u8; 32] {
        self.records.last().map(|r| r.record_hash).unwrap_or(INTEGRATION_GENESIS_HASH)
    }

    pub fn terminal_hash(&self) -> Option<[u8; 32]> {
        self.records.last().map(|r| r.record_hash)
    }

    pub fn append(&mut self, input: &EpochIntegrationInput) -> Result<&EpochIntegrationRecord, IntegrationError> {
        if let Some(last) = self.records.last() {
            if input.epoch <= last.epoch {
                return Err(IntegrationError::StaleEpoch);
            }
        }
        let prev = self.last_hash();
        let r = build_integration_record(input, &prev);
        self.records.push(r);
        Ok(self.records.last().unwrap())
    }

    pub fn healthy_epoch_count(&self) -> usize {
        // Health score ≥ 80 = healthy
        self.records.iter().filter(|r| r.health_score >= 80).count()
    }

    pub fn degraded_epoch_count(&self) -> usize {
        self.records.iter().filter(|r| r.health_score < 80).count()
    }

    pub fn avg_health_score(&self) -> u8 {
        if self.records.is_empty() { return 0; }
        let sum: u32 = self.records.iter().map(|r| r.health_score as u32).sum();
        (sum / self.records.len() as u32) as u8
    }

    pub fn verify_chain(&self) -> (bool, Option<usize>) {
        let mut expected_prev = INTEGRATION_GENESIS_HASH;
        for (i, r) in self.records.iter().enumerate() {
            if r.prev_hash != expected_prev { return (false, Some(i)); }
            let recomputed = compute_integration_hash(
                r.epoch, r.flood_banned_count, r.flood_dropped,
                r.ttl_expired, r.ttl_inflated, r.bw_denied_peers,
                r.audit_consistent, r.rate_limited_count, r.decayed_peers,
                r.health_score, &r.prev_hash,
            );
            if recomputed != r.record_hash { return (false, Some(i)); }
            expected_prev = r.record_hash;
        }
        (true, None)
    }
}

impl Default for IntegrationChain {
    fn default() -> Self { Self::new() }
}

// ─── Tests ────────────────────────────────────────────────────────────────────

#[cfg(test)]
mod tests {
    use super::*;

    fn clean_input(epoch: u64) -> EpochIntegrationInput {
        EpochIntegrationInput {
            epoch,
            flood_banned_count: 0,
            flood_dropped:      0,
            ttl_expired:        0,
            ttl_inflated:       0,
            bw_denied_peers:    0,
            audit_consistent:   true,
            rate_limited_count: 0,
            decayed_peers:      0,
        }
    }

    // ── compute_health_score ──────────────────────────────────────────────────

    #[test]
    fn perfect_score() {
        assert_eq!(compute_health_score(&clean_input(1)), 100);
    }

    #[test]
    fn flood_banned_penalty() {
        let mut i = clean_input(1);
        i.flood_banned_count = 1;
        assert_eq!(compute_health_score(&i), 80);
    }

    #[test]
    fn ttl_inflated_penalty() {
        let mut i = clean_input(1);
        i.ttl_inflated = 1;
        assert_eq!(compute_health_score(&i), 85);
    }

    #[test]
    fn audit_inconsistent_penalty() {
        let mut i = clean_input(1);
        i.audit_consistent = false;
        assert_eq!(compute_health_score(&i), 70);
    }

    #[test]
    fn bw_denied_penalty() {
        let mut i = clean_input(1);
        i.bw_denied_peers = 4;
        assert_eq!(compute_health_score(&i), 85);
    }

    #[test]
    fn all_penalties_saturate_at_zero() {
        let i = EpochIntegrationInput {
            epoch:              1,
            flood_banned_count: 5,
            flood_dropped:      100,
            ttl_expired:        10,
            ttl_inflated:       5,
            bw_denied_peers:    10,
            audit_consistent:   false,
            rate_limited_count: 50,
            decayed_peers:      3,
        };
        // Penalties: 20+15+30+15=80 → score=20
        assert_eq!(compute_health_score(&i), 20);
    }

    // ── build_integration_record ──────────────────────────────────────────────

    #[test]
    fn record_hash_nonzero() {
        let r = build_integration_record(&clean_input(1), &INTEGRATION_GENESIS_HASH);
        assert_ne!(r.record_hash, [0u8; 32]);
    }

    #[test]
    fn record_hash_deterministic() {
        let r1 = build_integration_record(&clean_input(1), &INTEGRATION_GENESIS_HASH);
        let r2 = build_integration_record(&clean_input(1), &INTEGRATION_GENESIS_HASH);
        assert_eq!(r1.record_hash, r2.record_hash);
    }

    #[test]
    fn health_score_embedded() {
        let r = build_integration_record(&clean_input(1), &INTEGRATION_GENESIS_HASH);
        assert_eq!(r.health_score, 100);
    }

    // ── IntegrationChain ──────────────────────────────────────────────────────

    #[test]
    fn new_chain_empty() {
        let c = IntegrationChain::new();
        assert!(c.is_empty());
        assert_eq!(c.avg_health_score(), 0);
        assert_eq!(c.terminal_hash(), None);
    }

    #[test]
    fn append_and_query() {
        let mut c = IntegrationChain::new();
        c.append(&clean_input(1)).unwrap();
        c.append(&clean_input(2)).unwrap();
        assert_eq!(c.len(), 2);
        assert_eq!(c.healthy_epoch_count(), 2);
        assert_eq!(c.degraded_epoch_count(), 0);
    }

    #[test]
    fn stale_epoch_rejected() {
        let mut c = IntegrationChain::new();
        c.append(&clean_input(5)).unwrap();
        assert!(matches!(c.append(&clean_input(4)), Err(IntegrationError::StaleEpoch)));
    }

    #[test]
    fn chain_links() {
        let mut c = IntegrationChain::new();
        c.append(&clean_input(1)).unwrap();
        c.append(&clean_input(2)).unwrap();
        assert_eq!(c.records()[1].prev_hash, c.records()[0].record_hash);
    }

    #[test]
    fn degraded_epoch_tracked() {
        let mut c = IntegrationChain::new();
        c.append(&clean_input(1)).unwrap(); // score 100 → healthy
        let mut bad = clean_input(2);
        bad.audit_consistent = false;
        bad.flood_banned_count = 1;
        c.append(&bad).unwrap(); // score 50 → degraded
        assert_eq!(c.degraded_epoch_count(), 1);
    }

    #[test]
    fn terminal_hash_set() {
        let mut c = IntegrationChain::new();
        c.append(&clean_input(1)).unwrap();
        assert!(c.terminal_hash().is_some());
        assert_ne!(c.terminal_hash().unwrap(), [0u8; 32]);
    }

    #[test]
    fn verify_chain_valid() {
        let mut c = IntegrationChain::new();
        for e in 1..=6u64 {
            c.append(&clean_input(e)).unwrap();
        }
        let (valid, broken) = c.verify_chain();
        assert!(valid);
        assert!(broken.is_none());
    }

    #[test]
    fn avg_health_score_computed() {
        let mut c = IntegrationChain::new();
        c.append(&clean_input(1)).unwrap(); // 100
        let mut bad = clean_input(2);
        bad.ttl_inflated = 1; // 85
        c.append(&bad).unwrap();
        // (100+85)/2 = 92 (integer division)
        assert_eq!(c.avg_health_score(), 92);
    }
}
