use aegis_cl_psi::abjad_encoder_v01::{
    authorize_inequality_from_aggregate, encode_canonical, mode_a_delta, mode_a_dominates,
    profile_mod9, AbjadEncoderInputV01, AuthorityDomain, CanonicalLetter, Digest32, ExactU64,
    Mod9Orbit, ObservabilityAuthorityError, Rational,
};

fn digest(byte: u8) -> Digest32 {
    Digest32([byte; 32])
}

fn input(values: &[u64]) -> AbjadEncoderInputV01 {
    AbjadEncoderInputV01 {
        letters: values
            .iter()
            .copied()
            .map(|abjad_value| CanonicalLetter {
                canonical_letter_id: abjad_value as u32,
                abjad_value,
            })
            .collect(),
        alphabet_spec_digest: digest(0xaa),
        normalization_spec_digest: digest(0xbb),
    }
}

#[test]
fn ring_1_mod9_orbits_are_exact() {
    assert_eq!(profile_mod9(9).residue, 0);
    assert_eq!(profile_mod9(9).orbit, Mod9Orbit::O1);
    assert_eq!(profile_mod9(9).cycle_length, 1);

    assert_eq!(profile_mod9(3).residue, 3);
    assert_eq!(profile_mod9(3).orbit, Mod9Orbit::O2);
    assert_eq!(profile_mod9(3).cycle_length, 2);
}

#[test]
fn ring_2_tariq_exact_regression() {
    let enc = encode_canonical(&input(&[9, 1, 200, 100])).unwrap();

    assert_eq!(enc.aggregate.exact_sum, ExactU64::Value(310));
    assert_eq!(enc.aggregate.exact_product, ExactU64::Value(180_000));
    assert_eq!(enc.aggregate.sum_mod9, profile_mod9(310));
    assert_eq!(enc.aggregate.product_mod9, profile_mod9(180_000));
    assert_eq!(enc.aggregate.sum_mod9.residue, 4);
    assert_eq!(enc.aggregate.sum_mod9.orbit, Mod9Orbit::O6);
    assert_eq!(enc.aggregate.sum_mod9.cycle_length, 6);
    assert_eq!(enc.aggregate.product_mod9.residue, 0);
    assert_eq!(enc.aggregate.product_mod9.orbit, Mod9Orbit::O1);
    assert_eq!(enc.aggregate.product_mod9.cycle_length, 1);
    assert_eq!(enc.full.dodecagon_projection, vec![9, 1, 8, 4]);
    assert_eq!(enc.full.routing_path, vec![9, 3, 2, 1, 2, 8, 2, 3, 4]);
}

#[test]
fn ring_3_exact_overflow_does_not_poison_mod9() {
    let enc = encode_canonical(&input(&[1000; 10])).unwrap();

    assert_eq!(enc.aggregate.exact_product, ExactU64::Overflow);
    assert_eq!(enc.aggregate.product_mod9.residue, 1);
    assert_eq!(enc.aggregate.product_mod9.orbit, Mod9Orbit::O6);
    assert_eq!(enc.aggregate.product_mod9.cycle_length, 6);
}

#[test]
fn ring_4_dodecagonal_route_is_byte_identical() {
    let first = encode_canonical(&input(&[9, 1, 200, 100])).unwrap();
    let second = encode_canonical(&input(&[9, 1, 200, 100])).unwrap();
    assert_eq!(first.full.routing_path, second.full.routing_path);
}

#[test]
fn ring_5_aggregate_collision_cannot_authorize_inequality() {
    let w1 = encode_canonical(&input(&[200, 100])).unwrap();
    let w2 = encode_canonical(&input(&[100, 200])).unwrap();

    assert_eq!(w1.aggregate, w2.aggregate);
    assert_ne!(w1.full, w2.full);
    assert_eq!(w1.aggregate.exact_sum, ExactU64::Value(300));
    assert_eq!(w1.aggregate.exact_product, ExactU64::Value(20_000));
    assert_eq!(w1.aggregate.sum_mod9.residue, 3);
    assert_eq!(w1.aggregate.sum_mod9.orbit, Mod9Orbit::O2);
    assert_eq!(w1.aggregate.sum_mod9.cycle_length, 2);
    assert_eq!(w1.aggregate.product_mod9.residue, 2);
    assert_eq!(w1.aggregate.product_mod9.orbit, Mod9Orbit::O6);
    assert_eq!(w1.aggregate.product_mod9.cycle_length, 6);

    assert_eq!(
        authorize_inequality_from_aggregate(&w1.aggregate, &w2.aggregate),
        Err(ObservabilityAuthorityError::ObservabilityAuthorityBreach)
    );
}

#[test]
fn ring_6_tariq_sum_profile_strictly_dominates_product_profile_in_mode_a() {
    let enc = encode_canonical(&input(&[9, 1, 200, 100])).unwrap();
    let delta = mode_a_delta(enc.aggregate.sum_mod9.orbit, enc.aggregate.product_mod9.orbit).unwrap();

    assert_eq!(delta.0, Rational::new(5, 1).unwrap());
    assert_eq!(delta.1, Rational::new(1, 2).unwrap());
    assert_eq!(delta.2, Rational::new(5, 9).unwrap());
    assert_eq!(
        mode_a_dominates(enc.aggregate.sum_mod9.orbit, enc.aggregate.product_mod9.orbit),
        Ok(true)
    );
}

#[test]
fn digest_json_is_normatively_sha256_lowercase_hex() {
    let d = digest(0xab);
    let json = serde_json::to_string(&d).unwrap();
    assert_eq!(
        json,
        "\"sha256:abababababababababababababababababababababababababababababababab\""
    );
    assert_eq!(serde_json::from_str::<Digest32>(&json).unwrap(), d);
}

#[test]
fn authority_domains_have_frozen_cross_runtime_labels() {
    assert_eq!(serde_json::to_string(&AuthorityDomain::RawText).unwrap(), "\"RAW_TEXT\"");
    assert_eq!(
        serde_json::to_string(&AuthorityDomain::CanonicalLetterSequence).unwrap(),
        "\"CANONICAL_LETTER_SEQUENCE\""
    );
    assert_eq!(
        serde_json::to_string(&AuthorityDomain::AggregateProfile).unwrap(),
        "\"AGGREGATE_PROFILE\""
    );
}
