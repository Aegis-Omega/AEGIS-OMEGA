//! Gate 386 — Gossip Jitter Tracker (T2)
//! EPISTEMIC TIER: T2 (engineering hypothesis)
//!
//! Measures epoch-to-epoch delivery jitter as the absolute difference between
//! consecutive epoch frame counts. High jitter indicates unstable throughput.
//! All arithmetic is integer — no f64.
//!
//! GossipJitterEntry (hash-chained):
//!   epoch_end:      u64
//!   frame_count:    u32   — frames delivered this epoch
//!   jitter:         u32   — |frame_count - prev_frame_count| (0 for first entry)
//!   entry_hash:     [u8;32]
//!   prev_hash:      [u8;32]
//!
//! entry_hash = SHA-256(prev[32] ‖ epoch_end_be8 ‖ frame_count_be4 ‖ jitter_be4)
//!
//! GossipJitterLog: record(epoch_end, frame_count),
//!   latest(), entry_count(), max_jitter(), avg_jitter(), verify_chain().

use sha2::{Sha256, Digest};

pub const GOSSIP_JITTER_GENESIS_HASH: [u8; 32] = [0u8; 32];

// ─── GossipJitterEntry ────────────────────────────────────────────────────────

#[derive(Debug, Clone, PartialEq)]
pub struct GossipJitterEntry {
    pub epoch_end:   u64,
    pub frame_count: u32,
    pub jitter:      u32,
    pub entry_hash:  [u8; 32],
    pub prev_hash:   [u8; 32],
}

fn compute_jitter_hash(
    prev:        &[u8; 32],
    epoch_end:   u64,
    frame_count: u32,
    jitter:      u32,
) -> [u8; 32] {
    let mut h = Sha256::new();
    h.update(prev);
    h.update(epoch_end.to_be_bytes());
    h.update(frame_count.to_be_bytes());
    h.update(jitter.to_be_bytes());
    h.finalize().into()
}

// ─── GossipJitterLog ──────────────────────────────────────────────────────────

pub struct GossipJitterLog {
    entries:          Vec<GossipJitterEntry>,
    last_frame_count: Option<u32>,
}

impl GossipJitterLog {
    pub fn new() -> Self {
        Self {
            entries:          Vec::new(),
            last_frame_count: None,
        }
    }

    pub fn entry_count(&self) -> usize { self.entries.len() }
    pub fn is_empty(&self)    -> bool  { self.entries.is_empty() }
    pub fn entries(&self)     -> &[GossipJitterEntry] { &self.entries }
    pub fn latest(&self)      -> Option<&GossipJitterEntry> { self.entries.last() }

    /// Maximum jitter value across all entries. Returns 0 if empty.
    pub fn max_jitter(&self) -> u32 {
        self.entries.iter().map(|e| e.jitter).max().unwrap_or(0)
    }

    /// Integer average jitter (floor). Returns 0 if empty.
    pub fn avg_jitter(&self) -> u32 {
        if self.entries.is_empty() { return 0; }
        let sum: u64 = self.entries.iter().map(|e| e.jitter as u64).sum();
        (sum / self.entries.len() as u64) as u32
    }

    /// Record frame count for one epoch.
    /// jitter = |frame_count - prev_frame_count| (0 for the first entry).
    pub fn record(&mut self, epoch_end: u64, frame_count: u32) -> &GossipJitterEntry {
        let jitter = match self.last_frame_count {
            None    => 0,
            Some(p) => if frame_count >= p { frame_count - p } else { p - frame_count },
        };

        self.last_frame_count = Some(frame_count);

        let prev = self.entries.last()
            .map(|e| e.entry_hash)
            .unwrap_or(GOSSIP_JITTER_GENESIS_HASH);

        let entry_hash = compute_jitter_hash(&prev, epoch_end, frame_count, jitter);

        self.entries.push(GossipJitterEntry {
            epoch_end,
            frame_count,
            jitter,
            entry_hash,
            prev_hash: prev,
        });
        self.entries.last().unwrap()
    }

    pub fn verify_chain(&self) -> (bool, Option<usize>) {
        let mut prev = GOSSIP_JITTER_GENESIS_HASH;
        for (i, e) in self.entries.iter().enumerate() {
            if e.prev_hash != prev {
                return (false, Some(i));
            }
            let expected = compute_jitter_hash(&prev, e.epoch_end, e.frame_count, e.jitter);
            if e.entry_hash != expected {
                return (false, Some(i));
            }
            prev = e.entry_hash;
        }
        (true, None)
    }
}

impl Default for GossipJitterLog {
    fn default() -> Self { Self::new() }
}

// ─── Tests ────────────────────────────────────────────────────────────────────

