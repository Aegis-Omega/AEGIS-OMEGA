//! Gate: INT4 LUT-KAN — Cache-Local Kolmogorov-Arnold Inference
//! EPISTEMIC TIER: T2 (engineering hypothesis)
//!
//! Replaces continuous B-spline activations in Kolmogorov-Arnold Networks with
//! INT4 integer lookup tables. Each activation is a 16-entry LUT (one cache line,
//! 64 bytes) indexed by a 4-bit quantised input. This eliminates floating-point
//! spline evaluation and makes activation O(1), cache-resident, and replay-safe.
//!
//! Kolmogorov-Arnold representation:
//!   f(x_1..x_n) = Σ_q Φ_q( Σ_p φ_{q,p}(x_p) )
//! where every univariate φ / Φ is an INT4 LUT, not a B-spline.
//!
//! Constitutional invariants (per CLAUDE.md §Rust):
//!   - NO f64 anywhere. All arithmetic is fixed-point i32/i64 integer.
//!   - Fixed-point scale is a power of two so rescale is an arithmetic bit-shift.
//!   - Hash inputs use `to_be_bytes()` (big-endian) only — never little-endian.
//!   - `saturating_add` / `saturating_mul` — no silent overflow.
//!   - Determinism: identical input → identical output across AMD/NVIDIA/CPU/ARM.
//!
//! The scorer produces a scalar fixed-point `score`. That score feeds the existing
//! constitutional hash-audit chain via `KanInferenceLog` — the inference mechanism
//! does not alter the hash-chain topology; it only contributes a verifiable record.

use sha2::{Digest, Sha256};

/// Genesis hash for the inference audit chain. Every chain begins here.
pub const KAN_GENESIS_HASH: [u8; 32] = [0u8; 32];

/// Number of representable INT4 values per activation (4-bit → 16 entries).
pub const LUT_SIZE: usize = 16;

/// One activation lookup table: 16 fixed-point entries, exactly one cache line
/// when stored as i32 (16 × 4 = 64 bytes).
pub type Lut = [i32; LUT_SIZE];

// ─── Core activation ──────────────────────────────────────────────────────────

/// INT4 LUT activation. Clamps the input to the valid 4-bit index range [0, 15]
/// and returns the table entry. O(1), cache-local, no floating point.
///
/// This is the primitive named in the skill's Tier Promotion Criterion #1.
#[inline]
pub fn lut_activation(input: i32, table: &Lut) -> i32 {
    let idx = input.clamp(0, (LUT_SIZE - 1) as i32) as usize;
    table[idx]
}

/// Quantise a fixed-point value to a 4-bit LUT index in [0, 15].
///
/// `shift` is the right-shift (power-of-two divide) applied before clamping.
/// Determinism is preserved: arithmetic shift on i32 is exact and platform-stable.
#[inline]
pub fn quantize_int4(value: i32, shift: u32) -> i32 {
    (value >> shift).clamp(0, (LUT_SIZE - 1) as i32)
}

// ─── KAN layer ────────────────────────────────────────────────────────────────

/// A single KAN layer: a dense grid of univariate LUT activations.
/// `edges[out][inp]` is the LUT on the edge from input `inp` to output node `out`.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct KanLayer {
    pub n_in: usize,
    pub n_out: usize,
    pub edges: Vec<Lut>, // length n_out * n_in, row-major by output node
    /// Right-shift applied to each output node's accumulated sum before the
    /// next layer requantises it. Power-of-two rescale (no f64).
    pub rescale_shift: u32,
}

