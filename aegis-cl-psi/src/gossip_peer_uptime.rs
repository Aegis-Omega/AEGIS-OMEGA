//! Gate 405 — Gossip Peer Uptime Log (T2)
//! EPISTEMIC TIER: T2 (engineering hypothesis)
//!
//! Per-epoch tracking of peer uptime. For each epoch, records how many
//! ticks/slots a peer was connected vs disconnected.
//!
//! connected_ticks:    u32 — ticks peer was connected this epoch
//! total_ticks:        u32 — total ticks in epoch (≥ connected_ticks)
//! uptime_pct:         u32 — connected_ticks * 100 / max(total_ticks, 1)
//! low_uptime:         bool — uptime_pct < UPTIME_FLOOR (80%)
//!
//! UPTIME_FLOOR: u32 = 80
//!
//! GossipPeerUptimeEntry (hash-chained):
//!   epoch_end:         u64
//!   connected_ticks:   u32
//!   total_ticks:       u32
//!   uptime_pct:        u32
//!   low_uptime:        bool
//!   entry_hash:        [u8;32]
//!   prev_hash:         [u8;32]
//!
//! entry_hash = SHA-256(prev[32] ‖ epoch_end_be8 ‖ connected_ticks_be4
//!                       ‖ total_ticks_be4 ‖ uptime_pct_be4 ‖ low_uptime_byte)
//!
//! GossipPeerUptimeLog: record(epoch_end, connected_ticks, total_ticks),
//!   total_connected(), total_ticks_all(), low_uptime_count(),
//!   min_uptime_pct(), verify_chain().

use sha2::{Sha256, Digest};

pub const GOSSIP_PEER_UPTIME_GENESIS_HASH: [u8; 32] = [0u8; 32];
pub const UPTIME_FLOOR: u32 = 80; // percent

// ─── GossipPeerUptimeEntry ────────────────────────────────────────────────────

#[derive(Debug, Clone, PartialEq)]
pub struct GossipPeerUptimeEntry {
    pub epoch_end:       u64,
    pub connected_ticks: u32,
    pub total_ticks:     u32,
    pub uptime_pct:      u32,
    pub low_uptime:      bool,
    pub entry_hash:      [u8; 32],
    pub prev_hash:       [u8; 32],
}

fn compute_peer_uptime_hash(
    prev:            &[u8; 32],
    epoch_end:       u64,
    connected_ticks: u32,
    total_ticks:     u32,
    uptime_pct:      u32,
    low_uptime:      bool,
) -> [u8; 32] {
    let mut h = Sha256::new();
    h.update(prev);
    h.update(epoch_end.to_be_bytes());
    h.update(connected_ticks.to_be_bytes());
    h.update(total_ticks.to_be_bytes());
    h.update(uptime_pct.to_be_bytes());
    h.update([low_uptime as u8]);
    h.finalize().into()
}

// ─── GossipPeerUptimeLog ──────────────────────────────────────────────────────

pub struct GossipPeerUptimeLog {
    entries: Vec<GossipPeerUptimeEntry>,
}

impl GossipPeerUptimeLog {
    pub fn new() -> Self { Self { entries: Vec::new() } }

    pub fn entry_count(&self) -> usize { self.entries.len() }
    pub fn is_empty(&self)    -> bool  { self.entries.is_empty() }
    pub fn entries(&self)     -> &[GossipPeerUptimeEntry] { &self.entries }
    pub fn latest(&self)      -> Option<&GossipPeerUptimeEntry> { self.entries.last() }

    /// Total connected ticks across all epochs.
    pub fn total_connected(&self) -> u64 {
        self.entries.iter().map(|e| e.connected_ticks as u64).sum()
    }

    /// Total ticks across all epochs.
    pub fn total_ticks_all(&self) -> u64 {
        self.entries.iter().map(|e| e.total_ticks as u64).sum()
    }

