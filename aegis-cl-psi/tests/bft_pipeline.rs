/// Gate 183 — BFT Pipeline End-to-End Integration Test
/// EPISTEMIC TIER: T2 (engineering hypothesis)
///
/// Proves that ValidatorRegistry → verify_quorum_at_edge → log_verification_result
/// → AuditLogger::verify_chain() compose correctly as a complete pipeline.
///
/// Five scenarios:
///   1. Full quorum (5/5): all validators sign → is_quorum_verified=true → audit chain valid
///   2. Threshold quorum (4/5 = 0.8 ≥ 0.618): passes 1/φ → true → audit chain valid
///   3. Below threshold (2/5 = 0.4 < 0.618): fails 1/φ → false → audit chain still valid
///   4. Insertion-order determinism: register(A,B) == register(B,A) → same registry_hash
///   5. Multi-round audit: 5 sequential verifications → 5-entry chain → verify_chain() valid
use aegis_cl_psi::audit::AuditLogger;
use aegis_cl_psi::edge_verifier::{
    log_verification_result, verify_quorum_at_edge, NodeSignature, QuorumProof, ValidatorEntry,
    ValidatorRegistry,
};
use ed25519_dalek::{Signer, SigningKey};
use std::collections::BTreeMap;

fn make_key(seed: u8) -> SigningKey {
    SigningKey::from_bytes(&[seed; 32])
}

fn entry_from_key(node_id: &str, sk: &SigningKey) -> ValidatorEntry {
    ValidatorEntry { node_id: node_id.to_string(), public_key: sk.verifying_key().to_bytes() }
}

fn sign_proof(
    sequence: u64,
    topology_hash: [u8; 32],
    signers: &[(&str, &SigningKey)],
) -> QuorumProof {
    let signatures = signers
        .iter()
        .map(|(node_id, sk)| NodeSignature {
            node_id: node_id.to_string(),
            signature: sk.sign(&topology_hash).to_bytes().to_vec(),
        })
        .collect();
    QuorumProof { sequence, signatures, topology_hash }
}

#[test]
fn full_quorum_five_of_five_pipeline() {
    let keys: Vec<SigningKey> = (1u8..=5).map(make_key).collect();
    let node_ids: Vec<String> = (0..5).map(|i| format!("node-{:03}", i)).collect();

    let registry = node_ids.iter().zip(keys.iter()).fold(
        ValidatorRegistry::empty(),
        |r, (id, sk)| r.register(entry_from_key(id, sk)).unwrap(),
    );
    assert_eq!(registry.size(), 5);

    let hash = [0x5fu8; 32];
    let signers: Vec<(&str, &SigningKey)> =
        node_ids.iter().zip(keys.iter()).map(|(id, sk)| (id.as_str(), sk)).collect();
    let proof = sign_proof(1, hash, &signers);

    let result = verify_quorum_at_edge(&proof, registry.as_map()).unwrap();
    assert!(result.is_quorum_verified);
    assert_eq!(result.valid_count, 5);
    assert_eq!(result.total_count, 5);

    let mut logger = AuditLogger::new();
    let entry_hash = log_verification_result(&mut logger, &result);
    assert_eq!(entry_hash.len(), 64);
    let (chain_valid, first_bad) = logger.verify_chain();
    assert!(chain_valid);
    assert!(first_bad.is_none());
}

#[test]
fn threshold_quorum_four_of_five_pipeline() {
    let keys: Vec<SigningKey> = (1u8..=5).map(make_key).collect();
    let node_ids: Vec<String> = (0..5).map(|i| format!("node-{:03}", i)).collect();

    let registry = node_ids.iter().zip(keys.iter()).fold(
        ValidatorRegistry::empty(),
        |r, (id, sk)| r.register(entry_from_key(id, sk)).unwrap(),
    );

    let hash = [0x4fu8; 32];
    // Only 4 of 5 sign — 4/5 = 0.8 >= 0.618034 → quorum
    let signers: Vec<(&str, &SigningKey)> =
        node_ids.iter().zip(keys.iter()).take(4).map(|(id, sk)| (id.as_str(), sk)).collect();
    let proof = sign_proof(2, hash, &signers);

    let result = verify_quorum_at_edge(&proof, registry.as_map()).unwrap();
    assert!(result.is_quorum_verified);
    assert_eq!(result.valid_count, 4);
    assert_eq!(result.total_count, 5);

    let mut logger = AuditLogger::new();
    log_verification_result(&mut logger, &result);
    let (chain_valid, _) = logger.verify_chain();
    assert!(chain_valid);
}

