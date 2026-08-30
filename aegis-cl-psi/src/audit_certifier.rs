//! Gate 253 — Constitutional Audit Certifier: final tamper-evident certificate (T2)
//! EPISTEMIC TIER: T2 (engineering hypothesis)
//!
//! Produces an AuditCertificate over the triple:
//!   (VectorHistory, AlertLog, PlanHistory)
//!
//! AuditCertificate:
//!   epoch_start     — first epoch covered
//!   epoch_end       — last epoch covered
//!   epoch_count     — total epochs certified
//!   vector_terminal — terminal hash from VectorHistory
//!   alert_terminal  — terminal hash from AlertLog
//!   plan_terminal   — terminal hash from PlanHistory
//!   chains_valid    — true iff all three chains verify
//!   peak_condition  — worst OverallCondition across VectorHistory
//!   peak_severity   — worst AlertSeverity across AlertLog
//!   certificate_hash— SHA-256(vector_terminal ‖ alert_terminal ‖ plan_terminal ‖ epoch_end_be8)
//!   is_replay_reconstructable — always true

use sha2::{Sha256, Digest};
use crate::health_aggregator::{VectorHistory, OverallCondition};
use crate::alert_engine::{AlertLog, AlertSeverity};
use crate::intervention_recommender::PlanHistory;

// ─── Audit certificate ────────────────────────────────────────────────────────

#[derive(Debug, Clone, PartialEq)]
pub struct AuditCertificate {
    pub epoch_start:            u64,
    pub epoch_end:              u64,
    pub epoch_count:            usize,
    pub vector_terminal:        [u8; 32],
    pub alert_terminal:         [u8; 32],
    pub plan_terminal:          [u8; 32],
    pub chains_valid:           bool,
    pub peak_condition:         OverallCondition,
    pub peak_severity:          AlertSeverity,
    pub certificate_hash:       [u8; 32],
    pub is_replay_reconstructable: bool,
}

