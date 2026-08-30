//! Gate 327 — Synthesis Resilience Monitor (T2)
//! EPISTEMIC TIER: T2 (engineering hypothesis)
//!
//! Rolling-window health tracker for the constitutional synthesis arc
//! (Gates 320–326) under network stress. Detects three failure signatures:
//!
//!   T0Oscillation  — T0 verdict flips more than OSCILLATION_THRESHOLD times
//!                    within the window (sign of Byzantine influence or gossip instability)
//!   QuorumLoss     — fraction of epochs with quorum_converged < 1/φ in window
//!                    exceeds QUORUM_LOSS_THRESHOLD
//!   EpochGap       — epochs arrive non-consecutively (drop > MAX_ALLOWED_GAP)
//!
//! Constants:
//!   WINDOW_SIZE             = 8  epochs
//!   OSCILLATION_THRESHOLD   = 3  flips within window → alert
//!   QUORUM_LOSS_THRESHOLD   = 3  non-quorum epochs within window → alert
//!   MAX_ALLOWED_GAP         = 2  missing epoch slots allowed before EpochGap fires
//!
//! ResilienceVerdict: Healthy / T0Oscillating / QuorumLoss / EpochGap / Degraded(multiple)
//! ResilienceRecord: hash-chained per-epoch snapshot.
//! SynthesisResilienceMonitor: observe(), latest(), current_verdict(), verify_chain().

use sha2::{Sha256, Digest};
use std::collections::VecDeque;

pub const RESILIENCE_GENESIS_HASH:   [u8; 32] = [0u8; 32];
pub const WINDOW_SIZE:               usize     = 8;
pub const OSCILLATION_THRESHOLD:     usize     = 3;
pub const QUORUM_LOSS_THRESHOLD:     usize     = 3;
pub const MAX_ALLOWED_GAP:           u64       = 2;

// ─── ResilienceVerdict ────────────────────────────────────────────────────────

/// Constitutional synthesis resilience verdict for the rolling window.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum ResilienceVerdict {
    Healthy,       // all three checks pass
    T0Oscillating, // T0 flips exceed threshold
    QuorumLoss,    // too many non-quorum epochs in window
    EpochGap,      // epoch sequence gap detected
    Degraded,      // two or more failure signatures simultaneously
}

impl ResilienceVerdict {
    pub fn is_healthy(self) -> bool { self == ResilienceVerdict::Healthy }

    fn from_flags(oscillating: bool, quorum_loss: bool, epoch_gap: bool) -> Self {
        let count = oscillating as usize + quorum_loss as usize + epoch_gap as usize;
        match count {
            0 => ResilienceVerdict::Healthy,
            1 if oscillating  => ResilienceVerdict::T0Oscillating,
            1 if quorum_loss  => ResilienceVerdict::QuorumLoss,
            1                 => ResilienceVerdict::EpochGap,
            _                 => ResilienceVerdict::Degraded,
        }
    }
}

// ─── Epoch Snapshot ───────────────────────────────────────────────────────────

/// Compact per-epoch observation fed into the rolling window.
#[derive(Debug, Clone, Copy)]
pub struct EpochSnapshot {
    pub epoch:          u64,
    pub t0_verdict:     bool,
    pub quorum_met:     bool,
}

// ─── ResilienceRecord ─────────────────────────────────────────────────────────

/// One hash-chained resilience record produced per observed epoch.
#[derive(Debug, Clone, PartialEq)]
pub struct ResilienceRecord {
    pub epoch:            u64,
    pub t0_verdict:       bool,
    pub quorum_met:       bool,
    pub verdict:          ResilienceVerdict,
    pub flip_count:       u8,   // T0 flips within current window
    pub quorum_miss_count: u8,  // non-quorum epochs within current window
    pub record_hash:      [u8; 32],
    pub prev_hash:        [u8; 32],
}

// ─── Hash ─────────────────────────────────────────────────────────────────────

fn verdict_byte(v: ResilienceVerdict) -> u8 {
    match v {
        ResilienceVerdict::Healthy       => 0,
        ResilienceVerdict::T0Oscillating => 1,
        ResilienceVerdict::QuorumLoss    => 2,
        ResilienceVerdict::EpochGap      => 3,
        ResilienceVerdict::Degraded      => 4,
    }
}