#[derive(Debug, PartialEq, Eq)]
pub struct KanError(pub &'static str);

impl KanLayer {
    /// Construct a layer. `edges.len()` must equal `n_out * n_in`.
    pub fn new(n_in: usize, n_out: usize, edges: Vec<Lut>, rescale_shift: u32) -> Result<Self, KanError> {
        if n_in == 0 || n_out == 0 {
            return Err(KanError("n_in and n_out must be non-zero"));
        }
        if edges.len() != n_out.saturating_mul(n_in) {
            return Err(KanError("edges length must equal n_out * n_in"));
        }
        Ok(Self { n_in, n_out, edges, rescale_shift })
    }

    /// Forward pass. Each input is a 4-bit index in [0,15] (already quantised).
    /// Output node value = (Σ_inp lut_activation(input, edge)) >> rescale_shift.
    /// Returns one fixed-point value per output node.
    pub fn forward(&self, inputs: &[i32]) -> Result<Vec<i32>, KanError> {
        if inputs.len() != self.n_in {
            return Err(KanError("input length must equal n_in"));
        }
        let mut out = Vec::with_capacity(self.n_out);
        for o in 0..self.n_out {
            let base = o * self.n_in;
            let mut acc: i32 = 0;
            for (i, &x) in inputs.iter().enumerate() {
                let edge = &self.edges[base + i];
                acc = acc.saturating_add(lut_activation(x, edge));
            }
            // Power-of-two rescale — arithmetic shift, deterministic.
            out.push(acc >> self.rescale_shift);
        }
        Ok(out)
    }
}

// ─── KAN scorer (two-layer Kolmogorov-Arnold form) ────────────────────────────

/// A two-layer INT4 LUT-KAN scorer producing a single scalar governance score.
/// Layer 1 (φ): n_in → n_hidden. Layer 2 (Φ): n_hidden → 1.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct KanScorer {
    pub inner: KanLayer,
    pub outer: KanLayer,
}

impl KanScorer {
    pub fn new(inner: KanLayer, outer: KanLayer) -> Result<Self, KanError> {
        if outer.n_in != inner.n_out {
            return Err(KanError("outer.n_in must equal inner.n_out"));
        }
        if outer.n_out != 1 {
            return Err(KanError("scorer outer layer must have exactly one output"));
        }
        Ok(Self { inner, outer })
    }

    /// Score a quantised input vector. Returns the fixed-point scalar score.
    /// The inner layer's outputs are requantised to int4 before the outer layer.
    pub fn score(&self, inputs: &[i32]) -> Result<i32, KanError> {
        let hidden = self.inner.forward(inputs)?;
        // Requantise hidden values to 4-bit indices for the outer LUTs.
        let hidden_q: Vec<i32> = hidden.iter().map(|&v| quantize_int4(v, 0)).collect();
        let out = self.outer.forward(&hidden_q)?;
        Ok(out[0])
    }
}

// ─── Inference audit chain ────────────────────────────────────────────────────

/// One scored inference, hash-linked to the prior record. The record binds the
/// input fingerprint and the produced score so the scoring decision is replayable.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct KanInferenceRecord {
    pub sequence: u64,
    pub input_fingerprint: [u8; 32],
    pub score: i32,
    pub record_hash: [u8; 32],
    pub prev_hash: [u8; 32],
}

/// Deterministic fingerprint of a quantised input vector (big-endian i32 bytes).
pub fn fingerprint_inputs(inputs: &[i32]) -> [u8; 32] {
    let mut h = Sha256::new();
    h.update((inputs.len() as u64).to_be_bytes());
    for &x in inputs {
        h.update(x.to_be_bytes());
    }
    h.finalize().into()
}

fn compute_record_hash(
    prev: &[u8; 32],
    sequence: u64,
    input_fingerprint: &[u8; 32],
    score: i32,
) -> [u8; 32] {
    let mut h = Sha256::new();
    h.update(prev);
    h.update(sequence.to_be_bytes());
    h.update(input_fingerprint);
    h.update(score.to_be_bytes());
    h.finalize().into()
}

/// Append-only, hash-chained log of KAN scoring decisions.
#[derive(Debug, Default)]
pub struct KanInferenceLog {
    records: Vec<KanInferenceRecord>,
}

impl KanInferenceLog {
    pub fn new() -> Self {
        Self { records: Vec::new() }
    }

