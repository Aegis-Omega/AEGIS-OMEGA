//! Module Lattice - Calligraphic Stroke Generation
//! 
//! Maps NTT coefficients to calligraphic strokes following CRYSTALS lattice structure.

use serde::{Serialize, Deserialize};

/// LatticeStroke - Fundamental calligraphic unit derived from lattice point
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct LatticeStroke {
    /// Start point (x, y)
    pub start: (f64, f64),
    /// End point (x, y)
    pub end: (f64, f64),
    /// Stroke width (derived from coefficient magnitude)
    pub width: f64,
    /// Stroke type (Nuqta, Alif, Rasm, etc.)
    pub stroke_type: StrokeType,
    /// Coefficient value that generated this stroke
    pub coefficient: i16,
}

/// Types of calligraphic strokes
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
pub enum StrokeType {
    /// Nuqta - Atomic dot (Dimension 0)
    Nuqta,
    /// Alif - Vertical axis (Dimension 1)
    Alif,
    /// Rasm - Curved flow (Dimension 2)
    Rasm,
    /// Tashkeel - Diacritic mark (Dimension 3)
    Tashkeel,
    /// Ornament - Decorative element
    Ornament,
}

/// ModuleLattice - Generates strokes from NTT coefficients
pub struct ModuleLattice;

impl ModuleLattice {
    /// Generate calligraphic strokes from NTT coefficients
    pub fn generate_strokes(coefficients: &[i16], modular_base: u64) -> Vec<LatticeStroke> {
        let mut strokes = Vec::new();
        
        if coefficients.is_empty() {
            return strokes;
        }

        // First coefficient always generates Nuqta (atomic truth)
        if let Some(&first_coeff) = coefficients.first() {
            let nuqta = Self::generate_nuqta(first_coeff, modular_base);
            strokes.push(nuqta);
        }

        // Generate Alif (vertical axis) from second coefficient if present
        if coefficients.len() > 1 {
            let alif = Self::generate_alif(coefficients[1], modular_base, &strokes[0]);
            strokes.push(alif);
        }

        // Generate Rasm (flowing connections) from remaining coefficients
        for i in 2..coefficients.len() {
            let rasm = Self::generate_rasm(
                coefficients[i],
                modular_base,
                strokes.last().map(|s| s.end).unwrap_or((0.0, 0.0)),
            );
            strokes.push(rasm);
        }

        strokes
    }

    /// Generate Nuqta stroke (atomic dot)
    fn generate_nuqta(coefficient: i16, modular_base: u64) -> LatticeStroke {
        let normalized = Self::normalize_coefficient(coefficient, modular_base);
        let size = 0.5 + normalized * 0.5; // 0.5 to 1.0
        
        LatticeStroke {
            start: (0.0, 0.0),
            end: (size, size),
            width: size * 0.3,
            stroke_type: StrokeType::Nuqta,
            coefficient,
        }
    }

    /// Generate Alif stroke (vertical axis)
    fn generate_alif(coefficient: i16, modular_base: u64, nuqta: &LatticeStroke) -> LatticeStroke {
        let normalized = Self::normalize_coefficient(coefficient, modular_base);
        let height = 7.0 + normalized * 2.0; // Traditional Alif is 7-9 Nuqtas high
        
        LatticeStroke {
            start: nuqta.end,
            end: (nuqta.end.0, nuqta.end.1 + height),
            width: 0.3 + normalized * 0.2,
            stroke_type: StrokeType::Alif,
            coefficient,
        }
    }

    /// Generate Rasm stroke (flowing connection)
    fn generate_rasm(coefficient: i16, modular_base: u64, start: (f64, f64)) -> LatticeStroke {
        let normalized = Self::normalize_coefficient(coefficient, modular_base);
        
        // Create curved path based on coefficient
        let angle = normalized * std::f64::consts::PI / 4.0;
        let length = 2.0 + normalized;
        
        let end_x = start.0 + length * angle.cos();
        let end_y = start.1 + length * angle.sin();
        
        LatticeStroke {
            start,
            end: (end_x, end_y),
            width: 0.2 + normalized.abs() * 0.15,
            stroke_type: StrokeType::Rasm,
            coefficient,
        }
    }

    /// Normalize coefficient to [0, 1] range
    fn normalize_coefficient(coefficient: i16, modular_base: u64) -> f64 {
        let centered = coefficient as f64 + 8192.0;
        let normalized = centered / 16384.0;
        normalized.clamp(0.0, 1.0)
    }

    /// Compute bounding box for all strokes
    pub fn compute_bounds(strokes: &[LatticeStroke]) -> ((f64, f64), (f64, f64)) {
        if strokes.is_empty() {
            return ((0.0, 0.0), (1.0, 1.0));
        }

        let mut min_x = f64::INFINITY;
        let mut min_y = f64::INFINITY;
        let mut max_x = f64::NEG_INFINITY;
        let mut max_y = f64::NEG_INFINITY;

        for stroke in strokes {
            min_x = min_x.min(stroke.start.0).min(stroke.end.0);
            min_y = min_y.min(stroke.start.1).min(stroke.end.1);
            max_x = max_x.max(stroke.start.0).max(stroke.end.0);
            max_y = max_y.max(stroke.start.1).max(stroke.end.1);
        }

        // Add padding
        let padding = 0.5;
        ((min_x - padding, min_y - padding), (max_x + padding, max_y + padding))
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_generate_strokes_empty() {
        let strokes = ModuleLattice::generate_strokes(&[], 65537);
        assert!(strokes.is_empty());
    }

    #[test]
    fn test_generate_strokes_single() {
        let strokes = ModuleLattice::generate_strokes(&[100], 65537);
        assert_eq!(strokes.len(), 1);
        assert_eq!(strokes[0].stroke_type, StrokeType::Nuqta);
    }

    #[test]
    fn test_generate_strokes_multiple() {
        let coeffs: Vec<i16> = vec![100, -50, 200, -100, 300];
        let strokes = ModuleLattice::generate_strokes(&coeffs, 65537);
        
        assert_eq!(strokes.len(), 5);
        assert_eq!(strokes[0].stroke_type, StrokeType::Nuqta);
        assert_eq!(strokes[1].stroke_type, StrokeType::Alif);
        assert_eq!(strokes[2].stroke_type, StrokeType::Rasm);
    }

    #[test]
    fn test_compute_bounds() {
        let strokes = ModuleLattice::generate_strokes(&[100, 200, 300], 65537);
        let (min, max) = ModuleLattice::compute_bounds(&strokes);
        
        assert!(min.0 <= 0.0);
        assert!(min.1 <= 0.0);
        assert!(max.0 > 0.0);
        assert!(max.1 > 0.0);
    }

    #[test]
    fn test_stroke_connectivity() {
        let coeffs: Vec<i16> = vec![100, 200, 300, 400];
        let strokes = ModuleLattice::generate_strokes(&coeffs, 65537);
        
        // Verify Rasm strokes connect to previous stroke end
        for i in 1..strokes.len() {
            if strokes[i].stroke_type == StrokeType::Rasm {
                assert_eq!(strokes[i].start, strokes[i - 1].end);
            }
        }
    }
}