    /// Count of epochs where low_uptime == true.
    pub fn low_uptime_count(&self) -> usize {
        self.entries.iter().filter(|e| e.low_uptime).count()
    }

    /// Minimum uptime_pct across all epochs. Returns 100 if empty.
    pub fn min_uptime_pct(&self) -> u32 {
        self.entries.iter().map(|e| e.uptime_pct).min().unwrap_or(100)
    }

    /// Record uptime for one epoch.
    /// uptime_pct = connected_ticks * 100 / max(total_ticks, 1).
    /// low_uptime = uptime_pct < UPTIME_FLOOR.
    pub fn record(
        &mut self,
        epoch_end:       u64,
        connected_ticks: u32,
        total_ticks:     u32,
    ) -> &GossipPeerUptimeEntry {
        let uptime_pct = (connected_ticks as u64 * 100
            / total_ticks.max(1) as u64) as u32;
        let low_uptime = uptime_pct < UPTIME_FLOOR;

        let prev = self.entries.last()
            .map(|e| e.entry_hash)
            .unwrap_or(GOSSIP_PEER_UPTIME_GENESIS_HASH);

        let entry_hash = compute_peer_uptime_hash(
            &prev, epoch_end, connected_ticks, total_ticks, uptime_pct, low_uptime,
        );

        self.entries.push(GossipPeerUptimeEntry {
            epoch_end,
            connected_ticks,
            total_ticks,
            uptime_pct,
            low_uptime,
            entry_hash,
            prev_hash: prev,
        });
        self.entries.last().unwrap()
    }

    pub fn verify_chain(&self) -> (bool, Option<usize>) {
        let mut prev = GOSSIP_PEER_UPTIME_GENESIS_HASH;
        for (i, e) in self.entries.iter().enumerate() {
            if e.prev_hash != prev {
                return (false, Some(i));
            }
            let expected = compute_peer_uptime_hash(
                &prev, e.epoch_end, e.connected_ticks, e.total_ticks,
                e.uptime_pct, e.low_uptime,
            );
            if e.entry_hash != expected {
                return (false, Some(i));
            }
            prev = e.entry_hash;
        }
        (true, None)
    }
}

impl Default for GossipPeerUptimeLog {
    fn default() -> Self { Self::new() }
}

// ─── Tests ────────────────────────────────────────────────────────────────────

#[cfg(test)]
mod tests {
    use super::*;

    // ── record fields ─────────────────────────────────────────────────────────

    #[test]
    fn record_fields_stored() {
        let mut log = GossipPeerUptimeLog::new();
        let e = log.record(1, 90, 100);
        assert_eq!(e.epoch_end, 1);
        assert_eq!(e.connected_ticks, 90);
        assert_eq!(e.total_ticks, 100);
        assert_eq!(e.uptime_pct, 90);
    }

    #[test]
    fn zero_ticks_stored() {
        let mut log = GossipPeerUptimeLog::new();
        let e = log.record(1, 0, 0);
        assert_eq!(e.uptime_pct, 0);
        assert!(e.low_uptime);
    }

    #[test]
    fn full_uptime_stored() {
        let mut log = GossipPeerUptimeLog::new();
        let e = log.record(1, 100, 100);
        assert_eq!(e.uptime_pct, 100);
        assert!(!e.low_uptime);
    }

    #[test]
    fn uptime_rounds_down() {
        let mut log = GossipPeerUptimeLog::new();
        // 85*100/101 = 84 (rounds down)
        let e = log.record(1, 85, 101);
        assert_eq!(e.uptime_pct, 84);
    }

    // ── low_uptime threshold ──────────────────────────────────────────────────

    #[test]
    fn low_uptime_below_floor() {
        let mut log = GossipPeerUptimeLog::new();
        let e = log.record(1, 79, 100);
        assert_eq!(e.uptime_pct, 79);
        assert!(e.low_uptime);
    }

