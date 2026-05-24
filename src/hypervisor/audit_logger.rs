//! Audit Logger - Records all hypervisor decisions and violations

use crate::hypervisor::{AuditEntry, AuditStatus};
use std::sync::{Arc, Mutex};
use std::time::{SystemTime, UNIX_EPOCH};

/// Thread-safe audit logger for hypervisor operations
pub struct AuditLogger {
    entries: Arc<Mutex<Vec<AuditEntry>>>,
}

impl AuditLogger {
    pub fn new() -> Self {
        Self {
            entries: Arc::new(Mutex::new(Vec::new())),
        }
    }

    /// Get current timestamp in milliseconds
    fn current_timestamp() -> u64 {
        SystemTime::now()
            .duration_since(UNIX_EPOCH)
            .unwrap_or_default()
            .as_millis() as u64
    }

    /// Log a successful operation
    pub fn log_success(&self, operation: &str) {
        let entry = AuditEntry {
            timestamp: Self::current_timestamp(),
            operation: operation.to_string(),
            status: AuditStatus::Success,
            details: None,
        };

        if let Ok(mut entries) = self.entries.lock() {
            entries.push(entry);
        }
    }

    /// Log a violation
    pub fn log_violation(&self, operation: &str, details: impl Into<String>) {
        let entry = AuditEntry {
            timestamp: Self::current_timestamp(),
            operation: operation.to_string(),
            status: AuditStatus::Violation,
            details: Some(details.into()),
        };

        if let Ok(mut entries) = self.entries.lock() {
            entries.push(entry);
        }
    }

    /// Get all audit entries
    pub fn get_entries(&self) -> Vec<AuditEntry> {
        self.entries
            .lock()
            .map(|entries| entries.clone())
            .unwrap_or_default()
    }

    /// Get recent violations only
    pub fn get_violations(&self) -> Vec<AuditEntry> {
        self.entries
            .lock()
            .map(|entries| {
                entries
                    .iter()
                    .filter(|e| e.status == AuditStatus::Violation)
                    .cloned()
                    .collect()
            })
            .unwrap_or_default()
    }

    /// Clear audit log
    pub fn clear(&self) {
        if let Ok(mut entries) = self.entries.lock() {
            entries.clear();
        }
    }

    /// Export audit log as JSON
    pub fn export_json(&self) -> serde_json::Value {
        let entries = self.get_entries();
        let json_entries: Vec<serde_json::Value> = entries
            .into_iter()
            .map(|e| {
                serde_json::json!({
                    "timestamp": e.timestamp,
                    "operation": e.operation,
                    "status": match e.status {
                        AuditStatus::Success => "success",
                        AuditStatus::Violation => "violation",
                    },
                    "details": e.details,
                })
            })
            .collect();

        serde_json::json!(json_entries)
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_log_success() {
        let logger = AuditLogger::new();
        logger.log_success("test_operation");

        let entries = logger.get_entries();
        assert_eq!(entries.len(), 1);
        assert_eq!(entries[0].status, AuditStatus::Success);
        assert_eq!(entries[0].operation, "test_operation");
    }

    #[test]
    fn test_log_violation() {
        let logger = AuditLogger::new();
        logger.log_violation("bad_op", "Constraint violated");

        let entries = logger.get_entries();
        assert_eq!(entries.len(), 1);
        assert_eq!(entries[0].status, AuditStatus::Violation);
        assert_eq!(entries[0].details, Some("Constraint violated".to_string()));
    }

    #[test]
    fn test_get_violations() {
        let logger = AuditLogger::new();
        logger.log_success("good_op");
        logger.log_violation("bad_op1", "violation 1");
        logger.log_violation("bad_op2", "violation 2");

        let violations = logger.get_violations();
        assert_eq!(violations.len(), 2);
        assert!(violations.iter().all(|e| e.status == AuditStatus::Violation));
    }

    #[test]
    fn test_clear_log() {
        let logger = AuditLogger::new();
        logger.log_success("op1");
        logger.log_violation("op2", "error");

        logger.clear();

        let entries = logger.get_entries();
        assert_eq!(entries.len(), 0);
    }
}
