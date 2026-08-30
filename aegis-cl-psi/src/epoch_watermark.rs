//! Gate 310 — Gossip Epoch Watermark: high-water-mark epoch tracking per peer (T2)
//! EPISTEMIC TIER: T2 (engineering hypothesis)
//!
//! Tracks the highest epoch observed from each peer. The watermark advances
//! monotonically — it never moves backward. When a peer reports an epoch lower
//! than the recorded watermark, it is classified as Stale. The global watermark
//! is the minimum watermark across all tracked peers (the "consensus floor").
//! Watermark updates are hash-chained for audit.
//!
//! Constants:
//!   MAX_TRACKED_PEERS: usize = 256
//!
//! WatermarkEvent: Advance | Stale
//!
//! WatermarkRecord:
//!   peer_id, epoch, previous_watermark, new_watermark, event
//!   record_hash = SHA-256(prev ‖ peer_be4 ‖ epoch_be8 ‖ prev_wm_be8 ‖ new_wm_be8 ‖ event_byte)
//!   prev_hash
//!
//! WatermarkLog: hash-chained WatermarkRecords (global).
//!   push(), advance_count(), stale_count(), verify_chain().
//!
//! EpochWatermark:
//!   update(peer_id, epoch) → WatermarkEvent   (advances or marks Stale; records event)
//!   watermark(peer_id) → Option<u64>          (current high-water mark for peer)
//!   global_floor() → Option<u64>             (min watermark across all peers)
//!   peers_at_or_above(epoch) → usize         (count of peers with watermark ≥ epoch)
//!   get_log() → &WatermarkLog

use sha2::{Sha256, Digest};
use std::collections::BTreeMap;

pub const MAX_TRACKED_PEERS: usize = 256;

// ─── Watermark event ──────────────────────────────────────────────────────────

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum WatermarkEvent {
    Advance = 0,
    Stale   = 1,
}

impl WatermarkEvent {
    pub fn event_byte(self) -> u8 { self as u8 }
}

// ─── Watermark record ─────────────────────────────────────────────────────────

#[derive(Debug, Clone, PartialEq)]
pub struct WatermarkRecord {
    pub peer_id:            u32,
    pub epoch:              u64,
    pub previous_watermark: u64,
    pub new_watermark:      u64,
    pub event:              WatermarkEvent,
    pub record_hash:        [u8; 32],
    pub prev_hash:          [u8; 32],
}

pub const WATERMARK_GENESIS_HASH: [u8; 32] = [0u8; 32];

fn compute_watermark_hash(
    peer_id:            u32,
    epoch:              u64,
    previous_watermark: u64,
    new_watermark:      u64,
    event:              WatermarkEvent,
    prev:               &[u8; 32],
) -> [u8; 32] {
    let mut h = Sha256::new();
    h.update(prev);
    h.update(peer_id.to_be_bytes());
    h.update(epoch.to_be_bytes());
    h.update(previous_watermark.to_be_bytes());
    h.update(new_watermark.to_be_bytes());
    h.update([event.event_byte()]);
    h.finalize().into()
}

pub fn build_watermark_record(
    peer_id:            u32,
    epoch:              u64,
    previous_watermark: u64,
    new_watermark:      u64,
    event:              WatermarkEvent,
    prev_hash:          &[u8; 32],
) -> WatermarkRecord {
    let record_hash = compute_watermark_hash(peer_id, epoch, previous_watermark, new_watermark, event, prev_hash);
    WatermarkRecord { peer_id, epoch, previous_watermark, new_watermark, event, record_hash, prev_hash: *prev_hash }
}

// ─── Watermark log ────────────────────────────────────────────────────────────

#[derive(Debug, Clone)]
pub struct WatermarkLog {
    records: Vec<WatermarkRecord>,
}

impl WatermarkLog {
    pub fn new() -> Self { Self { records: Vec::new() } }

    pub fn len(&self)      -> usize { self.records.len() }
    pub fn is_empty(&self) -> bool  { self.records.is_empty() }
    pub fn records(&self)  -> &[WatermarkRecord] { &self.records }

