//! AbjadEncoder v0.1 — Canonical Freeze.
//!
//! This module is the exact integer/modular kernel specified by
//! `docs/specs/abjad-encoder-v0.1-canonical-freeze.md`.
//!
//! Authority boundary:
//! - arithmetic: exact / fail-closed;
//! - mod-9 orbit classification: exact;
//! - mod-12 routing: deterministic convention;
//! - semantic/identity authority: projection-bounded.

use crate::dodecagonal_router::{build_dodecagonal_mesh, route, DODECAGON_NODES};
use serde::{Deserialize, Deserializer, Serialize, Serializer};
use std::fmt;

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "SCREAMING_SNAKE_CASE")]
pub enum AuthorityDomain {
    RawText,
    CanonicalLetterSequence,
    AggregateProfile,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
pub enum ExactU64 {
    Value(u64),
    Overflow,
}

impl ExactU64 {
    fn checked_add(self, rhs: u64) -> Self {
        match self {
            Self::Value(lhs) => lhs
                .checked_add(rhs)
                .map(Self::Value)
                .unwrap_or(Self::Overflow),
            Self::Overflow => Self::Overflow,
        }
    }

    fn checked_mul(self, rhs: u64) -> Self {
        match self {
            Self::Value(lhs) => lhs
                .checked_mul(rhs)
                .map(Self::Value)
                .unwrap_or(Self::Overflow),
            Self::Overflow => Self::Overflow,
        }
    }
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
pub enum Mod9Orbit {
    O1,
    O2,
    O6,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct Mod9Profile {
    pub residue: u8,
    pub orbit: Mod9Orbit,
    pub cycle_length: u8,
}

fn profile_mod9_residue(residue: u8) -> Mod9Profile {
    debug_assert!(residue < 9);
    match residue {
        0 => Mod9Profile {
            residue,
            orbit: Mod9Orbit::O1,
            cycle_length: 1,
        },
        3 | 6 => Mod9Profile {
            residue,
            orbit: Mod9Orbit::O2,
            cycle_length: 2,
        },
        1 | 2 | 4 | 5 | 7 | 8 => Mod9Profile {
            residue,
            orbit: Mod9Orbit::O6,
            cycle_length: 6,
        },
        _ => unreachable!("residue is reduced modulo 9"),
    }
}

pub fn profile_mod9(value: u64) -> Mod9Profile {
    profile_mod9_residue((value % 9) as u8)
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct CanonicalLetter {
    pub canonical_letter_id: u32,
    pub abjad_value: u64,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash)]
pub struct Digest32(pub [u8; 32]);

impl Serialize for Digest32 {
    fn serialize<S>(&self, serializer: S) -> Result<S::Ok, S::Error>
    where
        S: Serializer,
    {
        const HEX: &[u8; 16] = b"0123456789abcdef";
        let mut out = String::with_capacity(71);
        out.push_str("sha256:");
        for byte in self.0 {
            out.push(HEX[(byte >> 4) as usize] as char);
            out.push(HEX[(byte & 0x0f) as usize] as char);
        }
        serializer.serialize_str(&out)
    }
}

struct Digest32Visitor;

impl<'de> serde::de::Visitor<'de> for Digest32Visitor {
    type Value = Digest32;

    fn expecting(&self, formatter: &mut fmt::Formatter<'_>) -> fmt::Result {
        formatter.write_str("sha256:<64 lowercase hex>")
    }

