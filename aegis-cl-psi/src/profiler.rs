//! AEGIS-Ω Phase 7 — Resource Profiler
//! EPISTEMIC TIER: T2
//!
//! O(1) sampled telemetry for VRAM/RAM, cache pressure, and Lyapunov eviction.
//! Uses atomic counters for thread-safe bookkeeping without locks.
//! `Instant` is used for elapsed-time measurement only — not in determinism-critical paths.

use std::sync::atomic::{AtomicUsize, Ordering};
use std::time::Instant;

#[derive(Clone, Debug)]
pub struct ResourceSnapshot {
    pub vram_used_mb: f32,
    pub ram_used_mb: f32,
    pub cache_hits: usize,
    pub cache_misses: usize,
    pub lyapunov_evictions: usize,
    pub step_count: usize,
    pub elapsed_ms: f32,
}

impl ResourceSnapshot {
    pub fn cache_hit_rate(&self) -> f32 {
        let total = self.cache_hits + self.cache_misses;
        if total == 0 { 1.0 } else { self.cache_hits as f32 / total as f32 }
    }
}

pub struct Profiler {
    pub vram_limit_mb: f32,
    pub ram_limit_mb: f32,
    start_time: Instant,
    pub step_count: AtomicUsize,
    pub cache_hits: AtomicUsize,
    pub cache_misses: AtomicUsize,
    pub lyapunov_evictions: AtomicUsize,
}

impl Profiler {
    pub fn new(vram_limit_mb: f32, ram_limit_mb: f32) -> Self {
        Self {
            vram_limit_mb,
            ram_limit_mb,
            start_time: Instant::now(),
            step_count: AtomicUsize::new(0),
            cache_hits: AtomicUsize::new(0),
            cache_misses: AtomicUsize::new(0),
            lyapunov_evictions: AtomicUsize::new(0),
        }
    }

    pub fn record_step(&self) {
        self.step_count.fetch_add(1, Ordering::Relaxed);
    }

    pub fn record_cache_hit(&self) {
        self.cache_hits.fetch_add(1, Ordering::Relaxed);
    }

    pub fn record_cache_miss(&self) {
        self.cache_misses.fetch_add(1, Ordering::Relaxed);
    }

    pub fn record_lyapunov_eviction(&self) {
        self.lyapunov_evictions.fetch_add(1, Ordering::Relaxed);
    }

    pub fn snapshot(&self, vram_used_mb: f32, ram_used_mb: f32) -> ResourceSnapshot {
        let elapsed_ms = self.start_time.elapsed().as_secs_f32() * 1000.0;
        ResourceSnapshot {
            vram_used_mb,
            ram_used_mb,
            cache_hits: self.cache_hits.load(Ordering::Relaxed),
            cache_misses: self.cache_misses.load(Ordering::Relaxed),
            lyapunov_evictions: self.lyapunov_evictions.load(Ordering::Relaxed),
            step_count: self.step_count.load(Ordering::Relaxed),
            elapsed_ms,
        }
    }

    pub fn is_within_bounds(&self, vram_used_mb: f32, ram_used_mb: f32) -> bool {
        vram_used_mb <= self.vram_limit_mb && ram_used_mb <= self.ram_limit_mb
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn bounds_pass_within_limits() {
        let p = Profiler::new(5500.0, 6000.0);
        assert!(p.is_within_bounds(4000.0, 4000.0));
    }

    #[test]
    fn bounds_fail_above_vram() {
        let p = Profiler::new(5500.0, 6000.0);
        assert!(!p.is_within_bounds(6000.0, 4000.0));
    }

    #[test]
    fn bounds_fail_above_ram() {
        let p = Profiler::new(5500.0, 6000.0);
        assert!(!p.is_within_bounds(4000.0, 7000.0));
    }

    #[test]
    fn counters_increment_correctly() {
        let p = Profiler::new(5500.0, 6000.0);
        for _ in 0..10 { p.record_step(); }
        for _ in 0..7 { p.record_cache_hit(); }
        for _ in 0..3 { p.record_cache_miss(); }
        for _ in 0..4 { p.record_lyapunov_eviction(); }
        let snap = p.snapshot(1000.0, 1000.0);
        assert_eq!(snap.step_count, 10);
        assert_eq!(snap.cache_hits, 7);
        assert_eq!(snap.cache_misses, 3);
        assert_eq!(snap.lyapunov_evictions, 4);
    }

    #[test]
    fn cache_hit_rate_correct() {
        let p = Profiler::new(100.0, 100.0);
        for _ in 0..3 { p.record_cache_hit(); }
        for _ in 0..1 { p.record_cache_miss(); }
        let snap = p.snapshot(0.0, 0.0);
        assert!((snap.cache_hit_rate() - 0.75).abs() < 1e-5);
    }

    #[test]
    fn empty_profiler_zero_hit_rate_is_one() {
        let p = Profiler::new(100.0, 100.0);
        let snap = p.snapshot(0.0, 0.0);
        assert_eq!(snap.cache_hit_rate(), 1.0);
    }

    // 7. VRAM exactly at the limit is within bounds (≤)
    #[test]
    fn bounds_pass_exactly_at_vram_limit() {
        let p = Profiler::new(5500.0, 6000.0);
        assert!(p.is_within_bounds(5500.0, 4000.0));
    }

    // 8. snapshot passes through the provided vram/ram values
    #[test]
    fn snapshot_vram_ram_passthrough() {
        let p = Profiler::new(8000.0, 8000.0);
        let snap = p.snapshot(1234.5, 5678.9);
        assert!((snap.vram_used_mb - 1234.5).abs() < 0.01);
        assert!((snap.ram_used_mb - 5678.9).abs() < 0.01);
    }

    // 9. Fresh profiler has step_count = 0
    #[test]
    fn fresh_profiler_step_count_zero() {
        let p = Profiler::new(100.0, 100.0);
        let snap = p.snapshot(0.0, 0.0);
        assert_eq!(snap.step_count, 0);
    }

    // 10. elapsed_ms is non-negative
    #[test]
    fn elapsed_ms_nonneg() {
        let p = Profiler::new(100.0, 100.0);
        let snap = p.snapshot(0.0, 0.0);
        assert!(snap.elapsed_ms >= 0.0);
    }
}
