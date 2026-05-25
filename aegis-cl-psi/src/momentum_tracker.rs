//! Gate 245 — Constitutional Momentum Tracker: directional stability trend (T2)
//! EPISTEMIC TIER: T2 (engineering hypothesis)
//!
//! Computes a signed momentum integer from consecutive StabilityScore observations.
//! Positive momentum = improving. Negative = declining. Zero = stable.
//!
//! MomentumSample — one (epoch, raw_score) pair from StabilityScore.
//!
//! MomentumReport:
//!   momentum_int  — signed integer: sum of score deltas over rolling window
//!   momentum_dir  — Improving (+1)/Stable (0)/Declining (-1) derived from momentum_int
//!   peak_score    — highest raw_score in window
//!   trough_score  — lowest raw_score in window
//!   score_range   — peak - trough
//!
//! momentum_hash = SHA-256(prev_hash ‖ momentum_dir_byte ‖ momentum_int_be8_signed ‖ epoch_be8)
//! Uses i64 to store signed momentum_int; serialized as i64::to_be_bytes().

use sha2::{Sha256, Digest};

// ─── Momentum direction ───────────────────────────────────────────────────────

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum MomentumDir {
    Improving = 0,
    Stable    = 1,
    Declining = 2,
}

impl MomentumDir {
    pub fn as_u8(self) -> u8 { self as u8 }

    pub fn as_str(self) -> &'static str {
        match self {
            Self::Improving => "improving",
            Self::Stable    => "stable",
            Self::Declining => "declining",
        }
    }

    pub fn from_int(v: i64) -> Self {
        if v > 0 { Self::Improving }
        else if v < 0 { Self::Declining }
        else { Self::Stable }
    }
}

// ─── Momentum sample ─────────────────────────────────────────────────────────

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub struct MomentumSample {
    pub epoch:     u64,
    pub raw_score: u64, // 0..=100
}

// ─── Momentum report ─────────────────────────────────────────────────────────

#[derive(Debug, Clone, PartialEq)]
pub struct MomentumReport {
    pub epoch:         u64,
    pub momentum_int:  i64,
    pub momentum_dir:  MomentumDir,
    pub peak_score:    u64,
    pub trough_score:  u64,
    pub score_range:   u64,
    pub sample_count:  usize,
    pub momentum_hash: [u8; 32],
    pub prev_hash:     [u8; 32],
}

pub const MOMENTUM_GENESIS_HASH: [u8; 32] = [0u8; 32];
pub const DEFAULT_MOMENTUM_WINDOW: usize = 8;

// ─── Compute momentum ────────────────────────────────────────────────────────

pub fn compute_momentum(
    samples:   &[MomentumSample],
    epoch:     u64,
    prev_hash: &[u8; 32],
) -> MomentumReport {
    let sample_count = samples.len();

    if sample_count == 0 {
        let hash = compute_momentum_hash(prev_hash, MomentumDir::Stable, 0, epoch);
        return MomentumReport {
            epoch,
            momentum_int: 0,
            momentum_dir: MomentumDir::Stable,
            peak_score:   0,
            trough_score: 0,
            score_range:  0,
            sample_count: 0,
            momentum_hash: hash,
            prev_hash: *prev_hash,
        };
    }

    let peak   = samples.iter().map(|s| s.raw_score).max().unwrap_or(0);
    let trough = samples.iter().map(|s| s.raw_score).min().unwrap_or(0);

    // momentum_int = sum of consecutive deltas: Σ (score[i] - score[i-1])
    // = score[last] - score[first]  (telescoping sum)
    let momentum_int = if sample_count < 2 {
        0i64
    } else {
        let first = samples[0].raw_score as i64;
        let last  = samples[sample_count - 1].raw_score as i64;
        last - first
    };

    let momentum_dir  = MomentumDir::from_int(momentum_int);
    let momentum_hash = compute_momentum_hash(prev_hash, momentum_dir, momentum_int, epoch);

    MomentumReport {
        epoch,
        momentum_int,
        momentum_dir,
        peak_score:   peak,
        trough_score: trough,
        score_range:  peak - trough,
        sample_count,
        momentum_hash,
        prev_hash: *prev_hash,
    }
}

fn compute_momentum_hash(
    prev:         &[u8; 32],
    dir:          MomentumDir,
    momentum_int: i64,
    epoch:        u64,
) -> [u8; 32] {
    let mut h = Sha256::new();
    h.update(prev);
    h.update([dir.as_u8()]);
    h.update(momentum_int.to_be_bytes());
    h.update(epoch.to_be_bytes());
    h.finalize().into()
}

// ─── Momentum history ────────────────────────────────────────────────────────

