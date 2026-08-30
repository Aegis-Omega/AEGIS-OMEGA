//! # Constitutional Execution Substrate
//!
//! Deterministic replay-verifiable enforcement primitives for provenance continuity,
//! invariant validation, entropy containment, and schema-governed archival persistence.
//!
//! EPISTEMIC TIER: T0
//! TRACEABILITY: docs/TRACEABILITY.md → crates/constitutional-substrate/
//! ONTOLOGY: docs/ONTOLOGY.md — all exported types map to a registered canonical term
//!
//! ## Scope
//! - Deterministic replay primitives
//! - Invariant-safe fixed-point arithmetic (Q16.16)
//! - Append-only replay ledger primitives
//! - Entropy boundary primitives
//! - Verifier attestation primitives
//! - Schema-versioned archive primitives
//!
//! ## Non-Scope (explicitly excluded)
//! Cognition claims, autonomous reasoning, ontology authority, semantic generation,
//! recursive abstraction logic, universal architecture claims.
//!
//! ## Determinism Guarantee
//! All numeric computation uses Q16.16 fixed-point integer arithmetic.
//! No floating-point arithmetic appears anywhere in this crate.
//! All serialization is little-endian with explicit field ordering.
//! Architecture-independent: produces identical bytes on any conforming target.

#![deny(clippy::float_arithmetic)]

pub mod archive;
pub mod attestation;
pub mod entropy;
pub mod primitives;
pub mod replay;

pub use archive::{ArchiveVersion, ARCHIVE_V1_0_0};
pub use attestation::{VerifierAttestation, VCG_WEIGHT_EXCLUDED_CLASS};
pub use entropy::EntropyVector;
pub use primitives::{
    fixed_div, fixed_mul, InvariantViolation, OntologyReference, ProvenanceReference, StateHash,
    ViolationSeverity, FIXED_SCALE, FIXED_SHIFT, HOLONIC_ATOMIC, HOLONIC_CELLULAR,
    HOLONIC_FIELD, HOLONIC_MOLECULAR, HOLONIC_ORGANISM, HOLONIC_SUBATOMIC,
};
pub use replay::{ChainHasher, ReplayEvent, ReplayLedger};