    pub fn len(&self) -> usize {
        self.records.len()
    }

    pub fn is_empty(&self) -> bool {
        self.records.is_empty()
    }

    pub fn records(&self) -> &[KanInferenceRecord] {
        &self.records
    }

    pub fn records_mut(&mut self) -> &mut [KanInferenceRecord] {
        &mut self.records
    }

    pub fn terminal_hash(&self) -> [u8; 32] {
        self.records
            .last()
            .map(|r| r.record_hash)
            .unwrap_or(KAN_GENESIS_HASH)
    }

    /// Score an input through the scorer and append the result to the chain.
    pub fn append_scored(
        &mut self,
        scorer: &KanScorer,
        inputs: &[i32],
    ) -> Result<&KanInferenceRecord, KanError> {
        let score = scorer.score(inputs)?;
        let fingerprint = fingerprint_inputs(inputs);
        Ok(self.append_record(fingerprint, score))
    }

    /// Append a pre-computed (fingerprint, score) pair to the chain.
    pub fn append_record(&mut self, input_fingerprint: [u8; 32], score: i32) -> &KanInferenceRecord {
        let prev = self.terminal_hash();
        let sequence = self.records.len() as u64;
        let record_hash = compute_record_hash(&prev, sequence, &input_fingerprint, score);
        self.records.push(KanInferenceRecord {
            sequence,
            input_fingerprint,
            score,
            record_hash,
            prev_hash: prev,
        });
        self.records.last().unwrap()
    }

    /// Re-walk the chain. Returns (true, None) if intact, else (false, Some(index))
    /// of the first record that fails verification.
    pub fn verify_chain(&self) -> (bool, Option<usize>) {
        let mut prev = KAN_GENESIS_HASH;
        for (i, r) in self.records.iter().enumerate() {
            if r.prev_hash != prev {
                return (false, Some(i));
            }
            if r.sequence != i as u64 {
                return (false, Some(i));
            }
            let expected = compute_record_hash(&prev, r.sequence, &r.input_fingerprint, r.score);
            if r.record_hash != expected {
                return (false, Some(i));
            }
            prev = r.record_hash;
        }
        (true, None)
    }
}

// ─── Tests — 19-test viability ring ───────────────────────────────────────────

#[cfg(test)]
mod tests {
    use super::*;

    /// A deterministic identity-ish LUT: entry[i] = i * 4 (fixed-point, scale 4).
    fn ramp_lut() -> Lut {
        let mut t = [0i32; LUT_SIZE];
        for (i, e) in t.iter_mut().enumerate() {
            *e = (i as i32) * 4;
        }
        t
    }

    fn const_lut(v: i32) -> Lut {
        [v; LUT_SIZE]
    }

    /// Build a small 2-in → 2-hidden → 1-out scorer for chain tests.
    fn sample_scorer() -> KanScorer {
        let inner = KanLayer::new(2, 2, vec![ramp_lut(), ramp_lut(), ramp_lut(), ramp_lut()], 0).unwrap();
        let outer = KanLayer::new(2, 1, vec![ramp_lut(), ramp_lut()], 0).unwrap();
        KanScorer::new(inner, outer).unwrap()
    }

    // 1 — lut_activation basic lookup
    #[test]
    fn lut_activation_indexes_table() {
        let t = ramp_lut();
        assert_eq!(lut_activation(5, &t), 20); // 5 * 4
    }

    // 2 — lut_activation clamps high inputs (no out-of-bounds)
    #[test]
    fn lut_activation_clamps_high() {
        let t = ramp_lut();
        assert_eq!(lut_activation(999, &t), 60); // clamped to index 15 → 15*4
    }

    // 3 — lut_activation clamps negative inputs
    #[test]
    fn lut_activation_clamps_negative() {
        let t = ramp_lut();
        assert_eq!(lut_activation(-7, &t), 0); // clamped to index 0
    }

