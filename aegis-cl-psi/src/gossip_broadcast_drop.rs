//! Gate 417 — Gossip Broadcast Drop Log (T2)
//! EPISTEMIC TIER: T2 (engineering hypothesis)
//!
//! Per-epoch tracking of gossip message drops. A drop occurs when a message
//! is discarded before delivery (queue full, timeout, invalid peer).
//!
//! drop_count:   u32 — number of messages dropped this epoch
//! total_sent:   u32 — total messages sent (including dropped)
//! drop_rate_pct: u32 — (drop_count * 100) / max(total_sent, 1), capped at 100
//! critical_drop: bool — drop_rate_pct > DROP_THRESHOLD (10)
//!
//! DROP_THRESHOLD: u32 = 10  (>10% drop rate is critical for gossip health)
//!
//! GossipBroadcastDropEntry (hash-chained):
//!   epoch_end:    u64
//!   drop_count:   u32
//!   total_sent:   u32
//!   drop_rate_pct: u32
//!   critical_drop: bool
//!   entry_hash:   [u8;32]
//!   prev_hash:    [u8;32]
//!
//! entry_hash = SHA-256(prev[32] ‖ epoch_end_be8 ‖ drop_count_be4
//!                       ‖ total_sent_be4 ‖ drop_rate_pct_be4 ‖ critical_byte)
//!
//! GossipBroadcastDropLog: record(epoch_end, drop_count, total_sent),
//!   critical_drop_count(), total_drops(), mean_drop_rate_pct(), verify_chain().

use sha2::{Sha256, Digest};

pub const GOSSIP_BROADCAST_DROP_GENESIS_HASH: [u8; 32] = [0u8; 32];
pub const DROP_THRESHOLD: u32 = 10;

// ─── GossipBroadcastDropEntry ─────────────────────────────────────────────────

#[derive(Debug, Clone, PartialEq)]
pub struct GossipBroadcastDropEntry {
    pub epoch_end:     u64,
    pub drop_count:    u32,
    pub total_sent:    u32,
    pub drop_rate_pct: u32,
    pub critical_drop: bool,
    pub entry_hash:    [u8; 32],
    pub prev_hash:     [u8; 32],
}

fn compute_broadcast_drop_hash(
    prev:          &[u8; 32],
    epoch_end:     u64,
    drop_count:    u32,
    total_sent:    u32,
    drop_rate_pct: u32,
    critical_drop: bool,
) -> [u8; 32] {
    let mut h = Sha256::new();
    h.update(prev);
    h.update(epoch_end.to_be_bytes());
    h.update(drop_count.to_be_bytes());
    h.update(total_sent.to_be_bytes());
    h.update(drop_rate_pct.to_be_bytes());
    h.update([critical_drop as u8]);
    h.finalize().into()
}

// ─── GossipBroadcastDropLog ───────────────────────────────────────────────────

pub struct GossipBroadcastDropLog {
    entries: Vec<GossipBroadcastDropEntry>,
}

impl GossipBroadcastDropLog {
    pub fn new() -> Self { Self { entries: Vec::new() } }

    pub fn entry_count(&self) -> usize { self.entries.len() }
    pub fn is_empty(&self)    -> bool  { self.entries.is_empty() }
    pub fn entries(&self)     -> &[GossipBroadcastDropEntry] { &self.entries }
    pub fn latest(&self)      -> Option<&GossipBroadcastDropEntry> { self.entries.last() }

    /// Count of epochs where critical_drop == true.
    pub fn critical_drop_count(&self) -> usize {
        self.entries.iter().filter(|e| e.critical_drop).count()
    }

    /// Sum of all drop_count values across all epochs.
    pub fn total_drops(&self) -> u64 {
        self.entries.iter().map(|e| e.drop_count as u64).sum()
    }

    /// Integer mean of all per-epoch drop_rate_pct values. Returns 0 if empty.
    pub fn mean_drop_rate_pct(&self) -> u32 {
        if self.entries.is_empty() { return 0; }
        let sum: u64 = self.entries.iter().map(|e| e.drop_rate_pct as u64).sum();
        (sum / self.entries.len() as u64) as u32
    }