#[derive(Debug)]
pub struct CertifierError(pub &'static str);

// ─── Certify ──────────────────────────────────────────────────────────────────

pub fn certify(
    vectors: &VectorHistory,
    alerts:  &AlertLog,
    plans:   &PlanHistory,
) -> Result<AuditCertificate, CertifierError> {
    if vectors.is_empty() {
        return Err(CertifierError("VectorHistory is empty"));
    }

    let (vec_valid, _) = vectors.verify_chain();
    let (alert_valid, _) = alerts.verify_chain();
    let (plan_valid, _) = plans.verify_chain();
    let chains_valid = vec_valid && alert_valid && plan_valid;

    let epoch_start = vectors.vectors().first().map(|v| v.epoch).unwrap_or(0);
    let epoch_end   = vectors.vectors().last().map(|v| v.epoch).unwrap_or(0);
    let epoch_count = vectors.len();

    let peak_condition = vectors.vectors().iter()
        .map(|v| v.condition)
        .max()
        .unwrap_or(OverallCondition::Optimal);

    let peak_severity = alerts.records().iter()
        .map(|r| r.severity)
        .max()
        .unwrap_or(AlertSeverity::None);

    let vector_terminal = vectors.last_hash();
    let alert_terminal  = alerts.last_hash();
    let plan_terminal   = plans.last_hash();

    let certificate_hash = compute_certificate_hash(
        &vector_terminal, &alert_terminal, &plan_terminal, epoch_end);

    Ok(AuditCertificate {
        epoch_start,
        epoch_end,
        epoch_count,
        vector_terminal,
        alert_terminal,
        plan_terminal,
        chains_valid,
        peak_condition,
        peak_severity,
        certificate_hash,
        is_replay_reconstructable: true,
    })
}

fn compute_certificate_hash(
    vector_terminal: &[u8; 32],
    alert_terminal:  &[u8; 32],
    plan_terminal:   &[u8; 32],
    epoch_end:       u64,
) -> [u8; 32] {
    let mut h = Sha256::new();
    h.update(vector_terminal);
    h.update(alert_terminal);
    h.update(plan_terminal);
    h.update(epoch_end.to_be_bytes());
    h.finalize().into()
}

// ─── Tests ───────────────────────────────────────────────────────────────────

#[cfg(test)]
mod tests {
    use super::*;
    use crate::health_aggregator::{build_vector, VECTOR_GENESIS_HASH};
    use crate::health_dashboard::{build_frame, DASHBOARD_GENESIS_HASH};
    use crate::swarm_health::HealthVerdict;
    use crate::resilience_watchdog::ResilienceVerdict;
    use crate::constitutional_pulse::PulseVerdict;
    use crate::coherence_stability::StabilityGrade;
    use crate::momentum_tracker::MomentumDir;
    use crate::phase_transition::ConstitutionalPhase;

    fn fill_all(n: u64) -> (VectorHistory, AlertLog, PlanHistory) {
        let mut vh = VectorHistory::new();
        let mut al = AlertLog::new();
        let mut ph = PlanHistory::new();

        for i in 1..=n {
            let v = build_vector(i,
                HealthVerdict::Pass, ResilienceVerdict::Stable,
                PulseVerdict::Green, StabilityGrade::A,
                MomentumDir::Stable, ConstitutionalPhase::Nominal,
                &VECTOR_GENESIS_HASH);
            vh.record(i, HealthVerdict::Pass, ResilienceVerdict::Stable,
                      PulseVerdict::Green, StabilityGrade::A,
                      MomentumDir::Stable, ConstitutionalPhase::Nominal).unwrap();

            let frame = build_frame(i, v.clone(), ConstitutionalPhase::Nominal,
                                    MomentumDir::Stable, 0, &DASHBOARD_GENESIS_HASH);
            al.record(&frame).unwrap();

            ph.record(i, AlertSeverity::None, &v).unwrap();
        }
        (vh, al, ph)
    }

    fn fill_with_emergency(n: u64) -> (VectorHistory, AlertLog, PlanHistory) {
        let mut vh = VectorHistory::new();
        let mut al = AlertLog::new();
        let mut ph = PlanHistory::new();

        for i in 1..=n {
            let (health, resilience, pulse, grade, dir, phase) = if i == 2 {
                (HealthVerdict::Fail, ResilienceVerdict::Oscillating,
                 PulseVerdict::Red, StabilityGrade::F,
                 MomentumDir::Declining, ConstitutionalPhase::Critical)
            } else {
                (HealthVerdict::Pass, ResilienceVerdict::Stable,
                 PulseVerdict::Green, StabilityGrade::A,
                 MomentumDir::Stable, ConstitutionalPhase::Nominal)
            };

            let v = build_vector(i, health, resilience, pulse, grade, dir, phase,
                                 &VECTOR_GENESIS_HASH);
            vh.record(i, health, resilience, pulse, grade, dir, phase).unwrap();

            let severity = if i == 2 { AlertSeverity::Emergency } else { AlertSeverity::None };
            let frame = build_frame(i, v.clone(), phase, dir, 0, &DASHBOARD_GENESIS_HASH);
            al.record(&frame).unwrap();

            ph.record(i, severity, &v).unwrap();
        }
        (vh, al, ph)
    }

    // ── certify ───────────────────────────────────────────────────────────────

    #[test]
    fn empty_vectors_is_err() {
        let vh = VectorHistory::new();
        let al = AlertLog::new();
        let ph = PlanHistory::new();
        assert!(certify(&vh, &al, &ph).is_err());
    }

    #[test]
    fn clean_history_gives_chains_valid() {
        let (vh, al, ph) = fill_all(5);
        let cert = certify(&vh, &al, &ph).unwrap();
        assert!(cert.chains_valid);
    }

    #[test]
    fn epoch_span_correct() {
        let (vh, al, ph) = fill_all(5);
        let cert = certify(&vh, &al, &ph).unwrap();
        assert_eq!(cert.epoch_start, 1);
        assert_eq!(cert.epoch_end, 5);
        assert_eq!(cert.epoch_count, 5);
    }

    #[test]
    fn peak_condition_tracks_emergency() {
        let (vh, al, ph) = fill_with_emergency(5);
        let cert = certify(&vh, &al, &ph).unwrap();
        assert_eq!(cert.peak_condition, OverallCondition::Emergency);
    }

    #[test]
    fn peak_severity_tracks_emergency() {
        let (vh, al, ph) = fill_with_emergency(5);
        let cert = certify(&vh, &al, &ph).unwrap();
        assert_eq!(cert.peak_severity, AlertSeverity::Emergency);
    }

    #[test]
    fn peak_condition_nominal_when_all_optimal() {
        let (vh, al, ph) = fill_all(5);
        let cert = certify(&vh, &al, &ph).unwrap();
        assert_eq!(cert.peak_condition, OverallCondition::Optimal);
    }

    #[test]
    fn certificate_hash_nonzero() {
        let (vh, al, ph) = fill_all(3);
        let cert = certify(&vh, &al, &ph).unwrap();
        assert_ne!(cert.certificate_hash, [0u8; 32]);
    }

    #[test]
    fn certificate_hash_deterministic() {
        let (vh1, al1, ph1) = fill_all(4);
        let (vh2, al2, ph2) = fill_all(4);
        let (vh3, al3, ph3) = fill_all(4);
        let c1 = certify(&vh1, &al1, &ph1).unwrap();
        let c2 = certify(&vh2, &al2, &ph2).unwrap();
        let c3 = certify(&vh3, &al3, &ph3).unwrap();
        assert_eq!(c1.certificate_hash, c2.certificate_hash);
        assert_eq!(c2.certificate_hash, c3.certificate_hash);
    }

    #[test]
    fn different_histories_different_hash() {
        let (vh1, al1, ph1) = fill_all(3);
        let (vh2, al2, ph2) = fill_with_emergency(3);
        let c1 = certify(&vh1, &al1, &ph1).unwrap();
        let c2 = certify(&vh2, &al2, &ph2).unwrap();
        assert_ne!(c1.certificate_hash, c2.certificate_hash);
    }

    #[test]
    fn is_replay_reconstructable_true() {
        let (vh, al, ph) = fill_all(2);
        let cert = certify(&vh, &al, &ph).unwrap();
        assert!(cert.is_replay_reconstructable);
    }

    #[test]
    fn terminal_hashes_match_individual_histories() {
        let (vh, al, ph) = fill_all(4);
        let cert = certify(&vh, &al, &ph).unwrap();
        assert_eq!(cert.vector_terminal, vh.last_hash());
        assert_eq!(cert.alert_terminal, al.last_hash());
        assert_eq!(cert.plan_terminal, ph.last_hash());
    }

    #[test]
    fn alert_log_empty_still_certifies() {
        let (vh, _al, ph) = fill_all(3);
        let empty_al = AlertLog::new();
        // Empty alert log — chains_valid includes its (trivially valid) chain
        let cert = certify(&vh, &empty_al, &ph).unwrap();
        assert!(cert.chains_valid);
        assert_eq!(cert.peak_severity, AlertSeverity::None);
    }
}
