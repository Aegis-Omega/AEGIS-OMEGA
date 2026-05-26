//! Gate 282 — Gossip Topology Prober: active mesh connectivity probing (T2)
//! EPISTEMIC TIER: T2 (engineering hypothesis)
//!
//! Tracks active connectivity probes between gossip nodes. Each probe round
//! records per-peer results: Success (with RTT) or failure (Timeout/Refused/NoRoute).
//!
//! ProbeResult:
//!   Success { rtt_ms: u32 }
//!   Timeout                   — no response within probe window
//!   Refused                   — explicit rejection
//!   NoRoute                   — routing failure
//!
//! PeerProbeRecord:
//!   prober_id      — u32 (the node issuing the probe)
//!   target_id      — u32 (the node being probed)
//!   epoch          — u64
//!   result         — ProbeResult
//!   rtt_ms         — u32 (0 if not Success)
//!   record_hash    — SHA-256(prev ‖ prober_be4 ‖ target_be4 ‖ epoch_be8 ‖ result_byte ‖ rtt_be4)
//!   prev_hash      — [u8; 32]
//!
//! ProbeLog: per-(prober,target) hash-chained record log.
//!   record(), success_count(), timeout_count(), avg_rtt_ms(), verify_chain().
//!
//! ProbeMatrix: BTreeMap<(prober_id, target_id), ProbeLog>.
//!   record_probe(), reachable_from(), unreachable_peers(), avg_mesh_rtt().

use sha2::{Sha256, Digest};
use std::collections::BTreeMap;

// ─── Probe result ─────────────────────────────────────────────────────────────

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum ProbeResult {
    Success { rtt_ms: u32 },
    Timeout,
    Refused,
    NoRoute,
}

impl ProbeResult {
    pub fn result_byte(self) -> u8 {
        match self {
            Self::Success { .. } => 0,
            Self::Timeout        => 1,
            Self::Refused        => 2,
            Self::NoRoute        => 3,
        }
    }

    pub fn rtt_ms(self) -> u32 {
        match self {
            Self::Success { rtt_ms } => rtt_ms,
            _                        => 0,
        }
    }

    pub fn is_success(self) -> bool { matches!(self, Self::Success { .. }) }
}

// ─── Peer probe record ────────────────────────────────────────────────────────

#[derive(Debug, Clone, PartialEq)]
pub struct PeerProbeRecord {
    pub prober_id:   u32,
    pub target_id:   u32,
    pub epoch:       u64,
    pub result:      ProbeResult,
    pub rtt_ms:      u32,
    pub record_hash: [u8; 32],
    pub prev_hash:   [u8; 32],
}

pub const PROBE_GENESIS_HASH: [u8; 32] = [0u8; 32];

fn compute_probe_hash(
    prober_id: u32,
    target_id: u32,
    epoch:     u64,
    result:    ProbeResult,
    prev:      &[u8; 32],
) -> [u8; 32] {
    let mut h = Sha256::new();
    h.update(prev);
    h.update(prober_id.to_be_bytes());
    h.update(target_id.to_be_bytes());
    h.update(epoch.to_be_bytes());
    h.update([result.result_byte()]);
    h.update(result.rtt_ms().to_be_bytes());
    h.finalize().into()
}

pub fn build_probe_record(
    prober_id: u32,
    target_id: u32,
    epoch:     u64,
    result:    ProbeResult,
    prev_hash: &[u8; 32],
) -> PeerProbeRecord {
    let record_hash = compute_probe_hash(prober_id, target_id, epoch, result, prev_hash);
    PeerProbeRecord {
        prober_id, target_id, epoch, result,
        rtt_ms: result.rtt_ms(),
        record_hash,
        prev_hash: *prev_hash,
    }
}

// ─── Probe log (per prober-target pair) ───────────────────────────────────────

#[derive(Debug, Clone)]
pub struct ProbeLog {
    prober_id: u32,
    target_id: u32,
    records:   Vec<PeerProbeRecord>,
}

#[derive(Debug)]
pub enum ProbeError {
    StaleEpoch,
}

impl ProbeLog {
    pub fn new(prober_id: u32, target_id: u32) -> Self {
        Self { prober_id, target_id, records: Vec::new() }
    }

