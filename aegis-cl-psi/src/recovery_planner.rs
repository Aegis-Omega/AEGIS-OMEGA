//! Gate 265 — Recovery Planner: ranked recovery action sequences for degraded mesh (T2)
//! EPISTEMIC TIER: T2 (engineering hypothesis)
//!
//! Analyses CensusRecord + FaultReport to produce a ranked RecoveryPlan.
//! Each plan is a sequence of RecoveryAction items in priority order.
//!
//! RecoveryAction:
//!   kind           — RecoveryActionKind (enum)
//!   priority       — u8 (0 = highest, 255 = lowest)
//!   target_node_id — Option<u32> (Some if action targets a specific node)
//!   rationale      — &'static str
//!
//! RecoveryPlan:
//!   epoch          — u64
//!   fault_class    — FaultClass
//!   actions        — Vec<RecoveryAction> sorted by priority
//!   plan_hash      — SHA-256(epoch_be8 ‖ fault_class_byte ‖ action_count_be8 ‖ prev_hash)
//!   prev_hash      — [u8; 32]
//!
//! PlanLog: hash-chained RecoveryPlans; plan_count(), latest_plan().

use sha2::{Sha256, Digest};
use crate::fault_detector::FaultClass;
use crate::mesh_census::CensusRecord;

// ─── Recovery action kind ─────────────────────────────────────────────────────

#[derive(Debug, Clone, Copy, PartialEq, Eq, PartialOrd, Ord)]
pub enum RecoveryActionKind {
    MonitorOnly          = 0,
    IsolateNode          = 1,
    RestartNode          = 2,
    ReduceLoad           = 3,
    ActivateSpare        = 4,
    PartialQuorumMode    = 5,
    HaltAndReform        = 6,
}

impl RecoveryActionKind {
    pub fn as_u8(self) -> u8 { self as u8 }

    pub fn as_str(self) -> &'static str {
        match self {
            Self::MonitorOnly       => "monitor_only",
            Self::IsolateNode       => "isolate_node",
            Self::RestartNode       => "restart_node",
            Self::ReduceLoad        => "reduce_load",
            Self::ActivateSpare     => "activate_spare",
            Self::PartialQuorumMode => "partial_quorum_mode",
            Self::HaltAndReform     => "halt_and_reform",
        }
    }

    /// True if the action suspends mesh operations (irrecoverable without manual intervention).
    pub fn is_disruptive(self) -> bool {
        matches!(self, Self::PartialQuorumMode | Self::HaltAndReform)
    }
}

// ─── Recovery action ──────────────────────────────────────────────────────────

#[derive(Debug, Clone, PartialEq)]
pub struct RecoveryAction {
    pub kind:           RecoveryActionKind,
    pub priority:       u8,    // 0 = highest urgency
    pub target_node_id: Option<u32>,
    pub rationale:      &'static str,
}

impl RecoveryAction {
    pub fn is_node_specific(&self) -> bool { self.target_node_id.is_some() }
}

// ─── Recovery plan ────────────────────────────────────────────────────────────

#[derive(Debug, Clone, PartialEq)]
pub struct RecoveryPlan {
    pub epoch:        u64,
    pub fault_class:  FaultClass,
    pub actions:      Vec<RecoveryAction>,
    pub plan_hash:    [u8; 32],
    pub prev_hash:    [u8; 32],
}

impl RecoveryPlan {
    pub fn action_count(&self) -> usize { self.actions.len() }

    /// True if any action is disruptive.
    pub fn requires_disruption(&self) -> bool {
        self.actions.iter().any(|a| a.kind.is_disruptive())
    }

    /// Highest-urgency action (lowest priority number), or None if empty.
    pub fn top_action(&self) -> Option<&RecoveryAction> { self.actions.first() }
}

pub const PLAN_GENESIS_HASH: [u8; 32] = [0u8; 32];

