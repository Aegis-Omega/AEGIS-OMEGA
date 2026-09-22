//! Calligraphic Renderer - SVG Generation for ECCF
//! 
//! Converts lattice strokes to SVG calligraphic rendering.

use crate::lattice_stroke::{LatticeStroke, StrokeType};
use crate::{ECCFCharacter, DiacriticPosition, DiacriticType};

/// RenderedCharacter - Intermediate representation for SVG output
#[derive(Debug, Clone)]
pub struct RenderedCharacter {
    pub svg_path: String,
    pub width: f64,
    pub height: f64,
}

/// CalligraphicRenderer - Converts strokes to SVG
pub struct CalligraphicRenderer;

impl CalligraphicRenderer {
    /// Create new renderer
    pub fn new() -> Self {
        Self
    }

    /// Render strokes to intermediate representation
    pub fn render_strokes(&self, strokes: &[LatticeStroke]) -> RenderedCharacter {
        let mut paths = Vec::new();
        let mut min_x = f64::INFINITY;
        let mut min_y = f64::INFINITY;
        let mut max_x = f64::NEG_INFINITY;
        let mut max_y = f64::NEG_INFINITY;

        for stroke in strokes {
            let path = self.stroke_to_path(stroke);
            paths.push(path);

            min_x = min_x.min(stroke.start.0).min(stroke.end.0);
            min_y = min_y.min(stroke.start.1).min(stroke.end.1);
            max_x = max_x.max(stroke.start.0).max(stroke.end.0);
            max_y = max_y.max(stroke.start.1).max(stroke.end.1);
        }

        let width = max_x - min_x + 1.0;
        let height = max_y - min_y + 1.0;

        RenderedCharacter {
            svg_path: paths.join(" "),
            width,
            height,
        }
    }

    /// Convert single stroke to SVG path command
    fn stroke_to_path(&self, stroke: &LatticeStroke) -> String {
        match stroke.stroke_type {
            StrokeType::Nuqta => {
                // Draw rhombic dot
                let cx = (stroke.start.0 + stroke.end.0) / 2.0;
                let cy = (stroke.start.1 + stroke.end.1) / 2.0;
                let size = stroke.width;
                
                format!(
                    "M {} {} L {} {} L {} {} L {} {} Z",
                    cx, cy - size,
                    cx + size, cy,
                    cx, cy + size,
                    cx - size, cy
                )
            }
            StrokeType::Alif => {
                // Draw vertical line with slight curve
                format!(
                    "M {} {} Q {} {} {} {}",
                    stroke.start.0, stroke.start.1,
                    (stroke.start.0 + stroke.end.0) / 2.0, stroke.start.1 + 1.0,
                    stroke.end.0, stroke.end.1
                )
            }
            StrokeType::Rasm => {
                // Draw curved flowing line
                let control_x = (stroke.start.0 + stroke.end.0) / 2.0 + stroke.width;
                let control_y = (stroke.start.1 + stroke.end.1) / 2.0;
                
                format!(
                    "M {} {} Q {} {} {} {}",
                    stroke.start.0, stroke.start.1,
                    control_x, control_y,
                    stroke.end.0, stroke.end.1
                )
            }
            StrokeType::Tashkeel => {
                // Small diacritic mark
                format!(
                    "M {} {} L {} {}",
                    stroke.start.0, stroke.start.1,
                    stroke.end.0, stroke.end.1
                )
            }
            StrokeType::Ornament => {
                // Decorative element
                format!(
                    "M {} {} C {} {} {} {} {} {}",
                    stroke.start.0, stroke.start.1,
                    stroke.end.0, stroke.start.1,
                    stroke.start.0, stroke.end.1,
                    stroke.end.0, stroke.end.1
                )
            }
        }
    }

    /// Compute diacritic positions based on confidence
    pub fn compute_diacritics(&self, strokes: &[LatticeStroke], confidence: f64) -> Vec<DiacriticPosition> {
        let mut diacritics = Vec::new();

        if strokes.is_empty() {
            return diacritics;
        }

        // Place diacritics based on confidence level
        let last_stroke = strokes.last().unwrap();
        
        if confidence < 0.5 {
            // Low confidence: add Sukun (no vowel) above
            diacritics.push(DiacriticPosition {
                x: last_stroke.end.0,
                y: last_stroke.end.1 - 1.5,
                diacritic_type: DiacriticType::Sukun,
            });
        } else if confidence < 0.75 {
            // Medium confidence: add Fatha above
            diacritics.push(DiacriticPosition {
                x: last_stroke.end.0,
                y: last_stroke.end.1 - 1.5,
                diacritic_type: DiacriticType::Fatha,
            });
        } else if confidence < 0.9 {
            // High confidence: add Damma above
            diacritics.push(DiacriticPosition {
                x: last_stroke.end.0,
                y: last_stroke.end.1 - 1.5,
                diacritic_type: DiacriticType::Damma,
            });
        } else {
            // Very high confidence: add Shadda (gemination) indicating certainty
            diacritics.push(DiacriticPosition {
                x: last_stroke.end.0,
                y: last_stroke.end.1 - 1.5,
                diacritic_type: DiacriticType::Shadda,
            });
        }

        diacritics
    }

