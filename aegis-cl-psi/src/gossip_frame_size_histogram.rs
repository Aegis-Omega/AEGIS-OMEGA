//! Gate 397 — Gossip Frame Size Histogram (T2)
//! EPISTEMIC TIER: T2 (engineering hypothesis)
//!
//! Per-epoch histogram of gossip frame sizes bucketed into three ranges:
//!   small_count:  u32 — frames with size_bytes < 256
//!   medium_count: u32 — frames with 256 <= size_bytes < 1024
//!   large_count:  u32 — frames with size_bytes >= 1024
//!
//! total_frames = small_count + medium_count + large_count (saturating_add chain).
//!
//! GossipFrameSizeHistogramEntry (hash-chained):
//!   epoch_end:    u64
//!   small_count:  u32
//!   medium_count: u32
//!   large_count:  u32
//!   total_frames: u32
//!   entry_hash:   [u8;32]
//!   prev_hash:    [u8;32]
//!
//! entry_hash = SHA-256(prev[32] ‖ epoch_end_be8 ‖ small_count_be4
//!                       ‖ medium_count_be4 ‖ large_count_be4 ‖ total_frames_be4)
//!
//! GossipFrameSizeHistogramLog: record(epoch_end, small, medium, large),
//!   total_small(), total_medium(), total_large(), dominant_bucket(), verify_chain().

use sha2::{Sha256, Digest};

pub const GOSSIP_FRAME_SIZE_HISTOGRAM_GENESIS_HASH: [u8; 32] = [0u8; 32];

// ─── FrameSizeBucket ──────────────────────────────────────────────────────────

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum FrameSizeBucket {
    Small,   // < 256 bytes
    Medium,  // 256..1024 bytes
    Large,   // >= 1024 bytes
    Tied,    // two or more buckets share the maximum
}

// ─── GossipFrameSizeHistogramEntry ────────────────────────────────────────────

#[derive(Debug, Clone, PartialEq)]
pub struct GossipFrameSizeHistogramEntry {
    pub epoch_end:    u64,
    pub small_count:  u32,
    pub medium_count: u32,
    pub large_count:  u32,
    pub total_frames: u32,
    pub entry_hash:   [u8; 32],
    pub prev_hash:    [u8; 32],
}

fn compute_frame_size_histogram_hash(
    prev:         &[u8; 32],
    epoch_end:    u64,
    small_count:  u32,
    medium_count: u32,
    large_count:  u32,
    total_frames: u32,
) -> [u8; 32] {
    let mut h = Sha256::new();
    h.update(prev);
    h.update(epoch_end.to_be_bytes());
    h.update(small_count.to_be_bytes());
    h.update(medium_count.to_be_bytes());
    h.update(large_count.to_be_bytes());
    h.update(total_frames.to_be_bytes());
    h.finalize().into()
}

// ─── GossipFrameSizeHistogramLog ──────────────────────────────────────────────

pub struct GossipFrameSizeHistogramLog {
    entries: Vec<GossipFrameSizeHistogramEntry>,
}

impl GossipFrameSizeHistogramLog {
    pub fn new() -> Self { Self { entries: Vec::new() } }

    pub fn entry_count(&self) -> usize { self.entries.len() }
    pub fn is_empty(&self)    -> bool  { self.entries.is_empty() }
    pub fn entries(&self)     -> &[GossipFrameSizeHistogramEntry] { &self.entries }
    pub fn latest(&self)      -> Option<&GossipFrameSizeHistogramEntry> { self.entries.last() }

    /// Total small-bucket frames across all epochs.
    pub fn total_small(&self) -> u64 {
        self.entries.iter().map(|e| e.small_count as u64).sum()
    }

    /// Total medium-bucket frames across all epochs.
    pub fn total_medium(&self) -> u64 {
        self.entries.iter().map(|e| e.medium_count as u64).sum()
    }

    /// Total large-bucket frames across all epochs.
    pub fn total_large(&self) -> u64 {
        self.entries.iter().map(|e| e.large_count as u64).sum()
    }

    /// Bucket with the most frames across all epochs. Returns Tied if two share the max.
    pub fn dominant_bucket(&self) -> FrameSizeBucket {
        let s = self.total_small();
        let m = self.total_medium();
        let l = self.total_large();
        let max = s.max(m).max(l);
        let leaders = [s == max, m == max, l == max].iter().filter(|&&x| x).count();
        if leaders > 1 {
            FrameSizeBucket::Tied
        } else if s == max {
            FrameSizeBucket::Small
        } else if m == max {
            FrameSizeBucket::Medium
        } else {
            FrameSizeBucket::Large
        }
    }

    /// Record a frame size histogram for one epoch.
    /// total_frames = small.saturating_add(medium).saturating_add(large).
    pub fn record(
        &mut self,
        epoch_end:    u64,
        small_count:  u32,
        medium_count: u32,
        large_count:  u32,
    ) -> &GossipFrameSizeHistogramEntry {
        let total_frames = small_count
            .saturating_add(medium_count)
            .saturating_add(large_count);

        let prev = self.entries.last()
            .map(|e| e.entry_hash)
            .unwrap_or(GOSSIP_FRAME_SIZE_HISTOGRAM_GENESIS_HASH);

        let entry_hash = compute_frame_size_histogram_hash(
            &prev, epoch_end, small_count, medium_count, large_count, total_frames,
        );

        self.entries.push(GossipFrameSizeHistogramEntry {
            epoch_end,
            small_count,
            medium_count,
            large_count,
            total_frames,
            entry_hash,
            prev_hash: prev,
        });
        self.entries.last().unwrap()
    }