    pub fn last_hash(&self) -> [u8; 32] {
        self.records.last().map(|r| r.record_hash).unwrap_or(WATERMARK_GENESIS_HASH)
    }

    pub fn push(
        &mut self,
        peer_id:            u32,
        epoch:              u64,
        previous_watermark: u64,
        new_watermark:      u64,
        event:              WatermarkEvent,
    ) -> &WatermarkRecord {
        let prev = self.last_hash();
        let r = build_watermark_record(peer_id, epoch, previous_watermark, new_watermark, event, &prev);
        self.records.push(r);
        self.records.last().unwrap()
    }

    pub fn advance_count(&self) -> usize {
        self.records.iter().filter(|r| r.event == WatermarkEvent::Advance).count()
    }

    pub fn stale_count(&self) -> usize {
        self.records.iter().filter(|r| r.event == WatermarkEvent::Stale).count()
    }

    pub fn verify_chain(&self) -> (bool, Option<usize>) {
        let mut expected_prev = WATERMARK_GENESIS_HASH;
        for (i, r) in self.records.iter().enumerate() {
            if r.prev_hash != expected_prev { return (false, Some(i)); }
            let recomputed = compute_watermark_hash(
                r.peer_id, r.epoch, r.previous_watermark, r.new_watermark, r.event, &r.prev_hash
            );
            if recomputed != r.record_hash { return (false, Some(i)); }
            expected_prev = r.record_hash;
        }
        (true, None)
    }
}

impl Default for WatermarkLog {
    fn default() -> Self { Self::new() }
}

// ─── Errors ───────────────────────────────────────────────────────────────────

#[derive(Debug)]
pub enum WatermarkError {
    TooManyPeers,
}

// ─── EpochWatermark ───────────────────────────────────────────────────────────

#[derive(Debug, Clone)]
pub struct EpochWatermark {
    watermarks: BTreeMap<u32, u64>,  // peer_id → highest epoch seen
    pub log: WatermarkLog,
}

impl EpochWatermark {
    pub fn new() -> Self { Self { watermarks: BTreeMap::new(), log: WatermarkLog::new() } }

    /// Report an epoch from a peer. Returns Advance if it raises the watermark, Stale otherwise.
    pub fn update(&mut self, peer_id: u32, epoch: u64) -> Result<WatermarkEvent, WatermarkError> {
        let prev_wm = *self.watermarks.get(&peer_id).unwrap_or(&0);

        if epoch > prev_wm {
            if !self.watermarks.contains_key(&peer_id) && self.watermarks.len() >= MAX_TRACKED_PEERS {
                return Err(WatermarkError::TooManyPeers);
            }
            self.watermarks.insert(peer_id, epoch);
            self.log.push(peer_id, epoch, prev_wm, epoch, WatermarkEvent::Advance);
            Ok(WatermarkEvent::Advance)
        } else {
            // epoch <= prev_wm: stale report (watermark unchanged)
            self.log.push(peer_id, epoch, prev_wm, prev_wm, WatermarkEvent::Stale);
            Ok(WatermarkEvent::Stale)
        }
    }

    pub fn watermark(&self, peer_id: u32) -> Option<u64> {
        self.watermarks.get(&peer_id).copied()
    }

    /// Minimum watermark across all tracked peers (consensus floor).
    pub fn global_floor(&self) -> Option<u64> {
        self.watermarks.values().copied().min()
    }

    /// Count of peers with watermark ≥ given epoch.
    pub fn peers_at_or_above(&self, epoch: u64) -> usize {
        self.watermarks.values().filter(|&&wm| wm >= epoch).count()
    }

    pub fn tracked_count(&self) -> usize { self.watermarks.len() }

    pub fn get_log(&self) -> &WatermarkLog { &self.log }
}

impl Default for EpochWatermark {
    fn default() -> Self { Self::new() }
}

// ─── Tests ────────────────────────────────────────────────────────────────────

#[cfg(test)]
mod tests {
    use super::*;

    // ── WatermarkEvent ────────────────────────────────────────────────────────