    /// Record broadcast drop stats for one epoch.
    /// drop_rate_pct = (drop_count * 100) / max(total_sent, 1), capped at 100.
    /// critical_drop = drop_rate_pct > DROP_THRESHOLD.
    pub fn record(
        &mut self,
        epoch_end:  u64,
        drop_count: u32,
        total_sent: u32,
    ) -> &GossipBroadcastDropEntry {
        let denom = total_sent.max(1) as u64;
        let drop_rate_pct = ((drop_count as u64 * 100) / denom).min(100) as u32;
        let critical_drop = drop_rate_pct > DROP_THRESHOLD;

        let prev = self.entries.last()
            .map(|e| e.entry_hash)
            .unwrap_or(GOSSIP_BROADCAST_DROP_GENESIS_HASH);

        let entry_hash = compute_broadcast_drop_hash(
            &prev, epoch_end, drop_count, total_sent, drop_rate_pct, critical_drop,
        );

        self.entries.push(GossipBroadcastDropEntry {
            epoch_end,
            drop_count,
            total_sent,
            drop_rate_pct,
            critical_drop,
            entry_hash,
            prev_hash: prev,
        });
        self.entries.last().unwrap()
    }

    pub fn verify_chain(&self) -> (bool, Option<usize>) {
        let mut prev = GOSSIP_BROADCAST_DROP_GENESIS_HASH;
        for (i, e) in self.entries.iter().enumerate() {
            if e.prev_hash != prev {
                return (false, Some(i));
            }
            let expected = compute_broadcast_drop_hash(
                &prev, e.epoch_end, e.drop_count, e.total_sent,
                e.drop_rate_pct, e.critical_drop,
            );
            if e.entry_hash != expected {
                return (false, Some(i));
            }
            prev = e.entry_hash;
        }
        (true, None)
    }
}

impl Default for GossipBroadcastDropLog {
    fn default() -> Self { Self::new() }
}

// ─── Tests ────────────────────────────────────────────────────────────────────

#[cfg(test)]
mod tests {
    use super::*;

    // ── record fields ─────────────────────────────────────────────────────────

    #[test]
    fn record_fields_stored() {
        let mut log = GossipBroadcastDropLog::new();
        let e = log.record(1, 5, 50);
        assert_eq!(e.epoch_end, 1);
        assert_eq!(e.drop_count, 5);
        assert_eq!(e.total_sent, 50);
        assert_eq!(e.drop_rate_pct, 10); // 5*100/50 = 10
    }

    #[test]
    fn zero_drops_zero_rate() {
        let mut log = GossipBroadcastDropLog::new();
        let e = log.record(1, 0, 100);
        assert_eq!(e.drop_rate_pct, 0);
        assert!(!e.critical_drop);
    }

    #[test]
    fn total_sent_zero_uses_max_one() {
        let mut log = GossipBroadcastDropLog::new();
        let e = log.record(1, 0, 0);
        assert_eq!(e.drop_rate_pct, 0);
    }

    #[test]
    fn drop_rate_capped_at_100() {
        let mut log = GossipBroadcastDropLog::new();
        // drop_count > total_sent — can't exceed 100%
        let e = log.record(1, 200, 50);
        assert_eq!(e.drop_rate_pct, 100);
    }

    // ── critical_drop threshold ───────────────────────────────────────────────

    #[test]
    fn critical_drop_above_threshold() {
        let mut log = GossipBroadcastDropLog::new();
        // 11*100/100 = 11 > 10
        let e = log.record(1, 11, 100);
        assert_eq!(e.drop_rate_pct, 11);
        assert!(e.critical_drop);
    }

    #[test]
    fn critical_drop_at_threshold_not_critical() {
        let mut log = GossipBroadcastDropLog::new();
        // exactly 10 — NOT critical (> 10, not >=)
        let e = log.record(1, 10, 100);
        assert_eq!(e.drop_rate_pct, 10);
        assert!(!e.critical_drop);
    }

