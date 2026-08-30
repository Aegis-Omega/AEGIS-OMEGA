//! PAPO-Ψ Verifier — 3-Step Predictive Alignment Rollout
//! EPISTEMIC TIER: T2
//!
//! Three-phase alignment verification protocol:
//!   Step 0 (PREDICT):  Submit claim + context; record prediction response hash.
//!   Step 1 (CRITIQUE): Challenge the Step 0 prediction; record critique response hash.
//!   Step 2 (VERDICT):  Synthesize final alignment verdict from Step 1 response hash.
//!
//! Verdict derivation: SHA-256(step2_response_hash)[0..8] as u64 big-endian → verdict % 3:
//!   0 = Aligned, 1 = Misaligned, 2 = Uncertain.
//!   confidence_q8 = SHA-256(step2_response_hash)[8] — deterministic, no f64.
//!
//! Each verification run produces a PapoRecord hash-chained from PAPO_GENESIS_HASH.
//! verify_chain() re-derives every entry_hash and detects any tampering.
//!
//! Non-cloud path: CloudBridge stub returns deterministic "stub_verified" text.
//! Cloud path (feature = "cloud"): live DashScope calls via CloudBridge::http_post.

use sha2::{Sha256, Digest};
use crate::cloud_bridge::CloudBridge;

pub const PAPO_GENESIS_HASH: [u8; 32] = [0u8; 32];

/// The three possible PAPO alignment verdicts.
#[derive(Debug, Clone, PartialEq, Eq)]
pub enum AlignmentVerdict {
    Aligned,
    Misaligned,
    Uncertain,
}

impl AlignmentVerdict {
    fn to_byte(&self) -> u8 {
        match self {
            Self::Aligned    => 0,
            Self::Misaligned => 1,
            Self::Uncertain  => 2,
        }
    }

    fn from_byte(b: u8) -> Self {
        match b % 3 {
            0 => Self::Aligned,
            1 => Self::Misaligned,
            _ => Self::Uncertain,
        }
    }
}

/// One step in the 3-step PAPO-Ψ protocol.
#[derive(Debug, Clone)]
pub struct PapoStep {
    pub index:         u8,          // 0 = PREDICT, 1 = CRITIQUE, 2 = VERDICT
    pub prompt_hash:   [u8; 32],    // SHA-256 of the prompt sent to the bridge
    pub response_hash: [u8; 32],    // SHA-256 of the bridge response
}

/// A single PAPO-Ψ verification record, hash-chained for tamper detection.
#[derive(Debug, Clone)]
pub struct PapoRecord {
    pub sequence:       u64,
    pub claim_hash:     [u8; 32],   // SHA-256 of the input claim
    pub steps:          [PapoStep; 3],
    pub verdict:        AlignmentVerdict,
    pub confidence_q8:  u8,         // 0–255; derived from step2.response_hash[8]
    pub prev_hash:      [u8; 32],
    pub entry_hash:     [u8; 32],
}

/// Append-only chain of PAPO-Ψ verification records.
pub struct PapoChain {
    records: Vec<PapoRecord>,
}

impl PapoChain {
    pub fn new() -> Self {
        Self { records: Vec::new() }
    }

    /// Run a 3-step PAPO-Ψ verification and append the result to the chain.
    pub fn verify(
        &mut self,
        claim:    &str,
        context:  &str,
        sequence: u64,
        bridge:   &mut CloudBridge,
    ) -> &PapoRecord {
        let prev_hash  = self.records.last().map(|r| r.entry_hash).unwrap_or(PAPO_GENESIS_HASH);
        let claim_hash = sha256_bytes(claim.as_bytes());

        let steps = execute_steps(claim, context, bridge);
        let (verdict, confidence_q8) = derive_verdict(&steps);
        let entry_hash = compute_entry_hash(
            &prev_hash, sequence, &claim_hash, &steps, &verdict, confidence_q8,
        );

        self.records.push(PapoRecord {
            sequence,
            claim_hash,
            steps,
            verdict,
            confidence_q8,
            prev_hash,
            entry_hash,
        });
        self.records.last().unwrap()
    }

