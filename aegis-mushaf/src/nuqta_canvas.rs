//! Nuqta Canvas — Proportional geometric layout for Arabic calligraphy
//!
//! EPISTEMIC TIER: T2 (engineering hypothesis)
//!
//! The nuqta (نقطة, dot) is the fundamental unit of classical Arabic calligraphy.
//! In the Kufic/Naskh systems, all letter dimensions are integer multiples of
//! the nuqta — the rhombus impression left by the reed pen held at 45°.
//!
//! Classical proportions (Kufic, after Ibn Muqla — 10th century CE):
//!   Alif height   H_A = 7 nuqtaat
//!   Letter width  W_L = variable, but baseline = 5 nuqtaat
//!   Line spacing  H_line = 10 nuqtaat (H_A + 3 nuqtaat descender space)
//!   Letter gap    Δ_L = 1 nuqta
//!   Nuqta dim.    d_N = 1 (the fundamental unit — all others are multiples)
//!
//! The positioning matrix M_layout maps each letter index in a line to its
//! bounding box: (x_origin, y_baseline, width, height) in nuqta units.
//! Arabic is laid out right-to-left; x_origin decreases with each letter.
//!
//! Constitutional invariants:
//! - All arithmetic is integer — no floating-point
//! - BTreeMap<u32, LetterBound> for deterministic iteration (position-keyed)
//! - layout_line() is a pure function — replay-safe
//! - Width per letter derived from LetterClass — BTreeMap lookup

use std::collections::BTreeMap;
use crate::tajweed_dfa::LetterClass;

/// Fundamental nuqta unit — all dimensions are integer multiples of this.
pub const D_N: u32 = 1;

/// Alif height in nuqtaat — the tallest letter, sets the vertical baseline.
pub const H_A: u32 = 7 * D_N;

/// Inter-letter horizontal gap in nuqtaat.
pub const DELTA_L: u32 = 1 * D_N;

/// Line height (baseline to baseline) in nuqtaat.
pub const H_LINE: u32 = 10 * D_N;

/// Bounding box of one letter on the canvas, in nuqta units.
/// Arabic is right-to-left: x_origin is the *right* edge of the letter.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub struct LetterBound {
    /// Right edge x-coordinate (RTL layout — origin at right margin).
    pub x_right: u32,
    /// Left edge x-coordinate = x_right − width.
    pub x_left: u32,
    /// Baseline y-coordinate (letters hang from the baseline).
    pub y_baseline: u32,
    /// Width in nuqtaat.
    pub width: u32,
    /// Height above baseline in nuqtaat.
    pub height: u32,
    /// Depth below baseline (descenders) in nuqtaat.
    pub depth: u32,
}

impl LetterBound {
    pub fn top(&self) -> u32 {
        self.y_baseline.saturating_sub(self.height)
    }
    pub fn bottom(&self) -> u32 {
        self.y_baseline + self.depth
    }
}

/// Width (in nuqtaat) for each letter class — classical Kufic proportions.
/// LetterClass determines the structural width category.
fn class_width(class: LetterClass) -> u32 {
    match class {
        LetterClass::NunSakin     => 5,
        LetterClass::Tanwin       => 4,
        LetterClass::ThroatLetter => 5,
        LetterClass::IkhfaLetter  => 4,
        LetterClass::IdghamLetter => 5,
        LetterClass::MaddLetter   => 7, // alif/madd letters are taller and wider
        LetterClass::QalqalaLetter => 4,
        LetterClass::Other        => 4,
    }
}

/// Height above baseline for each letter class (in nuqtaat).
fn class_height(class: LetterClass) -> u32 {
    match class {
        LetterClass::MaddLetter => H_A,     // alif, waw, ya — full height
        LetterClass::ThroatLetter => 6,      // some throat letters have tall forms
        _ => 5,                              // most letters sit mid-height
    }
}

/// Depth below baseline for each letter class (in nuqtaat).
fn class_depth(class: LetterClass) -> u32 {
    match class {
        LetterClass::IdghamLetter => 2, // ya/lam have descenders
        LetterClass::IkhfaLetter  => 1,
        _ => 0,
    }
}