    fn visit_str<E>(self, value: &str) -> Result<Self::Value, E>
    where
        E: serde::de::Error,
    {
        let hex = value
            .strip_prefix("sha256:")
            .ok_or_else(|| E::custom("digest must start with sha256:"))?;
        if hex.len() != 64 {
            return Err(E::custom("digest must contain exactly 64 hex characters"));
        }
        if !hex
            .bytes()
            .all(|b| b.is_ascii_digit() || (b'a'..=b'f').contains(&b))
        {
            return Err(E::custom("digest must use lowercase hexadecimal only"));
        }

        let bytes = hex.as_bytes();
        let mut digest = [0u8; 32];
        for (index, slot) in digest.iter_mut().enumerate() {
            let hi = decode_hex(bytes[index * 2]).expect("validated lowercase hex");
            let lo = decode_hex(bytes[index * 2 + 1]).expect("validated lowercase hex");
            *slot = (hi << 4) | lo;
        }
        Ok(Digest32(digest))
    }
}

impl<'de> Deserialize<'de> for Digest32 {
    fn deserialize<D>(deserializer: D) -> Result<Self, D::Error>
    where
        D: Deserializer<'de>,
    {
        deserializer.deserialize_str(Digest32Visitor)
    }
}

fn decode_hex(byte: u8) -> Option<u8> {
    match byte {
        b'0'..=b'9' => Some(byte - b'0'),
        b'a'..=b'f' => Some(byte - b'a' + 10),
        _ => None,
    }
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct AbjadEncoderInputV01 {
    pub letters: Vec<CanonicalLetter>,
    pub alphabet_spec_digest: Digest32,
    pub normalization_spec_digest: Digest32,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct FullProjectionV01 {
    pub authority_domain: AuthorityDomain,
    pub canonical_letter_ids: Vec<u32>,
    pub abjad_values: Vec<u64>,
    pub dodecagon_projection: Vec<u8>,
    pub routing_path: Vec<u8>,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct AggregateProfileV01 {
    pub authority_domain: AuthorityDomain,
    pub exact_sum: ExactU64,
    pub exact_product: ExactU64,
    pub sum_mod9: Mod9Profile,
    pub product_mod9: Mod9Profile,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct AbjadEncodingV01 {
    pub full: FullProjectionV01,
    pub aggregate: AggregateProfileV01,
    pub alphabet_spec_digest: Digest32,
    pub normalization_spec_digest: Digest32,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum AbjadEncoderV01Error {
    EmptySequence,
    ZeroAbjadValue,
}

pub fn encode_canonical(input: &AbjadEncoderInputV01) -> Result<AbjadEncodingV01, AbjadEncoderV01Error> {
    if input.letters.is_empty() {
        return Err(AbjadEncoderV01Error::EmptySequence);
    }
    if input.letters.iter().any(|letter| letter.abjad_value == 0) {
        return Err(AbjadEncoderV01Error::ZeroAbjadValue);
    }

    let mut exact_sum = ExactU64::Value(0);
    let mut exact_product = ExactU64::Value(1);
    let mut sum_mod9 = 0u8;
    let mut product_mod9 = 1u8;

    let mut canonical_letter_ids = Vec::with_capacity(input.letters.len());
    let mut abjad_values = Vec::with_capacity(input.letters.len());
    let mut dodecagon_projection = Vec::with_capacity(input.letters.len());

    for letter in &input.letters {
        let value = letter.abjad_value;

        // The modular channel is intentionally independent of the exact channel.
        // It must continue even after an exact accumulator becomes Overflow.
        sum_mod9 = ((sum_mod9 as u16 + (value % 9) as u16) % 9) as u8;
        product_mod9 = ((product_mod9 as u16 * (value % 9) as u16) % 9) as u8;

        exact_sum = exact_sum.checked_add(value);
        exact_product = exact_product.checked_mul(value);

        canonical_letter_ids.push(letter.canonical_letter_id);
        abjad_values.push(value);
        dodecagon_projection.push((value % DODECAGON_NODES as u64) as u8);
    }

    let mesh = build_dodecagonal_mesh();
    let routing_path = build_routing_path(&mesh, &dodecagon_projection);

    Ok(AbjadEncodingV01 {
        full: FullProjectionV01 {
            authority_domain: AuthorityDomain::CanonicalLetterSequence,
            canonical_letter_ids,
            abjad_values,
            dodecagon_projection,
            routing_path,
        },
        aggregate: AggregateProfileV01 {
            authority_domain: AuthorityDomain::AggregateProfile,
            exact_sum,
            exact_product,
            sum_mod9: profile_mod9_residue(sum_mod9),
            product_mod9: profile_mod9_residue(product_mod9),
        },
        alphabet_spec_digest: input.alphabet_spec_digest,
        normalization_spec_digest: input.normalization_spec_digest,
    })
}

fn build_routing_path(
    mesh: &crate::dodecagonal_router::DodecagonalMesh,
    nodes: &[u8],
) -> Vec<u8> {
    if nodes.len() == 1 {
        return vec![nodes[0]];
    }

    let mut routing_path = Vec::new();
    for window in nodes.windows(2) {
        let segment = route(mesh, window[0], window[1]);
        if routing_path.is_empty() {
            routing_path.extend_from_slice(&segment);
        } else {
            routing_path.extend_from_slice(&segment[1..]);
        }
    }
    routing_path
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum ObservabilityAuthorityError {
    ObservabilityAuthorityBreach,
}

pub fn authorize_inequality_from_aggregate(
    lhs: &AggregateProfileV01,
    rhs: &AggregateProfileV01,
) -> Result<(), ObservabilityAuthorityError> {
    if lhs == rhs {
        Err(ObservabilityAuthorityError::ObservabilityAuthorityBreach)
    } else {
        Ok(())
    }
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub struct Rational {
    numerator: i64,
    denominator: u64,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum RationalError {
    ZeroDenominator,
    Overflow,
}

impl Rational {
    pub fn new(numerator: i64, denominator: u64) -> Result<Self, RationalError> {
        if denominator == 0 {
            return Err(RationalError::ZeroDenominator);
        }
        let gcd = gcd_u64(numerator.unsigned_abs(), denominator);
        let reduced_num = (numerator as i128) / (gcd as i128);
        let reduced_den = denominator / gcd;
        let numerator = i64::try_from(reduced_num).map_err(|_| RationalError::Overflow)?;
        Ok(Self {
            numerator,
            denominator: reduced_den,
        })
    }

    fn checked_sub(self, rhs: Self) -> Result<Self, RationalError> {
        let lhs_scaled = (self.numerator as i128) * (rhs.denominator as i128);
        let rhs_scaled = (rhs.numerator as i128) * (self.denominator as i128);
        let numerator = lhs_scaled
            .checked_sub(rhs_scaled)
            .ok_or(RationalError::Overflow)?;
        let denominator = (self.denominator as u128)
            .checked_mul(rhs.denominator as u128)
            .ok_or(RationalError::Overflow)?;

        let gcd = gcd_u128(numerator.unsigned_abs(), denominator);
        let reduced_num = numerator / gcd as i128;
        let reduced_den = denominator / gcd;
        let numerator = i64::try_from(reduced_num).map_err(|_| RationalError::Overflow)?;
        let denominator = u64::try_from(reduced_den).map_err(|_| RationalError::Overflow)?;
        Self::new(numerator, denominator)
    }

    fn is_nonnegative(self) -> bool {
        self.numerator >= 0
    }

    fn is_positive(self) -> bool {
        self.numerator > 0
    }
}

fn gcd_u64(mut a: u64, mut b: u64) -> u64 {
    while b != 0 {
        let remainder = a % b;
        a = b;
        b = remainder;
    }
    a
}

fn gcd_u128(mut a: u128, mut b: u128) -> u128 {
    while b != 0 {
        let remainder = a % b;
        a = b;
        b = remainder;
    }
    a
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum ParetoModeAError {
    ProfileUndefined,
    ArithmeticOverflow,
}

impl From<RationalError> for ParetoModeAError {
    fn from(_: RationalError) -> Self {
        Self::ArithmeticOverflow
    }
}

type ModeAFeatures = (Rational, Rational, Rational);

fn mode_a_features(orbit: Mod9Orbit) -> Result<ModeAFeatures, ParetoModeAError> {
    match orbit {
        Mod9Orbit::O6 => Ok((
            Rational::new(6, 1)?,
            Rational::new(1, 2)?,
            Rational::new(-1, 9)?,
        )),
        Mod9Orbit::O1 => Ok((
            Rational::new(1, 1)?,
            Rational::new(0, 1)?,
            Rational::new(-2, 3)?,
        )),
        Mod9Orbit::O2 => Err(ParetoModeAError::ProfileUndefined),
    }
}

pub fn mode_a_delta(
    lhs: Mod9Orbit,
    rhs: Mod9Orbit,
) -> Result<ModeAFeatures, ParetoModeAError> {
    let left = mode_a_features(lhs)?;
    let right = mode_a_features(rhs)?;
    Ok((
        left.0.checked_sub(right.0)?,
        left.1.checked_sub(right.1)?,
        left.2.checked_sub(right.2)?,
    ))
}

pub fn mode_a_dominates(lhs: Mod9Orbit, rhs: Mod9Orbit) -> Result<bool, ParetoModeAError> {
    let delta = mode_a_delta(lhs, rhs)?;
    Ok(
        delta.0.is_nonnegative()
            && delta.1.is_nonnegative()
            && delta.2.is_nonnegative()
            && (delta.0.is_positive() || delta.1.is_positive() || delta.2.is_positive()),
    )
}
