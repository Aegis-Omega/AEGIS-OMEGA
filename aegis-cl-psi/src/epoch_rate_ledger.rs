//! Gate 316 — Gossip Epoch Rate Ledger: per-epoch message throughput accounting (T2)
//! EPISTEMIC TIER: T2 (engineering hypothesis)
//!
//! Records the number of messages sent, received, and dropped in each gossip epoch.
//! A rate limit cap (MAX_MESSAGES_PER_EPOCH) triggers the Exceeded flag when the
//! combined sent+received count exceeds it. Epochs must be submitted in strictly
//! increasing order; submitting the same or older epoch returns Err(StaleEpoch).
//! All epoch summaries are hash-chained for audit.
//!
//! Constants:
//!   MAX_MESSAGES_PER_EPOCH: u64 = 10_000
//!
//! EpochRateStatus: Normal | Exceeded
//!
//! EpochRateRecord:
//!   epoch, sent, received, dropped, status
//!   record_hash = SHA-256(prev ‖ epoch_be8 ‖ sent_be8 ‖ recv_be8 ‖ dropped_be8 ‖ status_byte)
//!   prev_hash
//!
//! EpochRateLedger:
//!   seal_epoch(epoch, sent, received, dropped) → Result<EpochRateStatus, RateLedgerError>
//!     Seals an epoch summary; Exceeded if sent+received > MAX_MESSAGES_PER_EPOCH.
//!   total_sent() → u64
//!   total_received() → u64
//!   total_dropped() → u64
//!   exceeded_epoch_count() → usize
//!   verify_chain() → (bool, Option<usize>)

use sha2::{Sha256, Digest};

pub const MAX_MESSAGES_PER_EPOCH: u64 = 10_000;

// ─── Epoch rate status ────────────────────────────────────────────────────────

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum EpochRateStatus {
    Normal   = 0,
    Exceeded = 1,
}

impl EpochRateStatus {
    pub fn status_byte(self) -> u8 { self as u8 }
}

// ─── Epoch rate record ────────────────────────────────────────────────────────

#[derive(Debug, Clone, PartialEq)]
pub struct EpochRateRecord {
    pub epoch:       u64,
    pub sent:        u64,
    pub received:    u64,
    pub dropped:     u64,
    pub status:      EpochRateStatus,
    pub record_hash: [u8; 32],
    pub prev_hash:   [u8; 32],
}

pub const RATE_LEDGER_GENESIS_HASH: [u8; 32] = [0u8; 32];

fn compute_rate_hash(
    epoch:    u64,
    sent:     u64,
    received: u64,
    dropped:  u64,
    status:   EpochRateStatus,
    prev:     &[u8; 32],
) -> [u8; 32] {
    let mut h = Sha256::new();
    h.update(prev);
    h.update(epoch.to_be_bytes());
    h.update(sent.to_be_bytes());
    h.update(received.to_be_bytes());
    h.update(dropped.to_be_bytes());
    h.update([status.status_byte()]);
    h.finalize().into()
}

pub fn build_rate_record(
    epoch:     u64,
    sent:      u64,
    received:  u64,
    dropped:   u64,
    status:    EpochRateStatus,
    prev_hash: &[u8; 32],
) -> EpochRateRecord {
    let record_hash = compute_rate_hash(epoch, sent, received, dropped, status, prev_hash);
    EpochRateRecord { epoch, sent, received, dropped, status, record_hash, prev_hash: *prev_hash }
}

// ─── Errors ───────────────────────────────────────────────────────────────────

#[derive(Debug, PartialEq, Eq)]
pub enum RateLedgerError {
    StaleEpoch,
}

// ─── EpochRateLedger ─────────────────────────────────────────────────────────

#[derive(Debug, Clone)]
pub struct EpochRateLedger {
    records:    Vec<EpochRateRecord>,
    last_epoch: Option<u64>,
}

impl EpochRateLedger {
    pub fn new() -> Self { Self { records: Vec::new(), last_epoch: None } }

    pub fn len(&self)      -> usize { self.records.len() }
    pub fn is_empty(&self) -> bool  { self.records.is_empty() }
    pub fn records(&self)  -> &[EpochRateRecord] { &self.records }

    fn last_hash(&self) -> [u8; 32] {
        self.records.last().map(|r| r.record_hash).unwrap_or(RATE_LEDGER_GENESIS_HASH)
    }

    /// Seal a completed epoch. Returns status (Normal|Exceeded).
    /// Epoch must be strictly greater than the last sealed epoch.
    pub fn seal_epoch(
        &mut self,
        epoch:    u64,
        sent:     u64,
        received: u64,
        dropped:  u64,
    ) -> Result<EpochRateStatus, RateLedgerError> {
        if let Some(last) = self.last_epoch {
            if epoch <= last {
                return Err(RateLedgerError::StaleEpoch);
            }
        }

        let total = sent.saturating_add(received);
        let status = if total > MAX_MESSAGES_PER_EPOCH {
            EpochRateStatus::Exceeded
        } else {
            EpochRateStatus::Normal
        };

        let prev = self.last_hash();
        let r = build_rate_record(epoch, sent, received, dropped, status, &prev);
        self.records.push(r);
        self.last_epoch = Some(epoch);
        Ok(status)
    }

