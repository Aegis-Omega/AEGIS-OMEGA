//! Tashkeel: Epistemic Metadata Layer (Dimension 3)
//!
//! Diacritics (Tashkeel) hover above or below the Rasm to clarify
//! pronunciation and meaning without altering the skeleton.
//!
//! Cognitive Translation: The Tashkeel is the Uncertainty Preservation Layer.
//! It is the metadata that hovers over the causal chain.
//! It tags assumptions, probabilities, and confidence intervals (P(x)).
//!
//! Operational Rule: The base text (the action/code) must remain clean
//! and executable, while the Tashkeel (epistemic risk assessment) floats
//! above it, visible to the observer but not breaking execution flow.

use std::collections::BTreeMap;
use crate::rasm::NodeId;

/// Risk Level for epistemic uncertainty
#[derive(Debug, Clone, Copy, PartialEq, Eq, PartialOrd, Ord)]
pub enum RiskLevel {
    /// p > 0.99 - Negligible risk
    Negligible,
    /// p > 0.95 - Low risk
    Low,
    /// p > 0.80 - Medium risk
    Medium,
    /// p > 0.50 - High risk
    High,
    /// p ≤ 0.50 - Critical risk
    Critical,
}

impl RiskLevel {
    /// Convert probability to risk level
    pub fn from_probability(p: f64) -> Self {
        if p > 0.99 {
            RiskLevel::Negligible
        } else if p > 0.95 {
            RiskLevel::Low
        } else if p > 0.80 {
            RiskLevel::Medium
        } else if p > 0.50 {
            RiskLevel::High
        } else {
            RiskLevel::Critical
        }
    }

    /// Get minimum probability for this risk level
    pub fn min_probability(&self) -> f64 {
        match self {
            RiskLevel::Negligible => 0.99,
            RiskLevel::Low => 0.95,
            RiskLevel::Medium => 0.80,
            RiskLevel::High => 0.50,
            RiskLevel::Critical => 0.0,
        }
    }

    /// Get visual indicator for risk level
    pub fn indicator(&self) -> &'static str {
        match self {
            RiskLevel::Negligible => "✓",
            RiskLevel::Low => "○",
            RiskLevel::Medium => "△",
            RiskLevel::High => "⚠",
            RiskLevel::Critical => "✗",
        }
    }
}

/// Confidence interval with epistemic metadata
#[derive(Debug, Clone)]
pub struct Confidence {
    /// Probability P(x) ∈ [0, 1]
    pub probability: f64,
    /// Derived risk level
    pub epistemic_risk: RiskLevel,
    /// Additional metadata
    pub metadata: BTreeMap<String, String>,
}

impl Confidence {
    /// Create new confidence from probability
    pub fn new(probability: f64) -> Self {
        Self {
            probability,
            epistemic_risk: RiskLevel::from_probability(probability),
            metadata: BTreeMap::new(),
        }
    }

    /// Add metadata key-value pair
    pub fn with_metadata(mut self, key: String, value: String) -> Self {
        self.metadata.insert(key, value);
        self
    }

    /// Check if confidence meets threshold
    pub fn meets_threshold(&self, threshold: f64) -> bool {
        self.probability >= threshold
    }

    /// Get confidence as percentage
    pub fn as_percentage(&self) -> f64 {
        self.probability * 100.0
    }
}

/// Assumption in the Tashkeel layer
#[derive(Debug, Clone)]
pub struct Assumption {
    /// Unique identifier
    pub id: u64,
    /// Description of the assumption
    pub description: String,
    /// Confidence in this assumption
    pub confidence: Confidence,
    /// Whether assumption has been validated
    pub validated: bool,
}

impl Assumption {
    pub fn new(id: u64, description: String, probability: f64) -> Self {
        Self {
            id,
            description,
            confidence: Confidence::new(probability),
            validated: false,
        }
    }

    pub fn validate(&mut self) {
        self.validated = true;
    }
}

/// Stress test result for adversarial validation
#[derive(Debug, Clone)]
pub struct StressTestResult {
    /// Test name/identifier
    pub test_name: String,
    /// Whether test passed
    pub passed: bool,
    /// Details of failure (if any)
    pub failure_details: Option<String>,
    /// Performance metrics
    pub metrics: BTreeMap<String, f64>,
}

