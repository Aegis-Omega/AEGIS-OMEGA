//! Gate 419 — Gossip Broadcast Timeout Log (T2)
//! EPISTEMIC TIER: T2 (engineering hypothesis)
//!
//! Per-epoch tracking of gossip message delivery timeouts. A timeout occurs
//! when a message is sent but no delivery confirmation arrives within the
//! epoch window.
//!
//! timeout_count:     u32 — number of messages that timed out this epoch
//! total_sent:        u32 — total messages sent this epoch
//! timeout_rate_pct:  u32 — (timeout_count * 100) / max(total_sent, 1), capped at 100
//! excessive_timeout: bool — timeout_rate_pct > TIMEOUT_THRESHOLD (5)
//!
//! TIMEOUT_THRESHOLD: u32 = 5  (>5% timeout rate indicates delivery failure)
//!
//! GossipBroadcastTimeoutEntry (hash-chained):
//!   epoch_end:        u64
//!   timeout_count:    u32
//!   total_sent:       u32
//!   timeout_rate_pct: u32
//!   excessive_timeout: bool
//!   entry_hash:       [u8;32]
//!   prev_hash:        [u8;32]
//!
//! entry_hash = SHA-256(prev[32] ‖ epoch_end_be8 ‖ timeout_count_be4
//!                       ‖ total_sent_be4 ‖ timeout_rate_pct_be4 ‖ excessive_timeout_byte)
//!
//! GossipBroadcastTimeoutLog: record(epoch_end, timeout_count, total_sent),
//!   excessive_timeout_count(), total_timeouts(), mean_timeout_rate_pct(), verify_chain().

use sha2::{Sha256, Digest};

pub const GOSSIP_BROADCAST_TIMEOUT_GENESIS_HASH: [u8; 32] = [0u8; 32];
pub const TIMEOUT_THRESHOLD: u32 = 5;

// ─── GossipBroadcastTimeoutEntry ─────────────────────────────────────────────

#[derive(Debug, Clone, PartialEq)]
pub struct GossipBroadcastTimeoutEntry {
    pub epoch_end:         u64,
    pub timeout_count:     u32,
    pub total_sent:        u32,
    pub timeout_rate_pct:  u32,
    pub excessive_timeout: bool,
    pub entry_hash:        [u8; 32],
    pub prev_hash:         [u8; 32],
}

fn compute_broadcast_timeout_hash(
    prev:              &[u8; 32],
    epoch_end:         u64,
    timeout_count:     u32,
    total_sent:        u32,
    timeout_rate_pct:  u32,
    excessive_timeout: bool,
) -> [u8; 32] {
    let mut h = Sha256::new();
    h.update(prev);
    h.update(epoch_end.to_be_bytes());
    h.update(timeout_count.to_be_bytes());
    h.update(total_sent.to_be_bytes());
    h.update(timeout_rate_pct.to_be_bytes());
    h.update([excessive_timeout as u8]);
    h.finalize().into()
}

// ─── GossipBroadcastTimeoutLog ────────────────────────────────────────────────

pub struct GossipBroadcastTimeoutLog {
    entries: Vec<GossipBroadcastTimeoutEntry>,
}

impl GossipBroadcastTimeoutLog {
    pub fn new() -> Self { Self { entries: Vec::new() } }

    pub fn entry_count(&self) -> usize { self.entries.len() }
    pub fn is_empty(&self)    -> bool  { self.entries.is_empty() }
    pub fn entries(&self)     -> &[GossipBroadcastTimeoutEntry] { &self.entries }
    pub fn latest(&self)      -> Option<&GossipBroadcastTimeoutEntry> { self.entries.last() }

    /// Count of epochs where excessive_timeout == true.
    pub fn excessive_timeout_count(&self) -> usize {
        self.entries.iter().filter(|e| e.excessive_timeout).count()
    }

    /// Sum of all timeout_count values across epochs.
    pub fn total_timeouts(&self) -> u64 {
        self.entries.iter().map(|e| e.timeout_count as u64).sum()
    }

    /// Integer mean of all per-epoch timeout_rate_pct values. Returns 0 if empty.
    pub fn mean_timeout_rate_pct(&self) -> u32 {
        if self.entries.is_empty() { return 0; }
        let sum: u64 = self.entries.iter().map(|e| e.timeout_rate_pct as u64).sum();
        (sum / self.entries.len() as u64) as u32
    }