fn compute_record_hash(
    prev:        &[u8; 32],
    epoch:       u64,
    t0:          bool,
    quorum:      bool,
    verdict:     ResilienceVerdict,
    flips:       u8,
    quorum_miss: u8,
) -> [u8; 32] {
    let mut h = Sha256::new();
    h.update(prev);
    h.update(epoch.to_be_bytes());
    h.update([t0 as u8]);
    h.update([quorum as u8]);
    h.update([verdict_byte(verdict)]);
    h.update([flips]);
    h.update([quorum_miss]);
    h.finalize().into()
}

// ─── SynthesisResilienceMonitor ───────────────────────────────────────────────

/// Rolling-window monitor for the synthesis arc under network stress.
pub struct SynthesisResilienceMonitor {
    records:     Vec<ResilienceRecord>,
    /// Sliding window of recent epoch snapshots (length ≤ WINDOW_SIZE).
    window:      VecDeque<EpochSnapshot>,
    last_epoch:  Option<u64>,
}

impl SynthesisResilienceMonitor {
    pub fn new() -> Self {
        Self {
            records:    Vec::new(),
            window:     VecDeque::with_capacity(WINDOW_SIZE + 1),
            last_epoch: None,
        }
    }

    pub fn len(&self)      -> usize { self.records.len() }
    pub fn is_empty(&self) -> bool  { self.records.is_empty() }
    pub fn records(&self)  -> &[ResilienceRecord] { &self.records }

    /// Observe one epoch snapshot, update the rolling window, produce a record.
    pub fn observe(&mut self, snap: EpochSnapshot) -> ResilienceRecord {
        // Epoch gap detection
        let epoch_gap = match self.last_epoch {
            Some(prev) => snap.epoch.saturating_sub(prev) > MAX_ALLOWED_GAP + 1,
            None       => false,
        };
        self.last_epoch = Some(snap.epoch);

        // Push into window; evict oldest if at capacity
        self.window.push_back(snap);
        if self.window.len() > WINDOW_SIZE {
            self.window.pop_front();
        }

        // Count T0 flips within window
        let flip_count = self.count_flips();

        // Count non-quorum epochs within window
        let quorum_miss_count = self.window.iter()
            .filter(|s| !s.quorum_met)
            .count() as u8;

        let oscillating  = (flip_count as usize) >= OSCILLATION_THRESHOLD;
        let quorum_loss  = (quorum_miss_count as usize) >= QUORUM_LOSS_THRESHOLD;
        let verdict      = ResilienceVerdict::from_flags(oscillating, quorum_loss, epoch_gap);

        let prev = self.records.last()
            .map(|r| r.record_hash)
            .unwrap_or(RESILIENCE_GENESIS_HASH);

        let record_hash = compute_record_hash(
            &prev, snap.epoch, snap.t0_verdict, snap.quorum_met,
            verdict, flip_count, quorum_miss_count,
        );

        let rec = ResilienceRecord {
            epoch:             snap.epoch,
            t0_verdict:        snap.t0_verdict,
            quorum_met:        snap.quorum_met,
            verdict,
            flip_count,
            quorum_miss_count,
            record_hash,
            prev_hash: prev,
        };
        self.records.push(rec.clone());
        rec
    }

    /// Most recent resilience record, or `None` if empty.
    pub fn latest(&self) -> Option<&ResilienceRecord> {
        self.records.last()
    }

    /// Current resilience verdict, or `None` if empty.
    pub fn current_verdict(&self) -> Option<ResilienceVerdict> {
        self.latest().map(|r| r.verdict)
    }

    /// Count healthy epochs in all records.
    pub fn healthy_count(&self) -> usize {
        self.records.iter().filter(|r| r.verdict.is_healthy()).count()
    }

    /// Count records with Degraded verdict (multiple failure signatures).
    pub fn degraded_count(&self) -> usize {
        self.records.iter()
            .filter(|r| r.verdict == ResilienceVerdict::Degraded)
            .count()
    }