    #[test]
    fn event_bytes() {
        assert_eq!(WatermarkEvent::Advance.event_byte(), 0);
        assert_eq!(WatermarkEvent::Stale.event_byte(),   1);
    }

    // ── build_watermark_record ────────────────────────────────────────────────

    #[test]
    fn record_hash_nonzero() {
        let r = build_watermark_record(1, 5, 0, 5, WatermarkEvent::Advance, &WATERMARK_GENESIS_HASH);
        assert_ne!(r.record_hash, [0u8; 32]);
    }

    #[test]
    fn record_hash_deterministic() {
        let r1 = build_watermark_record(1, 5, 0, 5, WatermarkEvent::Advance, &WATERMARK_GENESIS_HASH);
        let r2 = build_watermark_record(1, 5, 0, 5, WatermarkEvent::Advance, &WATERMARK_GENESIS_HASH);
        assert_eq!(r1.record_hash, r2.record_hash);
    }

    // ── WatermarkLog ──────────────────────────────────────────────────────────

    #[test]
    fn log_counts_events() {
        let mut l = WatermarkLog::new();
        l.push(1, 5, 0, 5, WatermarkEvent::Advance);
        l.push(1, 3, 5, 5, WatermarkEvent::Stale);
        l.push(2, 10, 0, 10, WatermarkEvent::Advance);
        assert_eq!(l.advance_count(), 2);
        assert_eq!(l.stale_count(), 1);
    }

    #[test]
    fn log_chain_links() {
        let mut l = WatermarkLog::new();
        l.push(1, 5, 0, 5, WatermarkEvent::Advance);
        l.push(1, 10, 5, 10, WatermarkEvent::Advance);
        assert_eq!(l.records()[1].prev_hash, l.records()[0].record_hash);
    }

    #[test]
    fn log_verify_chain_valid() {
        let mut l = WatermarkLog::new();
        for i in 1..=5u64 {
            l.push(1, i * 10, (i - 1) * 10, i * 10, WatermarkEvent::Advance);
        }
        let (valid, broken) = l.verify_chain();
        assert!(valid);
        assert!(broken.is_none());
    }

    // ── EpochWatermark ────────────────────────────────────────────────────────

    #[test]
    fn advance_on_new_peer() {
        let mut w = EpochWatermark::new();
        assert_eq!(w.update(1, 5).unwrap(), WatermarkEvent::Advance);
        assert_eq!(w.watermark(1), Some(5));
    }

    #[test]
    fn advance_raises_watermark() {
        let mut w = EpochWatermark::new();
        w.update(1, 5).unwrap();
        assert_eq!(w.update(1, 10).unwrap(), WatermarkEvent::Advance);
        assert_eq!(w.watermark(1), Some(10));
    }

    #[test]
    fn stale_does_not_lower_watermark() {
        let mut w = EpochWatermark::new();
        w.update(1, 10).unwrap();
        assert_eq!(w.update(1, 5).unwrap(), WatermarkEvent::Stale);
        assert_eq!(w.watermark(1), Some(10)); // unchanged
    }

    #[test]
    fn same_epoch_is_stale() {
        let mut w = EpochWatermark::new();
        w.update(1, 10).unwrap();
        assert_eq!(w.update(1, 10).unwrap(), WatermarkEvent::Stale);
    }

    #[test]
    fn global_floor_is_minimum() {
        let mut w = EpochWatermark::new();
        w.update(1, 10).unwrap();
        w.update(2, 5).unwrap();
        w.update(3, 20).unwrap();
        assert_eq!(w.global_floor(), Some(5));
    }

    #[test]
    fn peers_at_or_above() {
        let mut w = EpochWatermark::new();
        w.update(1, 10).unwrap();
        w.update(2, 5).unwrap();
        w.update(3, 15).unwrap();
        assert_eq!(w.peers_at_or_above(10), 2); // peers 1 and 3
        assert_eq!(w.peers_at_or_above(5), 3);  // all three
    }

    #[test]
    fn watermark_none_for_unknown_peer() {
        let w = EpochWatermark::new();
        assert_eq!(w.watermark(99), None);
    }
}
