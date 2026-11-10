//! Alif: The Primary Causal Axis (Dimension 1)
//!
//! The Alif is the vertical stroke, the backbone of the script,
//! strictly measured in Nuqtas (usually 7 or 9 high).
//! It represents the unyielding vertical axis.
//!
//! Cognitive Translation: The Alif is the Hard Constraint / Invariant.
//! It is the primary objective or physical law that cannot be violated.
//! All other reasoning flows relative to this axis.
//!
//! Operational Rule: If a causal chain deviates from the Alif,
//! the system collapses (immediate termination).

use std::fmt;

/// Alif Constraint Types - Non-negotiable invariants
#[derive(Debug, Clone, PartialEq, Eq)]
pub enum Constraint {
    /// AGPL-3.0 license compliance required
    Agpl3Compliance,
    /// Zero-allocation memory in hot paths
    ZeroAllocationMemory,
    /// BTreeMap for deterministic iteration (no HashMap)
    BTreeMapDeterministic,
    /// No tokio in critical/determinism paths
    NoTokioInCriticalPath,
    /// T0 Genesis Seal verification required
    T0GenesisSealRequired,
    /// Domain isolation enforced (D₀ → D₁ unidirectional)
    DomainIsolationEnforced,
    /// Cryptographic integrity vigil active
    IntegrityVigilActive,
    /// Custom constraint with description
    Custom(&'static str),
}

impl Constraint {
    /// Check if constraint is satisfied by system state
    pub fn check(&self, state: &SystemState) -> bool {
        match self {
            Constraint::Agpl3Compliance => state.license_compliant,
            Constraint::ZeroAllocationMemory => state.zero_allocation_hot_paths,
            Constraint::BTreeMapDeterministic => state.uses_btreemap_only,
            Constraint::NoTokioInCriticalPath => state.no_tokio_critical,
            Constraint::T0GenesisSealRequired => state.genesis_seal_verified,
            Constraint::DomainIsolationEnforced => state.domain_isolation_active,
            Constraint::IntegrityVigilActive => state.integrity_vigil_running,
            Constraint::Custom(_) => true, // Custom constraints handled externally
        }
    }

    /// Get human-readable description
    pub fn description(&self) -> &'static str {
        match self {
            Constraint::Agpl3Compliance => "AGPL-3.0 license compliance required",
            Constraint::ZeroAllocationMemory => "Zero-allocation memory in hot paths",
            Constraint::BTreeMapDeterministic => "BTreeMap for deterministic iteration",
            Constraint::NoTokioInCriticalPath => "No tokio in critical paths",
            Constraint::T0GenesisSealRequired => "T0 Genesis Seal verification required",
            Constraint::DomainIsolationEnforced => "Domain isolation (D₀→D₁ unidirectional)",
            Constraint::IntegrityVigilActive => "Cryptographic integrity vigil active",
            Constraint::Custom(desc) => desc,
        }
    }
}

/// System State for constraint validation
#[derive(Debug, Clone, Default)]
pub struct SystemState {
    pub license_compliant: bool,
    pub zero_allocation_hot_paths: bool,
    pub uses_btreemap_only: bool,
    pub no_tokio_critical: bool,
    pub genesis_seal_verified: bool,
    pub domain_isolation_active: bool,
    pub integrity_vigil_running: bool,
}

/// Constraint Violation Error
#[derive(Debug, Clone)]
pub struct ConstraintViolation {
    pub constraint: Constraint,
    pub message: String,
    pub severity: ViolationSeverity,
}

impl ConstraintViolation {
    pub fn new(constraint: Constraint) -> Self {
        Self {
            constraint,
            message: format!("Constraint violation: {}", constraint.description()),
            severity: ViolationSeverity::Critical,
        }
    }

    pub fn with_message(mut self, message: String) -> Self {
        self.message = message;
        self
    }

    pub fn with_severity(mut self, severity: ViolationSeverity) -> Self {
        self.severity = severity;
        self
    }
}

impl fmt::Display for ConstraintViolation {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        write!(f, "[ALIF VIOLATION] {}: {}", self.severity, self.message)
    }
}

impl std::error::Error for ConstraintViolation {}

/// Violation Severity Levels
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum ViolationSeverity {
    Warning,    // Log but continue
    Error,      // Fail current operation
    Critical,   // Immediate system termination
}

impl fmt::Display for ViolationSeverity {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            ViolationSeverity::Warning => write!(f, "WARNING"),
            ViolationSeverity::Error => write!(f, "ERROR"),
            ViolationSeverity::Critical => write!(f, "CRITICAL"),
        }
    }
}

/// Violation Handler Callback Type
pub type ViolationCallback = Box<dyn Fn(ConstraintViolation) + Send + Sync>;

/// Alif: The Primary Causal Axis
pub struct Alif {
    /// List of active constraints (invariants)
    pub invariants: Vec<Constraint>,
    /// Callback for handling violations
    pub violation_handler: Option<ViolationCallback>,
    /// Violation count (for telemetry)
    pub violation_count: u64,
}

impl Alif {
    /// Create a new Alif with default Sovereign constraints
    pub fn sovereign_default() -> Self {
        Self {
            invariants: vec![
                Constraint::Agpl3Compliance,
                Constraint::BTreeMapDeterministic,
                Constraint::NoTokioInCriticalPath,
                Constraint::T0GenesisSealRequired,
                Constraint::DomainIsolationEnforced,
            ],
            violation_handler: Some(Box::new(|v| {
                eprintln!("{}", v);
                if v.severity == ViolationSeverity::Critical {
                    std::process::exit(1);
                }
            })),
            violation_count: 0,
        }
    }

