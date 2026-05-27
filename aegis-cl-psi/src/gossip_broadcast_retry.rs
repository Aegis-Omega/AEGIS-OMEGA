//! Gate 416 — Gossip Broadcast Retry Log (T2)
//! EPISTEMIC TIER: T2 (engineering hypothesis)
//!
//! Per-epoch tracking of gossip broadcast retries. A retry occurs when a
//! message must be resent to a peer that did not acknowledge the first attempt.
//!
//! retry_count:    u32 — number of retry events in this epoch
//! total_sent:     u32 — total message sends including retries
//! retry_rate_pct: u32 — (retry_count * 100) / max(total_sent, 1), capped at 100
//! high_retry:     bool — retry_rate_pct > RETRY_CEILING (25)
//!
//! RETRY_CEILING: u32 = 25  (25% — above this the gossip layer is stressed)
//!
//! GossipBroadcastRetryEntry (hash-chained):
//!   epoch_end:      u64
//!   retry_count:    u32
//!   total_sent:     u32
//!   retry_rate_pct: u32
//!   high_retry:     bool
//!   entry_hash:     [u8;32]
//!   prev_hash:      [u8;32]
//!
//! entry_hash = SHA-256(prev[32] ‖ epoch_end_be8 ‖ retry_count_be4
//!                       ‖ total_sent_be4 ‖ retry_rate_pct_be4 ‖ high_retry_byte)
//!
//! GossipBroadcastRetryLog: record(epoch_end, retry_count, total_sent),
//!   high_retry_count(), total_retries(), mean_retry_rate_pct(), verify_chain().

use sha2::{Sha256, Digest};

pub const GOSSIP_BROADCAST_RETRY_GENESIS_HASH: [u8; 32] = [0u8; 32];
pub const RETRY_CEILING: u32 = 25;

// ─── GossipBroadcastRetryEntry ────────────────────────────────────────────────

#[derive(Debug, Clone, PartialEq)]
pub struct GossipBroadcastRetryEntry {
    pub epoch_end:      u64,
    pub retry_count:    u32,
    pub total_sent:     u32,
    pub retry_rate_pct: u32,
    pub high_retry:     bool,
    pub entry_hash:     [u8; 32],
    pub prev_hash:      [u8; 32],
}

fn compute_broadcast_retry_hash(
    prev:           &[u8; 32],
    epoch_end:      u64,
    retry_count:    u32,
    total_sent:     u32,
    retry_rate_pct: u32,
    high_retry:     bool,
) -> [u8; 32] {
    let mut h = Sha256::new();
    h.update(prev);
    h.update(epoch_end.to_be_bytes());
    h.update(retry_count.to_be_bytes());
    h.update(total_sent.to_be_bytes());
    h.update(retry_rate_pct.to_be_bytes());
    h.update([high_retry as u8]);
    h.finalize().into()
}

// ─── GossipBroadcastRetryLog ──────────────────────────────────────────────────

pub struct GossipBroadcastRetryLog {
    entries: Vec<GossipBroadcastRetryEntry>,
}

impl GossipBroadcastRetryLog {
    pub fn new() -> Self { Self { entries: Vec::new() } }

    pub fn entry_count(&self) -> usize { self.entries.len() }
    pub fn is_empty(&self)    -> bool  { self.entries.is_empty() }
    pub fn entries(&self)     -> &[GossipBroadcastRetryEntry] { &self.entries }
    pub fn latest(&self)      -> Option<&GossipBroadcastRetryEntry> { self.entries.last() }

    /// Count of epochs where high_retry == true.
    pub fn high_retry_count(&self) -> usize {
        self.entries.iter().filter(|e| e.high_retry).count()
    }

    /// Sum of all retry_count values across all epochs.
    pub fn total_retries(&self) -> u64 {
        self.entries.iter().map(|e| e.retry_count as u64).sum()
    }

    /// Integer mean of all per-epoch retry_rate_pct values. Returns 0 if empty.
    pub fn mean_retry_rate_pct(&self) -> u32 {
        if self.entries.is_empty() { return 0; }
        let sum: u64 = self.entries.iter().map(|e| e.retry_rate_pct as u64).sum();
        (sum / self.entries.len() as u64) as u32
    }

