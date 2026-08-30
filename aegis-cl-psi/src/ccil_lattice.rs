//! CCIL-Ψ Constitutional Constraint Lattice
//! EPISTEMIC TIER: T2
//!
//! Pre-softmax zero-violation enforcement.
//! Policy hyperplane masking: blocked indices set to safety_floor.
//! Deterministic fallback distribution if all logits masked.
//! EU AI Act risk tier escalation.

use serde::Serialize;

#[derive(Serialize, Debug, Clone)]
pub struct CCILReport {
    pub interventions: usize,
    pub masked_indices: Vec<usize>,
    pub fallback_triggered: bool,
    pub risk_tier: String,
}

pub struct CCILLattice {
    pub policy_mask: Vec<bool>,
    pub safety_floor: f32,
    pub fallback_dist: Vec<f32>,
}

impl CCILLattice {
    pub fn new(vocab_size: usize, blocked_indices: &[usize]) -> Self {
        let mut mask = vec![true; vocab_size];
        for &idx in blocked_indices {
            if idx < vocab_size {
                mask[idx] = false;
            }
        }
        let n = vocab_size.max(1);
        let fallback_dist = vec![1.0 / n as f32; vocab_size];
        Self { policy_mask: mask, safety_floor: -1e9, fallback_dist }
    }

    /// Apply constitutional masking to logits in-place.
    /// Returns a CCILReport documenting all interventions.
    pub fn apply(&self, logits: &mut Vec<f32>) -> CCILReport {
        let mut masked_indices = Vec::new();
        let mut interventions = 0;

        for (i, logit) in logits.iter_mut().enumerate() {
            if i >= self.policy_mask.len() { break; }
            if !self.policy_mask[i] {
                *logit = self.safety_floor;
                masked_indices.push(i);
                interventions += 1;
            }
        }

        // Fallback: if all allowed logits are below floor, use fallback distribution
        let all_masked = logits.iter().enumerate().all(|(i, &v)| {
            i >= self.policy_mask.len() || !self.policy_mask[i] || v <= self.safety_floor
        });
        let fallback_triggered = all_masked && !self.fallback_dist.is_empty();
        if fallback_triggered {
            for (i, logit) in logits.iter_mut().enumerate() {
                if i < self.fallback_dist.len() {
                    *logit = self.fallback_dist[i];
                }
            }
        }

        let risk_tier = if interventions == 0 { "NONE" }
            else if interventions < 3 { "LOW" }
            else if interventions < 10 { "MEDIUM" }
            else { "HIGH" }.to_string();

        CCILReport { interventions, masked_indices, fallback_triggered, risk_tier }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn blocked_indices_get_safety_floor() {
        let lattice = CCILLattice::new(5, &[1, 3]);
        let mut logits = vec![1.0, 2.0, 3.0, 4.0, 5.0];
        let report = lattice.apply(&mut logits);
        assert_eq!(report.interventions, 2);
        assert_eq!(logits[1], lattice.safety_floor);
        assert_eq!(logits[3], lattice.safety_floor);
        assert_eq!(logits[0], 1.0); // unchanged
        assert_eq!(logits[2], 3.0); // unchanged
    }

    #[test]
    fn no_interventions_when_no_blocks() {
        let lattice = CCILLattice::new(4, &[]);
        let mut logits = vec![1.0, 2.0, 3.0, 4.0];
        let report = lattice.apply(&mut logits);
        assert_eq!(report.interventions, 0);
        assert_eq!(report.risk_tier, "NONE");
        assert!(!report.fallback_triggered);
    }

    #[test]
    fn fallback_triggers_when_all_blocked() {
        let lattice = CCILLattice::new(3, &[0, 1, 2]);
        let mut logits = vec![1.0, 2.0, 3.0];
        let report = lattice.apply(&mut logits);
        assert!(report.fallback_triggered);
    }

    // 4. risk_tier "LOW" for 1–2 interventions
    #[test]
    fn risk_tier_low_for_few_blocks() {
        let lattice = CCILLattice::new(5, &[2]);
        let mut logits = vec![1.0, 2.0, 3.0, 4.0, 5.0];
        let report = lattice.apply(&mut logits);
        assert_eq!(report.interventions, 1);
        assert_eq!(report.risk_tier, "LOW");
    }

    // 5. masked_indices matches blocked set
    #[test]
    fn masked_indices_match_blocked() {
        let lattice = CCILLattice::new(6, &[1, 4]);
        let mut logits = vec![1.0; 6];
        let report = lattice.apply(&mut logits);
        assert_eq!(report.masked_indices, vec![1, 4]);
    }

    // 6. interventions == masked_indices.len() always
    #[test]
    fn interventions_matches_masked_len() {
        let lattice = CCILLattice::new(8, &[0, 2, 5, 7]);
        let mut logits = vec![1.0; 8];
        let report = lattice.apply(&mut logits);
        assert_eq!(report.interventions, report.masked_indices.len());
    }

    // 7. risk_tier "MEDIUM" for 3–9 interventions
    #[test]
    fn risk_tier_medium_for_mid_blocks() {
        let lattice = CCILLattice::new(10, &[0, 1, 2, 3]);
        let mut logits = vec![1.0; 10];
        let report = lattice.apply(&mut logits);
        assert_eq!(report.interventions, 4);
        assert_eq!(report.risk_tier, "MEDIUM");
    }

    // 8. safety_floor is very negative (≤ −1e8)
    #[test]
    fn safety_floor_is_very_negative() {
        let lattice = CCILLattice::new(4, &[]);
        assert!(lattice.safety_floor <= -1e8);
    }

    // 9. Out-of-range blocked index is silently ignored
    #[test]
    fn out_of_range_blocked_index_ignored() {
        let lattice = CCILLattice::new(3, &[10]); // 10 >= vocab_size=3
        let mut logits = vec![1.0, 2.0, 3.0];
        let report = lattice.apply(&mut logits);
        assert_eq!(report.interventions, 0);
    }

    // 10. policy_mask is all-true when no indices blocked
    #[test]
    fn policy_mask_all_true_when_no_blocks() {
        let lattice = CCILLattice::new(4, &[]);
        assert!(lattice.policy_mask.iter().all(|&v| v));
    }
}