    /// Create a custom Alif
    pub fn new(invariants: Vec<Constraint>) -> Self {
        Self {
            invariants,
            violation_handler: None,
            violation_count: 0,
        }
    }

    /// Set violation handler callback
    pub fn with_handler(mut self, handler: ViolationCallback) -> Self {
        self.violation_handler = Some(handler);
        self
    }

    /// Validate system state against all constraints (Phase 2 of Khatt Loop)
    pub fn validate(&mut self, state: &SystemState) -> Result<(), ConstraintViolation> {
        for constraint in &self.invariants {
            if !constraint.check(state) {
                let violation = ConstraintViolation::new(constraint.clone())
                    .with_severity(ViolationSeverity::Critical);

                self.violation_count += 1;

                // Invoke handler if present
                if let Some(ref handler) = self.violation_handler {
                    handler(violation.clone());
                }

                return Err(violation);
            }
        }
        Ok(())
    }

    /// Validate with tolerance (non-critical violations logged only)
    pub fn validate_with_tolerance(&mut self, state: &SystemState) -> Vec<ConstraintViolation> {
        let mut violations = Vec::new();

        for constraint in &self.invariants {
            if !constraint.check(state) {
                let violation = ConstraintViolation::new(constraint.clone())
                    .with_severity(ViolationSeverity::Warning);

                self.violation_count += 1;

                if let Some(ref handler) = self.violation_handler {
                    handler(violation.clone());
                }

                violations.push(violation);
            }
        }

        violations
    }

    /// Add a new constraint
    pub fn add_constraint(&mut self, constraint: Constraint) {
        self.invariants.push(constraint);
    }

    /// Remove a constraint
    pub fn remove_constraint(&mut self, constraint: &Constraint) {
        self.invariants.retain(|c| c != constraint);
    }

    /// Get all active constraints
    pub fn constraints(&self) -> &[Constraint] {
        &self.invariants
    }

    /// Check if Alif is upright (all constraints satisfied)
    pub fn is_upright(&self, state: &SystemState) -> bool {
        self.invariants.iter().all(|c| c.check(state))
    }
}

impl Default for Alif {
    fn default() -> Self {
        Self::sovereign_default()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_sovereign_default_alif() {
        let alif = Alif::sovereign_default();
        assert_eq!(alif.invariants.len(), 5);
        assert!(alif.invariants.contains(&Constraint::Agpl3Compliance));
        assert!(alif.invariants.contains(&Constraint::BTreeMapDeterministic));
    }

    #[test]
    fn test_constraint_check() {
        let valid_state = SystemState {
            license_compliant: true,
            zero_allocation_hot_paths: true,
            uses_btreemap_only: true,
            no_tokio_critical: true,
            genesis_seal_verified: true,
            domain_isolation_active: true,
            integrity_vigil_running: true,
        };

        let invalid_state = SystemState {
            license_compliant: false,
            ..Default::default()
        };

        assert!(Constraint::Agpl3Compliance.check(&valid_state));
        assert!(!Constraint::Agpl3Compliance.check(&invalid_state));
    }

    #[test]
    fn test_alif_validation_success() {
        let mut alif = Alif::sovereign_default();
        let state = SystemState {
            license_compliant: true,
            zero_allocation_hot_paths: true,
            uses_btreemap_only: true,
            no_tokio_critical: true,
            genesis_seal_verified: true,
            domain_isolation_active: true,
            integrity_vigil_running: true,
        };

        assert!(alif.validate(&state).is_ok());
        assert_eq!(alif.violation_count, 0);
    }

    #[test]
    fn test_alif_validation_failure() {
        let mut alif = Alif::sovereign_default();
        let state = SystemState {
            license_compliant: false, // Violation!
            zero_allocation_hot_paths: true,
            uses_btreemap_only: true,
            no_tokio_critical: true,
            genesis_seal_verified: true,
            domain_isolation_active: true,
            integrity_vigil_running: true,
        };

        let result = alif.validate(&state);
        assert!(result.is_err());
        assert_eq!(alif.violation_count, 1);

        let violation = result.unwrap_err();
        assert_eq!(violation.constraint, Constraint::Agpl3Compliance);
        assert_eq!(violation.severity, ViolationSeverity::Critical);
    }

    #[test]
    fn test_alif_is_upright() {
        let alif = Alif::sovereign_default();

        let valid_state = SystemState {
            license_compliant: true,
            zero_allocation_hot_paths: true,
            uses_btreemap_only: true,
            no_tokio_critical: true,
            genesis_seal_verified: true,
            domain_isolation_active: true,
            integrity_vigil_running: true,
        };

        let invalid_state = SystemState {
            license_compliant: false,
            ..Default::default()
        };

        assert!(alif.is_upright(&valid_state));
        assert!(!alif.is_upright(&invalid_state));
    }

    #[test]
    fn test_violation_severity_display() {
        assert_eq!(format!("{}", ViolationSeverity::Warning), "WARNING");
        assert_eq!(format!("{}", ViolationSeverity::Error), "ERROR");
        assert_eq!(format!("{}", ViolationSeverity::Critical), "CRITICAL");
    }

    #[test]
    fn test_constraint_description() {
        assert!(Constraint::Agpl3Compliance.description().contains("AGPL"));
        assert!(Constraint::BTreeMapDeterministic.description().contains("BTreeMap"));
        assert!(Constraint::Custom("test").description() == "test");
    }
}