impl StressTestResult {
    pub fn pass(test_name: String) -> Self {
        Self {
            test_name,
            passed: true,
            failure_details: None,
            metrics: BTreeMap::new(),
        }
    }

    pub fn fail(test_name: String, details: String) -> Self {
        Self {
            test_name,
            passed: false,
            failure_details: Some(details),
            metrics: BTreeMap::new(),
        }
    }

    pub fn with_metric(mut self, name: String, value: f64) -> Self {
        self.metrics.insert(name, value);
        self
    }
}

/// TashkeelLayer: Epistemic metadata hovering over causal chain
pub struct TashkeelLayer {
    /// List of assumptions
    pub assumptions: Vec<Assumption>,
    /// Confidence intervals per node
    pub confidence_intervals: BTreeMap<NodeId, Confidence>,
    /// Adversarial stress test results
    pub adversarial_results: Vec<StressTestResult>,
    /// Next assumption ID
    next_assumption_id: u64,
}

impl TashkeelLayer {
    /// Create a new empty Tashkeel layer
    pub fn new() -> Self {
        Self {
            assumptions: Vec::new(),
            confidence_intervals: BTreeMap::new(),
            adversarial_results: Vec::new(),
            next_assumption_id: 0,
        }
    }

    /// Add an assumption (Phase 4 of Khatt Loop - Apply Tashkeel)
    pub fn add_assumption(&mut self, description: String, probability: f64) -> &Assumption {
        let assumption = Assumption::new(self.next_assumption_id, description, probability);
        self.next_assumption_id += 1;
        self.assumptions.push(assumption);
        self.assumptions.last().unwrap()
    }

    /// Set confidence for a node
    pub fn set_confidence(&mut self, node_id: NodeId, probability: f64) {
        self.confidence_intervals
            .insert(node_id, Confidence::new(probability));
    }

    /// Set confidence with metadata
    pub fn set_confidence_with_metadata(
        &mut self,
        node_id: NodeId,
        probability: f64,
        metadata: Vec<(String, String)>,
    ) {
        let mut confidence = Confidence::new(probability);
        for (key, value) in metadata {
            confidence.metadata.insert(key, value);
        }
        self.confidence_intervals.insert(node_id, confidence);
    }

    /// Add stress test result
    pub fn add_stress_result(&mut self, result: StressTestResult) {
        self.adversarial_results.push(result);
    }

    /// Get overall confidence (average across all nodes)
    pub fn overall_confidence(&self) -> Option<f64> {
        if self.confidence_intervals.is_empty() {
            return None;
        }

        let sum: f64 = self.confidence_intervals.values().map(|c| c.probability).sum();
        Some(sum / self.confidence_intervals.len() as f64)
    }

    /// Get minimum confidence (weakest link)
    pub fn minimum_confidence(&self) -> Option<f64> {
        self.confidence_intervals
            .values()
            .map(|c| c.probability)
            .fold(None, |min, p| Some(min.map_or(p, |m: f64| m.min(p))))
    }

    /// Get all high-risk nodes (probability < threshold)
    pub fn high_risk_nodes(&self, threshold: f64) -> Vec<(NodeId, &Confidence)> {
        self.confidence_intervals
            .iter()
            .filter(|(_, c)| c.probability < threshold)
            .map(|(&id, c)| (id, c))
            .collect()
    }

    /// Validate all assumptions
    pub fn validate_assumptions(&mut self) {
        for assumption in &mut self.assumptions {
            assumption.validate();
        }
    }

    /// Get count of unvalidated assumptions
    pub fn unvalidated_count(&self) -> usize {
        self.assumptions.iter().filter(|a| !a.validated).count()
    }

    /// Check if all stress tests passed
    pub fn all_tests_passed(&self) -> bool {
        self.adversarial_results.iter().all(|r| r.passed)
    }

    /// Get failure summary
    pub fn failure_summary(&self) -> Vec<&StressTestResult> {
        self.adversarial_results.iter().filter(|r| !r.passed).collect()
    }

    /// Clear all data (for reset)
    pub fn clear(&mut self) {
        self.assumptions.clear();
        self.confidence_intervals.clear();
        self.adversarial_results.clear();
        self.next_assumption_id = 0;
    }
}

impl Default for TashkeelLayer {
    fn default() -> Self {
        Self::new()
    }
}

