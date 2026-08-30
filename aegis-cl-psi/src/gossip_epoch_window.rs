//! Gate 380 — Gossip Epoch Window (T2)
//! EPISTEMIC TIER: T2 (engineering hypothesis)
//!
//! Maintains a fixed-size sliding window of recent gossip epoch coverage
//! observations, classifying the window as Healthy/Degraded/Critical based
//! on average coverage percentage.
//!
//! Window size: 4 (matches trend analyzer rolling window convention).
//!
//! GossipWindowState:
//!   Healthy  — avg_coverage_pct >= 75
//!   Degraded — avg_coverage_pct >= 50 && < 75
//!   Critical — avg_coverage_pct < 50
//!
//! GossipWindowEntry (hash-chained):
//!   epoch_end:         u64
//!   coverage_pct:      u32
//!   window_avg_pct:    u32   — floor average of last ≤4 entries
//!   state:             GossipWindowState
//!   entry_hash:        [u8;32]
//!   prev_hash:         [u8;32]
//!
//! entry_hash = SHA-256(prev[32] ‖ epoch_end_be8 ‖ coverage_pct_be4
//!                        ‖ window_avg_pct_be4 ‖ state_byte)
//!
//! GossipEpochWindow: push(epoch_end, coverage_pct),
//!   latest(), entry_count(), healthy/degraded/critical_count(),
//!   verify_chain().

use sha2::{Sha256, Digest};

pub const GOSSIP_WINDOW_GENESIS_HASH: [u8; 32] = [0u8; 32];
pub const GOSSIP_WINDOW_SIZE: usize = 4;

// ─── GossipWindowState ────────────────────────────────────────────────────────

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
#[repr(u8)]
pub enum GossipWindowState {
    Healthy  = 0,
    Degraded = 1,
    Critical = 2,
}

impl GossipWindowState {
    pub fn as_u8(self) -> u8 { self as u8 }

    fn classify(avg_coverage_pct: u32) -> Self {
        if avg_coverage_pct >= 75 { Self::Healthy }
        else if avg_coverage_pct >= 50 { Self::Degraded }
        else { Self::Critical }
    }
}

// ─── GossipWindowEntry ────────────────────────────────────────────────────────

#[derive(Debug, Clone, PartialEq)]
pub struct GossipWindowEntry {
    pub epoch_end:      u64,
    pub coverage_pct:   u32,
    pub window_avg_pct: u32,
    pub state:          GossipWindowState,
    pub entry_hash:     [u8; 32],
    pub prev_hash:      [u8; 32],
}

fn compute_window_hash(
    prev:           &[u8; 32],
    epoch_end:      u64,
    coverage_pct:   u32,
    window_avg_pct: u32,
    state:          GossipWindowState,
) -> [u8; 32] {
    let mut h = Sha256::new();
    h.update(prev);
    h.update(epoch_end.to_be_bytes());
    h.update(coverage_pct.to_be_bytes());
    h.update(window_avg_pct.to_be_bytes());
    h.update([state.as_u8()]);
    h.finalize().into()
}

// ─── GossipEpochWindow ────────────────────────────────────────────────────────

pub struct GossipEpochWindow {
    entries:       Vec<GossipWindowEntry>,
    window_buffer: Vec<u32>, // rolling coverage_pct values for avg computation
}

impl GossipEpochWindow {
    pub fn new() -> Self {
        Self {
            entries:       Vec::new(),
            window_buffer: Vec::new(),
        }
    }

    pub fn entry_count(&self) -> usize { self.entries.len() }
    pub fn is_empty(&self)    -> bool  { self.entries.is_empty() }
    pub fn entries(&self)     -> &[GossipWindowEntry] { &self.entries }
    pub fn latest(&self)      -> Option<&GossipWindowEntry> { self.entries.last() }

    pub fn healthy_count(&self) -> usize {
        self.entries.iter().filter(|e| e.state == GossipWindowState::Healthy).count()
    }

    pub fn degraded_count(&self) -> usize {
        self.entries.iter().filter(|e| e.state == GossipWindowState::Degraded).count()
    }

    pub fn critical_count(&self) -> usize {
        self.entries.iter().filter(|e| e.state == GossipWindowState::Critical).count()
    }

    /// Push a new coverage observation. Maintains a rolling window of size 4.
    pub fn push(&mut self, epoch_end: u64, coverage_pct: u32) -> &GossipWindowEntry {
        // Maintain rolling window
        self.window_buffer.push(coverage_pct);
        if self.window_buffer.len() > GOSSIP_WINDOW_SIZE {
            self.window_buffer.remove(0);
        }

        let sum: u64 = self.window_buffer.iter().map(|&v| v as u64).sum();
        let window_avg_pct = (sum / self.window_buffer.len() as u64) as u32;
        let state = GossipWindowState::classify(window_avg_pct);

        let prev = self.entries.last()
            .map(|e| e.entry_hash)
            .unwrap_or(GOSSIP_WINDOW_GENESIS_HASH);

        let entry_hash = compute_window_hash(&prev, epoch_end, coverage_pct, window_avg_pct, state);

        self.entries.push(GossipWindowEntry {
            epoch_end,
            coverage_pct,
            window_avg_pct,
            state,
            entry_hash,
            prev_hash: prev,
        });
        self.entries.last().unwrap()
    }

    pub fn verify_chain(&self) -> (bool, Option<usize>) {
        let mut prev = GOSSIP_WINDOW_GENESIS_HASH;
        for (i, e) in self.entries.iter().enumerate() {
            if e.prev_hash != prev {
                return (false, Some(i));
            }
            let expected = compute_window_hash(
                &prev, e.epoch_end, e.coverage_pct, e.window_avg_pct, e.state,
            );
            if e.entry_hash != expected {
                return (false, Some(i));
            }
            prev = e.entry_hash;
        }
        (true, None)
    }
}