    // 4 — determinism: same input → identical output across 3 runs
    #[test]
    fn lut_activation_deterministic_three_runs() {
        let t = ramp_lut();
        let a = lut_activation(9, &t);
        let b = lut_activation(9, &t);
        let c = lut_activation(9, &t);
        assert_eq!(a, b);
        assert_eq!(b, c);
    }

    // 5 — quantize_int4 maps via power-of-two shift and clamps to [0,15]
    #[test]
    fn quantize_int4_shifts_and_clamps() {
        assert_eq!(quantize_int4(256, 4), 15); // 256>>4 = 16 → clamp 15
        assert_eq!(quantize_int4(32, 4), 2); // 32>>4 = 2
        assert_eq!(quantize_int4(-100, 1), 0); // negative clamps to 0
    }

    // 6 — KanLayer rejects wrong edge count
    #[test]
    fn kan_layer_rejects_bad_edge_count() {
        let r = KanLayer::new(2, 2, vec![ramp_lut()], 0);
        assert_eq!(r, Err(KanError("edges length must equal n_out * n_in")));
    }

    // 7 — KanLayer rejects zero dimensions
    #[test]
    fn kan_layer_rejects_zero_dim() {
        assert!(KanLayer::new(0, 2, vec![], 0).is_err());
        assert!(KanLayer::new(2, 0, vec![], 0).is_err());
    }

    // 8 — KanLayer forward sums LUT outputs across inputs
    #[test]
    fn kan_layer_forward_sums_edges() {
        // 2 inputs → 1 output, both edges ramp. inputs [3, 5] → 3*4 + 5*4 = 32
        let layer = KanLayer::new(2, 1, vec![ramp_lut(), ramp_lut()], 0).unwrap();
        let out = layer.forward(&[3, 5]).unwrap();
        assert_eq!(out, vec![32]);
    }

    // 9 — KanLayer forward rejects wrong input length
    #[test]
    fn kan_layer_forward_rejects_bad_input_len() {
        let layer = KanLayer::new(2, 1, vec![ramp_lut(), ramp_lut()], 0).unwrap();
        assert!(layer.forward(&[1]).is_err());
    }

    // 10 — rescale_shift divides the accumulated sum by a power of two
    #[test]
    fn kan_layer_rescale_shift_divides() {
        // sum = 3*4 + 5*4 = 32, shift 2 → 32 >> 2 = 8
        let layer = KanLayer::new(2, 1, vec![ramp_lut(), ramp_lut()], 2).unwrap();
        assert_eq!(layer.forward(&[3, 5]).unwrap(), vec![8]);
    }

    // 11 — saturating_add prevents overflow on extreme LUT values
    #[test]
    fn kan_layer_saturates_on_overflow() {
        let big = const_lut(i32::MAX);
        let layer = KanLayer::new(2, 1, vec![big, big], 0).unwrap();
        // i32::MAX + i32::MAX saturates to i32::MAX, not wraps to negative
        assert_eq!(layer.forward(&[0, 0]).unwrap(), vec![i32::MAX]);
    }

    // 12 — KanScorer rejects mismatched layer dimensions
    #[test]
    fn kan_scorer_rejects_dim_mismatch() {
        let inner = KanLayer::new(2, 3, vec![ramp_lut(); 6], 0).unwrap();
        let outer = KanLayer::new(2, 1, vec![ramp_lut(), ramp_lut()], 0).unwrap();
        assert!(KanScorer::new(inner, outer).is_err());
    }

    // 13 — KanScorer rejects non-scalar output
    #[test]
    fn kan_scorer_rejects_non_scalar_output() {
        let inner = KanLayer::new(2, 2, vec![ramp_lut(); 4], 0).unwrap();
        let outer = KanLayer::new(2, 2, vec![ramp_lut(); 4], 0).unwrap();
        assert!(KanScorer::new(inner, outer).is_err());
    }

