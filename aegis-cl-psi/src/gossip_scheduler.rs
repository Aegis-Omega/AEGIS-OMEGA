//! Gate 271 — Gossip Scheduler: Fibonacci-paced gossip interval calculator (T2)
//! EPISTEMIC TIER: T2 (engineering hypothesis)
//!
//! Computes gossip broadcast intervals using Fibonacci pacing (same constitutional
//! basis as the TypeScript Fibonacci scheduler in Gate 124). Intervals are bounded
//! to prevent unbounded spacing at large sequence numbers.
//!
//! GossipInterval:
//!   sequence       — u64 (monotone gossip sequence counter)
//!   fib_index      — u8 (Fibonacci index, capped at F_11=89)
//!   interval_ms    — u32 (computed interval in milliseconds)
//!   cumulative_ms  — u64 (running total of all intervals)
//!   interval_hash  — SHA-256(seq_be8 ‖ fib_index ‖ interval_ms_be4 ‖ prev_hash)
//!   prev_hash      — [u8; 32]
//!
//! Constants:
//!   FIB_CAP_INDEX  — 11 (F_11 = 89 — maximum Fibonacci index)
//!   BASE_INTERVAL_MS — 100 (base gossip tick in milliseconds)
//!   MAX_INTERVAL_MS  — 8900 (89 * 100 — maximum interval)
//!
//! GossipSchedule: hash-chained GossipIntervals; next_interval_ms(), total_elapsed_ms().

use sha2::{Sha256, Digest};

// ─── Fibonacci support ────────────────────────────────────────────────────────

pub const FIB_CAP_INDEX: u8 = 11;
pub const BASE_INTERVAL_MS: u32 = 100;
pub const MAX_INTERVAL_MS: u32 = 89 * BASE_INTERVAL_MS; // F_11 * BASE

/// Compute the nth Fibonacci number (1-indexed), capped at F_CAP_INDEX.
/// F(1)=1, F(2)=1, F(3)=2, ... F(11)=89. F(n>11)=89.
pub fn fibonacci(n: u8) -> u8 {
    let n = n.min(FIB_CAP_INDEX);
    match n {
        0 | 1 => 1,
        2     => 1,
        _     => {
            let mut a: u8 = 1;
            let mut b: u8 = 1;
            for _ in 2..n {
                let c = a.saturating_add(b);
                a = b;
                b = c;
            }
            b
        }
    }
}

/// Compute gossip interval in ms for Fibonacci index n: fibonacci(n) * BASE_INTERVAL_MS.
pub fn interval_ms(fib_index: u8) -> u32 {
    fibonacci(fib_index) as u32 * BASE_INTERVAL_MS
}

// ─── Gossip interval record ───────────────────────────────────────────────────

#[derive(Debug, Clone, PartialEq)]
pub struct GossipInterval {
    pub sequence:      u64,
    pub fib_index:     u8,
    pub interval_ms:   u32,
    pub cumulative_ms: u64,
    pub interval_hash: [u8; 32],
    pub prev_hash:     [u8; 32],
}

pub const GOSSIP_SCHED_GENESIS_HASH: [u8; 32] = [0u8; 32];

fn compute_interval_hash(
    sequence:    u64,
    fib_index:   u8,
    interval_ms: u32,
    prev:        &[u8; 32],
) -> [u8; 32] {
    let mut h = Sha256::new();
    h.update(prev);
    h.update(sequence.to_be_bytes());
    h.update([fib_index]);
    h.update(interval_ms.to_be_bytes());
    h.finalize().into()
}

// ─── Gossip schedule ──────────────────────────────────────────────────────────

#[derive(Debug, Clone)]
pub struct GossipSchedule {
    intervals: Vec<GossipInterval>,
}

#[derive(Debug)]
pub enum ScheduleError {
    StaleSequence,
}

impl ScheduleError {
    pub fn as_str(&self) -> &'static str { "stale sequence" }
}

impl GossipSchedule {
    pub fn new() -> Self { Self { intervals: Vec::new() } }

    pub fn len(&self) -> usize { self.intervals.len() }
    pub fn is_empty(&self) -> bool { self.intervals.is_empty() }
    pub fn intervals(&self) -> &[GossipInterval] { &self.intervals }
    pub fn latest(&self) -> Option<&GossipInterval> { self.intervals.last() }

    pub fn last_hash(&self) -> [u8; 32] {
        self.intervals.last().map(|i| i.interval_hash).unwrap_or(GOSSIP_SCHED_GENESIS_HASH)
    }

    /// The next Fibonacci index (1-based, capped at FIB_CAP_INDEX).
    fn next_fib_index(&self) -> u8 {
        let n = (self.intervals.len() + 1) as u8;
        n.min(FIB_CAP_INDEX)
    }

    /// Cumulative elapsed ms so far.
    fn current_cumulative(&self) -> u64 {
        self.intervals.last().map(|i| i.cumulative_ms).unwrap_or(0)
    }

    pub fn tick(&mut self, sequence: u64) -> Result<&GossipInterval, ScheduleError> {
        if let Some(last) = self.intervals.last() {
            if sequence <= last.sequence {
                return Err(ScheduleError::StaleSequence);
            }
        }
        let fib_index   = self.next_fib_index();
        let ms          = interval_ms(fib_index);
        let cumulative  = self.current_cumulative() + ms as u64;
        let prev_hash   = self.last_hash();
        let hash        = compute_interval_hash(sequence, fib_index, ms, &prev_hash);

        self.intervals.push(GossipInterval {
            sequence,
            fib_index,
            interval_ms: ms,
            cumulative_ms: cumulative,
            interval_hash: hash,
            prev_hash,
        });
        Ok(self.intervals.last().unwrap())
    }

