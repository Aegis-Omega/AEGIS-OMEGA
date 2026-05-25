//! Gate 244 — Coherence Stability Index: rolling integer stability score (T2)
//! EPISTEMIC TIER: T2 (engineering hypothesis)
//!
//! Aggregates lattice coherence signals over a rolling window into a single
//! integer stability score in [0, 100].
//!
//! CoherenceSnapshot — per-epoch coherence inputs (avoids importing from lattice_coherence):
//!   global_section: bool — L0–L4 all satisfied
//!   satisfied_count: u8  — 0..=5
//!   coherence_score: u64 — integer [0, 100] from coherence_broadcaster
//!
//! StabilityScore — computed from window:
//!   raw_score = (global_section_rate + satisfied_rate + score_avg) / 3
//!   where:
//!     global_section_rate = (epochs_with_global_section * 100) / window.len()
//!     satisfied_rate      = (sum(satisfied_count) * 100) / (window.len() * 5)
//!     score_avg           = sum(coherence_score) / window.len()
//!   StabilityGrade: A[90+], B[70-89], C[50-69], D[30-49], F[<30]
//!
//! stability_hash = SHA-256(prev_hash ‖ score_be8 ‖ grade_byte ‖ epoch_be8)

use sha2::{Sha256, Digest};

// ─── Coherence snapshot ───────────────────────────────────────────────────────

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct CoherenceSnapshot {
    pub epoch:           u64,
    pub global_section:  bool,
    pub satisfied_count: u8,    // 0..=5
    pub coherence_score: u64,   // 0..=100
}

// ─── Stability grade ─────────────────────────────────────────────────────────

#[derive(Debug, Clone, Copy, PartialEq, Eq, PartialOrd, Ord)]
pub enum StabilityGrade {
    F = 0,
    D = 1,
    C = 2,
    B = 3,
    A = 4,
}

impl StabilityGrade {
    pub fn as_u8(self) -> u8 { self as u8 }

    pub fn as_str(self) -> &'static str {
        match self {
            Self::F => "F",
            Self::D => "D",
            Self::C => "C",
            Self::B => "B",
            Self::A => "A",
        }
    }

    pub fn from_score(score: u64) -> Self {
        match score {
            90..=100 => Self::A,
            70..=89  => Self::B,
            50..=69  => Self::C,
            30..=49  => Self::D,
            _        => Self::F,
        }
    }

    pub fn is_passing(self) -> bool { self >= Self::C }
}

// ─── Stability score ─────────────────────────────────────────────────────────

#[derive(Debug, Clone, PartialEq)]
pub struct StabilityScore {
    pub epoch:                  u64,
    pub raw_score:              u64,   // 0..=100
    pub grade:                  StabilityGrade,
    pub global_section_rate:    u64,   // 0..=100 (%)
    pub satisfied_rate:         u64,   // 0..=100 (%)
    pub score_avg:              u64,   // 0..=100
    pub sample_count:           usize,
    pub stability_hash:         [u8; 32],
    pub prev_stability_hash:    [u8; 32],
}

pub const STABILITY_GENESIS_HASH: [u8; 32] = [0u8; 32];

// ─── Compute stability ───────────────────────────────────────────────────────

pub fn compute_stability(
    window:    &[CoherenceSnapshot],
    epoch:     u64,
    prev_hash: &[u8; 32],
) -> StabilityScore {
    let sample_count = window.len();

    if sample_count == 0 {
        let hash = compute_stability_hash(prev_hash, 0, StabilityGrade::F, epoch);
        return StabilityScore {
            epoch,
            raw_score:           0,
            grade:               StabilityGrade::F,
            global_section_rate: 0,
            satisfied_rate:      0,
            score_avg:           0,
            sample_count:        0,
            stability_hash:      hash,
            prev_stability_hash: *prev_hash,
        };
    }

    let n = sample_count as u64;

    let global_section_count = window.iter().filter(|s| s.global_section).count() as u64;
    let global_section_rate  = global_section_count * 100 / n;

    let satisfied_sum: u64 = window.iter().map(|s| s.satisfied_count as u64).sum();
    // max possible = n * 5
    let satisfied_rate = satisfied_sum * 100 / (n * 5);

    let score_sum: u64 = window.iter().map(|s| s.coherence_score.min(100)).sum();
    let score_avg = score_sum / n;

    let raw_score = (global_section_rate + satisfied_rate + score_avg) / 3;
    let raw_score = raw_score.min(100);

    let grade = StabilityGrade::from_score(raw_score);

    let stability_hash = compute_stability_hash(prev_hash, raw_score, grade, epoch);

    StabilityScore {
        epoch,
        raw_score,
        grade,
        global_section_rate,
        satisfied_rate,
        score_avg,
        sample_count,
        stability_hash,
        prev_stability_hash: *prev_hash,
    }
}

