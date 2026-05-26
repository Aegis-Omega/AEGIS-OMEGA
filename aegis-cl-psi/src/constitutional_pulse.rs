//! Gate 240 — Constitutional Pulse: compact 3-byte epoch health signal (T2)
//! EPISTEMIC TIER: T2 (engineering hypothesis)
//!
//! Combines HealthVerdict + ResilienceVerdict + DivergenceClass into a single
//! [health_byte, resilience_byte, divergence_byte] pulse that can be broadcast
//! cheaply over gossip channels.
//!
//! PulseVerdict — derived from the triad:
//!   Green   — health=Pass, resilience=Recovering|Stable, divergence≤Nominal
//!   Yellow  — health=Warn OR resilience non-intervention OR divergence=Elevated
//!   Red     — health=Fail OR resilience requires intervention OR divergence≥Critical
//!
//! pulse_hash = SHA-256(prev_hash ‖ pulse_bytes[3] ‖ epoch_be8)
//! PulseChain enforces epoch monotonicity.

use sha2::{Sha256, Digest};
use crate::swarm_health::HealthVerdict;
use crate::resilience_watchdog::ResilienceVerdict;
use crate::divergence_oracle::DivergenceClass;

// ─── Pulse verdict ───────────────────────────────────────────────────────────

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum PulseVerdict {
    Green  = 0,
    Yellow = 1,
    Red    = 2,
}

impl PulseVerdict {
    pub fn as_u8(self) -> u8 { self as u8 }

    pub fn as_str(self) -> &'static str {
        match self {
            Self::Green  => "green",
            Self::Yellow => "yellow",
            Self::Red    => "red",
        }
    }

    pub fn is_nominal(self) -> bool { self == PulseVerdict::Green }
    pub fn is_alert(self) -> bool   { self == PulseVerdict::Red   }
}

// ─── Pulse ───────────────────────────────────────────────────────────────────

#[derive(Debug, Clone, PartialEq)]
pub struct ConstitutionalPulse {
    pub epoch:             u64,
    pub health_verdict:    HealthVerdict,
    pub resilience_verdict:ResilienceVerdict,
    pub divergence_class:  DivergenceClass,
    pub pulse_verdict:     PulseVerdict,
    /// [health_byte, resilience_byte, divergence_byte]
    pub pulse_bytes:       [u8; 3],
    pub pulse_hash:        [u8; 32],
    pub prev_pulse_hash:   [u8; 32],
}

pub const PULSE_GENESIS_HASH: [u8; 32] = [0u8; 32];

/// Build a ConstitutionalPulse from the three constitutional signals.
pub fn build_pulse(
    epoch:              u64,
    health:             HealthVerdict,
    resilience:         ResilienceVerdict,
    divergence:         DivergenceClass,
    prev_hash:          &[u8; 32],
) -> ConstitutionalPulse {
    let pulse_bytes = [health.as_u8(), resilience.as_u8(), divergence.as_u8()];
    let pulse_verdict = derive_verdict(health, resilience, divergence);
    let pulse_hash = compute_pulse_hash(prev_hash, &pulse_bytes, epoch);

    ConstitutionalPulse {
        epoch,
        health_verdict: health,
        resilience_verdict: resilience,
        divergence_class: divergence,
        pulse_verdict,
        pulse_bytes,
        pulse_hash,
        prev_pulse_hash: *prev_hash,
    }
}

fn derive_verdict(h: HealthVerdict, r: ResilienceVerdict, d: DivergenceClass) -> PulseVerdict {
    // Red: any critical signal
    if h == HealthVerdict::Fail || r.requires_intervention() || d.as_u8() >= DivergenceClass::Critical.as_u8() {
        return PulseVerdict::Red;
    }
    // Yellow: any non-optimal signal
    if h == HealthVerdict::Warn || !r.is_healthy() || d.as_u8() >= DivergenceClass::Elevated.as_u8() {
        return PulseVerdict::Yellow;
    }
    PulseVerdict::Green
}

fn compute_pulse_hash(prev: &[u8; 32], pulse_bytes: &[u8; 3], epoch: u64) -> [u8; 32] {
    let mut h = Sha256::new();
    h.update(prev);
    h.update(pulse_bytes);
    h.update(epoch.to_be_bytes());
    h.finalize().into()
}

// ─── Pulse chain ─────────────────────────────────────────────────────────────

#[derive(Debug, Clone)]
pub struct PulseChain {
    pulses: Vec<ConstitutionalPulse>,
}

