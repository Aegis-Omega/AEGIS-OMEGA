//! Gate 296 — Gossip Adaptive Fanout Controller: delivery-rate-aware fanout adjustment (T2)
//! EPISTEMIC TIER: T2 (engineering hypothesis)
//!
//! Dynamically adjusts the gossip fanout based on observed delivery success rate.
//! When delivery rate falls below LOW_DELIVERY_THRESHOLD (60%), fanout is increased.
//! When it exceeds HIGH_DELIVERY_THRESHOLD (90%), fanout is decreased.
//! Each adjustment is hash-chained in a FanoutLog.
//!
//! Constants: MIN_FANOUT=2, MAX_FANOUT=16, DEFAULT_FANOUT=4, FANOUT_STEP=1
//! FanoutAdjustment: Increase / Decrease / Unchanged
//! FanoutRecord: hash-chained (epoch, delivery_rate, old_fanout, new_fanout, adjustment)
//! FanoutLog: record(), increase_count(), decrease_count(), avg_fanout(), verify_chain().
//! FanoutController: observe(epoch, delivered, attempted) → FanoutAdjustment

use sha2::{Sha256, Digest};

pub const MIN_FANOUT:              u8 = 2;
pub const MAX_FANOUT:              u8 = 16;
pub const DEFAULT_FANOUT:          u8 = 4;
pub const LOW_DELIVERY_THRESHOLD:  u8 = 60;
pub const HIGH_DELIVERY_THRESHOLD: u8 = 90;
pub const FANOUT_STEP:             u8 = 1;

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum FanoutAdjustment {
    Increase  = 0,
    Decrease  = 1,
    Unchanged = 2,
}

impl FanoutAdjustment {
    pub fn adj_byte(self) -> u8 { self as u8 }
}

#[derive(Debug, Clone, PartialEq)]
pub struct FanoutRecord {
    pub epoch:         u64,
    pub delivery_rate: u8,
    pub old_fanout:    u8,
    pub new_fanout:    u8,
    pub adjustment:    FanoutAdjustment,
    pub record_hash:   [u8; 32],
    pub prev_hash:     [u8; 32],
}

pub const FANOUT_GENESIS_HASH: [u8; 32] = [0u8; 32];

fn compute_fanout_hash(
    epoch: u64, delivery_rate: u8, old_fanout: u8, new_fanout: u8,
    adjustment: FanoutAdjustment, prev: &[u8; 32],
) -> [u8; 32] {
    let mut h = Sha256::new();
    h.update(prev);
    h.update(epoch.to_be_bytes());
    h.update([delivery_rate, old_fanout, new_fanout, adjustment.adj_byte()]);
    h.finalize().into()
}

pub fn build_fanout_record(
    epoch: u64, delivery_rate: u8, old_fanout: u8, new_fanout: u8,
    adjustment: FanoutAdjustment, prev_hash: &[u8; 32],
) -> FanoutRecord {
    let record_hash = compute_fanout_hash(epoch, delivery_rate, old_fanout, new_fanout, adjustment, prev_hash);
    FanoutRecord { epoch, delivery_rate, old_fanout, new_fanout, adjustment, record_hash, prev_hash: *prev_hash }
}

#[derive(Debug, Clone)]
pub struct FanoutLog {
    records: Vec<FanoutRecord>,
}

#[derive(Debug)]
pub enum FanoutError {
    StaleEpoch,
    AttemptedZero,
}

impl FanoutLog {
    pub fn new() -> Self { Self { records: Vec::new() } }
    pub fn len(&self)      -> usize { self.records.len() }
    pub fn is_empty(&self) -> bool  { self.records.is_empty() }
    pub fn records(&self)  -> &[FanoutRecord] { &self.records }

    pub fn last_hash(&self) -> [u8; 32] {
        self.records.last().map(|r| r.record_hash).unwrap_or(FANOUT_GENESIS_HASH)
    }

    pub fn record(
        &mut self, epoch: u64, delivery_rate: u8, old_fanout: u8,
        new_fanout: u8, adjustment: FanoutAdjustment,
    ) -> Result<&FanoutRecord, FanoutError> {
        if let Some(last) = self.records.last() {
            if epoch <= last.epoch { return Err(FanoutError::StaleEpoch); }
        }
        let prev = self.last_hash();
        let r = build_fanout_record(epoch, delivery_rate, old_fanout, new_fanout, adjustment, &prev);
        self.records.push(r);
        Ok(self.records.last().unwrap())
    }