    #[test]
    fn uptime_at_floor_not_low() {
        let mut log = GossipPeerUptimeLog::new();
        let e = log.record(1, 80, 100);
        assert_eq!(e.uptime_pct, 80);
        assert!(!e.low_uptime);
    }

    #[test]
    fn uptime_above_floor_not_low() {
        let mut log = GossipPeerUptimeLog::new();
        let e = log.record(1, 95, 100);
        assert!(!e.low_uptime);
    }

    // ── aggregate stats ───────────────────────────────────────────────────────

    #[test]
    fn totals_correct() {
        let mut log = GossipPeerUptimeLog::new();
        log.record(1, 90, 100);
        log.record(2, 80, 100);
        log.record(3, 70, 100);
        assert_eq!(log.total_connected(), 240);
        assert_eq!(log.total_ticks_all(), 300);
    }

    #[test]
    fn low_uptime_count_correct() {
        let mut log = GossipPeerUptimeLog::new();
        log.record(1, 90, 100); // 90% — ok
        log.record(2, 75, 100); // 75% — low
        log.record(3, 80, 100); // 80% — ok (at floor)
        log.record(4, 60, 100); // 60% — low
        assert_eq!(log.low_uptime_count(), 2);
    }

    #[test]
    fn min_uptime_pct_correct() {
        let mut log = GossipPeerUptimeLog::new();
        log.record(1, 95, 100); // 95%
        log.record(2, 70, 100); // 70%
        log.record(3, 85, 100); // 85%
        assert_eq!(log.min_uptime_pct(), 70);
    }

    #[test]
    fn min_uptime_empty_is_100() {
        let log = GossipPeerUptimeLog::new();
        assert_eq!(log.min_uptime_pct(), 100);
    }

    // ── hash chain ────────────────────────────────────────────────────────────

    #[test]
    fn entry_hash_nonzero() {
        let mut log = GossipPeerUptimeLog::new();
        let e = log.record(1, 90, 100);
        assert_ne!(e.entry_hash, [0u8; 32]);
    }

    #[test]
    fn first_entry_prev_hash_is_genesis() {
        let mut log = GossipPeerUptimeLog::new();
        let e = log.record(1, 90, 100);
        assert_eq!(e.prev_hash, GOSSIP_PEER_UPTIME_GENESIS_HASH);
    }

    #[test]
    fn chain_prev_links() {
        let mut log = GossipPeerUptimeLog::new();
        log.record(1, 90, 100);
        let h0 = log.entries()[0].entry_hash;
        log.record(2, 80, 100);
        assert_eq!(log.entries()[1].prev_hash, h0);
    }

    // ── verify_chain ──────────────────────────────────────────────────────────

    #[test]
    fn verify_chain_empty_ok() {
        let log = GossipPeerUptimeLog::new();
        let (ok, idx) = log.verify_chain();
        assert!(ok);
        assert!(idx.is_none());
    }

    #[test]
    fn verify_chain_multiple_ok() {
        let mut log = GossipPeerUptimeLog::new();
        for i in 1u64..=5 { log.record(i, i as u32 * 18, 100); }
        let (ok, idx) = log.verify_chain();
        assert!(ok);
        assert!(idx.is_none());
    }

    #[test]
    fn verify_chain_detects_tamper() {
        let mut log = GossipPeerUptimeLog::new();
        log.record(1, 90, 100);
        log.record(2, 80, 100);
        log.entries[0].entry_hash[0] ^= 0xFF;
        let (ok, idx) = log.verify_chain();
        assert!(!ok);
        assert_eq!(idx, Some(0));
    }

    // ── determinism ───────────────────────────────────────────────────────────

    #[test]
    fn entry_hash_deterministic() {
        let mut l1 = GossipPeerUptimeLog::new();
        let mut l2 = GossipPeerUptimeLog::new();
        let h1 = l1.record(5, 95, 100).entry_hash;
        let h2 = l2.record(5, 95, 100).entry_hash;
        assert_eq!(h1, h2);
    }
}