/// Tashkeel Overlay: Combines Rasm node with epistemic metadata
pub struct TashkeelOverlay {
    pub node_id: NodeId,
    pub tashkeel: TashkeelLayer,
}

impl TashkeelOverlay {
    pub fn new(node_id: NodeId) -> Self {
        Self {
            node_id,
            tashkeel: TashkeelLayer::new(),
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_risk_level_from_probability() {
        assert_eq!(RiskLevel::from_probability(0.995), RiskLevel::Negligible);
        assert_eq!(RiskLevel::from_probability(0.97), RiskLevel::Low);
        assert_eq!(RiskLevel::from_probability(0.85), RiskLevel::Medium);
        assert_eq!(RiskLevel::from_probability(0.60), RiskLevel::High);
        assert_eq!(RiskLevel::from_probability(0.40), RiskLevel::Critical);
    }

    #[test]
    fn test_risk_level_indicators() {
        assert_eq!(RiskLevel::Negligible.indicator(), "✓");
        assert_eq!(RiskLevel::Low.indicator(), "○");
        assert_eq!(RiskLevel::Medium.indicator(), "△");
        assert_eq!(RiskLevel::High.indicator(), "⚠");
        assert_eq!(RiskLevel::Critical.indicator(), "✗");
    }

    #[test]
    fn test_confidence_creation() {
        let conf = Confidence::new(0.95);
        assert_eq!(conf.probability, 0.95);
        assert_eq!(conf.epistemic_risk, RiskLevel::Low);
        assert!(conf.meets_threshold(0.90));
        assert!(!conf.meets_threshold(0.99));
    }

    #[test]
    fn test_confidence_metadata() {
        let conf = Confidence::new(0.85)
            .with_metadata("source".to_string(), "test".to_string())
            .with_metadata("version".to_string(), "1.0".to_string());

        assert_eq!(conf.metadata.get("source"), Some(&"test".to_string()));
        assert_eq!(conf.metadata.get("version"), Some(&"1.0".to_string()));
    }

    #[test]
    fn test_tashkeel_layer_basic() {
        let mut layer = TashkeelLayer::new();

        layer.add_assumption("Test assumption".to_string(), 0.90);
        layer.set_confidence(1, 0.95);
        layer.set_confidence(2, 0.85);

        assert_eq!(layer.assumptions.len(), 1);
        assert_eq!(layer.confidence_intervals.len(), 2);
    }

    #[test]
    fn test_overall_confidence() {
        let mut layer = TashkeelLayer::new();
        layer.set_confidence(1, 0.90);
        layer.set_confidence(2, 0.80);
        layer.set_confidence(3, 0.70);

        let overall = layer.overall_confidence().unwrap();
        assert!((overall - 0.80).abs() < 0.001);
    }

    #[test]
    fn test_minimum_confidence() {
        let mut layer = TashkeelLayer::new();
        layer.set_confidence(1, 0.90);
        layer.set_confidence(2, 0.60);
        layer.set_confidence(3, 0.80);

        let min = layer.minimum_confidence().unwrap();
        assert!((min - 0.60).abs() < 0.001);
    }

    #[test]
    fn test_high_risk_nodes() {
        let mut layer = TashkeelLayer::new();
        layer.set_confidence(1, 0.95);
        layer.set_confidence(2, 0.40);
        layer.set_confidence(3, 0.60);

        let high_risk = layer.high_risk_nodes(0.70);
        assert_eq!(high_risk.len(), 2);
        assert!(high_risk.iter().any(|(id, _)| *id == 2));
        assert!(high_risk.iter().any(|(id, _)| *id == 3));
    }

    #[test]
    fn test_stress_test_results() {
        let mut layer = TashkeelLayer::new();
        layer.add_stress_result(StressTestResult::pass("test_1".to_string()));
        layer.add_stress_result(StressTestResult::fail("test_2".to_string(), "timeout".to_string()));

        assert!(!layer.all_tests_passed());
        assert_eq!(layer.failure_summary().len(), 1);
    }

    #[test]
    fn test_assumption_validation() {
        let mut layer = TashkeelLayer::new();
        layer.add_assumption("untested".to_string(), 0.50);
        layer.add_assumption("untested".to_string(), 0.60);

        assert_eq!(layer.unvalidated_count(), 2);

        layer.validate_assumptions();
        assert_eq!(layer.unvalidated_count(), 0);
    }
}