    // 14 — KanScorer produces a deterministic scalar score
    #[test]
    fn kan_scorer_scores_deterministically() {
        let s = sample_scorer();
        let a = s.score(&[2, 7]).unwrap();
        let b = s.score(&[2, 7]).unwrap();
        assert_eq!(a, b);
    }

    // 15 — fingerprint is deterministic and input-sensitive
    #[test]
    fn fingerprint_deterministic_and_sensitive() {
        assert_eq!(fingerprint_inputs(&[1, 2, 3]), fingerprint_inputs(&[1, 2, 3]));
        assert_ne!(fingerprint_inputs(&[1, 2, 3]), fingerprint_inputs(&[1, 2, 4]));
    }

    // 16 — empty inference log: terminal hash is genesis, chain verifies
    #[test]
    fn empty_log_is_genesis() {
        let log = KanInferenceLog::new();
        assert_eq!(log.terminal_hash(), KAN_GENESIS_HASH);
        assert_eq!(log.verify_chain(), (true, None));
        assert!(log.is_empty());
    }

    // 17 — append_scored links records and verifies across five entries
    #[test]
    fn append_scored_chain_verifies() {
        let scorer = sample_scorer();
        let mut log = KanInferenceLog::new();
        for i in 0..5 {
            log.append_scored(&scorer, &[i % 16, (i * 3) % 16]).unwrap();
        }
        assert_eq!(log.len(), 5);
        assert_eq!(log.verify_chain(), (true, None));
        assert_ne!(log.terminal_hash(), KAN_GENESIS_HASH);
        // prev_hash linkage
        assert_eq!(log.records()[1].prev_hash, log.records()[0].record_hash);
    }

    // 18 — verify_chain detects a tampered score (entry_hash defends itself)
    #[test]
    fn verify_chain_detects_tampered_score() {
        let scorer = sample_scorer();
        let mut log = KanInferenceLog::new();
        log.append_scored(&scorer, &[1, 2]).unwrap();
        log.append_scored(&scorer, &[3, 4]).unwrap();
        log.append_scored(&scorer, &[5, 6]).unwrap();
        log.records_mut()[1].score ^= 0x7FFF_FFFF; // tamper
        assert_eq!(log.verify_chain(), (false, Some(1)));
    }

    // 19 — verify_chain detects a tampered prev_hash link
    #[test]
    fn verify_chain_detects_tampered_prev_hash() {
        let scorer = sample_scorer();
        let mut log = KanInferenceLog::new();
        log.append_scored(&scorer, &[1, 2]).unwrap();
        log.append_scored(&scorer, &[3, 4]).unwrap();
        log.records_mut()[1].prev_hash[0] ^= 0xFF;
        assert_eq!(log.verify_chain(), (false, Some(1)));
    }

    // 20 — cross-implementation parity: byte-identical to the Python port in
    // agents/cognitive_pipeline.py. These reference values were computed by the
    // Python implementation; matching them proves deterministic replay across
    // Rust and Python (Tier Promotion Criterion #3 — cross-platform determinism).
    #[test]
    fn fingerprint_matches_python_reference() {
        let fp = fingerprint_inputs(&[1, 2, 3]);
        assert_eq!(
            hex::encode(fp),
            "887d1c0263dda885c9bf9848a91bdcd2c7efdb2d3b5a5100feb64de2d8f85549"
        );
        let rh = compute_record_hash(&KAN_GENESIS_HASH, 0, &fp, 42);
        assert_eq!(
            hex::encode(rh),
            "218edd96c1852207f1c1ed1774f613fa25abf60de6bb3298819b2c4debae6eef"
        );
    }

    /// Minimal hex encoder (no external dep — keeps the crate's dep surface fixed).
    mod hex {
        pub fn encode(bytes: [u8; 32]) -> String {
            let mut s = String::with_capacity(64);
            for b in bytes.iter() {
                s.push_str(&format!("{:02x}", b));
            }
            s
        }
    }
}
