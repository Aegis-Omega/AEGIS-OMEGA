//! Matter-Hash Load-Shedding
//! EPISTEMIC TIER: T2
//!
//! Probabilistic admission gate: an event is admitted when the first 8 bytes
//! of SHA-256(key || sequence_be) interpreted as a u64 big-endian value are
//! strictly less than `threshold`.
//!
//! Admission invariants:
//!   - Deterministic: same (key, sequence, threshold) → same verdict; replay-safe.
//!   - No f64 in the admission path; `threshold` is a u64 fraction of u64::MAX.
//!   - `from_rate(rate_q16)` converts a Q16.16 fixed-point rate to a u64 threshold.
//!   - Tamper-evident: `LoadShedChain` hash-links each `LoadShedRecord` from
//!     `LOAD_SHED_GENESIS_HASH = [0u8; 32]`.
//!
//! Source: From Metaphysics to Production — Matter-Hash load-shedding, T2.

use sha2::{Sha256, Digest};

pub const LOAD_SHED_GENESIS_HASH: [u8; 32] = [0u8; 32];

/// Admission gate whose threshold is a u64 fraction of u64::MAX.
/// Events where `hash_prefix_u64(key, sequence) < threshold` are admitted.
pub struct LoadShedGate {
    pub threshold: u64,
}

impl LoadShedGate {
    /// Construct directly from a raw u64 threshold.
    pub fn new(threshold: u64) -> Self {
        Self { threshold }
    }

    /// Construct from a Q16.16 fixed-point rate in [0, 65536].
    /// `rate_q16 = 65536` → admit all; `rate_q16 = 0` → admit none.
    pub fn from_rate_q16(rate_q16: u32) -> Self {
        // Scale: threshold = (rate_q16 / 65536) × u64::MAX
        // Computed with u128 to avoid overflow.
        let threshold = (rate_q16 as u128 * u64::MAX as u128 / 65536) as u64;
        Self { threshold }
    }

    /// Returns true when the event with `key` and `sequence` is admitted.
    #[inline]
    pub fn admits(&self, key: &[u8], sequence: u64) -> bool {
        let h = hash_prefix(key, sequence);
        h < self.threshold
    }
}

/// Computes SHA-256(key || sequence_be)[0..8] as a big-endian u64.
#[inline]
fn hash_prefix(key: &[u8], sequence: u64) -> u64 {
    let mut hasher = Sha256::new();
    hasher.update(key);
    hasher.update(sequence.to_be_bytes());
    let digest = hasher.finalize();
    u64::from_be_bytes([
        digest[0], digest[1], digest[2], digest[3],
        digest[4], digest[5], digest[6], digest[7],
    ])
}

/// A single admission decision, hash-linked for replay traceability.
#[derive(Debug, Clone)]
pub struct LoadShedRecord {
    pub sequence:       u64,
    pub key_hash:       [u8; 32],   // SHA-256 of the event key
    pub admitted:       bool,
    pub threshold:      u64,
    pub hash_prefix:    u64,        // the u64 drawn from hash(key, sequence)
    pub prev_hash:      [u8; 32],
    pub entry_hash:     [u8; 32],
}

/// Append-only chain of `LoadShedRecord`s.
pub struct LoadShedChain {
    records: Vec<LoadShedRecord>,
}

impl LoadShedChain {
    pub fn new() -> Self {
        Self { records: Vec::new() }
    }

    /// Record an admission decision and chain it to the previous entry.
    pub fn record(&mut self, key: &[u8], sequence: u64, gate: &LoadShedGate) -> &LoadShedRecord {
        let prev_hash = self.records.last().map(|r| r.entry_hash).unwrap_or(LOAD_SHED_GENESIS_HASH);
        let hp = hash_prefix(key, sequence);
        let admitted = hp < gate.threshold;

        let key_hash: [u8; 32] = Sha256::digest(key).into();
        let entry_hash = Self::compute_entry_hash(&prev_hash, sequence, admitted, gate.threshold, hp);

        self.records.push(LoadShedRecord {
            sequence,
            key_hash,
            admitted,
            threshold: gate.threshold,
            hash_prefix: hp,
            prev_hash,
            entry_hash,
        });
        self.records.last().unwrap()
    }

    /// Verify the hash chain: each entry_hash re-derives from the prior record.
    /// Returns (is_valid, first_invalid_index).
    pub fn verify_chain(&self) -> (bool, Option<usize>) {
        let mut prev = LOAD_SHED_GENESIS_HASH;
        for (i, r) in self.records.iter().enumerate() {
            if r.prev_hash != prev { return (false, Some(i)); }
            let expected = Self::compute_entry_hash(&prev, r.sequence, r.admitted, r.threshold, r.hash_prefix);
            if r.entry_hash != expected { return (false, Some(i)); }
            prev = r.entry_hash;
        }
        (true, None)
    }

    pub fn records(&self) -> &[LoadShedRecord] { &self.records }