    pub fn len(&self)      -> usize { self.records.len() }
    pub fn is_empty(&self) -> bool  { self.records.is_empty() }
    pub fn records(&self)  -> &[PeerProbeRecord] { &self.records }

    pub fn last_hash(&self) -> [u8; 32] {
        self.records.last().map(|r| r.record_hash).unwrap_or(PROBE_GENESIS_HASH)
    }

    pub fn record(&mut self, epoch: u64, result: ProbeResult) -> Result<&PeerProbeRecord, ProbeError> {
        if let Some(last) = self.records.last() {
            if epoch <= last.epoch {
                return Err(ProbeError::StaleEpoch);
            }
        }
        let prev = self.last_hash();
        let r = build_probe_record(self.prober_id, self.target_id, epoch, result, &prev);
        self.records.push(r);
        Ok(self.records.last().unwrap())
    }

    pub fn success_count(&self) -> usize {
        self.records.iter().filter(|r| r.result.is_success()).count()
    }

    pub fn timeout_count(&self) -> usize {
        self.records.iter().filter(|r| matches!(r.result, ProbeResult::Timeout)).count()
    }

    pub fn failure_count(&self) -> usize {
        self.records.iter().filter(|r| !r.result.is_success()).count()
    }

    /// Average RTT across successful probes. 0 if none.
    pub fn avg_rtt_ms(&self) -> u32 {
        let successes: Vec<u32> = self.records.iter()
            .filter(|r| r.result.is_success())
            .map(|r| r.rtt_ms)
            .collect();
        if successes.is_empty() { return 0; }
        let sum: u64 = successes.iter().map(|&v| v as u64).sum();
        (sum / successes.len() as u64) as u32
    }

    /// Last probe was a success.
    pub fn currently_reachable(&self) -> bool {
        self.records.last().map(|r| r.result.is_success()).unwrap_or(false)
    }

    pub fn verify_chain(&self) -> (bool, Option<usize>) {
        let mut expected_prev = PROBE_GENESIS_HASH;
        for (i, r) in self.records.iter().enumerate() {
            if r.prev_hash != expected_prev {
                return (false, Some(i));
            }
            let recomputed = compute_probe_hash(
                r.prober_id, r.target_id, r.epoch, r.result, &r.prev_hash,
            );
            if recomputed != r.record_hash {
                return (false, Some(i));
            }
            expected_prev = r.record_hash;
        }
        (true, None)
    }
}

// ─── Probe matrix ─────────────────────────────────────────────────────────────

#[derive(Debug, Clone)]
pub struct ProbeMatrix {
    logs: BTreeMap<(u32, u32), ProbeLog>,
}

impl ProbeMatrix {
    pub fn new() -> Self { Self { logs: BTreeMap::new() } }

    pub fn pair_count(&self) -> usize { self.logs.len() }

    pub fn record_probe(
        &mut self,
        prober_id: u32,
        target_id: u32,
        epoch:     u64,
        result:    ProbeResult,
    ) -> Result<(), ProbeError> {
        let log = self.logs
            .entry((prober_id, target_id))
            .or_insert_with(|| ProbeLog::new(prober_id, target_id));
        log.record(epoch, result)?;
        Ok(())
    }

    pub fn get_log(&self, prober_id: u32, target_id: u32) -> Option<&ProbeLog> {
        self.logs.get(&(prober_id, target_id))
    }

    /// All targets currently reachable from prober_id (last probe was Success).
    pub fn reachable_from(&self, prober_id: u32) -> Vec<u32> {
        self.logs.iter()
            .filter(|((p, _), log)| *p == prober_id && log.currently_reachable())
            .map(|((_, t), _)| *t)
            .collect()
    }

    /// All targets NOT currently reachable from prober_id.
    pub fn unreachable_peers(&self, prober_id: u32) -> Vec<u32> {
        self.logs.iter()
            .filter(|((p, _), log)| *p == prober_id && !log.currently_reachable())
            .map(|((_, t), _)| *t)
            .collect()
    }