#[test]
fn below_threshold_two_of_five_pipeline() {
    let keys: Vec<SigningKey> = (1u8..=5).map(make_key).collect();
    let node_ids: Vec<String> = (0..5).map(|i| format!("node-{:03}", i)).collect();

    let registry = node_ids.iter().zip(keys.iter()).fold(
        ValidatorRegistry::empty(),
        |r, (id, sk)| r.register(entry_from_key(id, sk)).unwrap(),
    );

    let hash = [0x2fu8; 32];
    // 2/5 = 0.4 < 0.618034 → no quorum
    let signers: Vec<(&str, &SigningKey)> =
        node_ids.iter().zip(keys.iter()).take(2).map(|(id, sk)| (id.as_str(), sk)).collect();
    let proof = sign_proof(3, hash, &signers);

    let result = verify_quorum_at_edge(&proof, registry.as_map()).unwrap();
    assert!(!result.is_quorum_verified);
    assert_eq!(result.valid_count, 2);

    // Audit chain still valid even for rejected quorum
    let mut logger = AuditLogger::new();
    log_verification_result(&mut logger, &result);
    let (chain_valid, _) = logger.verify_chain();
    assert!(chain_valid);
}

#[test]
fn registry_insertion_order_determinism() {
    let sk_a = make_key(1);
    let sk_b = make_key(2);

    let r_ab = ValidatorRegistry::empty()
        .register(entry_from_key("node-alpha", &sk_a)).unwrap()
        .register(entry_from_key("node-beta", &sk_b)).unwrap();

    let r_ba = ValidatorRegistry::empty()
        .register(entry_from_key("node-beta", &sk_b)).unwrap()
        .register(entry_from_key("node-alpha", &sk_a)).unwrap();

    // BTreeMap sorts by key → same content regardless of insertion order
    assert_eq!(r_ab.registry_hash(), r_ba.registry_hash());
    assert_eq!(r_ab.size(), r_ba.size());
}

#[test]
fn multi_round_audit_chain_integrity() {
    let keys: Vec<SigningKey> = (1u8..=8).map(make_key).collect();
    let node_ids: Vec<String> = (0..8).map(|i| format!("node-{:03}", i)).collect();

    let registry = node_ids.iter().zip(keys.iter()).fold(
        ValidatorRegistry::empty(),
        |r, (id, sk)| r.register(entry_from_key(id, sk)).unwrap(),
    );
    // quorum_size for n=8: ceiling(8 * 618_034 / 1_000_000) = ceiling(4.944...) = 5
    assert_eq!(registry.quorum_size(), 5);

    let mut logger = AuditLogger::new();

    for round in 0u64..5 {
        let hash: [u8; 32] = {
            let mut h = [0u8; 32];
            h[0] = round as u8;
            h
        };
        // Alternate between quorum (6/8) and non-quorum (3/8)
        let sign_count = if round % 2 == 0 { 6 } else { 3 };
        let signers: Vec<(&str, &SigningKey)> = node_ids
            .iter()
            .zip(keys.iter())
            .take(sign_count)
            .map(|(id, sk)| (id.as_str(), sk))
            .collect();
        let proof = sign_proof(round + 10, hash, &signers);
        let result = verify_quorum_at_edge(&proof, registry.as_map()).unwrap();
        log_verification_result(&mut logger, &result);
    }

    assert_eq!(logger.len(), 5);
    let (chain_valid, first_bad) = logger.verify_chain();
    assert!(chain_valid, "audit chain should be valid after 5 rounds");
    assert!(first_bad.is_none());
}