    /// Convert ECCFCharacter to full SVG document
    pub fn to_svg(&self, character: &ECCFCharacter) -> String {
        let mut svg_content = String::new();
        
        // Add stroke paths
        svg_content.push_str(&character.strokes.iter()
            .map(|s| self.stroke_to_path(s))
            .collect::<Vec<_>>()
            .join(" "));

        // Add Tashkeel if present
        if let Some(ref tashkeel) = character.tashkeel {
            for diacritic in &tashkeel.diacritic_positions {
                let path = match diacritic.diacritic_type {
                    DiacriticType::Fatha => {
                        format!("M {} {} L {} {}", 
                            diacritic.x - 0.5, diacritic.y,
                            diacritic.x + 0.5, diacritic.y + 0.3)
                    }
                    DiacriticType::Kasra => {
                        format!("M {} {} L {} {}",
                            diacritic.x - 0.5, diacritic.y,
                            diacritic.x + 0.5, diacritic.y - 0.3)
                    }
                    DiacriticType::Damma => {
                        format!("M {} {} Q {} {} {} {}",
                            diacritic.x - 0.3, diacritic.y,
                            diacritic.x, diacritic.y - 0.5,
                            diacritic.x + 0.3, diacritic.y)
                    }
                    DiacriticType::Sukun => {
                        format!("M {} {} L {} {} M {} {} L {} {}",
                            diacritic.x - 0.4, diacritic.y,
                            diacritic.x + 0.4, diacritic.y,
                            diacritic.x - 0.4, diacritic.y + 0.2,
                            diacritic.x + 0.4, diacritic.y + 0.2)
                    }
                    DiacriticType::Shadda => {
                        format!("M {} {} Q {} {} {} {} M {} {} Q {} {} {} {}",
                            diacritic.x - 0.4, diacritic.y,
                            diacritic.x, diacritic.y - 0.4,
                            diacritic.x + 0.4, diacritic.y,
                            diacritic.x - 0.3, diacritic.y + 0.2,
                            diacritic.x, diacritic.y - 0.2,
                            diacritic.x + 0.3, diacritic.y + 0.2)
                    }
                    DiacriticType::Tanween => {
                        format!("M {} {} L {} {} M {} {} L {} {}",
                            diacritic.x - 0.5, diacritic.y,
                            diacritic.x + 0.5, diacritic.y + 0.3,
                            diacritic.x - 0.5, diacritic.y + 0.4,
                            diacritic.x + 0.5, diacritic.y + 0.7)
                    }
                };
                svg_content.push_str(&path);
            }
        }

        // Wrap in SVG document
        format!(
            r#"<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {} {}" width="{}" height="{}">
  <desc>ECCF Character - Complexity: {}, Lattice Dim: {}, Hash: {}</desc>
  <path d="{}" fill="none" stroke="#1a2b3c" stroke-width="0.1" stroke-linecap="round"/>
</svg>"#,
            character.lattice_dimension as f64 * 2.0,
            character.modular_base as f64 / 32768.0,
            character.lattice_dimension as f64 * 2.0 * 10.0,
            character.modular_base as f64 / 32768.0 * 10.0,
            character.complexity,
            character.lattice_dimension,
            &character.input_hash[..16],
            svg_content
        )
    }
}

impl Default for CalligraphicRenderer {
    fn default() -> Self {
        Self::new()
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::lattice_stroke::ModuleLattice;

    #[test]
    fn test_render_strokes() {
        let renderer = CalligraphicRenderer::new();
        let strokes = ModuleLattice::generate_strokes(&[100, 200, 300], 65537);
        
        let rendered = renderer.render_strokes(&strokes);
        
        assert!(!rendered.svg_path.is_empty());
        assert!(rendered.width > 0.0);
        assert!(rendered.height > 0.0);
    }

    #[test]
    fn test_compute_diacritics_low_confidence() {
        let renderer = CalligraphicRenderer::new();
        let strokes = ModuleLattice::generate_strokes(&[100], 65537);
        
        let diacritics = renderer.compute_diacritics(&strokes, 0.3);
        
        assert!(!diacritics.is_empty());
        assert_eq!(diacritics[0].diacritic_type, DiacriticType::Sukun);
    }

    #[test]
    fn test_compute_diacritics_high_confidence() {
        let renderer = CalligraphicRenderer::new();
        let strokes = ModuleLattice::generate_strokes(&[100], 65537);
        
        let diacritics = renderer.compute_diacritics(&strokes, 0.95);
        
        assert!(!diacritics.is_empty());
        assert_eq!(diacritics[0].diacritic_type, DiacriticType::Shadda);
    }

    #[test]
    fn test_svg_generation() {
        use crate::ECCFEngine;
        
        let engine = ECCFEngine::new();
        let character = engine.generate_character(b"Test", 5);
        let svg = engine.render_to_svg(&character);
        
        assert!(svg.contains("<svg"));
        assert!(svg.contains("</svg>"));
        assert!(svg.contains(&character.input_hash[..16]));
    }
}