    pub fn total_sent(&self) -> u64 {
        self.records.iter().map(|r| r.sent).fold(0u64, u64::saturating_add)
    }

    pub fn total_received(&self) -> u64 {
        self.records.iter().map(|r| r.received).fold(0u64, u64::saturating_add)
    }

    pub fn total_dropped(&self) -> u64 {
        self.records.iter().map(|r| r.dropped).fold(0u64, u64::saturating_add)
    }

    pub fn exceeded_epoch_count(&self) -> usize {
        self.records.iter().filter(|r| r.status == EpochRateStatus::Exceeded).count()
    }

    pub fn verify_chain(&self) -> (bool, Option<usize>) {
        let mut expected_prev = RATE_LEDGER_GENESIS_HASH;
        for (i, r) in self.records.iter().enumerate() {
            if r.prev_hash != expected_prev { return (false, Some(i)); }
            let recomputed = compute_rate_hash(r.epoch, r.sent, r.received, r.dropped, r.status, &r.prev_hash);
            if recomputed != r.record_hash { return (false, Some(i)); }
            expected_prev = r.record_hash;
        }
        (true, None)
    }
}

impl Default for EpochRateLedger {
    fn default() -> Self { Self::new() }
}

// ─── Tests ────────────────────────────────────────────────────────────────────

#[cfg(test)]
mod tests {
    use super::*;

    // ── EpochRateStatus ───────────────────────────────────────────────────────

    #[test]
    fn status_bytes() {
        assert_eq!(EpochRateStatus::Normal.status_byte(),   0);
        assert_eq!(EpochRateStatus::Exceeded.status_byte(), 1);
    }

    // ── build_rate_record ─────────────────────────────────────────────────────

    #[test]
    fn record_hash_nonzero() {
        let r = build_rate_record(1, 100, 200, 5, EpochRateStatus::Normal, &RATE_LEDGER_GENESIS_HASH);
        assert_ne!(r.record_hash, [0u8; 32]);
    }

    #[test]
    fn record_hash_deterministic() {
        let r1 = build_rate_record(1, 100, 200, 5, EpochRateStatus::Normal, &RATE_LEDGER_GENESIS_HASH);
        let r2 = build_rate_record(1, 100, 200, 5, EpochRateStatus::Normal, &RATE_LEDGER_GENESIS_HASH);
        assert_eq!(r1.record_hash, r2.record_hash);
    }

    // ── EpochRateLedger ───────────────────────────────────────────────────────

    #[test]
    fn normal_epoch() {
        let mut l = EpochRateLedger::new();
        let s = l.seal_epoch(1, 1000, 2000, 10).unwrap();
        assert_eq!(s, EpochRateStatus::Normal); // 3000 ≤ 10_000
    }

    #[test]
    fn exceeded_epoch() {
        let mut l = EpochRateLedger::new();
        // sent + received = 6000 + 5000 = 11000 > MAX
        let s = l.seal_epoch(1, 6000, 5000, 0).unwrap();
        assert_eq!(s, EpochRateStatus::Exceeded);
        assert_eq!(l.exceeded_epoch_count(), 1);
    }

    #[test]
    fn stale_epoch_rejected() {
        let mut l = EpochRateLedger::new();
        l.seal_epoch(5, 100, 100, 0).unwrap();
        assert_eq!(l.seal_epoch(5, 100, 100, 0), Err(RateLedgerError::StaleEpoch));
        assert_eq!(l.seal_epoch(3, 100, 100, 0), Err(RateLedgerError::StaleEpoch));
    }

    #[test]
    fn totals_accumulate() {
        let mut l = EpochRateLedger::new();
        l.seal_epoch(1, 100, 200, 5).unwrap();
        l.seal_epoch(2, 300, 400, 10).unwrap();
        assert_eq!(l.total_sent(),     400);
        assert_eq!(l.total_received(), 600);
        assert_eq!(l.total_dropped(),  15);
    }

    #[test]
    fn chain_links_correct() {
        let mut l = EpochRateLedger::new();
        l.seal_epoch(1, 100, 100, 0).unwrap();
        l.seal_epoch(2, 200, 200, 0).unwrap();
        assert_eq!(l.records()[1].prev_hash, l.records()[0].record_hash);
    }

    #[test]
    fn verify_chain_valid() {
        let mut l = EpochRateLedger::new();
        for i in 1u64..=5 {
            l.seal_epoch(i, i * 100, i * 50, i).unwrap();
        }
        let (valid, broken) = l.verify_chain();
        assert!(valid);
        assert!(broken.is_none());
    }

    #[test]
    fn exactly_at_limit_is_normal() {
        let mut l = EpochRateLedger::new();
        // 5000 + 5000 = 10000 == MAX — not exceeded
        let s = l.seal_epoch(1, 5000, 5000, 0).unwrap();
        assert_eq!(s, EpochRateStatus::Normal);
    }

    #[test]
    fn one_over_limit_is_exceeded() {
        let mut l = EpochRateLedger::new();
        // 5001 + 5000 = 10001 > MAX
        let s = l.seal_epoch(1, 5001, 5000, 0).unwrap();
        assert_eq!(s, EpochRateStatus::Exceeded);
    }
}