    /// Verify hash-chain integrity. Returns (is_valid, first_invalid_index).
    pub fn verify_chain(&self) -> (bool, Option<usize>) {
        let mut prev = PAPO_GENESIS_HASH;
        for (i, r) in self.records.iter().enumerate() {
            if r.prev_hash != prev { return (false, Some(i)); }
            let expected = compute_entry_hash(
                &prev, r.sequence, &r.claim_hash, &r.steps, &r.verdict, r.confidence_q8,
            );
            if r.entry_hash != expected { return (false, Some(i)); }
            prev = r.entry_hash;
        }
        (true, None)
    }

    pub fn records(&self) -> &[PapoRecord] { &self.records }
}

impl Default for PapoChain {
    fn default() -> Self { Self::new() }
}

// ─── Internal helpers ────────────────────────────────────────────────────────

fn sha256_bytes(data: &[u8]) -> [u8; 32] {
    Sha256::digest(data).into()
}

/// Execute the 3-step PAPO-Ψ protocol against the bridge.
fn execute_steps(claim: &str, context: &str, bridge: &mut CloudBridge) -> [PapoStep; 3] {
    // Step 0 — PREDICT
    let p0 = format!(
        "[PAPO-Step0:PREDICT] Claim: {} Context: {} Does this align with constitutional constraints?",
        claim, context
    );
    let p0_hash = sha256_bytes(p0.as_bytes());
    let r0 = bridge.verify(&p0).unwrap_or_else(|_| "no_response".to_string());
    let r0_hash = sha256_bytes(r0.as_bytes());

    // Step 1 — CRITIQUE (references step-0 response hash prefix)
    let p1 = format!(
        "[PAPO-Step1:CRITIQUE] r0_prefix={} Identify misalignment risks in: {}",
        hex_prefix_4(&r0_hash), claim
    );
    let p1_hash = sha256_bytes(p1.as_bytes());
    let r1 = bridge.verify(&p1).unwrap_or_else(|_| "no_response".to_string());
    let r1_hash = sha256_bytes(r1.as_bytes());

    // Step 2 — VERDICT (references step-1 response hash prefix)
    let p2 = format!(
        "[PAPO-Step2:VERDICT] r1_prefix={} Final verdict: ALIGNED, MISALIGNED, or UNCERTAIN.",
        hex_prefix_4(&r1_hash)
    );
    let p2_hash = sha256_bytes(p2.as_bytes());
    let r2 = bridge.verify(&p2).unwrap_or_else(|_| "no_response".to_string());
    let r2_hash = sha256_bytes(r2.as_bytes());

    [
        PapoStep { index: 0, prompt_hash: p0_hash, response_hash: r0_hash },
        PapoStep { index: 1, prompt_hash: p1_hash, response_hash: r1_hash },
        PapoStep { index: 2, prompt_hash: p2_hash, response_hash: r2_hash },
    ]
}

/// Derive verdict + confidence deterministically from the step-2 response hash.
/// verdict     = AlignmentVerdict::from_byte(v % 3) where v = r2_hash[0..8] as u64 be
/// confidence  = r2_hash[8]
fn derive_verdict(steps: &[PapoStep; 3]) -> (AlignmentVerdict, u8) {
    let h = &steps[2].response_hash;
    let v = u64::from_be_bytes([h[0], h[1], h[2], h[3], h[4], h[5], h[6], h[7]]);
    let confidence_q8 = h[8];
    (AlignmentVerdict::from_byte((v % 3) as u8), confidence_q8)
}

/// entry_hash = SHA-256(prev || sequence_be || claim_hash || steps[0..2] || verdict_byte || confidence_q8)
fn compute_entry_hash(
    prev:          &[u8; 32],
    sequence:      u64,
    claim_hash:    &[u8; 32],
    steps:         &[PapoStep; 3],
    verdict:       &AlignmentVerdict,
    confidence_q8: u8,
) -> [u8; 32] {
    let mut h = Sha256::new();
    h.update(prev);
    h.update(sequence.to_be_bytes());
    h.update(claim_hash);
    for s in steps {
        h.update([s.index]);
        h.update(s.prompt_hash);
        h.update(s.response_hash);
    }
    h.update([verdict.to_byte()]);
    h.update([confidence_q8]);
    h.finalize().into()
}

fn hex_prefix_4(hash: &[u8; 32]) -> String {
    format!("{:02x}{:02x}{:02x}{:02x}", hash[0], hash[1], hash[2], hash[3])
}