    /// Average RTT across all successful probes in the matrix. 0 if none.
    pub fn avg_mesh_rtt(&self) -> u32 {
        let mut total: u64 = 0;
        let mut count: u64 = 0;
        for log in self.logs.values() {
            for r in log.records() {
                if r.result.is_success() {
                    total += r.rtt_ms as u64;
                    count += 1;
                }
            }
        }
        if count == 0 { 0 } else { (total / count) as u32 }
    }

    /// Total success probes across all pairs.
    pub fn total_success_count(&self) -> usize {
        self.logs.values().map(|l| l.success_count()).sum()
    }

    /// Total failure probes across all pairs.
    pub fn total_failure_count(&self) -> usize {
        self.logs.values().map(|l| l.failure_count()).sum()
    }
}

impl Default for ProbeMatrix {
    fn default() -> Self { Self::new() }
}

// ─── Tests ───────────────────────────────────────────────────────────────────

#[cfg(test)]
mod tests {
    use super::*;

    // ── ProbeResult ───────────────────────────────────────────────────────────

    #[test]
    fn success_is_success() {
        let r = ProbeResult::Success { rtt_ms: 42 };
        assert!(r.is_success());
        assert_eq!(r.rtt_ms(), 42);
        assert_eq!(r.result_byte(), 0);
    }

    #[test]
    fn timeout_not_success() {
        assert!(!ProbeResult::Timeout.is_success());
        assert_eq!(ProbeResult::Timeout.rtt_ms(), 0);
        assert_eq!(ProbeResult::Timeout.result_byte(), 1);
    }

    #[test]
    fn refused_and_noroute_bytes() {
        assert_eq!(ProbeResult::Refused.result_byte(), 2);
        assert_eq!(ProbeResult::NoRoute.result_byte(), 3);
    }

    // ── build_probe_record ────────────────────────────────────────────────────

    #[test]
    fn record_hash_nonzero() {
        let r = build_probe_record(1, 2, 1, ProbeResult::Success { rtt_ms: 10 }, &PROBE_GENESIS_HASH);
        assert_ne!(r.record_hash, [0u8; 32]);
    }

    #[test]
    fn record_hash_deterministic() {
        let r1 = build_probe_record(1, 2, 1, ProbeResult::Success { rtt_ms: 10 }, &PROBE_GENESIS_HASH);
        let r2 = build_probe_record(1, 2, 1, ProbeResult::Success { rtt_ms: 10 }, &PROBE_GENESIS_HASH);
        assert_eq!(r1.record_hash, r2.record_hash);
    }

    #[test]
    fn different_result_different_hash() {
        let r1 = build_probe_record(1, 2, 1, ProbeResult::Success { rtt_ms: 10 }, &PROBE_GENESIS_HASH);
        let r2 = build_probe_record(1, 2, 1, ProbeResult::Timeout, &PROBE_GENESIS_HASH);
        assert_ne!(r1.record_hash, r2.record_hash);
    }

    #[test]
    fn rtt_stored_correctly() {
        let r = build_probe_record(1, 2, 1, ProbeResult::Success { rtt_ms: 150 }, &PROBE_GENESIS_HASH);
        assert_eq!(r.rtt_ms, 150);
    }

    // ── ProbeLog ──────────────────────────────────────────────────────────────

    #[test]
    fn new_log_empty() {
        let l = ProbeLog::new(1, 2);
        assert!(l.is_empty());
        assert_eq!(l.avg_rtt_ms(), 0);
        assert!(!l.currently_reachable());
    }

    #[test]
    fn record_success_and_count() {
        let mut l = ProbeLog::new(1, 2);
        l.record(1, ProbeResult::Success { rtt_ms: 20 }).unwrap();
        l.record(2, ProbeResult::Success { rtt_ms: 40 }).unwrap();
        assert_eq!(l.success_count(), 2);
        assert_eq!(l.avg_rtt_ms(), 30);
        assert!(l.currently_reachable());
    }

    #[test]
    fn record_timeout_not_reachable() {
        let mut l = ProbeLog::new(1, 2);
        l.record(1, ProbeResult::Success { rtt_ms: 20 }).unwrap();
        l.record(2, ProbeResult::Timeout).unwrap();
        assert!(!l.currently_reachable());
        assert_eq!(l.timeout_count(), 1);
        assert_eq!(l.failure_count(), 1);
    }

