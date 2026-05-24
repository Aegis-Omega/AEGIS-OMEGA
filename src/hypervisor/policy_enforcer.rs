//! Policy Enforcer - Executes constraint validation logic

use crate::hypervisor::{ConstraintRegistry, HypervisorError};

/// Enforces policies against operations
pub struct PolicyEnforcer {
    registry: ConstraintRegistry,
}

impl PolicyEnforcer {
    pub fn new() -> Self {
        Self {
            registry: ConstraintRegistry::new(),
        }
    }

    pub fn with_registry(registry: ConstraintRegistry) -> Self {
        Self { registry }
    }

    /// Check if an operation violates any policy
    pub fn enforce(
        &self,
        operation: &str,
        context: &std::collections::HashMap<String, serde_json::Value>,
    ) -> Result<(), HypervisorError> {
        // Check bypass mode
        if self.registry.get_bool("disableBypassPermissionsMode") == Some(true) {
            if context.contains_key("bypass_attempt") {
                return Err(HypervisorError::BypassAttempt);
            }
        }

        // Check effort level
        if let Some(required_effort) = self.registry.get_string("effort") {
            if required_effort == "xhigh" {
                let provided = context.get("effort").and_then(|v| v.as_str());
                if provided != Some("xhigh") {
                    return Err(HypervisorError::InsufficientEffort);
                }
            }
        }

        // Check tool whitelist
        if let Some(tool) = context.get("tool").and_then(|v| v.as_str()) {
            if let Some(allowed) = self.registry.get_string_list("allowedTools") {
                if !allowed.contains(&tool.to_string()) {
                    return Err(HypervisorError::UnauthorizedTool);
                }
            }
        }

        // Check truth over flow
        if self.registry.get_bool("truthOverFlow") == Some(true) {
            if context.get("prioritize_flow").and_then(|v| v.as_bool()) == Some(true) {
                return Err(HypervisorError::ConstraintViolation(
                    "Truth over flow violated".to_string(),
                ));
            }
        }

        // Check mechanism over metaphor
        if self.registry.get_bool("mechanismOverMetaphor") == Some(true) {
            if context.get("use_metaphor").and_then(|v| v.as_bool()) == Some(true) {
                return Err(HypervisorError::ConstraintViolation(
                    "Mechanism over metaphor violated".to_string(),
                ));
            }
        }

        Ok(())
    }

    /// Get reference to registry
    pub fn registry(&self) -> &ConstraintRegistry {
        &self.registry
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::collections::HashMap;

    #[test]
    fn test_enforce_bypass_block() {
        let mut enforcer = PolicyEnforcer::new();
        enforcer
            .registry
            .register_constraint("disableBypassPermissionsMode".to_string(), true, true);

        let mut context = HashMap::new();
        context.insert("bypass_attempt".to_string(), serde_json::json!(true));

        assert_eq!(
            enforcer.enforce("test", &context),
            Err(HypervisorError::BypassAttempt)
        );
    }

    #[test]
    fn test_enforce_effort_check() {
        let mut enforcer = PolicyEnforcer::new();
        enforcer
            .registry
            .register_constraint("effort".to_string(), "xhigh".to_string(), true);

        let mut context = HashMap::new();
        context.insert("effort".to_string(), serde_json::json!("low"));

        assert_eq!(
            enforcer.enforce("test", &context),
            Err(HypervisorError::InsufficientEffort)
        );
    }

    #[test]
    fn test_enforce_truth_over_flow() {
        let mut enforcer = PolicyEnforcer::new();
        enforcer
            .registry
            .register_constraint("truthOverFlow".to_string(), true, true);

        let mut context = HashMap::new();
        context.insert("prioritize_flow".to_string(), serde_json::json!(true));

        assert!(enforcer
            .enforce("test", &context)
            .is_err());
    }
}