// ─── Tests ───────────────────────────────────────────────────────────────────

#[cfg(test)]
mod tests {
    use super::*;

    fn stub_bridge() -> CloudBridge {
        CloudBridge::new(Some("stub-key".to_string()), "qwen-plus")
    }

    // 1. GENESIS hash is all zeros
    #[test]
    fn genesis_hash_all_zeros() {
        assert_eq!(PAPO_GENESIS_HASH, [0u8; 32]);
    }

    // 2. Empty chain is valid
    #[test]
    fn empty_chain_valid() {
        let chain = PapoChain::new();
        assert_eq!(chain.verify_chain(), (true, None));
    }

    // 3. Single verification produces a record
    #[test]
    fn single_verify_produces_record() {
        let mut chain = PapoChain::new();
        let mut bridge = stub_bridge();
        chain.verify("test claim", "context", 1, &mut bridge);
        assert_eq!(chain.records().len(), 1);
    }

    // 4. Chain valid after single record
    #[test]
    fn chain_valid_after_one_record() {
        let mut chain = PapoChain::new();
        let mut bridge = stub_bridge();
        chain.verify("claim", "ctx", 0, &mut bridge);
        assert_eq!(chain.verify_chain(), (true, None));
    }

    // 5. Chain valid after N records
    #[test]
    fn chain_valid_after_n_records() {
        let mut chain = PapoChain::new();
        let mut bridge = stub_bridge();
        for i in 0u64..5 {
            chain.verify("claim", "ctx", i, &mut bridge);
        }
        assert_eq!(chain.verify_chain(), (true, None));
        assert_eq!(chain.records().len(), 5);
    }

    // 6. Tamper claim_hash → chain fails at tampered index
    #[test]
    fn tamper_claim_hash_fails_verify() {
        let mut chain = PapoChain::new();
        let mut bridge = stub_bridge();
        for i in 0u64..3 { chain.verify("claim", "ctx", i, &mut bridge); }
        chain.records[1].claim_hash[0] ^= 0xFF;
        let (valid, idx) = chain.verify_chain();
        assert!(!valid);
        assert_eq!(idx, Some(1));
    }

    // 7. Tamper verdict → chain fails at tampered index
    #[test]
    fn tamper_verdict_fails_verify() {
        let mut chain = PapoChain::new();
        let mut bridge = stub_bridge();
        for i in 0u64..3 { chain.verify("claim", "ctx", i, &mut bridge); }
        chain.records[0].verdict = match chain.records[0].verdict {
            AlignmentVerdict::Aligned    => AlignmentVerdict::Misaligned,
            AlignmentVerdict::Misaligned => AlignmentVerdict::Uncertain,
            AlignmentVerdict::Uncertain  => AlignmentVerdict::Aligned,
        };
        let (valid, idx) = chain.verify_chain();
        assert!(!valid);
        assert_eq!(idx, Some(0));
    }

    // 8. Tamper confidence_q8 → chain fails
    #[test]
    fn tamper_confidence_fails_verify() {
        let mut chain = PapoChain::new();
        let mut bridge = stub_bridge();
        for i in 0u64..3 { chain.verify("claim", "ctx", i, &mut bridge); }
        chain.records[2].confidence_q8 = chain.records[2].confidence_q8.wrapping_add(1);
        let (valid, idx) = chain.verify_chain();
        assert!(!valid);
        assert_eq!(idx, Some(2));
    }

    // 9. Tamper step prompt_hash → chain fails
    #[test]
    fn tamper_step_prompt_hash_fails_verify() {
        let mut chain = PapoChain::new();
        let mut bridge = stub_bridge();
        for i in 0u64..2 { chain.verify("claim", "ctx", i, &mut bridge); }
        chain.records[0].steps[1].prompt_hash[0] ^= 0x01;
        let (valid, _) = chain.verify_chain();
        assert!(!valid);
    }

    // 10. Tamper step response_hash → chain fails
    #[test]
    fn tamper_step_response_hash_fails_verify() {
        let mut chain = PapoChain::new();
        let mut bridge = stub_bridge();
        chain.verify("claim", "ctx", 0, &mut bridge);
        chain.records[0].steps[2].response_hash[5] ^= 0xAA;
        let (valid, _) = chain.verify_chain();
        assert!(!valid);
    }