    pub fn increase_count(&self) -> usize {
        self.records.iter().filter(|r| r.adjustment == FanoutAdjustment::Increase).count()
    }

    pub fn decrease_count(&self) -> usize {
        self.records.iter().filter(|r| r.adjustment == FanoutAdjustment::Decrease).count()
    }

    pub fn avg_fanout(&self) -> u8 {
        if self.records.is_empty() { return 0; }
        let sum: u32 = self.records.iter().map(|r| r.new_fanout as u32).sum();
        (sum / self.records.len() as u32) as u8
    }

    pub fn verify_chain(&self) -> (bool, Option<usize>) {
        let mut expected_prev = FANOUT_GENESIS_HASH;
        for (i, r) in self.records.iter().enumerate() {
            if r.prev_hash != expected_prev { return (false, Some(i)); }
            let recomputed = compute_fanout_hash(
                r.epoch, r.delivery_rate, r.old_fanout, r.new_fanout, r.adjustment, &r.prev_hash,
            );
            if recomputed != r.record_hash { return (false, Some(i)); }
            expected_prev = r.record_hash;
        }
        (true, None)
    }
}

impl Default for FanoutLog {
    fn default() -> Self { Self::new() }
}

#[derive(Debug, Clone)]
pub struct FanoutController {
    fanout: u8,
    log:    FanoutLog,
}

impl FanoutController {
    pub fn new() -> Self { Self { fanout: DEFAULT_FANOUT, log: FanoutLog::new() } }

    pub fn with_fanout(fanout: u8) -> Self {
        Self { fanout: fanout.max(MIN_FANOUT).min(MAX_FANOUT), log: FanoutLog::new() }
    }

    pub fn current_fanout(&self) -> u8 { self.fanout }
    pub fn log(&self) -> &FanoutLog    { &self.log }

    pub fn observe(
        &mut self, epoch: u64, delivered: u32, attempted: u32,
    ) -> Result<FanoutAdjustment, FanoutError> {
        if attempted == 0 { return Err(FanoutError::AttemptedZero); }
        let rate = ((delivered.min(attempted) as u64 * 100) / attempted as u64) as u8;
        let old  = self.fanout;
        let adj = if rate < LOW_DELIVERY_THRESHOLD {
            self.fanout = self.fanout.saturating_add(FANOUT_STEP).min(MAX_FANOUT);
            FanoutAdjustment::Increase
        } else if rate > HIGH_DELIVERY_THRESHOLD {
            self.fanout = self.fanout.saturating_sub(FANOUT_STEP).max(MIN_FANOUT);
            FanoutAdjustment::Decrease
        } else {
            FanoutAdjustment::Unchanged
        };
        let _ = self.log.record(epoch, rate, old, self.fanout, adj);
        Ok(adj)
    }
}

impl Default for FanoutController {
    fn default() -> Self { Self::new() }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn constants_sane() {
        assert!(MIN_FANOUT < DEFAULT_FANOUT);
        assert!(DEFAULT_FANOUT < MAX_FANOUT);
        assert!(LOW_DELIVERY_THRESHOLD < HIGH_DELIVERY_THRESHOLD);
    }

    #[test]
    fn adj_bytes() {
        assert_eq!(FanoutAdjustment::Increase.adj_byte(),  0);
        assert_eq!(FanoutAdjustment::Decrease.adj_byte(),  1);
        assert_eq!(FanoutAdjustment::Unchanged.adj_byte(), 2);
    }

    #[test]
    fn record_hash_nonzero() {
        let r = build_fanout_record(1, 80, 4, 4, FanoutAdjustment::Unchanged, &FANOUT_GENESIS_HASH);
        assert_ne!(r.record_hash, [0u8; 32]);
    }

    #[test]
    fn record_hash_deterministic() {
        let r1 = build_fanout_record(1, 80, 4, 4, FanoutAdjustment::Unchanged, &FANOUT_GENESIS_HASH);
        let r2 = build_fanout_record(1, 80, 4, 4, FanoutAdjustment::Unchanged, &FANOUT_GENESIS_HASH);
        assert_eq!(r1.record_hash, r2.record_hash);
    }