    /// Record timeout stats for one epoch.
    /// timeout_rate_pct = (timeout_count * 100) / max(total_sent, 1), capped at 100.
    /// excessive_timeout = timeout_rate_pct > TIMEOUT_THRESHOLD.
    pub fn record(
        &mut self,
        epoch_end:     u64,
        timeout_count: u32,
        total_sent:    u32,
    ) -> &GossipBroadcastTimeoutEntry {
        let denom = total_sent.max(1) as u64;
        let timeout_rate_pct = ((timeout_count as u64 * 100) / denom).min(100) as u32;
        let excessive_timeout = timeout_rate_pct > TIMEOUT_THRESHOLD;

        let prev = self.entries.last()
            .map(|e| e.entry_hash)
            .unwrap_or(GOSSIP_BROADCAST_TIMEOUT_GENESIS_HASH);

        let entry_hash = compute_broadcast_timeout_hash(
            &prev, epoch_end, timeout_count, total_sent, timeout_rate_pct, excessive_timeout,
        );

        self.entries.push(GossipBroadcastTimeoutEntry {
            epoch_end,
            timeout_count,
            total_sent,
            timeout_rate_pct,
            excessive_timeout,
            entry_hash,
            prev_hash: prev,
        });
        self.entries.last().unwrap()
    }

    pub fn verify_chain(&self) -> (bool, Option<usize>) {
        let mut prev = GOSSIP_BROADCAST_TIMEOUT_GENESIS_HASH;
        for (i, e) in self.entries.iter().enumerate() {
            if e.prev_hash != prev {
                return (false, Some(i));
            }
            let expected = compute_broadcast_timeout_hash(
                &prev, e.epoch_end, e.timeout_count, e.total_sent,
                e.timeout_rate_pct, e.excessive_timeout,
            );
            if e.entry_hash != expected {
                return (false, Some(i));
            }
            prev = e.entry_hash;
        }
        (true, None)
    }
}

impl Default for GossipBroadcastTimeoutLog {
    fn default() -> Self { Self::new() }
}

// ─── Tests ────────────────────────────────────────────────────────────────────

#[cfg(test)]
mod tests {
    use super::*;

    // ── record fields ─────────────────────────────────────────────────────────

    #[test]
    fn record_fields_stored() {
        let mut log = GossipBroadcastTimeoutLog::new();
        let e = log.record(1, 2, 100);
        assert_eq!(e.epoch_end, 1);
        assert_eq!(e.timeout_count, 2);
        assert_eq!(e.total_sent, 100);
        assert_eq!(e.timeout_rate_pct, 2); // 2*100/100 = 2
    }

    #[test]
    fn zero_timeouts_zero_rate() {
        let mut log = GossipBroadcastTimeoutLog::new();
        let e = log.record(1, 0, 100);
        assert_eq!(e.timeout_rate_pct, 0);
        assert!(!e.excessive_timeout);
    }

    #[test]
    fn total_sent_zero_uses_max_one() {
        let mut log = GossipBroadcastTimeoutLog::new();
        let e = log.record(1, 0, 0);
        assert_eq!(e.timeout_rate_pct, 0);
        assert!(!e.excessive_timeout);
    }

    #[test]
    fn timeout_rate_capped_at_100() {
        let mut log = GossipBroadcastTimeoutLog::new();
        // timeout_count > total_sent — still capped at 100
        let e = log.record(1, 200, 100);
        assert_eq!(e.timeout_rate_pct, 100);
    }

    // ── excessive_timeout threshold ───────────────────────────────────────────

    #[test]
    fn at_threshold_not_excessive() {
        let mut log = GossipBroadcastTimeoutLog::new();
        // exactly 5% — NOT excessive (> 5, not >=)
        let e = log.record(1, 5, 100);
        assert_eq!(e.timeout_rate_pct, 5);
        assert!(!e.excessive_timeout);
    }

    #[test]
    fn above_threshold_excessive() {
        let mut log = GossipBroadcastTimeoutLog::new();
        // 6% > TIMEOUT_THRESHOLD(5)
        let e = log.record(1, 6, 100);
        assert_eq!(e.timeout_rate_pct, 6);
        assert!(e.excessive_timeout);
    }