/// The positioning matrix for one line of Arabic text.
/// BTreeMap keyed by letter index (0 = rightmost letter in RTL layout).
pub struct LayoutMatrix {
    pub bounds: BTreeMap<u32, LetterBound>,
    pub line_width: u32,
    pub y_baseline: u32,
}

impl LayoutMatrix {
    /// Canonical fingerprint — SHA-256 of all bounding boxes in index order.
    pub fn fingerprint(&self) -> [u8; 32] {
        use sha2::{Sha256, Digest};
        let mut h = Sha256::new();
        for (idx, b) in &self.bounds {
            h.update(idx.to_le_bytes());
            h.update(b.x_right.to_le_bytes());
            h.update(b.width.to_le_bytes());
            h.update(b.height.to_le_bytes());
            h.update(b.depth.to_le_bytes());
        }
        h.finalize().into()
    }
}

/// Pure layout function — maps a sequence of (codepoint, LetterClass) pairs
/// onto a LayoutMatrix. Right-to-left placement from x_margin.
///
/// `x_margin` — right-edge starting position (e.g., page width in nuqtaat).
/// `y_baseline` — baseline y-coordinate.
pub fn layout_line(
    letters: &[(u32, LetterClass)],
    x_margin: u32,
    y_baseline: u32,
) -> LayoutMatrix {
    let mut bounds = BTreeMap::new();
    let mut cursor = x_margin; // current right edge, moving leftward

    for (idx, &(_cp, class)) in letters.iter().enumerate() {
        let w = class_width(class);
        let h = class_height(class);
        let d = class_depth(class);

        let x_right = cursor;
        let x_left = x_right.saturating_sub(w);

        bounds.insert(idx as u32, LetterBound {
            x_right,
            x_left,
            y_baseline,
            width: w,
            height: h,
            depth: d,
        });

        // Advance cursor leftward: letter width + inter-letter gap
        cursor = x_left.saturating_sub(DELTA_L);
    }

    let line_width = x_margin.saturating_sub(cursor).saturating_sub(DELTA_L);

    LayoutMatrix { bounds, line_width, y_baseline }
}