impl Default for GossipEpochWindow {
    fn default() -> Self { Self::new() }
}

// ─── Tests ────────────────────────────────────────────────────────────────────

#[cfg(test)]
mod tests {
    use super::*;

    // ── GossipWindowState classification ─────────────────────────────────────

    #[test]
    fn state_healthy_at_100() {
        assert_eq!(GossipWindowState::classify(100), GossipWindowState::Healthy);
    }

    #[test]
    fn state_healthy_at_75() {
        assert_eq!(GossipWindowState::classify(75), GossipWindowState::Healthy);
    }

    #[test]
    fn state_degraded_at_74() {
        assert_eq!(GossipWindowState::classify(74), GossipWindowState::Degraded);
    }

    #[test]
    fn state_degraded_at_50() {
        assert_eq!(GossipWindowState::classify(50), GossipWindowState::Degraded);
    }

    #[test]
    fn state_critical_at_49() {
        assert_eq!(GossipWindowState::classify(49), GossipWindowState::Critical);
    }

    #[test]
    fn state_critical_at_0() {
        assert_eq!(GossipWindowState::classify(0), GossipWindowState::Critical);
    }

    // ── window average ────────────────────────────────────────────────────────

    #[test]
    fn first_entry_window_avg_equals_value() {
        let mut w = GossipEpochWindow::new();
        let e = w.push(1, 80);
        assert_eq!(e.window_avg_pct, 80);
    }

    #[test]
    fn window_rolls_after_4_entries() {
        let mut w = GossipEpochWindow::new();
        w.push(1, 100);
        w.push(2, 100);
        w.push(3, 100);
        w.push(4, 100);
        // Window now: [100,100,100,100] avg=100
        let e5 = w.push(5, 0);
        // Window now: [100,100,100,0] avg=75
        assert_eq!(e5.window_avg_pct, 75);
        assert_eq!(e5.state, GossipWindowState::Healthy);
    }

    #[test]
    fn window_cap_at_4() {
        let mut w = GossipEpochWindow::new();
        for i in 1u64..=5 { w.push(i, 0); }
        // After 5 pushes, window is still max 4 entries → avg=0
        assert_eq!(w.latest().unwrap().window_avg_pct, 0);
    }

    // ── push and state ────────────────────────────────────────────────────────

    #[test]
    fn push_stores_epoch_and_coverage() {
        let mut w = GossipEpochWindow::new();
        let e = w.push(7, 60);
        assert_eq!(e.epoch_end, 7);
        assert_eq!(e.coverage_pct, 60);
    }

    #[test]
    fn push_state_degraded() {
        let mut w = GossipEpochWindow::new();
        let e = w.push(1, 60);
        assert_eq!(e.state, GossipWindowState::Degraded);
    }

    #[test]
    fn push_state_critical() {
        let mut w = GossipEpochWindow::new();
        let e = w.push(1, 20);
        assert_eq!(e.state, GossipWindowState::Critical);
    }

    #[test]
    fn entry_hash_nonzero() {
        let mut w = GossipEpochWindow::new();
        let e = w.push(1, 80);
        assert_ne!(e.entry_hash, [0u8; 32]);
    }

    #[test]
    fn first_entry_prev_hash_is_genesis() {
        let mut w = GossipEpochWindow::new();
        let e = w.push(1, 80);
        assert_eq!(e.prev_hash, GOSSIP_WINDOW_GENESIS_HASH);
    }

    #[test]
    fn chain_prev_links() {
        let mut w = GossipEpochWindow::new();
        w.push(1, 80);
        let h0 = w.entries()[0].entry_hash;
        w.push(2, 70);
        assert_eq!(w.entries()[1].prev_hash, h0);
    }

    // ── aggregate counts ──────────────────────────────────────────────────────

    #[test]
    fn aggregate_counts_correct() {
        let mut w = GossipEpochWindow::new();
        w.push(1, 80); // window=[80],      avg=80 → Healthy
        w.push(2, 60); // window=[80,60],   avg=70 → Degraded
        w.push(3, 0);  // window=[80,60,0], avg=46 → Critical
        assert_eq!(w.healthy_count(), 1);
        assert_eq!(w.degraded_count(), 1);
        assert_eq!(w.critical_count(), 1);
    }

    // ── verify_chain ──────────────────────────────────────────────────────────

    #[test]
    fn verify_chain_empty_ok() {
        let w = GossipEpochWindow::new();
        let (ok, idx) = w.verify_chain();
        assert!(ok);
        assert!(idx.is_none());
    }

    #[test]
    fn verify_chain_multiple_ok() {
        let mut w = GossipEpochWindow::new();
        for i in 1u64..=5 { w.push(i, 80); }
        let (ok, idx) = w.verify_chain();
        assert!(ok);
        assert!(idx.is_none());
    }

    #[test]
    fn verify_chain_detects_tamper() {
        let mut w = GossipEpochWindow::new();
        w.push(1, 80);
        w.push(2, 70);
        w.entries[0].entry_hash[0] ^= 0xFF;
        let (ok, idx) = w.verify_chain();
        assert!(!ok);
        assert_eq!(idx, Some(0));
    }

    // ── determinism ───────────────────────────────────────────────────────────

    #[test]
    fn entry_hash_deterministic() {
        let mut w1 = GossipEpochWindow::new();
        let mut w2 = GossipEpochWindow::new();
        let h1 = w1.push(5, 75).entry_hash;
        let h2 = w2.push(5, 75).entry_hash;
        assert_eq!(h1, h2);
    }
}