    pub fn verify_chain(&self) -> (bool, Option<usize>) {
        let mut prev = GOSSIP_FRAME_SIZE_HISTOGRAM_GENESIS_HASH;
        for (i, e) in self.entries.iter().enumerate() {
            if e.prev_hash != prev {
                return (false, Some(i));
            }
            let expected = compute_frame_size_histogram_hash(
                &prev, e.epoch_end, e.small_count, e.medium_count,
                e.large_count, e.total_frames,
            );
            if e.entry_hash != expected {
                return (false, Some(i));
            }
            prev = e.entry_hash;
        }
        (true, None)
    }
}

impl Default for GossipFrameSizeHistogramLog {
    fn default() -> Self { Self::new() }
}

// ─── Tests ────────────────────────────────────────────────────────────────────

#[cfg(test)]
mod tests {
    use super::*;

    // ── record fields ─────────────────────────────────────────────────────────

    #[test]
    fn record_fields_stored() {
        let mut log = GossipFrameSizeHistogramLog::new();
        let e = log.record(1, 10, 5, 2);
        assert_eq!(e.epoch_end, 1);
        assert_eq!(e.small_count, 10);
        assert_eq!(e.medium_count, 5);
        assert_eq!(e.large_count, 2);
        assert_eq!(e.total_frames, 17);
    }

    #[test]
    fn zero_histogram_stored() {
        let mut log = GossipFrameSizeHistogramLog::new();
        let e = log.record(1, 0, 0, 0);
        assert_eq!(e.total_frames, 0);
    }

    #[test]
    fn total_frames_saturates() {
        let mut log = GossipFrameSizeHistogramLog::new();
        let e = log.record(1, u32::MAX, 1, 0);
        assert_eq!(e.total_frames, u32::MAX);
    }

    // ── aggregate totals ──────────────────────────────────────────────────────

    #[test]
    fn totals_correct() {
        let mut log = GossipFrameSizeHistogramLog::new();
        log.record(1, 10, 5, 2);
        log.record(2, 3, 8, 4);
        log.record(3, 7, 1, 1);
        assert_eq!(log.total_small(), 20);
        assert_eq!(log.total_medium(), 14);
        assert_eq!(log.total_large(), 7);
    }

    // ── dominant_bucket ───────────────────────────────────────────────────────

    #[test]
    fn dominant_small() {
        let mut log = GossipFrameSizeHistogramLog::new();
        log.record(1, 100, 20, 10);
        assert_eq!(log.dominant_bucket(), FrameSizeBucket::Small);
    }

    #[test]
    fn dominant_medium() {
        let mut log = GossipFrameSizeHistogramLog::new();
        log.record(1, 5, 50, 10);
        assert_eq!(log.dominant_bucket(), FrameSizeBucket::Medium);
    }

    #[test]
    fn dominant_large() {
        let mut log = GossipFrameSizeHistogramLog::new();
        log.record(1, 5, 10, 80);
        assert_eq!(log.dominant_bucket(), FrameSizeBucket::Large);
    }

    #[test]
    fn dominant_tied() {
        let mut log = GossipFrameSizeHistogramLog::new();
        log.record(1, 10, 10, 5);
        assert_eq!(log.dominant_bucket(), FrameSizeBucket::Tied);
    }

    #[test]
    fn dominant_empty_tied() {
        let log = GossipFrameSizeHistogramLog::new();
        // all zeros — all equal → Tied
        assert_eq!(log.dominant_bucket(), FrameSizeBucket::Tied);
    }

    // ── hash chain ────────────────────────────────────────────────────────────

    #[test]
    fn entry_hash_nonzero() {
        let mut log = GossipFrameSizeHistogramLog::new();
        let e = log.record(1, 10, 5, 2);
        assert_ne!(e.entry_hash, [0u8; 32]);
    }

    #[test]
    fn first_entry_prev_hash_is_genesis() {
        let mut log = GossipFrameSizeHistogramLog::new();
        let e = log.record(1, 10, 5, 2);
        assert_eq!(e.prev_hash, GOSSIP_FRAME_SIZE_HISTOGRAM_GENESIS_HASH);
    }

    #[test]
    fn chain_prev_links() {
        let mut log = GossipFrameSizeHistogramLog::new();
        log.record(1, 10, 5, 2);
        let h0 = log.entries()[0].entry_hash;
        log.record(2, 3, 8, 4);
        assert_eq!(log.entries()[1].prev_hash, h0);
    }

    // ── verify_chain ──────────────────────────────────────────────────────────

    #[test]
    fn verify_chain_empty_ok() {
        let log = GossipFrameSizeHistogramLog::new();
        let (ok, idx) = log.verify_chain();
        assert!(ok);
        assert!(idx.is_none());
    }

    #[test]
    fn verify_chain_multiple_ok() {
        let mut log = GossipFrameSizeHistogramLog::new();
        for i in 1u64..=5 { log.record(i, i as u32, i as u32 * 2, i as u32); }
        let (ok, idx) = log.verify_chain();
        assert!(ok);
        assert!(idx.is_none());
    }

    #[test]
    fn verify_chain_detects_tamper() {
        let mut log = GossipFrameSizeHistogramLog::new();
        log.record(1, 10, 5, 2);
        log.record(2, 3, 8, 4);
        log.entries[0].entry_hash[0] ^= 0xFF;
        let (ok, idx) = log.verify_chain();
        assert!(!ok);
        assert_eq!(idx, Some(0));
    }

    // ── determinism ───────────────────────────────────────────────────────────

    #[test]
    fn entry_hash_deterministic() {
        let mut l1 = GossipFrameSizeHistogramLog::new();
        let mut l2 = GossipFrameSizeHistogramLog::new();
        let h1 = l1.record(3, 15, 8, 4).entry_hash;
        let h2 = l2.record(3, 15, 8, 4).entry_hash;
        assert_eq!(h1, h2);
    }
}