/// Compute a multi-line layout for a full ayah, wrapping at `max_width` nuqtaat.
/// Returns one LayoutMatrix per line, spaced H_LINE nuqtaat apart.
pub fn layout_ayah(
    letters: &[(u32, LetterClass)],
    max_width: u32,
    x_margin: u32,
    y_start: u32,
) -> Vec<LayoutMatrix> {
    let mut lines: Vec<LayoutMatrix> = Vec::new();
    let mut line_start = 0usize;
    let mut line_y = y_start;

    while line_start < letters.len() {
        // Greedily fit as many letters as possible within max_width
        let mut cursor = max_width;
        let mut line_end = line_start;

        for i in line_start..letters.len() {
            let w = class_width(letters[i].1);
            let required = w + if i > line_start { DELTA_L } else { 0 };
            if cursor < required {
                break;
            }
            cursor = cursor.saturating_sub(required);
            line_end = i + 1;
        }

        // At least one letter per line (avoid infinite loop on very narrow canvas)
        if line_end == line_start {
            line_end = line_start + 1;
        }

        let matrix = layout_line(&letters[line_start..line_end], x_margin, line_y);
        lines.push(matrix);
        line_start = line_end;
        line_y += H_LINE;
    }

    lines
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::tajweed_dfa::LetterClass;

    fn sample_letters(n: usize) -> Vec<(u32, LetterClass)> {
        let classes = [
            LetterClass::MaddLetter,
            LetterClass::ThroatLetter,
            LetterClass::IkhfaLetter,
            LetterClass::QalqalaLetter,
            LetterClass::IdghamLetter,
        ];
        (0..n).map(|i| (0x0627 + i as u32, classes[i % classes.len()])).collect()
    }

    #[test]
    fn constants_are_correct() {
        assert_eq!(D_N, 1);
        assert_eq!(H_A, 7);
        assert_eq!(DELTA_L, 1);
        assert_eq!(H_LINE, 10);
    }

    #[test]
    fn single_letter_layout() {
        let letters = vec![(0x0627, LetterClass::MaddLetter)];
        let m = layout_line(&letters, 100, 50);
        assert_eq!(m.bounds.len(), 1);
        let b = &m.bounds[&0];
        assert_eq!(b.x_right, 100);
        assert_eq!(b.width, 7); // MaddLetter width
        assert_eq!(b.height, H_A); // full alif height
        assert_eq!(b.x_left, 93); // 100 − 7
    }

    #[test]
    fn rtl_placement_decreases_x() {
        let letters = sample_letters(3);
        let m = layout_line(&letters, 100, 30);
        // Each letter's x_right must be < the previous letter's x_right
        let bounds: Vec<_> = (0..3).map(|i| m.bounds[&i].x_right).collect();
        assert!(bounds[0] > bounds[1]);
        assert!(bounds[1] > bounds[2]);
    }

    #[test]
    fn letter_gap_is_delta_l() {
        let letters = vec![
            (0x627, LetterClass::MaddLetter),   // width=7
            (0x647, LetterClass::ThroatLetter), // width=5
        ];
        let m = layout_line(&letters, 100, 30);
        let b0 = &m.bounds[&0];
        let b1 = &m.bounds[&1];
        // b0: x_right=100, x_left=93. b1: x_right = 93 − DELTA_L = 92
        assert_eq!(b1.x_right, b0.x_left.saturating_sub(DELTA_L));
    }

    #[test]
    fn layout_deterministic_3x() {
        let make = || {
            let letters = sample_letters(5);
            layout_line(&letters, 200, 40).fingerprint()
        };
        assert_eq!(make(), make());
        assert_eq!(make(), make());
    }

    #[test]
    fn different_inputs_different_fingerprint() {
        let a = layout_line(&sample_letters(3), 200, 40).fingerprint();
        let b = layout_line(&sample_letters(4), 200, 40).fingerprint();
        assert_ne!(a, b);
    }

    #[test]
    fn btreemap_keys_in_order() {
        let letters = sample_letters(5);
        let m = layout_line(&letters, 200, 40);
        let keys: Vec<u32> = m.bounds.keys().copied().collect();
        assert_eq!(keys, vec![0, 1, 2, 3, 4]);
    }

    #[test]
    fn madd_letter_full_height() {
        let letters = vec![(0x627, LetterClass::MaddLetter)];
        let m = layout_line(&letters, 100, 50);
        assert_eq!(m.bounds[&0].height, H_A);
    }

    #[test]
    fn depth_below_baseline_for_idgham() {
        let letters = vec![(0x64A, LetterClass::IdghamLetter)];
        let m = layout_line(&letters, 100, 50);
        assert_eq!(m.bounds[&0].depth, 2);
    }

    #[test]
    fn top_and_bottom_helpers() {
        let b = LetterBound {
            x_right: 100, x_left: 93,
            y_baseline: 50,
            width: 7, height: 7, depth: 2,
        };
        assert_eq!(b.top(), 43);
        assert_eq!(b.bottom(), 52);
    }

    #[test]
    fn layout_ayah_produces_multiple_lines() {
        // 20 letters, max_width=30 nuqtaat → should wrap into multiple lines
        let letters = sample_letters(20);
        let lines = layout_ayah(&letters, 30, 100, 10);
        assert!(lines.len() > 1);
    }

    #[test]
    fn layout_ayah_line_spacing() {
        let letters = sample_letters(10);
        let lines = layout_ayah(&letters, 30, 100, 10);
        if lines.len() >= 2 {
            assert_eq!(lines[1].y_baseline - lines[0].y_baseline, H_LINE);
        }
    }

    #[test]
    fn layout_ayah_covers_all_letters() {
        let letters = sample_letters(15);
        let lines = layout_ayah(&letters, 40, 200, 10);
        let total: usize = lines.iter().map(|l| l.bounds.len()).sum();
        assert_eq!(total, 15);
    }
}