#[derive(Debug)]
pub struct PulseError(pub &'static str);

impl PulseChain {
    pub fn new() -> Self { Self { pulses: Vec::new() } }

    pub fn len(&self) -> usize { self.pulses.len() }
    pub fn is_empty(&self) -> bool { self.pulses.is_empty() }
    pub fn pulses(&self) -> &[ConstitutionalPulse] { &self.pulses }

    pub fn last_hash(&self) -> [u8; 32] {
        self.pulses.last().map(|p| p.pulse_hash).unwrap_or(PULSE_GENESIS_HASH)
    }

    pub fn current_verdict(&self) -> PulseVerdict {
        self.pulses.last().map(|p| p.pulse_verdict).unwrap_or(PulseVerdict::Yellow)
    }

    /// Count of consecutive Green pulses at tail of chain.
    pub fn green_streak(&self) -> usize {
        self.pulses.iter().rev().take_while(|p| p.pulse_verdict == PulseVerdict::Green).count()
    }

    /// Count of Red pulses across all epochs.
    pub fn red_count(&self) -> usize {
        self.pulses.iter().filter(|p| p.pulse_verdict == PulseVerdict::Red).count()
    }

    /// Append a new pulse. Epoch must be strictly greater than last.
    pub fn push(
        &mut self,
        epoch:      u64,
        health:     HealthVerdict,
        resilience: ResilienceVerdict,
        divergence: DivergenceClass,
    ) -> Result<&ConstitutionalPulse, PulseError> {
        if let Some(last) = self.pulses.last() {
            if epoch <= last.epoch {
                return Err(PulseError("epoch must be strictly greater than last epoch"));
            }
        }
        let prev_hash = self.last_hash();
        let pulse = build_pulse(epoch, health, resilience, divergence, &prev_hash);
        self.pulses.push(pulse);
        Ok(self.pulses.last().unwrap())
    }

    /// Verify full chain integrity.
    pub fn verify_chain(&self) -> (bool, Option<usize>) {
        let mut prev = PULSE_GENESIS_HASH;
        for (i, p) in self.pulses.iter().enumerate() {
            if p.prev_pulse_hash != prev {
                return (false, Some(i));
            }
            let expected = compute_pulse_hash(&prev, &p.pulse_bytes, p.epoch);
            if expected != p.pulse_hash {
                return (false, Some(i));
            }
            prev = p.pulse_hash;
        }
        (true, None)
    }
}

impl Default for PulseChain {
    fn default() -> Self { Self::new() }
}

// ─── Tests ───────────────────────────────────────────────────────────────────

#[cfg(test)]
mod tests {
    use super::*;

    fn green_pulse(epoch: u64, prev: &[u8; 32]) -> ConstitutionalPulse {
        build_pulse(epoch, HealthVerdict::Pass, ResilienceVerdict::Stable,
                    DivergenceClass::Stable, prev)
    }

    // ── PulseVerdict ──────────────────────────────────────────────────────────

    #[test]
    fn green_is_nominal() {
        assert!(PulseVerdict::Green.is_nominal());
        assert!(!PulseVerdict::Green.is_alert());
    }

    #[test]
    fn red_is_alert() {
        assert!(PulseVerdict::Red.is_alert());
        assert!(!PulseVerdict::Red.is_nominal());
    }

    #[test]
    fn yellow_neither_nominal_nor_alert() {
        assert!(!PulseVerdict::Yellow.is_nominal());
        assert!(!PulseVerdict::Yellow.is_alert());
    }

    #[test]
    fn verdict_as_u8() {
        assert_eq!(PulseVerdict::Green.as_u8(), 0);
        assert_eq!(PulseVerdict::Yellow.as_u8(), 1);
        assert_eq!(PulseVerdict::Red.as_u8(), 2);
    }

    // ── derive_verdict ────────────────────────────────────────────────────────

    #[test]
    fn all_optimal_gives_green() {
        let p = build_pulse(1, HealthVerdict::Pass, ResilienceVerdict::Stable,
                            DivergenceClass::Stable, &PULSE_GENESIS_HASH);
        assert_eq!(p.pulse_verdict, PulseVerdict::Green);
    }

    #[test]
    fn health_fail_gives_red() {
        let p = build_pulse(1, HealthVerdict::Fail, ResilienceVerdict::Stable,
                            DivergenceClass::Stable, &PULSE_GENESIS_HASH);
        assert_eq!(p.pulse_verdict, PulseVerdict::Red);
    }

    #[test]
    fn resilience_oscillating_gives_red() {
        let p = build_pulse(1, HealthVerdict::Pass, ResilienceVerdict::Oscillating,
                            DivergenceClass::Stable, &PULSE_GENESIS_HASH);
        assert_eq!(p.pulse_verdict, PulseVerdict::Red);
    }

    #[test]
    fn divergence_critical_gives_red() {
        let p = build_pulse(1, HealthVerdict::Pass, ResilienceVerdict::Stable,
                            DivergenceClass::Critical, &PULSE_GENESIS_HASH);
        assert_eq!(p.pulse_verdict, PulseVerdict::Red);
    }

    #[test]
    fn health_warn_gives_yellow() {
        let p = build_pulse(1, HealthVerdict::Warn, ResilienceVerdict::Stable,
                            DivergenceClass::Stable, &PULSE_GENESIS_HASH);
        assert_eq!(p.pulse_verdict, PulseVerdict::Yellow);
    }

    #[test]
    fn divergence_elevated_gives_yellow() {
        let p = build_pulse(1, HealthVerdict::Pass, ResilienceVerdict::Stable,
                            DivergenceClass::Elevated, &PULSE_GENESIS_HASH);
        assert_eq!(p.pulse_verdict, PulseVerdict::Yellow);
    }

    #[test]
    fn insufficient_resilience_gives_yellow() {
        let p = build_pulse(1, HealthVerdict::Pass, ResilienceVerdict::Insufficient,
                            DivergenceClass::Stable, &PULSE_GENESIS_HASH);
        assert_eq!(p.pulse_verdict, PulseVerdict::Yellow);
    }

    // ── pulse_bytes ───────────────────────────────────────────────────────────

    #[test]
    fn pulse_bytes_encode_triad() {
        let p = build_pulse(1, HealthVerdict::Warn, ResilienceVerdict::Degrading,
                            DivergenceClass::Elevated, &PULSE_GENESIS_HASH);
        assert_eq!(p.pulse_bytes[0], HealthVerdict::Warn.as_u8());
        assert_eq!(p.pulse_bytes[1], ResilienceVerdict::Degrading.as_u8());
        assert_eq!(p.pulse_bytes[2], DivergenceClass::Elevated.as_u8());
    }

    // ── pulse_hash ────────────────────────────────────────────────────────────

    #[test]
    fn pulse_hash_nonzero() {
        let p = green_pulse(1, &PULSE_GENESIS_HASH);
        assert_ne!(p.pulse_hash, [0u8; 32]);
    }

    #[test]
    fn pulse_hash_deterministic() {
        let p1 = green_pulse(42, &PULSE_GENESIS_HASH);
        let p2 = green_pulse(42, &PULSE_GENESIS_HASH);
        let p3 = green_pulse(42, &PULSE_GENESIS_HASH);
        assert_eq!(p1.pulse_hash, p2.pulse_hash);
        assert_eq!(p2.pulse_hash, p3.pulse_hash);
    }

    #[test]
    fn different_epochs_different_hash() {
        let p1 = green_pulse(1, &PULSE_GENESIS_HASH);
        let p2 = green_pulse(2, &PULSE_GENESIS_HASH);
        assert_ne!(p1.pulse_hash, p2.pulse_hash);
    }

    // ── PulseChain ────────────────────────────────────────────────────────────

    #[test]
    fn new_chain_empty() {
        let c = PulseChain::new();
        assert!(c.is_empty());
        assert_eq!(c.green_streak(), 0);
        assert_eq!(c.red_count(), 0);
    }

    #[test]
    fn push_grows_chain() {
        let mut c = PulseChain::new();
        c.push(1, HealthVerdict::Pass, ResilienceVerdict::Stable, DivergenceClass::Stable).unwrap();
        c.push(2, HealthVerdict::Pass, ResilienceVerdict::Stable, DivergenceClass::Stable).unwrap();
        assert_eq!(c.len(), 2);
    }

    #[test]
    fn duplicate_epoch_is_err() {
        let mut c = PulseChain::new();
        c.push(5, HealthVerdict::Pass, ResilienceVerdict::Stable, DivergenceClass::Stable).unwrap();
        assert!(c.push(5, HealthVerdict::Pass, ResilienceVerdict::Stable, DivergenceClass::Stable).is_err());
    }

    #[test]
    fn green_streak_counts_correctly() {
        let mut c = PulseChain::new();
        c.push(1, HealthVerdict::Fail, ResilienceVerdict::Stable, DivergenceClass::Stable).unwrap();
        c.push(2, HealthVerdict::Pass, ResilienceVerdict::Stable, DivergenceClass::Stable).unwrap();
        c.push(3, HealthVerdict::Pass, ResilienceVerdict::Stable, DivergenceClass::Stable).unwrap();
        c.push(4, HealthVerdict::Pass, ResilienceVerdict::Stable, DivergenceClass::Stable).unwrap();
        assert_eq!(c.green_streak(), 3);
    }

    #[test]
    fn red_count_tracks_correctly() {
        let mut c = PulseChain::new();
        c.push(1, HealthVerdict::Fail, ResilienceVerdict::Stable, DivergenceClass::Stable).unwrap();
        c.push(2, HealthVerdict::Pass, ResilienceVerdict::Stable, DivergenceClass::Stable).unwrap();
        c.push(3, HealthVerdict::Fail, ResilienceVerdict::Stable, DivergenceClass::Stable).unwrap();
        assert_eq!(c.red_count(), 2);
    }

    #[test]
    fn hash_chain_links() {
        let mut c = PulseChain::new();
        c.push(1, HealthVerdict::Pass, ResilienceVerdict::Stable, DivergenceClass::Stable).unwrap();
        c.push(2, HealthVerdict::Pass, ResilienceVerdict::Stable, DivergenceClass::Stable).unwrap();
        assert_eq!(c.pulses()[1].prev_pulse_hash, c.pulses()[0].pulse_hash);
    }

    #[test]
    fn verify_chain_clean() {
        let mut c = PulseChain::new();
        for i in 1u64..=6 {
            c.push(i, HealthVerdict::Pass, ResilienceVerdict::Stable, DivergenceClass::Stable).unwrap();
        }
        let (valid, broken) = c.verify_chain();
        assert!(valid);
        assert!(broken.is_none());
    }
}