    /// Verify hash chain integrity.
    pub fn verify_chain(&self) -> (bool, Option<usize>) {
        let mut prev = RESILIENCE_GENESIS_HASH;
        for (i, r) in self.records.iter().enumerate() {
            if r.prev_hash != prev {
                return (false, Some(i));
            }
            let expected = compute_record_hash(
                &prev, r.epoch, r.t0_verdict, r.quorum_met,
                r.verdict, r.flip_count, r.quorum_miss_count,
            );
            if r.record_hash != expected {
                return (false, Some(i));
            }
            prev = r.record_hash;
        }
        (true, None)
    }

    // Count T0 flips (adjacent changes) in current window
    fn count_flips(&self) -> u8 {
        let mut flips = 0u8;
        let snaps: Vec<_> = self.window.iter().collect();
        for w in snaps.windows(2) {
            if w[0].t0_verdict != w[1].t0_verdict {
                flips = flips.saturating_add(1);
            }
        }
        flips
    }
}

impl Default for SynthesisResilienceMonitor {
    fn default() -> Self { Self::new() }
}

// ─── Tests ────────────────────────────────────────────────────────────────────

#[cfg(test)]
mod tests {
    use super::*;

    fn snap(epoch: u64, t0: bool, quorum: bool) -> EpochSnapshot {
        EpochSnapshot { epoch, t0_verdict: t0, quorum_met: quorum }
    }

    fn healthy(epoch: u64) -> EpochSnapshot { snap(epoch, true, true) }

    // ── Genesis ───────────────────────────────────────────────────────────────

    #[test]
    fn constants_correct() {
        assert_eq!(WINDOW_SIZE, 8);
        assert_eq!(OSCILLATION_THRESHOLD, 3);
        assert_eq!(QUORUM_LOSS_THRESHOLD, 3);
        assert_eq!(MAX_ALLOWED_GAP, 2);
    }

    #[test]
    fn fresh_monitor_empty() {
        let m = SynthesisResilienceMonitor::new();
        assert!(m.is_empty());
        assert!(m.current_verdict().is_none());
    }

    // ── Healthy baseline ──────────────────────────────────────────────────────

    #[test]
    fn all_healthy_epochs_produce_healthy_verdict() {
        let mut m = SynthesisResilienceMonitor::new();
        for epoch in 1..=8u64 {
            let r = m.observe(healthy(epoch));
            assert_eq!(r.verdict, ResilienceVerdict::Healthy, "epoch {epoch}");
        }
        assert_eq!(m.healthy_count(), 8);
    }

    // ── T0 Oscillation ────────────────────────────────────────────────────────

    #[test]
    fn three_flips_triggers_t0_oscillating() {
        let mut m = SynthesisResilienceMonitor::new();
        // Alternating T0: T F T F T — 4 flips (> threshold=3)
        m.observe(snap(1, true,  true));
        m.observe(snap(2, false, true));
        m.observe(snap(3, true,  true));
        m.observe(snap(4, false, true));
        let r = m.observe(snap(5, true, true)); // 4th flip
        assert_eq!(r.verdict, ResilienceVerdict::T0Oscillating);
    }

    #[test]
    fn two_flips_below_oscillation_threshold() {
        let mut m = SynthesisResilienceMonitor::new();
        m.observe(snap(1, true,  true));
        m.observe(snap(2, false, true)); // flip 1
        let r = m.observe(snap(3, true, true)); // flip 2 (< 3 threshold)
        assert_eq!(r.verdict, ResilienceVerdict::Healthy);
    }

    // ── Quorum Loss ───────────────────────────────────────────────────────────

    #[test]
    fn three_quorum_misses_triggers_quorum_loss() {
        let mut m = SynthesisResilienceMonitor::new();
        m.observe(snap(1, true, false)); // miss 1
        m.observe(snap(2, true, false)); // miss 2
        let r = m.observe(snap(3, true, false)); // miss 3
        assert_eq!(r.verdict, ResilienceVerdict::QuorumLoss);
    }

    #[test]
    fn two_quorum_misses_below_threshold() {
        let mut m = SynthesisResilienceMonitor::new();
        m.observe(snap(1, true, false)); // miss 1
        let r = m.observe(snap(2, true, false)); // miss 2 (< 3)
        assert_eq!(r.verdict, ResilienceVerdict::Healthy);
    }