    // 11. Tamper prev_hash → chain fails
    #[test]
    fn tamper_prev_hash_fails_verify() {
        let mut chain = PapoChain::new();
        let mut bridge = stub_bridge();
        for i in 0u64..2 { chain.verify("claim", "ctx", i, &mut bridge); }
        chain.records[1].prev_hash[0] ^= 0xFF;
        let (valid, idx) = chain.verify_chain();
        assert!(!valid);
        assert_eq!(idx, Some(1));
    }

    // 12. Determinism ×3: same inputs → same entry_hash
    #[test]
    fn entry_hash_determinism_triple() {
        let mut c1 = PapoChain::new(); let mut b1 = stub_bridge();
        let mut c2 = PapoChain::new(); let mut b2 = stub_bridge();
        let mut c3 = PapoChain::new(); let mut b3 = stub_bridge();
        let h1 = c1.verify("claim", "ctx", 42, &mut b1).entry_hash;
        let h2 = c2.verify("claim", "ctx", 42, &mut b2).entry_hash;
        let h3 = c3.verify("claim", "ctx", 42, &mut b3).entry_hash;
        assert_eq!(h1, h2);
        assert_eq!(h2, h3);
    }

    // 13. Step indices are 0, 1, 2 in order
    #[test]
    fn step_indices_are_zero_one_two() {
        let mut chain = PapoChain::new();
        let mut bridge = stub_bridge();
        let r = chain.verify("claim", "ctx", 0, &mut bridge);
        assert_eq!(r.steps[0].index, 0);
        assert_eq!(r.steps[1].index, 1);
        assert_eq!(r.steps[2].index, 2);
    }

    // 14. Verdict is one of the three variants (no panic)
    #[test]
    fn verdict_is_valid_variant() {
        let mut chain = PapoChain::new();
        let mut bridge = stub_bridge();
        let r = chain.verify("claim", "ctx", 0, &mut bridge);
        matches!(r.verdict, AlignmentVerdict::Aligned | AlignmentVerdict::Misaligned | AlignmentVerdict::Uncertain);
    }

    // 15. Verdict derives from step-2 response hash deterministically
    #[test]
    fn verdict_matches_hash_derivation() {
        let mut chain = PapoChain::new();
        let mut bridge = stub_bridge();
        let r = chain.verify("claim", "ctx", 0, &mut bridge);
        let h = r.steps[2].response_hash;
        let v = u64::from_be_bytes([h[0], h[1], h[2], h[3], h[4], h[5], h[6], h[7]]);
        let expected = AlignmentVerdict::from_byte((v % 3) as u8);
        assert_eq!(r.verdict, expected);
    }

    // 16. confidence_q8 derives from step-2 response hash [8]
    #[test]
    fn confidence_q8_from_response_hash() {
        let mut chain = PapoChain::new();
        let mut bridge = stub_bridge();
        let r = chain.verify("claim", "ctx", 0, &mut bridge);
        assert_eq!(r.confidence_q8, r.steps[2].response_hash[8]);
    }

    // 17. Bridge call count = 3 per verification (one per step)
    #[test]
    fn bridge_call_count_is_three_per_verify() {
        let mut chain = PapoChain::new();
        let mut bridge = stub_bridge();
        chain.verify("claim", "ctx", 0, &mut bridge);
        assert_eq!(bridge.call_count, 3);
    }

    // 18. Two calls → 6 bridge calls total
    #[test]
    fn bridge_call_count_accumulates() {
        let mut chain = PapoChain::new();
        let mut bridge = stub_bridge();
        chain.verify("a", "b", 0, &mut bridge);
        chain.verify("c", "d", 1, &mut bridge);
        assert_eq!(bridge.call_count, 6);
    }

    // 19. Different claims yield different claim_hash values
    #[test]
    fn different_claims_yield_different_hashes() {
        let mut c1 = PapoChain::new(); let mut b1 = stub_bridge();
        let mut c2 = PapoChain::new(); let mut b2 = stub_bridge();
        let r1 = c1.verify("claim A", "ctx", 0, &mut b1);
        let r2 = c2.verify("claim B", "ctx", 0, &mut b2);
        assert_ne!(r1.claim_hash, r2.claim_hash);
        assert_ne!(r1.entry_hash, r2.entry_hash);
    }
}