    #[test]
    fn below_threshold_not_excessive() {
        let mut log = GossipBroadcastTimeoutLog::new();
        let e = log.record(1, 3, 100);
        assert!(!e.excessive_timeout);
    }

    // ── aggregate stats ───────────────────────────────────────────────────────

    #[test]
    fn excessive_timeout_count_correct() {
        let mut log = GossipBroadcastTimeoutLog::new();
        log.record(1, 2, 100); // 2% — ok
        log.record(2, 7, 100); // 7% — excessive
        log.record(3, 5, 100); // 5% — at threshold, not excessive
        log.record(4, 10, 100); // 10% — excessive
        assert_eq!(log.excessive_timeout_count(), 2);
    }

    #[test]
    fn total_timeouts_correct() {
        let mut log = GossipBroadcastTimeoutLog::new();
        log.record(1, 3, 100);
        log.record(2, 5, 100);
        log.record(3, 7, 100);
        assert_eq!(log.total_timeouts(), 15);
    }

    #[test]
    fn mean_timeout_rate_correct() {
        let mut log = GossipBroadcastTimeoutLog::new();
        log.record(1, 3, 100); // 3%
        log.record(2, 6, 100); // 6%
        log.record(3, 9, 100); // 9%
        // (3+6+9)/3 = 6
        assert_eq!(log.mean_timeout_rate_pct(), 6);
    }

    #[test]
    fn mean_timeout_rate_empty_zero() {
        let log = GossipBroadcastTimeoutLog::new();
        assert_eq!(log.mean_timeout_rate_pct(), 0);
    }

    #[test]
    fn total_timeouts_empty_zero() {
        let log = GossipBroadcastTimeoutLog::new();
        assert_eq!(log.total_timeouts(), 0);
    }

    // ── hash chain ────────────────────────────────────────────────────────────

    #[test]
    fn entry_hash_nonzero() {
        let mut log = GossipBroadcastTimeoutLog::new();
        let e = log.record(1, 3, 100);
        assert_ne!(e.entry_hash, [0u8; 32]);
    }

    #[test]
    fn first_entry_prev_hash_is_genesis() {
        let mut log = GossipBroadcastTimeoutLog::new();
        let e = log.record(1, 3, 100);
        assert_eq!(e.prev_hash, GOSSIP_BROADCAST_TIMEOUT_GENESIS_HASH);
    }

    #[test]
    fn chain_prev_links() {
        let mut log = GossipBroadcastTimeoutLog::new();
        log.record(1, 3, 100);
        let h0 = log.entries()[0].entry_hash;
        log.record(2, 5, 100);
        assert_eq!(log.entries()[1].prev_hash, h0);
    }

    // ── verify_chain ──────────────────────────────────────────────────────────

    #[test]
    fn verify_chain_empty_ok() {
        let log = GossipBroadcastTimeoutLog::new();
        let (ok, idx) = log.verify_chain();
        assert!(ok);
        assert!(idx.is_none());
    }

    #[test]
    fn verify_chain_multiple_ok() {
        let mut log = GossipBroadcastTimeoutLog::new();
        for i in 1u64..=5 { log.record(i, i as u32, i as u32 * 20); }
        let (ok, idx) = log.verify_chain();
        assert!(ok);
        assert!(idx.is_none());
    }

    #[test]
    fn verify_chain_detects_tamper() {
        let mut log = GossipBroadcastTimeoutLog::new();
        log.record(1, 3, 100);
        log.record(2, 5, 100);
        log.entries[0].entry_hash[0] ^= 0xFF;
        let (ok, idx) = log.verify_chain();
        assert!(!ok);
        assert_eq!(idx, Some(0));
    }

    // ── determinism ───────────────────────────────────────────────────────────

    #[test]
    fn entry_hash_deterministic() {
        let mut l1 = GossipBroadcastTimeoutLog::new();
        let mut l2 = GossipBroadcastTimeoutLog::new();
        let h1 = l1.record(7, 4, 80).entry_hash;
        let h2 = l2.record(7, 4, 80).entry_hash;
        assert_eq!(h1, h2);
    }
}
