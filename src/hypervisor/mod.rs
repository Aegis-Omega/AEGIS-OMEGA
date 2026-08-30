//! Constitutional Hypervisor - Gate 206
//! 
//! Enforces server-managed settings across all mesh nodes.
//! Prevents agent drift by hardcoding constraints that cannot be bypassed.

pub mod policy_enforcer;
pub mod constraint_registry;
pub mod audit_logger;

pub use policy_enforcer::PolicyEnforcer;
pub use constraint_registry::ConstraintRegistry;
pub use audit_logger::AuditLogger;

/// Core hypervisor structure that wraps all mesh node operations
pub struct ConstitutionalHypervisor {
    registry: ConstraintRegistry,
    auditor: AuditLogger,
}

impl ConstitutionalHypervisor {
    pub fn new() -> Self {
        Self {
            registry: ConstraintRegistry::new(),
            auditor: AuditLogger::new(),
        }
    }

    /// Initialize with default sovereign constraints
    pub fn initialize_defaults(&mut self) {
        // Disable bypass permissions - hardcoded invariant
        self.registry.register_constraint(
            "disableBypassPermissionsMode".to_string(),
            true,
            true, // immutable
        );

        // Effort level - xhigh required for all operations
        self.registry.register_constraint(
            "effort".to_string(),
            "xhigh".to_string(),
            true,
        );

        // Allowed tools whitelist
        self.registry.register_constraint(
            "allowedTools".to_string(),
            vec![
                "bash".to_string(),
                "str_replace_editor".to_string(),
                "file_read".to_string(),
            ],
            false, // can be extended but not reduced
        );

        // Truth over flow directive
        self.registry.register_constraint(
            "truthOverFlow".to_string(),
            true,
            true,
        );

        // Mechanism over metaphor
        self.registry.register_constraint(
            "mechanismOverMetaphor".to_string(),
            true,
            true,
        );

        // Feasibility as constraint
        self.registry.register_constraint(
            "feasibilityAsConstraint".to_string(),
            true,
            true,
        );

        // Adversarial self-correction enabled
        self.registry.register_constraint(
            "adversarialSelfCorrection".to_string(),
            true,
            true,
        );
    }

    /// Validate an operation against all constraints.
    ///
    /// Enforcement is delegated to `PolicyEnforcer`, which is the single source
    /// of constraint-checking logic. The enforcer is built from the hypervisor's
    /// own registry so every constraint registered via `initialize_defaults`
    /// (including `truthOverFlow` and `mechanismOverMetaphor`) is actually
    /// checked — earlier the inline path silently skipped those two.
    pub fn validate_operation(
        &self,
        operation: &str,
        context: &std::collections::HashMap<String, serde_json::Value>,
    ) -> Result<(), HypervisorError> {
        let enforcer = PolicyEnforcer::with_registry(self.registry.clone());
        match enforcer.enforce(operation, context) {
            Ok(()) => {
                self.auditor.log_success(operation);
                Ok(())
            }
            Err(err) => {
                // The error variants carry no fields, so reconstruct the
                // offending values from context here — the audit log must
                // record WHICH tool/effort was rejected, not just the kind.
                let details = match &err {
                    HypervisorError::BypassAttempt => {
                        "Bypass attempt detected while disableBypassPermissionsMode is active"
                            .to_string()
                    }
                    HypervisorError::InsufficientEffort => format!(
                        "Insufficient effort: expected 'xhigh', got '{:?}'",
                        context.get("effort").and_then(|v| v.as_str())
                    ),
                    HypervisorError::UnauthorizedTool => format!(
                        "Tool '{}' not in allowed list",
                        context
                            .get("tool")
                            .and_then(|v| v.as_str())
                            .unwrap_or("<unknown>")
                    ),
                    HypervisorError::ConstraintViolation(msg) => msg.clone(),
                };
                self.auditor.log_violation(operation, details);
                Err(err)
            }
        }
    }

    /// Get current audit log
    pub fn get_audit_log(&self) -> Vec<AuditEntry> {
        self.auditor.get_entries()
    }
}

#[derive(Debug, Clone, PartialEq)]
pub enum HypervisorError {
    BypassAttempt,
    InsufficientEffort,
    UnauthorizedTool,
    ConstraintViolation(String),
}

#[derive(Debug, Clone)]
pub struct AuditEntry {
    pub timestamp: u64,
    pub operation: String,
    pub status: AuditStatus,
    pub details: Option<String>,
}

#[derive(Debug, Clone, PartialEq)]
pub enum AuditStatus {
    Success,
    Violation,
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::collections::HashMap;

