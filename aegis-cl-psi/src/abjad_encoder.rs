//! Gate 215: Abjad Letter Encoder
//! EPISTEMIC TIER: T2 (engineering hypothesis)
//!
//! Encodes letter sequences (via Abjad integer values) into AEGIS routing structures.
//! The Abjad system assigns integer values to letters — functionally equivalent to
//! any bijective letter→integer mapping (like ASCII). The math operates on the integers.
//!
//! For طارق (Tariq): ط=9, ا=1, ر=200, ق=100
//!   sum=310,        DR(sum)=4,       Hexadic (period-6 entry path)
//!   product=180000, DR(product)=9,   Triadic fixed-point (convergence attractor)
//!   Dodecagon nodes: [9, 1, 8, 4],   name node = 310 % 12 = 10
//!
//! Constitutional invariant: no floating-point arithmetic. All routing via integer ops.

use crate::dodecagonal_router::{build_dodecagonal_mesh, ring_distance, route, DODECAGON_NODES};
use crate::vortex_classifier::{classify_vortex, digital_root, vortex_cycle_length, VortexFamily};
use crate::proportional_metric::SQUARED_SUM_K8;

/// One letter's encoding record.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct LetterRecord {
    pub abjad_value: u64,
    pub digital_root: u8,
    pub family: VortexFamily,
    pub dodecagon_node: u8,   // abjad_value % DODECAGON_NODES
    pub opposite_node: u8,    // (dodecagon_node + 6) % 12
    pub dot_count: u8,        // calligraphic dots (Nuqta beneath/above letter)
    pub cycle_length: Option<u8>,
}

/// Full encoding of a letter sequence.
#[derive(Debug, Clone)]
pub struct AbjadEncoding {
    pub letters: Vec<LetterRecord>,
    pub abjad_sum: u64,
    pub abjad_product: u64,
    pub sum_dr: u8,
    pub product_dr: u8,
    pub sum_family: VortexFamily,
    pub product_family: VortexFamily,
    pub name_node: u8,          // abjad_sum % 12
    pub routing_path: Vec<u8>,  // dodecagonal path through letter nodes
    /// True if DR(sum) == DR(product): name has a unified attractor
    pub is_self_referential: bool,
}