    /// Record broadcast retry stats for one epoch.
    /// retry_rate_pct = (retry_count * 100) / max(total_sent, 1), capped at 100.
    /// high_retry = retry_rate_pct > RETRY_CEILING.
    pub fn record(
        &mut self,
        epoch_end:   u64,
        retry_count: u32,
        total_sent:  u32,
    ) -> &GossipBroadcastRetryEntry {
        let denom = total_sent.max(1) as u64;
        let retry_rate_pct = ((retry_count as u64 * 100) / denom).min(100) as u32;
        let high_retry = retry_rate_pct > RETRY_CEILING;

        let prev = self.entries.last()
            .map(|e| e.entry_hash)
            .unwrap_or(GOSSIP_BROADCAST_RETRY_GENESIS_HASH);

        let entry_hash = compute_broadcast_retry_hash(
            &prev, epoch_end, retry_count, total_sent, retry_rate_pct, high_retry,
        );

        self.entries.push(GossipBroadcastRetryEntry {
            epoch_end,
            retry_count,
            total_sent,
            retry_rate_pct,
            high_retry,
            entry_hash,
            prev_hash: prev,
        });
        self.entries.last().unwrap()
    }

    pub fn verify_chain(&self) -> (bool, Option<usize>) {
        let mut prev = GOSSIP_BROADCAST_RETRY_GENESIS_HASH;
        for (i, e) in self.entries.iter().enumerate() {
            if e.prev_hash != prev {
                return (false, Some(i));
            }
            let expected = compute_broadcast_retry_hash(
                &prev, e.epoch_end, e.retry_count, e.total_sent,
                e.retry_rate_pct, e.high_retry,
            );
            if e.entry_hash != expected {
                return (false, Some(i));
            }
            prev = e.entry_hash;
        }
        (true, None)
    }
}

impl Default for GossipBroadcastRetryLog {
    fn default() -> Self { Self::new() }
}

// ─── Tests ────────────────────────────────────────────────────────────────────

#[cfg(test)]
mod tests {
    use super::*;

    // ── record fields ─────────────────────────────────────────────────────────

    #[test]
    fn record_fields_stored() {
        let mut log = GossipBroadcastRetryLog::new();
        let e = log.record(1, 5, 20);
        assert_eq!(e.epoch_end, 1);
        assert_eq!(e.retry_count, 5);
        assert_eq!(e.total_sent, 20);
        assert_eq!(e.retry_rate_pct, 25); // 5*100/20 = 25
    }

    #[test]
    fn zero_retries_zero_rate() {
        let mut log = GossipBroadcastRetryLog::new();
        let e = log.record(1, 0, 100);
        assert_eq!(e.retry_rate_pct, 0);
        assert!(!e.high_retry);
    }

    #[test]
    fn total_sent_zero_uses_max_one() {
        let mut log = GossipBroadcastRetryLog::new();
        // total_sent=0 → denom=1 → retry_rate_pct = retry_count * 100, capped at 100
        let e = log.record(1, 0, 0);
        assert_eq!(e.retry_rate_pct, 0);
    }

    #[test]
    fn retry_rate_capped_at_100() {
        let mut log = GossipBroadcastRetryLog::new();
        // retry_count > total_sent — can't exceed 100%
        let e = log.record(1, 50, 10);
        assert_eq!(e.retry_rate_pct, 100);
    }

    // ── high_retry threshold ──────────────────────────────────────────────────

    #[test]
    fn high_retry_above_ceiling() {
        let mut log = GossipBroadcastRetryLog::new();
        // 26*100/100 = 26 > 25
        let e = log.record(1, 26, 100);
        assert_eq!(e.retry_rate_pct, 26);
        assert!(e.high_retry);
    }

    #[test]
    fn high_retry_at_ceiling_not_high() {
        let mut log = GossipBroadcastRetryLog::new();
        // exactly 25 — NOT high (> 25, not >=)
        let e = log.record(1, 25, 100);
        assert_eq!(e.retry_rate_pct, 25);
        assert!(!e.high_retry);
    }