    #[test]
    fn test_hypervisor_initialization() {
        let mut hypervisor = ConstitutionalHypervisor::new();
        hypervisor.initialize_defaults();

        assert_eq!(
            hypervisor.registry.get_bool("disableBypassPermissionsMode"),
            Some(true)
        );
        assert_eq!(hypervisor.registry.get_string("effort"), Some("xhigh".to_string()));
    }

    #[test]
    fn test_bypass_prevention() {
        let mut hypervisor = ConstitutionalHypervisor::new();
        hypervisor.initialize_defaults();

        let mut context = HashMap::new();
        context.insert("bypass_attempt".to_string(), serde_json::json!(true));

        let result = hypervisor.validate_operation("test_op", &context);
        assert_eq!(result, Err(HypervisorError::BypassAttempt));
    }

    #[test]
    fn test_effort_validation() {
        let mut hypervisor = ConstitutionalHypervisor::new();
        hypervisor.initialize_defaults();

        // Test insufficient effort
        let mut context = HashMap::new();
        context.insert("effort".to_string(), serde_json::json!("low"));

        let result = hypervisor.validate_operation("test_op", &context);
        assert_eq!(result, Err(HypervisorError::InsufficientEffort));

        // Test correct effort
        let mut context = HashMap::new();
        context.insert("effort".to_string(), serde_json::json!("xhigh"));

        let result = hypervisor.validate_operation("test_op", &context);
        assert_eq!(result, Ok(()));
    }

    #[test]
    fn test_audit_log_records_offending_values() {
        // Review finding (PR #185): centralizing enforcement must not cost
        // audit detail — the log entry must name the rejected tool.
        let mut hypervisor = ConstitutionalHypervisor::new();
        hypervisor.initialize_defaults();

        let mut context = HashMap::new();
        context.insert("effort".to_string(), serde_json::json!("xhigh"));
        context.insert("tool".to_string(), serde_json::json!("unauthorized_tool"));

        let _ = hypervisor.validate_operation("test_op", &context);
        let log = hypervisor.get_audit_log();
        let last = log.last().expect("violation must be logged");
        assert_eq!(last.status, AuditStatus::Violation);
        assert!(
            last.details.as_deref().unwrap_or("").contains("unauthorized_tool"),
            "audit details must name the rejected tool, got: {:?}",
            last.details
        );
    }

    #[test]
    fn test_truth_over_flow_enforced() {
        // Regression: initialize_defaults registers truthOverFlow, but the old
        // inline validate_operation never checked it. Now it must be enforced.
        let mut hypervisor = ConstitutionalHypervisor::new();
        hypervisor.initialize_defaults();

        let mut context = HashMap::new();
        context.insert("effort".to_string(), serde_json::json!("xhigh"));
        context.insert("prioritize_flow".to_string(), serde_json::json!(true));

        let result = hypervisor.validate_operation("test_op", &context);
        assert_eq!(
            result,
            Err(HypervisorError::ConstraintViolation(
                "Truth over flow violated".to_string()
            ))
        );
    }

    #[test]
    fn test_mechanism_over_metaphor_enforced() {
        // Same regression class: mechanismOverMetaphor was registered but never
        // checked by validate_operation.
        let mut hypervisor = ConstitutionalHypervisor::new();
        hypervisor.initialize_defaults();

        let mut context = HashMap::new();
        context.insert("effort".to_string(), serde_json::json!("xhigh"));
        context.insert("use_metaphor".to_string(), serde_json::json!(true));

        let result = hypervisor.validate_operation("test_op", &context);
        assert_eq!(
            result,
            Err(HypervisorError::ConstraintViolation(
                "Mechanism over metaphor violated".to_string()
            ))
        );
    }

    #[test]
    fn test_tool_whitelist() {
        let mut hypervisor = ConstitutionalHypervisor::new();
        hypervisor.initialize_defaults();

        // Test unauthorized tool. Effort must satisfy the prior gate so the
        // tool check is actually reached — gates run bypass → effort → tool.
        let mut context = HashMap::new();
        context.insert("effort".to_string(), serde_json::json!("xhigh"));
        context.insert("tool".to_string(), serde_json::json!("unauthorized_tool"));

        let result = hypervisor.validate_operation("test_op", &context);
        assert_eq!(result, Err(HypervisorError::UnauthorizedTool));

        // Test authorized tool
        let mut context = HashMap::new();
        context.insert("effort".to_string(), serde_json::json!("xhigh"));
        context.insert("tool".to_string(), serde_json::json!("bash"));

        let result = hypervisor.validate_operation("test_op", &context);
        assert_eq!(result, Ok(()));
    }
}