fn compute_plan_hash(
    epoch:        u64,
    fault_class:  FaultClass,
    action_count: usize,
    prev:         &[u8; 32],
) -> [u8; 32] {
    let mut h = Sha256::new();
    h.update(prev);
    h.update(epoch.to_be_bytes());
    h.update([fault_class.as_u8()]);
    h.update((action_count as u64).to_be_bytes());
    h.finalize().into()
}

// ─── Planning logic ───────────────────────────────────────────────────────────

/// Derive a ranked RecoveryPlan from census + fault classification.
pub fn build_plan(
    epoch:       u64,
    census:      &CensusRecord,
    fault_class: FaultClass,
    degraded_nodes: &[u32],
    prev_hash:   &[u8; 32],
) -> RecoveryPlan {
    let mut actions: Vec<RecoveryAction> = Vec::new();

    match fault_class {
        FaultClass::None => {
            actions.push(RecoveryAction {
                kind:           RecoveryActionKind::MonitorOnly,
                priority:       200,
                target_node_id: None,
                rationale:      "no fault detected",
            });
        }
        FaultClass::Isolated => {
            // Single degraded node — restart it first.
            let target = degraded_nodes.first().copied();
            actions.push(RecoveryAction {
                kind:           RecoveryActionKind::RestartNode,
                priority:       10,
                target_node_id: target,
                rationale:      "isolated fault — restart degraded node",
            });
            actions.push(RecoveryAction {
                kind:           RecoveryActionKind::MonitorOnly,
                priority:       100,
                target_node_id: None,
                rationale:      "monitor mesh health after restart",
            });
        }
        FaultClass::Correlated => {
            // Multiple nodes degraded simultaneously — isolate then activate spare.
            for &n in degraded_nodes {
                actions.push(RecoveryAction {
                    kind:           RecoveryActionKind::IsolateNode,
                    priority:       20,
                    target_node_id: Some(n),
                    rationale:      "correlated fault — isolate degraded node",
                });
            }
            actions.push(RecoveryAction {
                kind:           RecoveryActionKind::ActivateSpare,
                priority:       30,
                target_node_id: None,
                rationale:      "replace isolated nodes with spare",
            });
            actions.push(RecoveryAction {
                kind:           RecoveryActionKind::ReduceLoad,
                priority:       40,
                target_node_id: None,
                rationale:      "reduce gossip load during recovery",
            });
        }
        FaultClass::Cascading => {
            // Cascading failure — partial quorum mode if health_ratio still permits.
            if census.mesh_healthy() {
                actions.push(RecoveryAction {
                    kind:           RecoveryActionKind::PartialQuorumMode,
                    priority:       5,
                    target_node_id: None,
                    rationale:      "cascading fault — operate at reduced quorum",
                });
                for &n in degraded_nodes {
                    actions.push(RecoveryAction {
                        kind:           RecoveryActionKind::IsolateNode,
                        priority:       15,
                        target_node_id: Some(n),
                        rationale:      "isolate cascading fault source",
                    });
                }
                actions.push(RecoveryAction {
                    kind:           RecoveryActionKind::ActivateSpare,
                    priority:       25,
                    target_node_id: None,
                    rationale:      "activate spare to restore quorum",
                });
            } else {
                // Below 1/φ — halt and reform.
                actions.push(RecoveryAction {
                    kind:           RecoveryActionKind::HaltAndReform,
                    priority:       0,
                    target_node_id: None,
                    rationale:      "mesh below phi threshold — halt and reform",
                });
            }
        }
    }

    // Sort by priority (ascending = highest urgency first).
    actions.sort_by_key(|a| (a.priority, a.kind as u8));

    let plan_hash = compute_plan_hash(epoch, fault_class, actions.len(), prev_hash);

    RecoveryPlan {
        epoch,
        fault_class,
        actions,
        plan_hash,
        prev_hash: *prev_hash,
    }
}

// ─── Plan log ─────────────────────────────────────────────────────────────────

#[derive(Debug, Clone)]
pub struct PlanLog {
    plans: Vec<RecoveryPlan>,
}

#[derive(Debug)]
pub enum PlanLogError {
    StaleEpoch,
}