#[cfg(test)]
mod tests {
    use super::*;

    // ── jitter computation ────────────────────────────────────────────────────

    #[test]
    fn first_entry_jitter_zero() {
        let mut log = GossipJitterLog::new();
        let e = log.record(1, 50);
        assert_eq!(e.jitter, 0);
    }

    #[test]
    fn jitter_positive_when_count_increases() {
        let mut log = GossipJitterLog::new();
        log.record(1, 40);
        let e = log.record(2, 60);
        assert_eq!(e.jitter, 20);
    }

    #[test]
    fn jitter_positive_when_count_decreases() {
        let mut log = GossipJitterLog::new();
        log.record(1, 60);
        let e = log.record(2, 40);
        assert_eq!(e.jitter, 20);
    }

    #[test]
    fn jitter_zero_when_same_count() {
        let mut log = GossipJitterLog::new();
        log.record(1, 50);
        let e = log.record(2, 50);
        assert_eq!(e.jitter, 0);
    }

    #[test]
    fn jitter_is_absolute_difference() {
        let mut log = GossipJitterLog::new();
        log.record(1, 100);
        log.record(2, 10);   // jitter = 90
        let e = log.record(3, 60);  // jitter = |60-10| = 50
        assert_eq!(e.jitter, 50);
    }

    // ── aggregate stats ───────────────────────────────────────────────────────

    #[test]
    fn max_jitter_empty_zero() {
        let log = GossipJitterLog::new();
        assert_eq!(log.max_jitter(), 0);
    }

    #[test]
    fn max_jitter_correct() {
        let mut log = GossipJitterLog::new();
        log.record(1, 10);
        log.record(2, 50);  // jitter=40
        log.record(3, 20);  // jitter=30
        assert_eq!(log.max_jitter(), 40);
    }

    #[test]
    fn avg_jitter_empty_zero() {
        let log = GossipJitterLog::new();
        assert_eq!(log.avg_jitter(), 0);
    }

    #[test]
    fn avg_jitter_floor() {
        let mut log = GossipJitterLog::new();
        log.record(1, 0);    // jitter=0
        log.record(2, 10);   // jitter=10
        log.record(3, 21);   // jitter=11
        // avg = floor((0+10+11)/3) = floor(7) = 7
        assert_eq!(log.avg_jitter(), 7);
    }

    // ── fields ────────────────────────────────────────────────────────────────

    #[test]
    fn record_fields_stored() {
        let mut log = GossipJitterLog::new();
        let e = log.record(7, 42);
        assert_eq!(e.epoch_end, 7);
        assert_eq!(e.frame_count, 42);
    }

    #[test]
    fn entry_hash_nonzero() {
        let mut log = GossipJitterLog::new();
        let e = log.record(1, 50);
        assert_ne!(e.entry_hash, [0u8; 32]);
    }

    #[test]
    fn first_entry_prev_hash_is_genesis() {
        let mut log = GossipJitterLog::new();
        let e = log.record(1, 50);
        assert_eq!(e.prev_hash, GOSSIP_JITTER_GENESIS_HASH);
    }

    #[test]
    fn chain_prev_links() {
        let mut log = GossipJitterLog::new();
        log.record(1, 50);
        let h0 = log.entries()[0].entry_hash;
        log.record(2, 60);
        assert_eq!(log.entries()[1].prev_hash, h0);
    }

    // ── verify_chain ──────────────────────────────────────────────────────────

    #[test]
    fn verify_chain_empty_ok() {
        let log = GossipJitterLog::new();
        let (ok, idx) = log.verify_chain();
        assert!(ok);
        assert!(idx.is_none());
    }

    #[test]
    fn verify_chain_multiple_ok() {
        let mut log = GossipJitterLog::new();
        for i in 1u64..=5 { log.record(i, (i * 10) as u32); }
        let (ok, idx) = log.verify_chain();
        assert!(ok);
        assert!(idx.is_none());
    }

    #[test]
    fn verify_chain_detects_tamper() {
        let mut log = GossipJitterLog::new();
        log.record(1, 50);
        log.record(2, 60);
        log.entries[0].entry_hash[0] ^= 0xFF;
        let (ok, idx) = log.verify_chain();
        assert!(!ok);
        assert_eq!(idx, Some(0));
    }

    // ── determinism ───────────────────────────────────────────────────────────

    #[test]
    fn entry_hash_deterministic() {
        let mut l1 = GossipJitterLog::new();
        let mut l2 = GossipJitterLog::new();
        let h1 = l1.record(5, 75).entry_hash;
        let h2 = l2.record(5, 75).entry_hash;
        assert_eq!(h1, h2);
    }
}
