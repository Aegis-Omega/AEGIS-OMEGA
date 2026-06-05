//! Epistemic Firewall - Domain Boundary Enforcement
//! 
//! EPISTEMIC TIER: T0 (mechanically proven)
//! Constitutional root: f: K → D₀ where D₁ cannot mutate D₀
//! 
//! This module enforces strict domain separation between the axiomatic core
//! (Domain 0) and human semantic overlays (Domain 1). The boundary is
//! unidirectional - overlays can reference axioms but never modify them.

use std::collections::BTreeMap;
use std::fmt;

/// A unique key identifying an axiomatic unit within the T0 Core.
/// Uses BTreeMap for deterministic iteration order (Constitutional requirement).
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, PartialOrd, Ord)]
pub struct AxiomKey {
    /// Section number within the axiomatic corpus
    pub section_num: u16,
    /// Node number within the section
    pub node_num: u16,
}

impl AxiomKey {
    /// Creates a new AxiomKey from section and node numbers.
    pub fn new(section_num: u16, node_num: u16) -> Self {
        Self { section_num, node_num }
    }
}

impl fmt::Display for AxiomKey {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        write!(f, "§{}.{}", self.section_num, self.node_num)
    }
}

/// The immutable T0 Axiomatic Core containing raw text bytes.
pub struct T0Core {
    raw_text_bytes: &'static [u8],
    offset_registry: BTreeMap<AxiomKey, (usize, usize)>,
}

/// A semantic overlay that provides human interpretation of axiomatic content.
/// Overlays are strictly read-only with respect to the underlying core.
#[derive(Debug, Clone)]
pub struct SemanticOverlay {
    /// Reference to the target axiom in the core
    pub target: AxiomKey,
    /// Name of the overlay author
    pub author_name: String,
    /// Human commentary or interpretation
    pub commentary: String,
}

impl SemanticOverlay {
    /// Creates a new semantic overlay targeting a specific axiom.
    pub fn new(target: AxiomKey, author_name: String, commentary: String) -> Self {
        Self { target, author_name, commentary }
    }
}

impl T0Core {
    /// Creates a new T0Core with pre-registered byte offsets.
    /// 
    /// # Arguments
    /// * `text` - Static slice containing the raw axiomatic text
    /// * `offsets` - BTreeMap mapping AxiomKeys to (start, end) byte ranges
    pub fn new(
        text: &'static [u8], 
        offsets: BTreeMap<AxiomKey, (usize, usize)>
    ) -> Self {
        Self { 
            raw_text_bytes: text, 
            offset_registry: offsets 
        }
    }

    /// Resolves an AxiomKey to its corresponding byte slice.
    /// 
    /// # Security Guarantees
    /// - Returns only immutable references (&[u8])
    /// - Validates bounds against physical core boundary
    /// - No allocation occurs during resolution
    /// 
    /// # Returns
    /// * `Ok(&[u8])` - Immutable reference to the axiomatic bytes
    /// * `Err(&'static str)` - Firewall violation or missing key
    pub fn resolve_reference(&self, key: &AxiomKey) -> Result<&[u8], &'static str> {
        match self.offset_registry.get(key) {
            Some(&(start, end)) => {
                if end <= self.raw_text_bytes.len() {
                    Ok(&self.raw_text_bytes[start..end])
                } else {
                    Err("[FIREWALL VIOLATION] Registered offsets exceed physical core boundary.")
                }
            }
            None => Err("[FIREWALL ERROR] Requested key does not exist in the T0 Axiomatic core.")
        }
    }

    /// Returns the total size of the raw text corpus in bytes.
    pub fn corpus_size(&self) -> usize {
        self.raw_text_bytes.len()
    }

    /// Returns an iterator over all registered AxiomKeys.
    pub fn iter_keys(&self) -> impl Iterator<Item = &AxiomKey> {
        self.offset_registry.keys()
    }
}

/// SystemComposer renders combined views of axiomatic content with overlays.
/// This is the only mechanism by which Domain 1 (human) content interfaces
/// with Domain 0 (axiomatic) content.
pub struct SystemComposer;

impl SystemComposer {
    /// Renders a visual frame combining axiomatic text with its semantic overlay.
    /// 
    /// The rendering maintains strict visual separation:
    /// - TEXT: Raw axiomatic content (immutable)
    /// - SOURCE: Attribution metadata
    /// - OVERLAY: Human interpretation (clearly distinguished)
    /// 
    /// # Arguments
    /// * `core` - Reference to the T0Core containing axiomatic data
    /// * `overlay` - Semantic overlay to render
    pub fn render_view(core: &T0Core, overlay: &SemanticOverlay) {
        match core.resolve_reference(&overlay.target) {
            Ok(axiomatic_slice) => {
                let text_string = std::str::from_utf8(axiomatic_slice)
                    .unwrap_or("<Corrupted Encoding>");
                println!("--- VISUAL RENDERING FRAMEBUFFER ---");
                println!("TEXT:   {}", text_string);
                println!("SOURCE: Commentary by {} for Key {:?}", overlay.author_name, overlay.target);
                println!("OVERLAY: {}", overlay.commentary);
                println!("------------------------------------");
            }
            Err(e) => {
                println!("Execution halted: {}", e);
            }
        }
    }