impl PlanLogError {
    pub fn as_str(&self) -> &'static str { "stale epoch" }
}

impl PlanLog {
    pub fn new() -> Self { Self { plans: Vec::new() } }

    pub fn len(&self) -> usize { self.plans.len() }
    pub fn is_empty(&self) -> bool { self.plans.is_empty() }
    pub fn plans(&self) -> &[RecoveryPlan] { &self.plans }
    pub fn latest(&self) -> Option<&RecoveryPlan> { self.plans.last() }

    pub fn last_hash(&self) -> [u8; 32] {
        self.plans.last().map(|p| p.plan_hash).unwrap_or(PLAN_GENESIS_HASH)
    }

    pub fn record(
        &mut self,
        epoch:          u64,
        census:         &CensusRecord,
        fault_class:    FaultClass,
        degraded_nodes: &[u32],
    ) -> Result<&RecoveryPlan, PlanLogError> {
        if let Some(last) = self.plans.last() {
            if epoch <= last.epoch {
                return Err(PlanLogError::StaleEpoch);
            }
        }
        let prev_hash = self.last_hash();
        let plan = build_plan(epoch, census, fault_class, degraded_nodes, &prev_hash);
        self.plans.push(plan);
        Ok(self.plans.last().unwrap())
    }

    pub fn disruptive_count(&self) -> usize {
        self.plans.iter().filter(|p| p.requires_disruption()).count()
    }

    pub fn verify_chain(&self) -> (bool, Option<usize>) {
        let mut expected_prev = PLAN_GENESIS_HASH;
        for (i, plan) in self.plans.iter().enumerate() {
            if plan.prev_hash != expected_prev {
                return (false, Some(i));
            }
            let recomputed = compute_plan_hash(
                plan.epoch, plan.fault_class, plan.action_count(), &plan.prev_hash);
            if recomputed != plan.plan_hash {
                return (false, Some(i));
            }
            expected_prev = plan.plan_hash;
        }
        (true, None)
    }
}

impl Default for PlanLog {
    fn default() -> Self { Self::new() }
}

// ─── Tests ───────────────────────────────────────────────────────────────────

#[cfg(test)]
mod tests {
    use super::*;
    use crate::fault_detector::FaultClass;
    use crate::mesh_census::{CensusRecord, CENSUS_GENESIS_HASH, take_census};
    use crate::node_state_machine::{NodeHistory, NodeState};
    use crate::peer_manifest::{PeerRegistry, build_manifest, cap};
    use crate::phase_transition::ConstitutionalPhase;

    fn active_history(id: u32) -> NodeHistory {
        let mut h = NodeHistory::new(id);
        h.transition(NodeState::Active, 1, "boot").unwrap();
        h
    }

    fn degraded_history(id: u32) -> NodeHistory {
        let mut h = NodeHistory::new(id);
        h.transition(NodeState::Active, 1, "boot").unwrap();
        h.transition(NodeState::Degraded, 2, "fault").unwrap();
        h
    }

    fn full_registry(n: u32) -> PeerRegistry {
        let mut r = PeerRegistry::new();
        for i in 0..n {
            r.register(build_manifest(i, 1, cap::ALL, ConstitutionalPhase::Nominal)).unwrap();
        }
        r
    }

    fn healthy_census(n: u32) -> CensusRecord {
        let histories: Vec<NodeHistory> = (0..n).map(|i| active_history(i)).collect();
        let refs: Vec<&NodeHistory> = histories.iter().collect();
        let r = full_registry(n);
        take_census(1, &refs, &r, &CENSUS_GENESIS_HASH)
    }

    fn unhealthy_census() -> CensusRecord {
        // 1 active out of 8 — well below 1/φ
        let histories: Vec<NodeHistory> = (0..8).map(|i| {
            if i == 0 { active_history(i) } else { degraded_history(i) }
        }).collect();
        let refs: Vec<&NodeHistory> = histories.iter().collect();
        let r = full_registry(8);
        take_census(1, &refs, &r, &CENSUS_GENESIS_HASH)
    }

