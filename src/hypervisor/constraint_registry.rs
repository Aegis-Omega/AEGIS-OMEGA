//! Constraint Registry - Stores and manages all hypervisor constraints

use std::collections::HashMap;

/// Represents a single constraint with immutability flag
#[derive(Debug, Clone)]
pub struct Constraint {
    pub value: serde_json::Value,
    pub immutable: bool,
}

/// Central registry for all constitutional constraints
pub struct ConstraintRegistry {
    constraints: HashMap<String, Constraint>,
}

impl ConstraintRegistry {
    pub fn new() -> Self {
        Self {
            constraints: HashMap::new(),
        }
    }

    /// Register a new constraint
    pub fn register_constraint<T: Into<serde_json::Value>>(
        &mut self,
        key: String,
        value: T,
        immutable: bool,
    ) {
        self.constraints.insert(
            key,
            Constraint {
                value: value.into(),
                immutable,
            },
        );
    }

    /// Update a constraint (fails if immutable)
    pub fn update_constraint<T: Into<serde_json::Value>>(
        &mut self,
        key: &str,
        value: T,
    ) -> Result<(), &'static str> {
        if let Some(constraint) = self.constraints.get(key) {
            if constraint.immutable {
                return Err("Cannot modify immutable constraint");
            }
        }

        if let Some(constraint) = self.constraints.get_mut(key) {
            constraint.value = value.into();
            Ok(())
        } else {
            Err("Constraint not found")
        }
    }

    /// Get a boolean value
    pub fn get_bool(&self, key: &str) -> Option<bool> {
        self.constraints
            .get(key)
            .and_then(|c| c.value.as_bool())
    }

    /// Get a string value
    pub fn get_string(&self, key: &str) -> Option<String> {
        self.constraints
            .get(key)
            .and_then(|c| c.value.as_str())
            .map(|s| s.to_string())
    }

    /// Get a list of strings
    pub fn get_string_list(&self, key: &str) -> Option<Vec<String>> {
        self.constraints.get(key).and_then(|c| {
            c.value.as_array().map(|arr| {
                arr.iter()
                    .filter_map(|v| v.as_str().map(|s| s.to_string()))
                    .collect()
            })
        })
    }

    /// Check if a constraint exists
    pub fn has_constraint(&self, key: &str) -> bool {
        self.constraints.contains_key(key)
    }

    /// Get all constraint keys
    pub fn get_all_keys(&self) -> Vec<&String> {
        self.constraints.keys().collect()
    }

    /// Export all constraints as JSON
    pub fn export_json(&self) -> serde_json::Value {
        let mut map = serde_json::Map::new();
        for (key, constraint) in &self.constraints {
            map.insert(
                key.clone(),
                serde_json::json!({
                    "value": constraint.value,
                    "immutable": constraint.immutable
                }),
            );
        }
        serde_json::Value::Object(map)
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_register_and_retrieve() {
        let mut registry = ConstraintRegistry::new();
        registry.register_constraint("test_bool".to_string(), true, true);
        registry.register_constraint("test_string".to_string(), "hello".to_string(), false);

        assert_eq!(registry.get_bool("test_bool"), Some(true));
        assert_eq!(registry.get_string("test_string"), Some("hello".to_string()));
    }

    #[test]
    fn test_immutable_constraint() {
        let mut registry = ConstraintRegistry::new();
        registry.register_constraint("locked".to_string(), 42, true);

        let result = registry.update_constraint("locked", 100);
        assert_eq!(result, Err("Cannot modify immutable constraint"));
    }

    #[test]
    fn test_mutable_constraint() {
        let mut registry = ConstraintRegistry::new();
        registry.register_constraint("mutable".to_string(), 42, false);

        let result = registry.update_constraint("mutable", 100);
        assert_eq!(result, Ok(()));
        assert_eq!(registry.get_bool("mutable"), None); // Changed to number
    }

    #[test]
    fn test_string_list() {
        let mut registry = ConstraintRegistry::new();
        let tools = vec!["bash".to_string(), "python".to_string()];
        registry.register_constraint("tools".to_string(), serde_json::json!(tools));

        let retrieved = registry.get_string_list("tools");
        assert_eq!(retrieved, Some(vec!["bash".to_string(), "python".to_string()]));
    }
}
