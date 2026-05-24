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
    enforcer: PolicyEnforcer,
    auditor: AuditLogger,
}

impl ConstitutionalHypervisor {
    pub fn new() -> Self {
        Self {
            registry: ConstraintRegistry::new(),
            enforcer: PolicyEnforcer::new(),
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

    /// Validate an operation against all constraints
    pub fn validate_operation(
        &self,
        operation: &str,
        context: &std::collections::HashMap<String, serde_json::Value>,
    ) -> Result<(), HypervisorError> {
        // Check if bypass is attempted
        if self.registry.get_bool("disableBypassPermissionsMode") == Some(true) {
            if context.contains_key("bypass_attempt") {
                self.auditor.log_violation(
                    operation,
                    "Bypass attempt detected while disableBypassPermissionsMode is active",
                );
                return Err(HypervisorError::BypassAttempt);
            }
        }

        // Verify effort level
        let required_effort = self.registry.get_string("effort");
        if required_effort.as_deref() == Some("xhigh") {
            let provided_effort = context.get("effort").and_then(|v| v.as_str());
            if provided_effort != Some("xhigh") {
                self.auditor.log_violation(
                    operation,
                    format!("Insufficient effort: expected 'xhigh', got '{:?}'", provided_effort),
                );
                return Err(HypervisorError::InsufficientEffort);
            }
        }

        // Verify tool usage
        if let Some(tool) = context.get("tool").and_then(|v| v.as_str()) {
            let allowed = self.registry.get_string_list("allowedTools");
            if let Some(allowed_list) = allowed {
                if !allowed_list.contains(&tool.to_string()) {
                    self.auditor.log_violation(
                        operation,
                        format!("Tool '{}' not in allowed list", tool),
                    );
                    return Err(HypervisorError::UnauthorizedTool);
                }
            }
        }

        // All checks passed
        self.auditor.log_success(operation);
        Ok(())
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
    fn test_tool_whitelist() {
        let mut hypervisor = ConstitutionalHypervisor::new();
        hypervisor.initialize_defaults();

        // Test unauthorized tool
        let mut context = HashMap::new();
        context.insert("tool".to_string(), serde_json::json!("unauthorized_tool"));

        let result = hypervisor.validate_operation("test_op", &context);
        assert_eq!(result, Err(HypervisorError::UnauthorizedTool));

        // Test authorized tool
        let mut context = HashMap::new();
        context.insert("tool".to_string(), serde_json::json!("bash"));

        let result = hypervisor.validate_operation("test_op", &context);
        assert_eq!(result, Ok(()));
    }
}