    #[test]
    fn critical_drop_below_threshold_not_critical() {
        let mut log = GossipBroadcastDropLog::new();
        let e = log.record(1, 5, 100);
        assert!(!e.critical_drop);
    }

    // ── aggregate stats ───────────────────────────────────────────────────────

    #[test]
    fn critical_drop_count_correct() {
        let mut log = GossipBroadcastDropLog::new();
        log.record(1, 5, 100);  // 5%  — ok
        log.record(2, 15, 100); // 15% — critical
        log.record(3, 10, 100); // 10% — at threshold, not critical
        log.record(4, 20, 100); // 20% — critical
        assert_eq!(log.critical_drop_count(), 2);
    }

    #[test]
    fn total_drops_correct() {
        let mut log = GossipBroadcastDropLog::new();
        log.record(1, 3, 50);
        log.record(2, 7, 80);
        log.record(3, 2, 30);
        assert_eq!(log.total_drops(), 12);
    }

    #[test]
    fn total_drops_empty_zero() {
        let log = GossipBroadcastDropLog::new();
        assert_eq!(log.total_drops(), 0);
    }

    #[test]
    fn mean_drop_rate_correct() {
        let mut log = GossipBroadcastDropLog::new();
        log.record(1, 6, 100);  // 6%
        log.record(2, 12, 100); // 12%
        log.record(3, 9, 100);  // 9%
        // (6+12+9)/3 = 9
        assert_eq!(log.mean_drop_rate_pct(), 9);
    }

    #[test]
    fn mean_drop_rate_empty_zero() {
        let log = GossipBroadcastDropLog::new();
        assert_eq!(log.mean_drop_rate_pct(), 0);
    }

    // ── hash chain ────────────────────────────────────────────────────────────

    #[test]
    fn entry_hash_nonzero() {
        let mut log = GossipBroadcastDropLog::new();
        let e = log.record(1, 5, 50);
        assert_ne!(e.entry_hash, [0u8; 32]);
    }

    #[test]
    fn first_entry_prev_hash_is_genesis() {
        let mut log = GossipBroadcastDropLog::new();
        let e = log.record(1, 5, 50);
        assert_eq!(e.prev_hash, GOSSIP_BROADCAST_DROP_GENESIS_HASH);
    }

    #[test]
    fn chain_prev_links() {
        let mut log = GossipBroadcastDropLog::new();
        log.record(1, 5, 50);
        let h0 = log.entries()[0].entry_hash;
        log.record(2, 8, 80);
        assert_eq!(log.entries()[1].prev_hash, h0);
    }

    // ── verify_chain ──────────────────────────────────────────────────────────

    #[test]
    fn verify_chain_empty_ok() {
        let log = GossipBroadcastDropLog::new();
        let (ok, idx) = log.verify_chain();
        assert!(ok);
        assert!(idx.is_none());
    }

    #[test]
    fn verify_chain_multiple_ok() {
        let mut log = GossipBroadcastDropLog::new();
        for i in 1u64..=5 { log.record(i, i as u32, i as u32 * 10); }
        let (ok, idx) = log.verify_chain();
        assert!(ok);
        assert!(idx.is_none());
    }

    #[test]
    fn verify_chain_detects_tamper() {
        let mut log = GossipBroadcastDropLog::new();
        log.record(1, 5, 50);
        log.record(2, 8, 80);
        log.entries[0].entry_hash[0] ^= 0xFF;
        let (ok, idx) = log.verify_chain();
        assert!(!ok);
        assert_eq!(idx, Some(0));
    }

    // ── determinism ───────────────────────────────────────────────────────────

    #[test]
    fn entry_hash_deterministic() {
        let mut l1 = GossipBroadcastDropLog::new();
        let mut l2 = GossipBroadcastDropLog::new();
        let h1 = l1.record(3, 8, 80).entry_hash;
        let h2 = l2.record(3, 8, 80).entry_hash;
        assert_eq!(h1, h2);
    }
}
