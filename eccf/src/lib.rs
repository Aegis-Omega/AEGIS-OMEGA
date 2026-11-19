//! ECCF - Ever-Evolving Crystalline Calligraphy Font
//! 
//! Maps post-quantum lattice cryptography to calligraphic geometry.
//! 
//! Mathematical State:
//! C(I, λ) = NTT₂₅₆(Keccak(I)) mod q(λ)
//! 
//! Where:
//! - I: Raw input data (ink)
//! - Keccak: Cryptographic fixation
//! - NTT₂₅₆: Geometric transformation over Z_q[X]/(X²⁵⁶+1)
//! - q(λ): Modular base adjusted by complexity λ

mod keccak_hash;
mod ntt_transform;
mod lattice_stroke;
mod calligraphic_renderer;
mod parametric_scaling;

pub use keccak_hash::KeccakInk;
pub use ntt_transform::NTTBrush;
pub use lattice_stroke::{ModuleLattice, LatticeStroke};
pub use calligraphic_renderer::{CalligraphicRenderer, RenderedCharacter};
pub use parametric_scaling::{ComplexityParameter, ParametricScaler};

use serde::{Serialize, Deserialize};

/// ECCF Character generated from input and complexity parameter
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ECCFCharacter {
    /// Input data hash
    pub input_hash: String,
    /// Complexity level (λ)
    pub complexity: u8,
    /// Lattice dimension
    pub lattice_dimension: usize,
    /// Modular base q(λ)
    pub modular_base: u64,
    /// NTT-transformed coefficients
    pub ntt_coefficients: Vec<i16>,
    /// Calligraphic stroke sequence
    pub strokes: Vec<LatticeStroke>,
    /// Tashkeel metadata (uncertainty diacritics)
    pub tashkeel: Option<TashkeelMetadata>,
}

/// Tashkeel metadata for uncertainty visualization
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct TashkeelMetadata {
    /// Confidence level (0.0 - 1.0)
    pub confidence: f64,
    /// Risk factors identified
    pub risk_factors: Vec<String>,
    /// Epistemic tags (diacritic positions)
    pub diacritic_positions: Vec<DiacriticPosition>,
}

/// Diacritic position in calligraphic space
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct DiacriticPosition {
    pub x: f64,
    pub y: f64,
    pub diacritic_type: DiacriticType,
}

/// Types of diacritical marks
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
pub enum DiacriticType {
    Fatha,      // Above - short 'a'
    Kasra,      // Below - short 'i'
    Damma,      // Above - short 'u'
    Sukun,      // Above - no vowel
    Shadda,     // Above - gemination
    Tanween,    // Nunation
}

/// ECCF Engine - Main orchestrator
pub struct ECCFEngine {
    keccak: KeccakInk,
    ntt_brush: NTTBrush,
    scaler: ParametricScaler,
    renderer: CalligraphicRenderer,
}

impl ECCFEngine {
    /// Create new ECCF engine with default parameters
    pub fn new() -> Self {
        Self {
            keccak: KeccakInk::new(),
            ntt_brush: NTTBrush::new(256),
            scaler: ParametricScaler::default(),
            renderer: CalligraphicRenderer::new(),
        }
    }

    /// Generate ECCF character from input and complexity
    /// 
    /// C(I, λ) = NTT₂₅₆(Keccak(I)) mod q(λ)
    pub fn generate_character(&self, input: &[u8], complexity: u8) -> ECCFCharacter {
        // Step 1: Keccak fixation (ink)
        let keccak_hash = self.keccak.fixate(input);
        let input_hash = hex::encode(&keccak_hash);
        
        // Step 2: Determine parametric scaling
        let params = self.scaler.scale_for_complexity(complexity);
        
        // Step 3: NTT transformation (brush stroke)
        let ntt_coeffs = self.ntt_brush.transform(&keccak_hash, params.lattice_dimension);
        
        // Step 4: Generate lattice strokes from NTT coefficients
        let strokes = ModuleLattice::generate_strokes(&ntt_coeffs, params.modular_base);
        
        // Step 5: Construct the character; rendering remains an explicit caller action.
        ECCFCharacter {
            input_hash,
            complexity,
            lattice_dimension: params.lattice_dimension,
            modular_base: params.modular_base,
            ntt_coefficients: ntt_coeffs,
            strokes,
            tashkeel: None,
        }
    }

    /// Apply Tashkeel (uncertainty metadata) to character
    pub fn apply_tashkeel(&mut self, character: &mut ECCFCharacter, confidence: f64, risks: Vec<String>) {
        let diacritics = self.renderer.compute_diacritics(&character.strokes, confidence);
        
        character.tashkeel = Some(TashkeelMetadata {
            confidence,
            risk_factors: risks,
            diacritic_positions: diacritics,
        });
    }

    /// Render character to SVG string
    pub fn render_to_svg(&self, character: &ECCFCharacter) -> String {
        self.renderer.to_svg(character)
    }

    /// Verify character integrity against input
    pub fn verify_character(&self, character: &ECCFCharacter, original_input: &[u8]) -> bool {
        let expected_hash = self.keccak.fixate(original_input);
        let actual_hash = hex::decode(&character.input_hash).unwrap_or_default();
        expected_hash == actual_hash
    }
}

impl Default for ECCFEngine {
    fn default() -> Self {
        Self::new()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_eccf_generation() {
        let engine = ECCFEngine::new();
        let input = b"Test input for ECCF";
        let complexity = 5;
        
        let character = engine.generate_character(input, complexity);
        
        assert_eq!(character.complexity, complexity);
        assert!(!character.ntt_coefficients.is_empty());
        assert!(!character.strokes.is_empty());
    }

    #[test]
    fn test_tashkeel_application() {
        let mut engine = ECCFEngine::new();
        let input = b"Test input with uncertainty";
        let mut character = engine.generate_character(input, 7);
        
        engine.apply_tashkeel(&mut character, 0.85, vec!["High complexity".to_string()]);
        
        assert!(character.tashkeel.is_some());
        assert_eq!(character.tashkeel.as_ref().unwrap().confidence, 0.85);
    }

    #[test]
    fn test_verification() {
        let engine = ECCFEngine::new();
        let input = b"Verified input";
        let character = engine.generate_character(input, 3);
        
        assert!(engine.verify_character(&character, input));
        assert!(!engine.verify_character(&character, b"Different input"));
    }

    #[test]
    fn test_parametric_scaling() {
        let engine = ECCFEngine::new();
        
        let low_complexity = engine.generate_character(b"Simple", 1);
        let high_complexity = engine.generate_character(b"Complex", 10);
        
        assert!(high_complexity.lattice_dimension >= low_complexity.lattice_dimension);
        assert!(high_complexity.modular_base >= low_complexity.modular_base);
    }
}