    /// The next expected interval_ms (peek without advancing).
    pub fn next_interval_ms(&self) -> u32 {
        interval_ms(self.next_fib_index())
    }

    /// Total elapsed milliseconds across all recorded intervals.
    pub fn total_elapsed_ms(&self) -> u64 { self.current_cumulative() }

    pub fn verify_chain(&self) -> (bool, Option<usize>) {
        let mut expected_prev = GOSSIP_SCHED_GENESIS_HASH;
        for (i, iv) in self.intervals.iter().enumerate() {
            if iv.prev_hash != expected_prev {
                return (false, Some(i));
            }
            let recomputed = compute_interval_hash(
                iv.sequence, iv.fib_index, iv.interval_ms, &iv.prev_hash);
            if recomputed != iv.interval_hash {
                return (false, Some(i));
            }
            expected_prev = iv.interval_hash;
        }
        (true, None)
    }
}

impl Default for GossipSchedule {
    fn default() -> Self { Self::new() }
}

// ─── Tests ───────────────────────────────────────────────────────────────────

#[cfg(test)]
mod tests {
    use super::*;

    // ── fibonacci ─────────────────────────────────────────────────────────────

    #[test]
    fn fibonacci_sequence() {
        assert_eq!(fibonacci(1),  1);
        assert_eq!(fibonacci(2),  1);
        assert_eq!(fibonacci(3),  2);
        assert_eq!(fibonacci(4),  3);
        assert_eq!(fibonacci(5),  5);
        assert_eq!(fibonacci(6),  8);
        assert_eq!(fibonacci(7), 13);
        assert_eq!(fibonacci(8), 21);
        assert_eq!(fibonacci(9), 34);
        assert_eq!(fibonacci(10),55);
        assert_eq!(fibonacci(11),89);
    }

    #[test]
    fn fibonacci_cap_at_11() {
        assert_eq!(fibonacci(12), 89);
        assert_eq!(fibonacci(50), 89);
        assert_eq!(fibonacci(255), 89);
    }

    #[test]
    fn interval_ms_correct() {
        assert_eq!(interval_ms(1),  100);
        assert_eq!(interval_ms(5),  500);
        assert_eq!(interval_ms(11), 8900);
        assert_eq!(interval_ms(12), 8900); // cap
    }

    #[test]
    fn max_interval_ms_constant() {
        assert_eq!(MAX_INTERVAL_MS, 8900);
    }

    // ── GossipSchedule ────────────────────────────────────────────────────────

    #[test]
    fn new_schedule_empty() {
        let s = GossipSchedule::new();
        assert!(s.is_empty());
        assert_eq!(s.total_elapsed_ms(), 0);
        assert_eq!(s.next_interval_ms(), 100); // F(1)*100
    }

    #[test]
    fn first_tick_fib1() {
        let mut s = GossipSchedule::new();
        let iv = s.tick(1).unwrap();
        assert_eq!(iv.fib_index,   1);
        assert_eq!(iv.interval_ms, 100);
        assert_eq!(iv.cumulative_ms, 100);
    }

    #[test]
    fn fibonacci_pacing_sequence() {
        let mut s = GossipSchedule::new();
        let expected_ms = [100u32, 100, 200, 300, 500, 800, 1300, 2100, 3400, 5500, 8900];
        for (i, &expected) in expected_ms.iter().enumerate() {
            let iv = s.tick(i as u64 + 1).unwrap();
            assert_eq!(iv.interval_ms, expected, "tick {} wrong", i+1);
        }
    }

    #[test]
    fn capped_after_11() {
        let mut s = GossipSchedule::new();
        for i in 1..=12u64 {
            s.tick(i).unwrap();
        }
        let last = s.latest().unwrap();
        assert_eq!(last.fib_index,   11); // capped
        assert_eq!(last.interval_ms, 8900);
    }

    #[test]
    fn stale_sequence_rejected() {
        let mut s = GossipSchedule::new();
        s.tick(5).unwrap();
        assert!(matches!(s.tick(5), Err(ScheduleError::StaleSequence)));
        assert!(matches!(s.tick(4), Err(ScheduleError::StaleSequence)));
    }

    #[test]
    fn cumulative_ms_accumulates() {
        let mut s = GossipSchedule::new();
        s.tick(1).unwrap(); // 100
        s.tick(2).unwrap(); // 100
        s.tick(3).unwrap(); // 200
        assert_eq!(s.total_elapsed_ms(), 400); // 100+100+200
    }

    #[test]
    fn interval_hash_nonzero() {
        let mut s = GossipSchedule::new();
        let iv = s.tick(1).unwrap();
        assert_ne!(iv.interval_hash, [0u8; 32]);
    }

    #[test]
    fn interval_hash_deterministic() {
        let mut s1 = GossipSchedule::new();
        let mut s2 = GossipSchedule::new();
        let iv1 = s1.tick(1).unwrap();
        let iv2 = s2.tick(1).unwrap();
        assert_eq!(iv1.interval_hash, iv2.interval_hash);
    }

    #[test]
    fn verify_chain_valid() {
        let mut s = GossipSchedule::new();
        for i in 1..=8u64 {
            s.tick(i).unwrap();
        }
        let (valid, broken) = s.verify_chain();
        assert!(valid);
        assert!(broken.is_none());
    }
}