    // ── RecoveryActionKind ────────────────────────────────────────────────────

    #[test]
    fn action_kind_as_str() {
        assert_eq!(RecoveryActionKind::MonitorOnly.as_str(),       "monitor_only");
        assert_eq!(RecoveryActionKind::IsolateNode.as_str(),       "isolate_node");
        assert_eq!(RecoveryActionKind::RestartNode.as_str(),       "restart_node");
        assert_eq!(RecoveryActionKind::ReduceLoad.as_str(),        "reduce_load");
        assert_eq!(RecoveryActionKind::ActivateSpare.as_str(),     "activate_spare");
        assert_eq!(RecoveryActionKind::PartialQuorumMode.as_str(), "partial_quorum_mode");
        assert_eq!(RecoveryActionKind::HaltAndReform.as_str(),     "halt_and_reform");
    }

    #[test]
    fn disruptive_kinds() {
        assert!(!RecoveryActionKind::MonitorOnly.is_disruptive());
        assert!(!RecoveryActionKind::RestartNode.is_disruptive());
        assert!(RecoveryActionKind::PartialQuorumMode.is_disruptive());
        assert!(RecoveryActionKind::HaltAndReform.is_disruptive());
    }

    // ── build_plan — FaultClass::None ─────────────────────────────────────────

    #[test]
    fn none_fault_monitor_only() {
        let c = healthy_census(4);
        let p = build_plan(1, &c, FaultClass::None, &[], &PLAN_GENESIS_HASH);
        assert_eq!(p.action_count(), 1);
        assert_eq!(p.top_action().unwrap().kind, RecoveryActionKind::MonitorOnly);
        assert!(!p.requires_disruption());
    }

    // ── build_plan — FaultClass::Isolated ────────────────────────────────────

    #[test]
    fn isolated_fault_restart() {
        let c = healthy_census(4);
        let p = build_plan(1, &c, FaultClass::Isolated, &[2], &PLAN_GENESIS_HASH);
        assert_eq!(p.top_action().unwrap().kind, RecoveryActionKind::RestartNode);
        assert_eq!(p.top_action().unwrap().target_node_id, Some(2));
        assert!(!p.requires_disruption());
    }

    #[test]
    fn isolated_fault_two_actions() {
        let c = healthy_census(4);
        let p = build_plan(1, &c, FaultClass::Isolated, &[1], &PLAN_GENESIS_HASH);
        assert_eq!(p.action_count(), 2); // restart + monitor
    }

    // ── build_plan — FaultClass::Correlated ──────────────────────────────────

    #[test]
    fn correlated_isolates_all_degraded() {
        let c = healthy_census(6);
        let p = build_plan(1, &c, FaultClass::Correlated, &[1, 2, 3], &PLAN_GENESIS_HASH);
        let isolate_count = p.actions.iter().filter(|a| a.kind == RecoveryActionKind::IsolateNode).count();
        assert_eq!(isolate_count, 3);
    }

    #[test]
    fn correlated_includes_activate_spare() {
        let c = healthy_census(6);
        let p = build_plan(1, &c, FaultClass::Correlated, &[1, 2], &PLAN_GENESIS_HASH);
        assert!(p.actions.iter().any(|a| a.kind == RecoveryActionKind::ActivateSpare));
    }

    #[test]
    fn correlated_includes_reduce_load() {
        let c = healthy_census(6);
        let p = build_plan(1, &c, FaultClass::Correlated, &[1, 2], &PLAN_GENESIS_HASH);
        assert!(p.actions.iter().any(|a| a.kind == RecoveryActionKind::ReduceLoad));
    }

    // ── build_plan — FaultClass::Cascading ───────────────────────────────────

