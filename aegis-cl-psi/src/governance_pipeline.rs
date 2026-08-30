//! Gate 236: Governance Pipeline — Field-Scale Constitutional Integration
//! EPISTEMIC TIER: T2 (engineering hypothesis)
//!
//! Wires the complete constitutional substrate into one stateful processing node:
//!   EntropyBudget  (Gate 234) — adaptive event accounting
//!   DriftHistory   (Gate 235) — D0–D4 severity classification
//!   ConstitutionalAutonode (Gate 231) — resonance + cert + coherence + chain
//!   ReplayChain    (Gate 233) — State_t = Replay(Lineage) proof surface
//!
//! One process() call = one atomic governance cycle:
//!   1. Check entropy budget — reject if insufficient (T0_ABORT signal)
//!   2. Run constitutional autonode tick → AutonodeCycleRecord
//!   3. Classify drift vs previous epoch
//!   4. Consume entropy budget for the adaptive event
//!   5. Replenish entropy if the cycle was fully coherent (replay-certified)
//!   6. Append tick to replay chain
//!   7. Return PipelineRecord with all outputs
//!
//! GovernancePipeline is the organism-scale stateful node. All constitutional
//! invariants are enforced within process() — a single point of accountability.

use crate::constitutional_autonode::{ConstitutionalAutonode, AutonodeTick, AutonodeCycleRecord};
use crate::constitutional_replay::ReplayChain;
use crate::entropy_budget::{EntropyBudget, BudgetError};
use crate::drift_classifier::{DriftHistory, DriftClass, DriftRecord};
use crate::resonance_monitor::ResonanceReport;

// ─── Pipeline error ───────────────────────────────────────────────────────