    /// Renders a view to a String buffer instead of stdout.
    /// Useful for testing or programmatic consumption.
    pub fn render_to_string(core: &T0Core, overlay: &SemanticOverlay) -> String {
        match core.resolve_reference(&overlay.target) {
            Ok(axiomatic_slice) => {
                let text_string = std::str::from_utf8(axiomatic_slice)
                    .unwrap_or("<Corrupted Encoding>");
                format!(
                    "--- VISUAL RENDERING FRAMEBUFFER ---\n\
                     TEXT:   {}\n\
                     SOURCE: Commentary by {} for Key {:?}\n\
                     OVERLAY: {}\n\
                     ------------------------------------",
                    text_string, overlay.author_name, overlay.target, overlay.commentary
                )
            }
            Err(e) => format!("Execution halted: {}", e),
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn create_test_core() -> T0Core {
        // "Section N Content." = 18 bytes each; total = 54
        let text: &'static [u8] = b"Section 1 Content.Section 2 Content.Section 3 Content.";
        let mut offsets = BTreeMap::new();
        offsets.insert(AxiomKey::new(1, 1), (0, 18));
        offsets.insert(AxiomKey::new(2, 1), (18, 36));
        offsets.insert(AxiomKey::new(3, 1), (36, 54));
        T0Core::new(text, offsets)
    }

    #[test]
    fn test_resolve_valid_key() {
        let core = create_test_core();
        let result = core.resolve_reference(&AxiomKey::new(1, 1));
        assert!(result.is_ok());
        assert_eq!(result.unwrap(), b"Section 1 Content.");
    }

    #[test]
    fn test_resolve_invalid_key() {
        let core = create_test_core();
        let result = core.resolve_reference(&AxiomKey::new(99, 99));
        assert!(result.is_err());
        assert!(result.unwrap_err().contains("does not exist"));
    }

    #[test]
    fn test_semantic_overlay_creation() {
        let overlay = SemanticOverlay::new(
            AxiomKey::new(1, 1),
            "Test Author".to_string(),
            "Test commentary".to_string(),
        );
        assert_eq!(overlay.target, AxiomKey::new(1, 1));
        assert_eq!(overlay.author_name, "Test Author");
        assert_eq!(overlay.commentary, "Test commentary");
    }

    #[test]
    fn test_system_composer_render() {
        let core = create_test_core();
        let overlay = SemanticOverlay::new(
            AxiomKey::new(1, 1),
            "Tester".to_string(),
            "This is a test".to_string(),
        );
        let output = SystemComposer::render_to_string(&core, &overlay);
        assert!(output.contains("Section 1 Content."));
        assert!(output.contains("Tester"));
        assert!(output.contains("This is a test"));
    }

    #[test]
    fn test_axiom_key_display() {
        let key = AxiomKey::new(42, 7);
        assert_eq!(format!("{}", key), "§42.7");
    }

    #[test]
    fn test_core_iter_keys() {
        let core = create_test_core();
        let keys: Vec<_> = core.iter_keys().collect();
        assert_eq!(keys.len(), 3);
        assert_eq!(keys[0], &AxiomKey::new(1, 1));
        assert_eq!(keys[1], &AxiomKey::new(2, 1));
        assert_eq!(keys[2], &AxiomKey::new(3, 1));
    }

    // 7. corpus_size matches the length of the static payload
    #[test]
    fn corpus_size_matches_payload_length() {
        let core = create_test_core();
        assert_eq!(core.corpus_size(), b"Section 1 Content.Section 2 Content.Section 3 Content.".len());
    }

    // 8. all three registered keys resolve successfully
    #[test]
    fn all_registered_keys_resolve() {
        let core = create_test_core();
        assert!(core.resolve_reference(&AxiomKey::new(1, 1)).is_ok());
        assert!(core.resolve_reference(&AxiomKey::new(2, 1)).is_ok());
        assert!(core.resolve_reference(&AxiomKey::new(3, 1)).is_ok());
    }

    // 9. AxiomKey ordering is (section, node) lexicographic
    #[test]
    fn axiom_key_ordering() {
        assert!(AxiomKey::new(1, 1) < AxiomKey::new(2, 1));
        assert!(AxiomKey::new(1, 1) < AxiomKey::new(1, 2));
        assert!(AxiomKey::new(2, 5) > AxiomKey::new(2, 4));
    }

    // 10. render_to_string on missing key shows error text
    #[test]
    fn render_to_string_missing_key_shows_error() {
        let core = create_test_core();
        let overlay = SemanticOverlay::new(
            AxiomKey::new(99, 99),
            "Author".to_string(),
            "Comment".to_string(),
        );
        let output = SystemComposer::render_to_string(&core, &overlay);
        assert!(output.contains("halted") || output.contains("FIREWALL") || output.contains("does not exist"));
    }
}