    #[test]
    fn cascading_healthy_mesh_partial_quorum() {
        // 6 active out of 8 → healthy (75% > 61.8%)
        let histories: Vec<NodeHistory> = (0..8).map(|i| {
            if i < 6 { active_history(i) } else { degraded_history(i) }
        }).collect();
        let refs: Vec<&NodeHistory> = histories.iter().collect();
        let r = full_registry(8);
        let c = take_census(1, &refs, &r, &CENSUS_GENESIS_HASH);
        let p = build_plan(1, &c, FaultClass::Cascading, &[6, 7], &PLAN_GENESIS_HASH);
        assert!(p.actions.iter().any(|a| a.kind == RecoveryActionKind::PartialQuorumMode));
        assert!(p.requires_disruption());
    }

    #[test]
    fn cascading_unhealthy_mesh_halt_and_reform() {
        let c = unhealthy_census(); // 1 of 8 — well below 1/φ
        let p = build_plan(1, &c, FaultClass::Cascading, &[1,2,3,4,5,6,7], &PLAN_GENESIS_HASH);
        assert_eq!(p.top_action().unwrap().kind, RecoveryActionKind::HaltAndReform);
        assert_eq!(p.top_action().unwrap().priority, 0); // highest urgency
    }

    // ── actions sorted by priority ────────────────────────────────────────────

    #[test]
    fn actions_sorted_ascending_priority() {
        let c = healthy_census(6);
        let p = build_plan(1, &c, FaultClass::Correlated, &[1, 2], &PLAN_GENESIS_HASH);
        let priorities: Vec<u8> = p.actions.iter().map(|a| a.priority).collect();
        let mut sorted = priorities.clone();
        sorted.sort();
        assert_eq!(priorities, sorted);
    }

    // ── plan_hash ─────────────────────────────────────────────────────────────

    #[test]
    fn plan_hash_nonzero() {
        let c = healthy_census(4);
        let p = build_plan(1, &c, FaultClass::None, &[], &PLAN_GENESIS_HASH);
        assert_ne!(p.plan_hash, [0u8; 32]);
    }

    #[test]
    fn plan_hash_deterministic() {
        let c = healthy_census(4);
        let p1 = build_plan(1, &c, FaultClass::None, &[], &PLAN_GENESIS_HASH);
        let p2 = build_plan(1, &c, FaultClass::None, &[], &PLAN_GENESIS_HASH);
        assert_eq!(p1.plan_hash, p2.plan_hash);
    }

    // ── PlanLog ───────────────────────────────────────────────────────────────

    #[test]
    fn new_log_empty() {
        let l = PlanLog::new();
        assert!(l.is_empty());
        assert_eq!(l.last_hash(), PLAN_GENESIS_HASH);
    }

    #[test]
    fn log_record_appends() {
        let mut l = PlanLog::new();
        let c = healthy_census(4);
        l.record(1, &c, FaultClass::None, &[]).unwrap();
        l.record(2, &c, FaultClass::None, &[]).unwrap();
        assert_eq!(l.len(), 2);
    }

    #[test]
    fn stale_epoch_rejected() {
        let mut l = PlanLog::new();
        let c = healthy_census(4);
        l.record(5, &c, FaultClass::None, &[]).unwrap();
        assert!(matches!(l.record(5, &c, FaultClass::None, &[]), Err(PlanLogError::StaleEpoch)));
        assert!(matches!(l.record(4, &c, FaultClass::None, &[]), Err(PlanLogError::StaleEpoch)));
    }

    #[test]
    fn disruptive_count_tracked() {
        let mut l = PlanLog::new();
        let c = healthy_census(4);
        let c_unhealthy = unhealthy_census();
        l.record(1, &c, FaultClass::None, &[]).unwrap();
        l.record(2, &c_unhealthy, FaultClass::Cascading, &[1,2,3,4,5,6,7]).unwrap();
        assert_eq!(l.disruptive_count(), 1);
    }

    #[test]
    fn verify_chain_valid() {
        let mut l = PlanLog::new();
        let c = healthy_census(4);
        for e in 1..=4u64 {
            l.record(e, &c, FaultClass::None, &[]).unwrap();
        }
        let (valid, broken) = l.verify_chain();
        assert!(valid);
        assert!(broken.is_none());
    }
}