#[derive(Debug)]
pub enum PipelineError {
    InsufficientEntropy { available: u64, required: u64 },
    AutonodeError(&'static str),
    DriftHistoryError(&'static str),
}

// ─── Pipeline record ──────────────────────────────────────────────────────

/// The full output of one governance pipeline cycle.
#[derive(Debug)]
pub struct PipelineRecord {
    pub epoch:                    u64,
    pub sequence_id:              u64,
    pub cycle:                    AutonodeCycleRecord,
    pub drift_class:              DriftClass,
    pub entropy_balance_before:   u64,
    pub entropy_balance_after:    u64,
    /// True iff the cycle was coherent AND budget was replenished.
    pub replay_replenished:       bool,
    /// Current entropy budget balance.
    pub entropy_balance:          u64,
    /// Whether mutation authority is currently active (drift + budget check).
    pub mutation_authority_active: bool,
}

// ─── Governance pipeline ──────────────────────────────────────────────────

/// Field-scale governance pipeline — stateful, single-point constitutional enforcement.
pub struct GovernancePipeline {
    autonode:      ConstitutionalAutonode,
    replay_chain:  ReplayChain,
    entropy:       EntropyBudget,
    drift_history: DriftHistory,
    last_resonance: Option<ResonanceReport>,
    constitutional_hash: [u8; 32],
}

impl GovernancePipeline {
    /// Create a new governance pipeline.
    pub fn new(constitutional_hash: [u8; 32], system_version: &'static str) -> Self {
        Self {
            autonode:          ConstitutionalAutonode::new(constitutional_hash, system_version),
            replay_chain:      ReplayChain::new(constitutional_hash, system_version),
            entropy:           EntropyBudget::new(),
            drift_history:     DriftHistory::new(),
            last_resonance:    None,
            constitutional_hash,
        }
    }

    /// Current entropy balance.
    pub fn entropy_balance(&self) -> u64 { self.entropy.balance() }

    /// True iff adaptive events are currently permitted.
    pub fn can_adapt(&self) -> bool { self.entropy.can_adapt() }

    /// Number of completed pipeline cycles.
    pub fn cycle_count(&self) -> usize { self.replay_chain.tick_count() }

    /// True iff the autonode has been continuously coherent across all epochs.
    pub fn is_continuously_coherent(&self) -> bool { self.autonode.is_continuously_coherent() }

    /// Current drift class (or D0 if no cycles yet).
    pub fn current_drift_class(&self) -> DriftClass {
        self.drift_history.records().last().map(|r| r.class).unwrap_or(DriftClass::D0)
    }

    /// True iff mutation authority is currently active (drift < D2 AND entropy sufficient).
    pub fn mutation_authority_active(&self) -> bool {
        self.drift_history.mutation_authority_active() && self.entropy.can_adapt()
    }

    /// Process one governance cycle.
    ///
    /// Rejects the cycle if entropy budget is insufficient (returns PipelineError::InsufficientEntropy).
    /// On success: consumes entropy, optionally replenishes for coherent cycles, records drift.
    pub fn process(&mut self, tick: AutonodeTick) -> Result<PipelineRecord, PipelineError> {
        let epoch = tick.epoch;
        let sequence_id = tick.sequence_id;

        // ── 1. Check entropy ──────────────────────────────────────────────
        let entropy_balance_before = self.entropy.balance();
        if !self.entropy.can_adapt() {
            return Err(PipelineError::InsufficientEntropy {
                available: entropy_balance_before,
                required: crate::entropy_budget::ADAPTIVE_EVENT_COST,
            });
        }

        // ── 2. Run autonode tick ──────────────────────────────────────────
        let cycle = self.autonode.tick(tick.clone())
            .map_err(|e| PipelineError::AutonodeError(e.0))?;

        // ── 3. Classify drift ─────────────────────────────────────────────
        let prev_resonance = self.last_resonance.as_ref();
        let drift_rec: &DriftRecord = self.drift_history
            .record(epoch, &cycle.resonance, prev_resonance)
            .map_err(|e| PipelineError::DriftHistoryError(e.0))?;
        let drift_class = drift_rec.class;

        // ── 4. Consume entropy ────────────────────────────────────────────
        self.entropy.consume_adaptive()
            .map_err(|e| match e {
                BudgetError::InsufficientBudget { available, required } =>
                    PipelineError::InsufficientEntropy { available, required },
                _ => PipelineError::AutonodeError("entropy custom delta error"),
            })?;

        // ── 5. Replenish if coherent ──────────────────────────────────────
        let replay_replenished = cycle.is_fully_coherent;
        if replay_replenished {
            self.entropy.replenish_replay();
        }
        let entropy_balance_after = self.entropy.balance();

        // ── 6. Append to replay chain ─────────────────────────────────────
        self.replay_chain.tick(tick)
            .map_err(|e| PipelineError::AutonodeError(e.0))?;

        // Update last resonance for next drift classification
        self.last_resonance = Some(cycle.resonance.clone());

        let mutation_authority_active =
            drift_class.mutation_authority_active() && self.entropy.can_adapt();

        Ok(PipelineRecord {
            epoch,
            sequence_id,
            cycle,
            drift_class,
            entropy_balance_before,
            entropy_balance_after,
            replay_replenished,
            entropy_balance: entropy_balance_after,
            mutation_authority_active,
        })
    }

    /// Build a replay proof of the current pipeline state.
    pub fn build_replay_proof(&self) -> crate::constitutional_replay::ReplayProof {
        self.replay_chain.build_proof()
    }
}

// ─── Tests ────────────────────────────────────────────────────────────────

#[cfg(test)]
mod tests {
    use super::*;
    use crate::chord_network::NetworkVerdict;
    use crate::self_certification::NetworkSnapshot;

    fn ch(v: u8) -> [u8; 32] { let mut h = [0u8; 32]; h[0] = v; h }

    fn ring5(s: u8) -> Vec<[u8; 32]> {
        vec![ch(s), ch(s+1), ch(s+2), ch(s+1), ch(s)]
    }

    fn net() -> NetworkSnapshot {
        NetworkSnapshot { verdict: NetworkVerdict::Unified, peer_count: 3, above_phi_count: 0, quorum_triadic: true }
    }

    fn good_tick(epoch: u64, seq: u64) -> AutonodeTick {
        AutonodeTick {
            epoch, sequence_id: seq, divergence_risk: 0.12,
            start_rank: 3, end_rank: 9, ring_hashes: ring5(1),
            network: net(), mutation_authority_active: true,
        }
    }

    #[test]
    fn new_pipeline_initial_state() {
        let p = GovernancePipeline::new(ch(1), "1.0.0");
        assert_eq!(p.cycle_count(), 0);
        assert!(p.can_adapt());
        assert!(p.mutation_authority_active());
    }

    #[test]
    fn process_good_cycle_succeeds() {
        let mut p = GovernancePipeline::new(ch(1), "1.0.0");
        let rec = p.process(good_tick(1, 100)).unwrap();
        assert_eq!(rec.epoch, 1);
        assert_eq!(rec.sequence_id, 100);
    }

    #[test]
    fn process_increments_cycle_count() {
        let mut p = GovernancePipeline::new(ch(1), "1.0.0");
        p.process(good_tick(1, 100)).unwrap();
        p.process(good_tick(2, 101)).unwrap();
        assert_eq!(p.cycle_count(), 2);
    }

    #[test]
    fn coherent_cycle_replenishes_entropy() {
        let mut p = GovernancePipeline::new(ch(1), "1.0.0");
        let rec = p.process(good_tick(1, 100)).unwrap();
        assert!(rec.cycle.is_fully_coherent);
        assert!(rec.replay_replenished);
        // balance_before - ADAPTIVE_EVENT_COST + REPLAY_REPLENISHMENT
        use crate::entropy_budget::{INITIAL_ENTROPY_BUDGET, ADAPTIVE_EVENT_COST, REPLAY_REPLENISHMENT};
        assert_eq!(rec.entropy_balance_after,
            INITIAL_ENTROPY_BUDGET - ADAPTIVE_EVENT_COST + REPLAY_REPLENISHMENT);
    }

    #[test]
    fn incoherent_cycle_no_replenishment() {
        let mut p = GovernancePipeline::new(ch(1), "1.0.0");
        let mut t = good_tick(1, 100);
        t.divergence_risk = 0.99; // above phi → incoherent
        let rec = p.process(t).unwrap();
        assert!(!rec.cycle.is_fully_coherent);
        assert!(!rec.replay_replenished);
    }

    #[test]
    fn insufficient_entropy_rejects_process() {
        let mut p = GovernancePipeline::new(ch(1), "1.0.0");
        // Drain entropy to 0
        p.entropy = crate::entropy_budget::EntropyBudget::with_balance(0);
        let err = p.process(good_tick(1, 100)).unwrap_err();
        assert!(matches!(err, PipelineError::InsufficientEntropy { .. }));
    }

    #[test]
    fn drift_class_d0_on_first_cycle() {
        let mut p = GovernancePipeline::new(ch(1), "1.0.0");
        let rec = p.process(good_tick(1, 100)).unwrap();
        assert_eq!(rec.drift_class, DriftClass::D0);
    }

    #[test]
    fn drift_class_d4_on_above_phi() {
        let mut p = GovernancePipeline::new(ch(1), "1.0.0");
        p.process(good_tick(1, 100)).unwrap();
        let mut t2 = good_tick(2, 101);
        t2.divergence_risk = 0.99;
        let rec = p.process(t2).unwrap();
        assert_eq!(rec.drift_class, DriftClass::D4);
    }

    #[test]
    fn mutation_authority_suspended_on_d4() {
        let mut p = GovernancePipeline::new(ch(1), "1.0.0");
        p.process(good_tick(1, 100)).unwrap();
        let mut t2 = good_tick(2, 101);
        t2.divergence_risk = 0.99;
        let rec = p.process(t2).unwrap();
        assert!(!rec.mutation_authority_active);
    }

    #[test]
    fn replay_proof_tick_count_matches_cycles() {
        let mut p = GovernancePipeline::new(ch(1), "1.0.0");
        for i in 0..5u64 { p.process(good_tick(i+1, 100+i)).unwrap(); }
        let proof = p.build_replay_proof();
        assert_eq!(proof.tick_count, 5);
    }

    #[test]
    fn replay_proof_terminal_hash_nonzero() {
        let mut p = GovernancePipeline::new(ch(1), "1.0.0");
        p.process(good_tick(1, 100)).unwrap();
        let proof = p.build_replay_proof();
        assert_ne!(proof.terminal_hash, [0u8; 32]);
    }

    #[test]
    fn continuously_coherent_on_all_good_cycles() {
        let mut p = GovernancePipeline::new(ch(1), "1.0.0");
        for i in 0..5u64 { p.process(good_tick(i+1, 100+i)).unwrap(); }
        assert!(p.is_continuously_coherent());
    }

    #[test]
    fn current_drift_class_d0_initially() {
        let p = GovernancePipeline::new(ch(1), "1.0.0");
        assert_eq!(p.current_drift_class(), DriftClass::D0);
    }
}