    fn compute_entry_hash(
        prev: &[u8; 32],
        sequence: u64,
        admitted: bool,
        threshold: u64,
        hp: u64,
    ) -> [u8; 32] {
        let mut h = Sha256::new();
        h.update(prev);
        h.update(sequence.to_be_bytes());
        h.update([admitted as u8]);
        h.update(threshold.to_be_bytes());
        h.update(hp.to_be_bytes());
        h.finalize().into()
    }
}

impl Default for LoadShedChain {
    fn default() -> Self { Self::new() }
}

#[cfg(test)]
mod tests {
    use super::*;

    // 1. Threshold 0 → admit nothing
    #[test]
    fn threshold_zero_admits_nothing() {
        let gate = LoadShedGate::new(0);
        for seq in 0u64..100 {
            assert!(!gate.admits(b"key", seq));
        }
    }

    // 2. Threshold u64::MAX → admit everything
    #[test]
    fn threshold_max_admits_everything() {
        let gate = LoadShedGate::new(u64::MAX);
        for seq in 0u64..100 {
            assert!(gate.admits(b"key", seq));
        }
    }

    // 3. from_rate_q16(0) → threshold 0 → admit nothing
    #[test]
    fn from_rate_q16_zero_admits_nothing() {
        let gate = LoadShedGate::from_rate_q16(0);
        assert!(!gate.admits(b"test", 1));
    }

    // 4. from_rate_q16(65536) → threshold u64::MAX → admit everything
    #[test]
    fn from_rate_q16_full_admits_everything() {
        let gate = LoadShedGate::from_rate_q16(65536);
        assert!(gate.admits(b"test", 1));
    }

    // 5. Determinism ×3: same inputs → same admission verdict
    #[test]
    fn admits_determinism_triple() {
        let gate = LoadShedGate::from_rate_q16(32768);  // 50%
        let r1 = gate.admits(b"hello", 42);
        let r2 = gate.admits(b"hello", 42);
        let r3 = gate.admits(b"hello", 42);
        assert_eq!(r1, r2);
        assert_eq!(r2, r3);
    }

    // 6. Different sequences yield different hash_prefix values (collision-resistant)
    #[test]
    fn different_sequences_differ() {
        let gate = LoadShedGate::new(u64::MAX);
        let h0 = { let gate = LoadShedGate::new(u64::MAX); gate.admits(b"k", 0); 0 };
        // Directly test hash_prefix distinctness via the chain recorder
        let mut chain = LoadShedChain::new();
        let r0 = chain.record(b"k", 0, &gate).hash_prefix;
        let r1 = chain.record(b"k", 1, &gate).hash_prefix;
        let _ = h0;
        assert_ne!(r0, r1, "distinct sequences should produce distinct hash prefixes");
    }

    // 7. Different keys yield different admission verdicts (probabilistic — test with non-trivial threshold)
    #[test]
    fn different_keys_may_differ() {
        let gate = LoadShedGate::from_rate_q16(32768);
        let mut both_same = true;
        let first = gate.admits(b"alpha", 0);
        for i in 1u64..100 {
            if gate.admits(b"alpha", i) != first { both_same = false; break; }
        }
        // At ~50% rate, hitting 100 identical outcomes has probability 2^-99 ≈ 0
        assert!(!both_same, "at 50% rate, 100 consecutive identical verdicts is statistically impossible");
    }

    // 8. Chain: empty → valid
    #[test]
    fn empty_chain_is_valid() {
        let chain = LoadShedChain::new();
        assert_eq!(chain.verify_chain(), (true, None));
    }

    // 9. Chain: after N records → valid
    #[test]
    fn chain_valid_after_records() {
        let gate = LoadShedGate::from_rate_q16(32768);
        let mut chain = LoadShedChain::new();
        for i in 0u64..20 {
            chain.record(b"event", i, &gate);
        }
        assert_eq!(chain.verify_chain(), (true, None));
        assert_eq!(chain.records().len(), 20);
    }

    // 10. Chain: tamper detection
    #[test]
    fn tampered_chain_fails_verify() {
        let gate = LoadShedGate::from_rate_q16(32768);
        let mut chain = LoadShedChain::new();
        for i in 0u64..5 {
            chain.record(b"event", i, &gate);
        }
        // Corrupt the admitted flag of record 2
        chain.records[2].admitted = !chain.records[2].admitted;
        let (valid, idx) = chain.verify_chain();
        assert!(!valid);
        assert_eq!(idx, Some(2));
    }

    // 11. from_rate_q16 midpoint is near half of u64::MAX
    #[test]
    fn from_rate_q16_midpoint_is_half() {
        let gate = LoadShedGate::from_rate_q16(32768);  // 0.5 × 65536
        let half = u64::MAX / 2;
        // Allow 1-LSB rounding error
        assert!(gate.threshold.abs_diff(half) <= 1);
    }

    // 12. GENESIS is all zeros
    #[test]
    fn genesis_hash_is_all_zeros() {
        assert_eq!(LOAD_SHED_GENESIS_HASH, [0u8; 32]);
    }
}