fn compute_stability_hash(
    prev:      &[u8; 32],
    score:     u64,
    grade:     StabilityGrade,
    epoch:     u64,
) -> [u8; 32] {
    let mut h = Sha256::new();
    h.update(prev);
    h.update(score.to_be_bytes());
    h.update([grade.as_u8()]);
    h.update(epoch.to_be_bytes());
    h.finalize().into()
}

// ─── Stability history ───────────────────────────────────────────────────────

#[derive(Debug, Clone)]
pub struct StabilityHistory {
    scores:      Vec<StabilityScore>,
    window_size: usize,
    snapshots:   Vec<CoherenceSnapshot>,
}

#[derive(Debug)]
pub struct StabilityError(pub &'static str);

impl StabilityHistory {
    pub fn new(window_size: usize) -> Self {
        Self { scores: Vec::new(), window_size, snapshots: Vec::new() }
    }

    pub fn new_default() -> Self { Self::new(10) }

    pub fn len(&self) -> usize { self.scores.len() }
    pub fn is_empty(&self) -> bool { self.scores.is_empty() }
    pub fn scores(&self) -> &[StabilityScore] { &self.scores }

    pub fn last_hash(&self) -> [u8; 32] {
        self.scores.last().map(|s| s.stability_hash).unwrap_or(STABILITY_GENESIS_HASH)
    }

    pub fn current_grade(&self) -> StabilityGrade {
        self.scores.last().map(|s| s.grade).unwrap_or(StabilityGrade::F)
    }

    pub fn passing_count(&self) -> usize {
        self.scores.iter().filter(|s| s.grade.is_passing()).count()
    }

    /// Record a new coherence snapshot and compute stability.
    pub fn record(
        &mut self,
        snap: CoherenceSnapshot,
    ) -> Result<&StabilityScore, StabilityError> {
        if let Some(last) = self.scores.last() {
            if snap.epoch <= last.epoch {
                return Err(StabilityError("epoch must be strictly greater"));
            }
        }
        let epoch = snap.epoch;
        self.snapshots.push(snap);
        let window_start = self.snapshots.len().saturating_sub(self.window_size);
        let window = &self.snapshots[window_start..];
        let prev_hash = self.last_hash();
        let score = compute_stability(window, epoch, &prev_hash);
        self.scores.push(score);
        Ok(self.scores.last().unwrap())
    }

    /// Verify hash chain integrity.
    pub fn verify_chain(&self) -> (bool, Option<usize>) {
        let mut prev = STABILITY_GENESIS_HASH;
        for (i, s) in self.scores.iter().enumerate() {
            if s.prev_stability_hash != prev {
                return (false, Some(i));
            }
            let expected = compute_stability_hash(&prev, s.raw_score, s.grade, s.epoch);
            if expected != s.stability_hash {
                return (false, Some(i));
            }
            prev = s.stability_hash;
        }
        (true, None)
    }
}

impl Default for StabilityHistory {
    fn default() -> Self { Self::new_default() }
}

// ─── Tests ───────────────────────────────────────────────────────────────────

#[cfg(test)]
mod tests {
    use super::*;

    fn snap(epoch: u64, global: bool, satisfied: u8, score: u64) -> CoherenceSnapshot {
        CoherenceSnapshot { epoch, global_section: global, satisfied_count: satisfied, coherence_score: score }
    }

    fn perfect_snap(epoch: u64) -> CoherenceSnapshot {
        snap(epoch, true, 5, 100)
    }

    fn poor_snap(epoch: u64) -> CoherenceSnapshot {
        snap(epoch, false, 0, 0)
    }

    // ── StabilityGrade ────────────────────────────────────────────────────────

    #[test]
    fn grade_from_score() {
        assert_eq!(StabilityGrade::from_score(100), StabilityGrade::A);
        assert_eq!(StabilityGrade::from_score(90),  StabilityGrade::A);
        assert_eq!(StabilityGrade::from_score(89),  StabilityGrade::B);
        assert_eq!(StabilityGrade::from_score(70),  StabilityGrade::B);
        assert_eq!(StabilityGrade::from_score(69),  StabilityGrade::C);
        assert_eq!(StabilityGrade::from_score(50),  StabilityGrade::C);
        assert_eq!(StabilityGrade::from_score(49),  StabilityGrade::D);
        assert_eq!(StabilityGrade::from_score(29),  StabilityGrade::F);
        assert_eq!(StabilityGrade::from_score(0),   StabilityGrade::F);
    }

    #[test]
    fn grade_ordering() {
        assert!(StabilityGrade::A > StabilityGrade::B);
        assert!(StabilityGrade::B > StabilityGrade::C);
        assert!(StabilityGrade::F < StabilityGrade::D);
    }

    #[test]
    fn passing_grades() {
        assert!(StabilityGrade::A.is_passing());
        assert!(StabilityGrade::B.is_passing());
        assert!(StabilityGrade::C.is_passing());
        assert!(!StabilityGrade::D.is_passing());
        assert!(!StabilityGrade::F.is_passing());
    }

    #[test]
    fn grade_as_str() {
        assert_eq!(StabilityGrade::A.as_str(), "A");
        assert_eq!(StabilityGrade::F.as_str(), "F");
    }

    // ── compute_stability ─────────────────────────────────────────────────────

    #[test]
    fn empty_window_gives_f() {
        let s = compute_stability(&[], 1, &STABILITY_GENESIS_HASH);
        assert_eq!(s.grade, StabilityGrade::F);
        assert_eq!(s.raw_score, 0);
        assert_eq!(s.sample_count, 0);
    }

    #[test]
    fn perfect_window_gives_a() {
        let window: Vec<_> = (1..=5).map(perfect_snap).collect();
        let s = compute_stability(&window, 5, &STABILITY_GENESIS_HASH);
        assert_eq!(s.raw_score, 100);
        assert_eq!(s.grade, StabilityGrade::A);
        assert_eq!(s.global_section_rate, 100);
        assert_eq!(s.satisfied_rate, 100);
        assert_eq!(s.score_avg, 100);
    }

    #[test]
    fn zero_window_gives_f() {
        let window: Vec<_> = (1..=5).map(poor_snap).collect();
        let s = compute_stability(&window, 5, &STABILITY_GENESIS_HASH);
        assert_eq!(s.raw_score, 0);
        assert_eq!(s.grade, StabilityGrade::F);
    }

    #[test]
    fn half_global_section_reflects_in_score() {
        // 5 snapshots: 3 with global=true, 2 false; all satisfied=5, score=100
        let mut window: Vec<_> = (1..=3).map(|i| snap(i, true, 5, 100)).collect();
        window.push(snap(4, false, 5, 100));
        window.push(snap(5, false, 5, 100));
        let s = compute_stability(&window, 5, &STABILITY_GENESIS_HASH);
        // global_section_rate = 60, satisfied_rate = 100, score_avg = 100 → (60+100+100)/3 = 86 → B
        assert_eq!(s.global_section_rate, 60);
        assert_eq!(s.grade, StabilityGrade::B);
    }

    #[test]
    fn stability_hash_nonzero() {
        let window = vec![perfect_snap(1)];
        let s = compute_stability(&window, 1, &STABILITY_GENESIS_HASH);
        assert_ne!(s.stability_hash, [0u8; 32]);
    }

    #[test]
    fn stability_hash_deterministic() {
        let window: Vec<_> = (1..=4).map(perfect_snap).collect();
        let s1 = compute_stability(&window, 4, &STABILITY_GENESIS_HASH);
        let s2 = compute_stability(&window, 4, &STABILITY_GENESIS_HASH);
        let s3 = compute_stability(&window, 4, &STABILITY_GENESIS_HASH);
        assert_eq!(s1.stability_hash, s2.stability_hash);
        assert_eq!(s2.stability_hash, s3.stability_hash);
    }

    // ── StabilityHistory ──────────────────────────────────────────────────────

    #[test]
    fn new_history_empty() {
        let h = StabilityHistory::new_default();
        assert!(h.is_empty());
        assert_eq!(h.current_grade(), StabilityGrade::F);
    }

    #[test]
    fn record_grows_history() {
        let mut h = StabilityHistory::new_default();
        h.record(perfect_snap(1)).unwrap();
        h.record(perfect_snap(2)).unwrap();
        assert_eq!(h.len(), 2);
    }

    #[test]
    fn duplicate_epoch_is_err() {
        let mut h = StabilityHistory::new_default();
        h.record(perfect_snap(5)).unwrap();
        assert!(h.record(perfect_snap(5)).is_err());
    }

    #[test]
    fn passing_count_tracks() {
        let mut h = StabilityHistory::new_default();
        h.record(perfect_snap(1)).unwrap(); // A
        // Window of 2: [perfect, poor] → global_rate=50, satisfied_rate=50, score_avg=50 → 50 → C (passing)
        h.record(poor_snap(2)).unwrap();    // C
        // Both are passing (A and C)
        assert_eq!(h.passing_count(), 2);
        // A truly failing score requires a large window dominated by poor snaps
        let mut h2 = StabilityHistory::new_default();
        for i in 1u64..=9 { h2.record(poor_snap(i)).unwrap(); }  // all F
        assert_eq!(h2.passing_count(), 0);
    }

    #[test]
    fn verify_chain_clean() {
        let mut h = StabilityHistory::new_default();
        for i in 1u64..=6 { h.record(perfect_snap(i)).unwrap(); }
        let (valid, broken) = h.verify_chain();
        assert!(valid);
        assert!(broken.is_none());
    }
}