    // ── Epoch Gap ─────────────────────────────────────────────────────────────

    #[test]
    fn epoch_gap_beyond_max_triggers() {
        let mut m = SynthesisResilienceMonitor::new();
        m.observe(snap(1, true, true));
        // Jump from 1 to 5 → gap = 4 > MAX_ALLOWED_GAP(2)+1=3 → EpochGap
        let r = m.observe(snap(5, true, true));
        assert_eq!(r.verdict, ResilienceVerdict::EpochGap);
    }

    #[test]
    fn epoch_gap_at_max_allowed_ok() {
        let mut m = SynthesisResilienceMonitor::new();
        m.observe(snap(1, true, true));
        // Jump 1→4 → gap=3 = MAX_ALLOWED_GAP(2)+1 → NOT a gap (> not >=)
        let r = m.observe(snap(4, true, true));
        assert_eq!(r.verdict, ResilienceVerdict::Healthy);
    }

    #[test]
    fn first_epoch_never_triggers_gap() {
        let mut m = SynthesisResilienceMonitor::new();
        let r = m.observe(snap(100, true, true)); // no previous epoch
        assert_eq!(r.verdict, ResilienceVerdict::Healthy);
    }

    // ── Degraded (multiple failures) ──────────────────────────────────────────

    #[test]
    fn oscillation_plus_quorum_loss_is_degraded() {
        let mut m = SynthesisResilienceMonitor::new();
        // Build 3+ quorum misses and 3+ T0 flips simultaneously
        m.observe(snap(1, true,  false)); // quorum miss, no flip
        m.observe(snap(2, false, false)); // quorum miss, flip 1
        m.observe(snap(3, true,  false)); // quorum miss (3), flip 2
        let r = m.observe(snap(4, false, true)); // flip 3 → oscillating + quorum_loss
        assert_eq!(r.verdict, ResilienceVerdict::Degraded);
    }

    // ── Window eviction ───────────────────────────────────────────────────────

    #[test]
    fn window_evicts_oldest_entries() {
        let mut m = SynthesisResilienceMonitor::new();
        // First 8 epochs: T0 alternates (oscillating)
        for epoch in 1..=8u64 {
            m.observe(snap(epoch, epoch % 2 == 1, true));
        }
        // Now push 8 clean healthy epochs — oscillation window should clear
        for epoch in 9..=16u64 {
            m.observe(healthy(epoch));
        }
        let r = m.latest().unwrap();
        assert_eq!(r.verdict, ResilienceVerdict::Healthy);
    }

    // ── verify_chain ──────────────────────────────────────────────────────────

    #[test]
    fn verify_chain_empty_ok() {
        let m = SynthesisResilienceMonitor::new();
        let (ok, idx) = m.verify_chain();
        assert!(ok);
        assert!(idx.is_none());
    }

    #[test]
    fn verify_chain_five_epochs_ok() {
        let mut m = SynthesisResilienceMonitor::new();
        for epoch in 1..=5u64 { m.observe(healthy(epoch)); }
        let (ok, idx) = m.verify_chain();
        assert!(ok);
        assert!(idx.is_none());
    }

    #[test]
    fn verify_chain_tampered_verdict() {
        let mut m = SynthesisResilienceMonitor::new();
        m.observe(healthy(1));
        m.observe(healthy(2));
        m.records[1].verdict = ResilienceVerdict::Degraded;
        let (ok, idx) = m.verify_chain();
        assert!(!ok);
        assert_eq!(idx, Some(1));
    }

    // ── Determinism ───────────────────────────────────────────────────────────

    #[test]
    fn determinism_same_sequence_three_times() {
        let mut m1 = SynthesisResilienceMonitor::new();
        let mut m2 = SynthesisResilienceMonitor::new();
        let mut m3 = SynthesisResilienceMonitor::new();
        for epoch in 1..=4u64 {
            m1.observe(healthy(epoch));
            m2.observe(healthy(epoch));
            m3.observe(healthy(epoch));
        }
        let h1 = m1.latest().unwrap().record_hash;
        let h2 = m2.latest().unwrap().record_hash;
        let h3 = m3.latest().unwrap().record_hash;
        assert_eq!(h1, h2);
        assert_eq!(h2, h3);
    }
}