    #[test]
    fn new_log_empty() {
        let l = FanoutLog::new();
        assert!(l.is_empty());
        assert_eq!(l.increase_count(), 0);
        assert_eq!(l.decrease_count(), 0);
        assert_eq!(l.avg_fanout(), 0);
    }

    #[test]
    fn log_tracks_adjustments() {
        let mut l = FanoutLog::new();
        l.record(1, 50, 4, 5, FanoutAdjustment::Increase).unwrap();
        l.record(2, 95, 5, 4, FanoutAdjustment::Decrease).unwrap();
        l.record(3, 80, 4, 4, FanoutAdjustment::Unchanged).unwrap();
        assert_eq!(l.increase_count(), 1);
        assert_eq!(l.decrease_count(), 1);
    }

    #[test]
    fn avg_fanout_computed() {
        let mut l = FanoutLog::new();
        l.record(1, 80, 4, 4, FanoutAdjustment::Unchanged).unwrap();
        l.record(2, 50, 4, 5, FanoutAdjustment::Increase).unwrap();
        assert_eq!(l.avg_fanout(), 4); // (4+5)/2 = 4
    }

    #[test]
    fn stale_epoch_rejected() {
        let mut l = FanoutLog::new();
        l.record(5, 80, 4, 4, FanoutAdjustment::Unchanged).unwrap();
        assert!(matches!(l.record(4, 80, 4, 4, FanoutAdjustment::Unchanged), Err(FanoutError::StaleEpoch)));
    }

    #[test]
    fn chain_links() {
        let mut l = FanoutLog::new();
        l.record(1, 80, 4, 4, FanoutAdjustment::Unchanged).unwrap();
        l.record(2, 80, 4, 4, FanoutAdjustment::Unchanged).unwrap();
        assert_eq!(l.records()[1].prev_hash, l.records()[0].record_hash);
    }

    #[test]
    fn verify_chain_valid() {
        let mut l = FanoutLog::new();
        for e in 1..=5u64 {
            l.record(e, 80, 4, 4, FanoutAdjustment::Unchanged).unwrap();
        }
        let (valid, broken) = l.verify_chain();
        assert!(valid);
        assert!(broken.is_none());
    }

    #[test]
    fn default_fanout() {
        assert_eq!(FanoutController::new().current_fanout(), DEFAULT_FANOUT);
    }

    #[test]
    fn low_delivery_increases_fanout() {
        let mut ctrl = FanoutController::new();
        let adj = ctrl.observe(1, 50, 100).unwrap();
        assert_eq!(adj, FanoutAdjustment::Increase);
        assert_eq!(ctrl.current_fanout(), DEFAULT_FANOUT + FANOUT_STEP);
    }

    #[test]
    fn high_delivery_decreases_fanout() {
        let mut ctrl = FanoutController::new();
        let adj = ctrl.observe(1, 95, 100).unwrap();
        assert_eq!(adj, FanoutAdjustment::Decrease);
        assert_eq!(ctrl.current_fanout(), DEFAULT_FANOUT - FANOUT_STEP);
    }

    #[test]
    fn mid_delivery_unchanged() {
        let mut ctrl = FanoutController::new();
        let adj = ctrl.observe(1, 75, 100).unwrap();
        assert_eq!(adj, FanoutAdjustment::Unchanged);
        assert_eq!(ctrl.current_fanout(), DEFAULT_FANOUT);
    }

    #[test]
    fn fanout_capped_at_max() {
        let mut ctrl = FanoutController::with_fanout(MAX_FANOUT);
        ctrl.observe(1, 0, 100).unwrap();
        assert_eq!(ctrl.current_fanout(), MAX_FANOUT);
    }

    #[test]
    fn fanout_floored_at_min() {
        let mut ctrl = FanoutController::with_fanout(MIN_FANOUT);
        ctrl.observe(1, 100, 100).unwrap();
        assert_eq!(ctrl.current_fanout(), MIN_FANOUT);
    }

    #[test]
    fn attempted_zero_errors() {
        let mut ctrl = FanoutController::new();
        assert!(matches!(ctrl.observe(1, 0, 0), Err(FanoutError::AttemptedZero)));
    }

    #[test]
    fn log_grows_on_observe() {
        let mut ctrl = FanoutController::new();
        ctrl.observe(1, 75, 100).unwrap();
        ctrl.observe(2, 75, 100).unwrap();
        assert_eq!(ctrl.log().len(), 2);
    }
}