#[test]
fn quorum_size_boundary_matches_verification() {
    // n=10: quorum_size = ceiling(10 * 618_034 / 1_000_000) = ceiling(6.18034) = 7
    let keys: Vec<SigningKey> = (1u8..=10).map(make_key).collect();
    let node_ids: Vec<String> = (0..10).map(|i| format!("node-{:03}", i)).collect();

    let registry = node_ids.iter().zip(keys.iter()).fold(
        ValidatorRegistry::empty(),
        |r, (id, sk)| r.register(entry_from_key(id, sk)).unwrap(),
    );
    assert_eq!(registry.quorum_size(), 7);

    let hash = [0xaau8; 32];

    // 7/10 should reach quorum (7 >= quorum_size)
    let signers_7: Vec<(&str, &SigningKey)> =
        node_ids.iter().zip(keys.iter()).take(7).map(|(id, sk)| (id.as_str(), sk)).collect();
    let proof_7 = sign_proof(100, hash, &signers_7);
    let result_7 = verify_quorum_at_edge(&proof_7, registry.as_map()).unwrap();
    assert!(result_7.is_quorum_verified);

    // 6/10 should NOT reach quorum (6 < quorum_size)
    let signers_6: Vec<(&str, &SigningKey)> =
        node_ids.iter().zip(keys.iter()).take(6).map(|(id, sk)| (id.as_str(), sk)).collect();
    let proof_6 = sign_proof(101, hash, &signers_6);
    let result_6 = verify_quorum_at_edge(&proof_6, registry.as_map()).unwrap();
    assert!(!result_6.is_quorum_verified);
}

#[test]
fn pipeline_deterministic_three_times() {
    let keys: Vec<SigningKey> = (1u8..=5).map(make_key).collect();
    let node_ids: Vec<String> = (0..5).map(|i| format!("node-{:03}", i)).collect();

    let run = |seq: u64| -> (bool, usize, String) {
        let registry = node_ids.iter().zip(keys.iter()).fold(
            ValidatorRegistry::empty(),
            |r, (id, sk)| r.register(entry_from_key(id, sk)).unwrap(),
        );
        let hash = [0x77u8; 32];
        let signers: Vec<(&str, &SigningKey)> =
            node_ids.iter().zip(keys.iter()).take(4).map(|(id, sk)| (id.as_str(), sk)).collect();
        let proof = sign_proof(seq, hash, &signers);
        let result = verify_quorum_at_edge(&proof, registry.as_map()).unwrap();
        let mut logger = AuditLogger::new();
        let hash_hex = log_verification_result(&mut logger, &result);
        (result.is_quorum_verified, result.valid_count, hash_hex)
    };

    let r1 = run(200);
    let r2 = run(200);
    let r3 = run(200);
    assert_eq!(r1, r2);
    assert_eq!(r2, r3);
}

/// Also exercises `BTreeMap` helper used in existing verify tests — proves
/// `as_map()` output is identical to a manually-constructed BTreeMap of the
/// same entries.
#[test]
fn as_map_equivalent_to_manual_btreemap() {
    let keys: Vec<SigningKey> = (1u8..=3).map(make_key).collect();
    let node_ids = ["node-000", "node-001", "node-002"];

    let registry = node_ids.iter().zip(keys.iter()).fold(
        ValidatorRegistry::empty(),
        |r, (id, sk)| r.register(entry_from_key(id, sk)).unwrap(),
    );

    let mut manual: BTreeMap<String, ValidatorEntry> = BTreeMap::new();
    for (id, sk) in node_ids.iter().zip(keys.iter()) {
        manual.insert(id.to_string(), entry_from_key(id, sk));
    }

    let hash = [0x11u8; 32];
    let signers: Vec<(&str, &SigningKey)> =
        node_ids.iter().zip(keys.iter()).map(|(id, sk)| (*id, sk)).collect();
    let proof = sign_proof(300, hash, &signers);

    let r_registry = verify_quorum_at_edge(&proof, registry.as_map()).unwrap();
    let r_manual = verify_quorum_at_edge(&proof, &manual).unwrap();

    assert_eq!(r_registry.is_quorum_verified, r_manual.is_quorum_verified);
    assert_eq!(r_registry.valid_count, r_manual.valid_count);
    assert_eq!(r_registry.total_count, r_manual.total_count);
}