#[derive(Debug, Clone)]
pub struct MomentumHistory {
    reports:     Vec<MomentumReport>,
    samples:     Vec<MomentumSample>,
    window_size: usize,
}

#[derive(Debug)]
pub struct MomentumError(pub &'static str);

impl MomentumHistory {
    pub fn new(window_size: usize) -> Self {
        Self { reports: Vec::new(), samples: Vec::new(), window_size }
    }

    pub fn new_default() -> Self { Self::new(DEFAULT_MOMENTUM_WINDOW) }

    pub fn len(&self) -> usize { self.reports.len() }
    pub fn is_empty(&self) -> bool { self.reports.is_empty() }
    pub fn reports(&self) -> &[MomentumReport] { &self.reports }

    pub fn last_hash(&self) -> [u8; 32] {
        self.reports.last().map(|r| r.momentum_hash).unwrap_or(MOMENTUM_GENESIS_HASH)
    }

    pub fn current_direction(&self) -> MomentumDir {
        self.reports.last().map(|r| r.momentum_dir).unwrap_or(MomentumDir::Stable)
    }

    pub fn improving_count(&self) -> usize {
        self.reports.iter().filter(|r| r.momentum_dir == MomentumDir::Improving).count()
    }

    pub fn declining_count(&self) -> usize {
        self.reports.iter().filter(|r| r.momentum_dir == MomentumDir::Declining).count()
    }

    /// Record a new sample. Epoch must be strictly greater.
    pub fn record(
        &mut self,
        sample: MomentumSample,
    ) -> Result<&MomentumReport, MomentumError> {
        if let Some(last) = self.reports.last() {
            if sample.epoch <= last.epoch {
                return Err(MomentumError("epoch must be strictly greater"));
            }
        }
        let epoch = sample.epoch;
        self.samples.push(sample);
        let window_start = self.samples.len().saturating_sub(self.window_size);
        let window = &self.samples[window_start..];
        let prev_hash = self.last_hash();
        let report = compute_momentum(window, epoch, &prev_hash);
        self.reports.push(report);
        Ok(self.reports.last().unwrap())
    }

    /// Verify hash chain integrity.
    pub fn verify_chain(&self) -> (bool, Option<usize>) {
        let mut prev = MOMENTUM_GENESIS_HASH;
        for (i, rep) in self.reports.iter().enumerate() {
            if rep.prev_hash != prev {
                return (false, Some(i));
            }
            let expected = compute_momentum_hash(&prev, rep.momentum_dir, rep.momentum_int, rep.epoch);
            if expected != rep.momentum_hash {
                return (false, Some(i));
            }
            prev = rep.momentum_hash;
        }
        (true, None)
    }
}

impl Default for MomentumHistory {
    fn default() -> Self { Self::new_default() }
}

// ─── Tests ───────────────────────────────────────────────────────────────────

#[cfg(test)]
mod tests {
    use super::*;

    fn s(epoch: u64, score: u64) -> MomentumSample { MomentumSample { epoch, raw_score: score } }

    // ── MomentumDir ───────────────────────────────────────────────────────────

    #[test]
    fn dir_from_int() {
        assert_eq!(MomentumDir::from_int(10), MomentumDir::Improving);
        assert_eq!(MomentumDir::from_int(0),  MomentumDir::Stable);
        assert_eq!(MomentumDir::from_int(-5), MomentumDir::Declining);
    }

    #[test]
    fn dir_as_u8() {
        assert_eq!(MomentumDir::Improving.as_u8(), 0);
        assert_eq!(MomentumDir::Stable.as_u8(), 1);
        assert_eq!(MomentumDir::Declining.as_u8(), 2);
    }

    #[test]
    fn dir_as_str() {
        assert_eq!(MomentumDir::Improving.as_str(), "improving");
        assert_eq!(MomentumDir::Declining.as_str(), "declining");
    }

    // ── compute_momentum ──────────────────────────────────────────────────────

    #[test]
    fn empty_samples_give_stable() {
        let rep = compute_momentum(&[], 1, &MOMENTUM_GENESIS_HASH);
        assert_eq!(rep.momentum_dir, MomentumDir::Stable);
        assert_eq!(rep.momentum_int, 0);
        assert_eq!(rep.sample_count, 0);
    }

    #[test]
    fn single_sample_is_stable() {
        let rep = compute_momentum(&[s(1, 70)], 1, &MOMENTUM_GENESIS_HASH);
        assert_eq!(rep.momentum_int, 0);
        assert_eq!(rep.momentum_dir, MomentumDir::Stable);
        assert_eq!(rep.peak_score, 70);
        assert_eq!(rep.trough_score, 70);
    }

    #[test]
    fn improving_trend_detected() {
        let samples = vec![s(1,50), s(2,60), s(3,70), s(4,80)];
        let rep = compute_momentum(&samples, 4, &MOMENTUM_GENESIS_HASH);
        assert_eq!(rep.momentum_int, 30); // 80-50
        assert_eq!(rep.momentum_dir, MomentumDir::Improving);
    }

    #[test]
    fn declining_trend_detected() {
        let samples = vec![s(1,90), s(2,75), s(3,60), s(4,45)];
        let rep = compute_momentum(&samples, 4, &MOMENTUM_GENESIS_HASH);
        assert_eq!(rep.momentum_int, -45); // 45-90
        assert_eq!(rep.momentum_dir, MomentumDir::Declining);
    }

    #[test]
    fn flat_trend_is_stable() {
        let samples: Vec<_> = (1..=5).map(|i| s(i, 75)).collect();
        let rep = compute_momentum(&samples, 5, &MOMENTUM_GENESIS_HASH);
        assert_eq!(rep.momentum_int, 0);
        assert_eq!(rep.momentum_dir, MomentumDir::Stable);
    }

    #[test]
    fn peak_trough_computed() {
        let samples = vec![s(1,40), s(2,90), s(3,55), s(4,20), s(5,70)];
        let rep = compute_momentum(&samples, 5, &MOMENTUM_GENESIS_HASH);
        assert_eq!(rep.peak_score, 90);
        assert_eq!(rep.trough_score, 20);
        assert_eq!(rep.score_range, 70);
    }

    #[test]
    fn momentum_hash_nonzero() {
        let samples = vec![s(1, 50), s(2, 60)];
        let rep = compute_momentum(&samples, 2, &MOMENTUM_GENESIS_HASH);
        assert_ne!(rep.momentum_hash, [0u8; 32]);
    }

    #[test]
    fn momentum_hash_deterministic() {
        let samples = vec![s(1,50), s(2,70), s(3,90)];
        let r1 = compute_momentum(&samples, 3, &MOMENTUM_GENESIS_HASH);
        let r2 = compute_momentum(&samples, 3, &MOMENTUM_GENESIS_HASH);
        let r3 = compute_momentum(&samples, 3, &MOMENTUM_GENESIS_HASH);
        assert_eq!(r1.momentum_hash, r2.momentum_hash);
        assert_eq!(r2.momentum_hash, r3.momentum_hash);
    }

    #[test]
    fn different_epochs_different_hash() {
        let samp = vec![s(1, 75)];
        let r1 = compute_momentum(&samp, 1, &MOMENTUM_GENESIS_HASH);
        let r2 = compute_momentum(&samp, 2, &MOMENTUM_GENESIS_HASH);
        assert_ne!(r1.momentum_hash, r2.momentum_hash);
    }

    // ── MomentumHistory ───────────────────────────────────────────────────────

    #[test]
    fn new_history_empty() {
        let h = MomentumHistory::new_default();
        assert!(h.is_empty());
        assert_eq!(h.current_direction(), MomentumDir::Stable);
    }

    #[test]
    fn record_grows_history() {
        let mut h = MomentumHistory::new_default();
        h.record(s(1, 50)).unwrap();
        h.record(s(2, 60)).unwrap();
        h.record(s(3, 70)).unwrap();
        assert_eq!(h.len(), 3);
    }

    #[test]
    fn duplicate_epoch_is_err() {
        let mut h = MomentumHistory::new_default();
        h.record(s(5, 75)).unwrap();
        assert!(h.record(s(5, 80)).is_err());
    }

    #[test]
    fn improving_count_tracked() {
        let mut h = MomentumHistory::new_default();
        h.record(s(1, 50)).unwrap();
        h.record(s(2, 60)).unwrap(); // window=[50,60] → +10 → Improving
        h.record(s(3, 40)).unwrap(); // window=[50,60,40] → 40-50=-10 → Declining
        assert_eq!(h.improving_count(), 1);
        assert_eq!(h.declining_count(), 1);
    }

    #[test]
    fn declining_count_tracked() {
        let mut h = MomentumHistory::new_default();
        h.record(s(1, 90)).unwrap();
        h.record(s(2, 70)).unwrap(); // declining (-20)
        h.record(s(3, 60)).unwrap(); // declining (-30 vs start=70)
        assert_eq!(h.declining_count(), 2);
    }

    #[test]
    fn verify_chain_clean() {
        let mut h = MomentumHistory::new_default();
        for i in 1u64..=6 { h.record(s(i, 50 + i * 5)).unwrap(); }
        let (valid, broken) = h.verify_chain();
        assert!(valid);
        assert!(broken.is_none());
    }
}