    #[test]
    fn stale_epoch_rejected() {
        let mut l = ProbeLog::new(1, 2);
        l.record(5, ProbeResult::Timeout).unwrap();
        assert!(matches!(l.record(4, ProbeResult::Timeout), Err(ProbeError::StaleEpoch)));
        assert!(matches!(l.record(5, ProbeResult::Timeout), Err(ProbeError::StaleEpoch)));
    }

    #[test]
    fn hash_chain_links() {
        let mut l = ProbeLog::new(1, 2);
        l.record(1, ProbeResult::Success { rtt_ms: 10 }).unwrap();
        l.record(2, ProbeResult::Timeout).unwrap();
        assert_eq!(l.records()[1].prev_hash, l.records()[0].record_hash);
    }

    #[test]
    fn verify_chain_valid() {
        let mut l = ProbeLog::new(1, 2);
        for e in 1..=5u64 {
            l.record(e, ProbeResult::Success { rtt_ms: e as u32 * 10 }).unwrap();
        }
        let (valid, broken) = l.verify_chain();
        assert!(valid);
        assert!(broken.is_none());
    }

    #[test]
    fn avg_rtt_only_successes() {
        let mut l = ProbeLog::new(1, 2);
        l.record(1, ProbeResult::Success { rtt_ms: 100 }).unwrap();
        l.record(2, ProbeResult::Timeout).unwrap();
        l.record(3, ProbeResult::Success { rtt_ms: 200 }).unwrap();
        // avg over only the 2 successes: (100+200)/2 = 150
        assert_eq!(l.avg_rtt_ms(), 150);
    }

    // ── ProbeMatrix ───────────────────────────────────────────────────────────

    #[test]
    fn new_matrix_empty() {
        let m = ProbeMatrix::new();
        assert_eq!(m.pair_count(), 0);
        assert_eq!(m.avg_mesh_rtt(), 0);
    }

    #[test]
    fn record_probe_creates_pairs() {
        let mut m = ProbeMatrix::new();
        m.record_probe(1, 2, 1, ProbeResult::Success { rtt_ms: 30 }).unwrap();
        m.record_probe(1, 3, 1, ProbeResult::Timeout).unwrap();
        assert_eq!(m.pair_count(), 2);
    }

    #[test]
    fn reachable_from_correct() {
        let mut m = ProbeMatrix::new();
        m.record_probe(1, 2, 1, ProbeResult::Success { rtt_ms: 10 }).unwrap();
        m.record_probe(1, 3, 1, ProbeResult::Timeout).unwrap();
        m.record_probe(1, 4, 1, ProbeResult::Success { rtt_ms: 20 }).unwrap();
        let r = m.reachable_from(1);
        assert_eq!(r.len(), 2);
        assert!(r.contains(&2));
        assert!(r.contains(&4));
    }

    #[test]
    fn unreachable_peers_correct() {
        let mut m = ProbeMatrix::new();
        m.record_probe(1, 2, 1, ProbeResult::Success { rtt_ms: 10 }).unwrap();
        m.record_probe(1, 3, 1, ProbeResult::Refused).unwrap();
        let u = m.unreachable_peers(1);
        assert_eq!(u, vec![3]);
    }

    #[test]
    fn avg_mesh_rtt_aggregates() {
        let mut m = ProbeMatrix::new();
        m.record_probe(1, 2, 1, ProbeResult::Success { rtt_ms: 100 }).unwrap();
        m.record_probe(1, 3, 1, ProbeResult::Success { rtt_ms: 200 }).unwrap();
        m.record_probe(2, 1, 1, ProbeResult::Timeout).unwrap();
        assert_eq!(m.avg_mesh_rtt(), 150); // (100+200)/2
    }

    #[test]
    fn total_counts_correct() {
        let mut m = ProbeMatrix::new();
        m.record_probe(1, 2, 1, ProbeResult::Success { rtt_ms: 10 }).unwrap();
        m.record_probe(1, 3, 1, ProbeResult::Timeout).unwrap();
        m.record_probe(2, 1, 1, ProbeResult::Refused).unwrap();
        assert_eq!(m.total_success_count(), 1);
        assert_eq!(m.total_failure_count(), 2);
    }
}