#[derive(Debug)]
pub struct AbjadEncoderError(pub &'static str);

/// A single letter specification: (abjad_value, dot_count)
pub type LetterSpec = (u64, u8);

/// Encode a sequence of letters into an AbjadEncoding.
///
/// # Arguments
/// * `letters` - slice of (abjad_value, dot_count) pairs, in reading order
///
/// Returns Err if letters is empty or any abjad_value is 0.
pub fn encode(letters: &[LetterSpec]) -> Result<AbjadEncoding, AbjadEncoderError> {
    if letters.is_empty() {
        return Err(AbjadEncoderError("Letter sequence must not be empty"));
    }
    if letters.iter().any(|&(v, _)| v == 0) {
        return Err(AbjadEncoderError("Abjad value 0 is not defined"));
    }

    let mesh = build_dodecagonal_mesh();
    let mut records = Vec::with_capacity(letters.len());
    let mut abjad_sum: u64 = 0;
    let mut abjad_product: u64 = 1;

    for &(val, dots) in letters {
        let dr = digital_root(val);
        let family = classify_vortex(val);
        let node = (val % DODECAGON_NODES as u64) as u8;
        let opposite = (node + 6) % DODECAGON_NODES;
        records.push(LetterRecord {
            abjad_value: val,
            digital_root: dr,
            family,
            dodecagon_node: node,
            opposite_node: opposite,
            dot_count: dots,
            cycle_length: vortex_cycle_length(val),
        });
        abjad_sum = abjad_sum.saturating_add(val);
        abjad_product = abjad_product.saturating_mul(val);
    }

    // Build routing path through each letter's dodecagon node in sequence
    let mut routing_path: Vec<u8> = Vec::new();
    if records.len() == 1 {
        routing_path = vec![records[0].dodecagon_node];
    } else {
        for window in records.windows(2) {
            let segment = route(&mesh, window[0].dodecagon_node, window[1].dodecagon_node);
            if routing_path.is_empty() {
                routing_path.extend_from_slice(&segment);
            } else {
                // Avoid duplicating the junction node
                routing_path.extend_from_slice(&segment[1..]);
            }
        }
    }

    let sum_dr = digital_root(abjad_sum);
    let product_dr = digital_root(abjad_product);
    let sum_family = classify_vortex(abjad_sum);
    let product_family = classify_vortex(abjad_product);
    let name_node = (abjad_sum % DODECAGON_NODES as u64) as u8;
    let is_self_referential = sum_dr == product_dr;

    Ok(AbjadEncoding {
        letters: records,
        abjad_sum,
        abjad_product,
        sum_dr,
        product_dr,
        sum_family,
        product_family,
        name_node,
        routing_path,
        is_self_referential,
    })
}

/// Canonical Abjad values for طارق (Tariq).
pub const TARIQ_LETTERS: &[LetterSpec] = &[
    (9,   0),  // ط (Tah)   — no dots
    (1,   0),  // ا (Alif)  — no dots
    (200, 0),  // ر (Ra)    — no dots
    (100, 2),  // ق (Qaf)   — 2 dots below
];

/// Pre-compute the canonical encoding for طارق.
pub fn tariq_encoding() -> AbjadEncoding {
    encode(TARIQ_LETTERS).expect("TARIQ_LETTERS is valid by construction")
}

/// Returns the ring distance between two letters' dodecagon nodes.
pub fn letter_distance(a: &LetterRecord, b: &LetterRecord) -> u8 {
    ring_distance(a.dodecagon_node, b.dodecagon_node)
}

/// True if the encoding's product converges to the triadic fixed point (DR=9).
/// DR(product)=9 means the name's multiplicative signature is the axis of stability.
pub fn is_triadic_attractor(enc: &AbjadEncoding) -> bool {
    enc.product_dr == 9
}

/// The squared-sum constant 204 divided by the name's dodecagon node
/// gives a proportionality metric. Returns None if name_node == 0.
pub fn squared_sum_ratio(enc: &AbjadEncoding) -> Option<u64> {
    if enc.name_node == 0 {
        None
    } else {
        Some(SQUARED_SUM_K8 / enc.name_node as u64)
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn tariq() -> AbjadEncoding {
        tariq_encoding()
    }

    #[test]
    fn test_tariq_sum() {
        let enc = tariq();
        assert_eq!(enc.abjad_sum, 310);   // 9+1+200+100
    }

    #[test]
    fn test_tariq_sum_dr() {
        let enc = tariq();
        assert_eq!(enc.sum_dr, 4);
        assert_eq!(enc.sum_family, VortexFamily::Hexadic);
    }

    #[test]
    fn test_tariq_product_dr() {
        let enc = tariq();
        // 9×1×200×100 = 180000, DR(180000) = 9
        assert_eq!(enc.product_dr, 9);
        assert_eq!(enc.product_family, VortexFamily::Triadic);
    }

    #[test]
    fn test_tariq_is_triadic_attractor() {
        let enc = tariq();
        assert!(is_triadic_attractor(&enc));
    }

    #[test]
    fn test_tariq_name_node() {
        let enc = tariq();
        assert_eq!(enc.name_node, 10);  // 310 % 12 = 10
    }

    #[test]
    fn test_tariq_first_letter() {
        let enc = tariq();
        let tah = &enc.letters[0];
        assert_eq!(tah.abjad_value, 9);
        assert_eq!(tah.digital_root, 9);
        assert_eq!(tah.family, VortexFamily::Triadic);
        assert_eq!(tah.dodecagon_node, 9);
        assert_eq!(tah.opposite_node, 3);
        assert_eq!(tah.dot_count, 0);
    }

    #[test]
    fn test_tariq_qaf_dots() {
        let enc = tariq();
        let qaf = &enc.letters[3];
        assert_eq!(qaf.abjad_value, 100);
        assert_eq!(qaf.dot_count, 2);
        assert_eq!(qaf.dodecagon_node, 4);  // 100 % 12 = 4
    }

    #[test]
    fn test_tariq_not_self_referential() {
        let enc = tariq();
        // sum_dr=4, product_dr=9 — different families
        assert!(!enc.is_self_referential);
    }

    #[test]
    fn test_routing_path_starts_at_first_node() {
        let enc = tariq();
        assert_eq!(enc.routing_path[0], enc.letters[0].dodecagon_node);
    }

    #[test]
    fn test_routing_path_ends_at_last_node() {
        let enc = tariq();
        assert_eq!(*enc.routing_path.last().unwrap(), enc.letters.last().unwrap().dodecagon_node);
    }

    #[test]
    fn test_letter_distance() {
        let enc = tariq();
        // ط at node 9, ا at node 1: ring_distance(9,1)=min(8,4)=4
        let d = letter_distance(&enc.letters[0], &enc.letters[1]);
        assert_eq!(d, 4);  // ring_distance(9,1) = min(8,12-8) = 4
    }

    #[test]
    fn test_squared_sum_ratio() {
        let enc = tariq();
        // name_node=10, 204/10=20
        assert_eq!(squared_sum_ratio(&enc), Some(20));
    }

    #[test]
    fn test_empty_sequence_rejected() {
        assert!(encode(&[]).is_err());
    }

    #[test]
    fn test_zero_value_rejected() {
        assert!(encode(&[(0, 0)]).is_err());
    }

    #[test]
    fn test_single_letter() {
        let enc = encode(&[(9, 0)]).unwrap();
        assert_eq!(enc.routing_path, vec![9]);
    }
}