    #[test]
    fn high_retry_below_ceiling_not_high() {
        let mut log = GossipBroadcastRetryLog::new();
        let e = log.record(1, 10, 100);
        assert!(!e.high_retry);
    }

    // ── aggregate stats ───────────────────────────────────────────────────────

    #[test]
    fn high_retry_count_correct() {
        let mut log = GossipBroadcastRetryLog::new();
        log.record(1, 10, 100); // 10% — ok
        log.record(2, 30, 100); // 30% — high
        log.record(3, 25, 100); // 25% — at ceiling, not high
        log.record(4, 50, 100); // 50% — high
        assert_eq!(log.high_retry_count(), 2);
    }

    #[test]
    fn total_retries_correct() {
        let mut log = GossipBroadcastRetryLog::new();
        log.record(1, 5, 50);
        log.record(2, 10, 80);
        log.record(3, 3, 30);
        assert_eq!(log.total_retries(), 18);
    }

    #[test]
    fn total_retries_empty_zero() {
        let log = GossipBroadcastRetryLog::new();
        assert_eq!(log.total_retries(), 0);
    }

    #[test]
    fn mean_retry_rate_correct() {
        let mut log = GossipBroadcastRetryLog::new();
        log.record(1, 10, 100); // 10%
        log.record(2, 20, 100); // 20%
        log.record(3, 30, 100); // 30%
        // (10+20+30)/3 = 20
        assert_eq!(log.mean_retry_rate_pct(), 20);
    }

    #[test]
    fn mean_retry_rate_empty_zero() {
        let log = GossipBroadcastRetryLog::new();
        assert_eq!(log.mean_retry_rate_pct(), 0);
    }

    // ── hash chain ────────────────────────────────────────────────────────────

    #[test]
    fn entry_hash_nonzero() {
        let mut log = GossipBroadcastRetryLog::new();
        let e = log.record(1, 5, 20);
        assert_ne!(e.entry_hash, [0u8; 32]);
    }

    #[test]
    fn first_entry_prev_hash_is_genesis() {
        let mut log = GossipBroadcastRetryLog::new();
        let e = log.record(1, 5, 20);
        assert_eq!(e.prev_hash, GOSSIP_BROADCAST_RETRY_GENESIS_HASH);
    }

    #[test]
    fn chain_prev_links() {
        let mut log = GossipBroadcastRetryLog::new();
        log.record(1, 5, 20);
        let h0 = log.entries()[0].entry_hash;
        log.record(2, 8, 40);
        assert_eq!(log.entries()[1].prev_hash, h0);
    }

    // ── verify_chain ──────────────────────────────────────────────────────────

    #[test]
    fn verify_chain_empty_ok() {
        let log = GossipBroadcastRetryLog::new();
        let (ok, idx) = log.verify_chain();
        assert!(ok);
        assert!(idx.is_none());
    }

    #[test]
    fn verify_chain_multiple_ok() {
        let mut log = GossipBroadcastRetryLog::new();
        for i in 1u64..=5 { log.record(i, i as u32 * 2, i as u32 * 10); }
        let (ok, idx) = log.verify_chain();
        assert!(ok);
        assert!(idx.is_none());
    }

    #[test]
    fn verify_chain_detects_tamper() {
        let mut log = GossipBroadcastRetryLog::new();
        log.record(1, 5, 20);
        log.record(2, 8, 40);
        log.entries[0].entry_hash[0] ^= 0xFF;
        let (ok, idx) = log.verify_chain();
        assert!(!ok);
        assert_eq!(idx, Some(0));
    }

    // ── determinism ───────────────────────────────────────────────────────────

    #[test]
    fn entry_hash_deterministic() {
        let mut l1 = GossipBroadcastRetryLog::new();
        let mut l2 = GossipBroadcastRetryLog::new();
        let h1 = l1.record(7, 15, 60).entry_hash;
        let h2 = l2.record(7, 15, 60).entry_hash;
        assert_eq!(h1, h2);
    }
}
