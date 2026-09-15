use aegis_cl_psi::abjad_encoder::{profile_mod9, Mod9Orbit};

const M: u8 = 36;

fn mul_mod36(k: u8, x: u8) -> u8 {
    (((k as u16) * (x as u16)) % (M as u16)) as u8
}

fn d(x: u8) -> u8 {
    mul_mod36(2, x)
}

fn d_pow(mut x: u8, n: usize) -> u8 {
    for _ in 0..n {
        x = d(x);
    }
    x
}

fn neg36(x: u8) -> u8 {
    if x == 0 { 0 } else { M - x }
}

fn compatible(r9: u8, r12: u8) -> bool {
    r9 % 3 == r12 % 3
}

fn lift_mod36(r9: u8, r12: u8) -> Option<u8> {
    let lifts: Vec<u8> = (0..M)
        .filter(|x| x % 9 == r9 && x % 12 == r12)
        .collect();
    match lifts.as_slice() {
        [] => None,
        [x] => Some(*x),
        _ => panic!("lift modulo 36 must be unique"),
    }
}

fn endomorphism(power: usize) -> Vec<u8> {
    (0..M).map(|x| d_pow(x, power)).collect()
}

fn same_fibers(lhs_power: usize, rhs_power: usize) -> bool {
    (0..M).all(|x| {
        (0..M).all(|y| {
            (d_pow(x, lhs_power) == d_pow(y, lhs_power))
                == (d_pow(x, rhs_power) == d_pow(y, rhs_power))
        })
    })
}

fn orbit_mu_lambda(start: u8) -> (Vec<u8>, usize, usize) {
    let mut seen = [None; 36];
    let mut seq = Vec::new();
    let mut x = start;
    loop {
        if let Some(mu) = seen[x as usize] {
            let period = seq.len() - mu;
            return (seq, mu, period);
        }
        seen[x as usize] = Some(seq.len());
        seq.push(x);
        x = d(x);
    }
}

#[test]
fn theorem_mod9_mod12_compatible_iff_mod3_and_unique_mod36_lift() {
    for r9 in 0..9 {
        for r12 in 0..12 {
            let lift = lift_mod36(r9, r12);
            assert_eq!(lift.is_some(), compatible(r9, r12));
            if let Some(x) = lift {
                assert_eq!(x % 9, r9);
                assert_eq!(x % 12, r12);
            }
        }
    }
}

#[test]
fn theorem_tariq_sequence_has_exact_joint_mod36_projection() {
    let values = [9u64, 1, 200, 100];
    let projected: Vec<u8> = values.iter().map(|x| (x % 36) as u8).collect();
    assert_eq!(projected, vec![9, 1, 20, 28]);

    for &x in &values {
        let r9 = (x % 9) as u8;
        let r12 = (x % 12) as u8;
        assert_eq!(lift_mod36(r9, r12), Some((x % 36) as u8));
    }

    assert_eq!(lift_mod36((310 % 9) as u8, (310 % 12) as u8), Some(22));
    assert_eq!(lift_mod36((180_000 % 9) as u8, (180_000 % 12) as u8), Some(0));
}

#[test]
fn theorem_independent_antipodes_break_source_coherence_exactly_on_o6() {
    for x in 0..M {
        let r9 = x % 9;
        let r12 = x % 12;
        let mod9_antipode = if r9 == 0 { 0 } else { 9 - r9 };
        let dodecagonal_opposite = (r12 + 6) % 12;
        let remains_source_coherent = compatible(mod9_antipode, dodecagonal_opposite);
        let in_o6 = profile_mod9(x as u64).orbit == Mod9Orbit::O6;

        assert_eq!(remains_source_coherent, !in_o6);
        assert_eq!(remains_source_coherent, r9 % 3 == 0);
    }

    assert_eq!(lift_mod36(8, 7), None); // Alif: (1,1) -> (8,7) is orphaned.
}

#[test]
fn theorem_source_negation_lifts_coherently() {
    for x in 0..M {
        let source_neg = neg36(x);
        let r9_neg = if x % 9 == 0 { 0 } else { 9 - (x % 9) };
        let r12_neg = if x % 12 == 0 { 0 } else { 12 - (x % 12) };
        assert_eq!(lift_mod36(r9_neg, r12_neg), Some(source_neg));
    }

    assert_eq!(lift_mod36(8, 11), Some(35)); // Alif: 1 -> -1 mod 36.
}

#[test]
fn theorem_fitting_drazin_kernel_and_projectors_for_d36() {
    for x in 0..M {
        let d_drazin = d_pow(x, 5);
        let p = d_pow(x, 6);
        let q = (x + M - p) % M;

        assert_eq!(p, mul_mod36(28, x));
        assert_eq!(q, mul_mod36(9, x));
        assert_eq!(d_pow(p, 6), p); // P^2 = P.
        assert_eq!(mul_mod36(9, q), q); // Q^2 = Q.
        assert_eq!(mul_mod36(28, q), 0); // P Q = 0.
        assert_eq!(mul_mod36(9, p), 0); // Q P = 0.
        assert_eq!((p + q) % M, x); // P + Q = I.

        assert_eq!(d(d_drazin), p); // D D^D = P.
        assert_eq!(d_pow(d(x), 5), p); // D^D D = P.
        assert_eq!(d_pow(d_pow(d_drazin, 1), 5), d_drazin); // D^D D D^D = D^D.
        assert_eq!(d_pow(d_pow(x, 3), 5), d_pow(x, 2)); // D^3 D^D = D^2, ind(D)=2 witness.

        assert_eq!(d_pow(x, 3), neg36(p)); // D^3 = -P.
        assert_eq!(d_pow(d_pow(p, 3), 3), p); // involution on Im(P).
    }
}

#[test]
fn theorem_kernel_filtration_stabilizes_at_exact_index_two() {
    let kernel = |n: usize| -> Vec<u8> { (0..M).filter(|&x| d_pow(x, n) == 0).collect() };

    assert_eq!(kernel(0), vec![0]);
    assert_eq!(kernel(1), vec![0, 18]);
    assert_eq!(kernel(2), vec![0, 9, 18, 27]);
    for n in 3..=12 {
        assert_eq!(kernel(n), kernel(2));
    }
}

#[test]
fn theorem_authority_fibers_stabilize_at_exact_index_two() {
    assert_ne!(d_pow(0, 0) == d_pow(18, 0), d_pow(0, 1) == d_pow(18, 1));
    assert_ne!(d_pow(0, 1) == d_pow(9, 1), d_pow(0, 2) == d_pow(9, 2));

    for n in 2..=12 {
        assert!(same_fibers(2, n));
    }

    // P = D^6 and D^2 induce the same observational equivalence relation.
    assert!(same_fibers(2, 6));
}

#[test]
fn theorem_power_monoid_has_transient_two_and_eventual_c6() {
    let powers: Vec<Vec<u8>> = (0..=7).map(endomorphism).collect();
    for i in 0..powers.len() {
        for j in (i + 1)..powers.len() {
            assert_ne!(powers[i], powers[j]);
        }
    }
    assert_eq!(endomorphism(8), endomorphism(2));

    let kernel_group: Vec<Vec<u8>> = (2..=7).map(endomorphism).collect();
    assert_eq!(kernel_group.len(), 6);
    let p = endomorphism(6);

    for exponent in 2..=7 {
        let f = endomorphism(exponent);
        assert_eq!(endomorphism(exponent + 6), f);
        // D^6 is the identity element inside the eventual group.
        let left: Vec<u8> = (0..M).map(|x| d_pow(d_pow(x, exponent), 6)).collect();
        let right: Vec<u8> = (0..M).map(|x| d_pow(d_pow(x, 6), exponent)).collect();
        assert_eq!(left, f);
        assert_eq!(right, f);
    }

    assert_eq!(endomorphism(12), p); // P^2 = P as the group identity.
    let d3_squared: Vec<u8> = (0..M).map(|x| d_pow(d_pow(x, 3), 3)).collect();
    let d2_cubed: Vec<u8> = (0..M)
        .map(|x| d_pow(d_pow(d_pow(x, 2), 2), 2))
        .collect();
    assert_eq!(d3_squared, p); // (D^3)^2 = D^6 = P.
    assert_eq!(d2_cubed, p); // (D^2)^3 = D^6 = P.

    // U = D^7 has order six relative to identity P.
    let generated: Vec<Vec<u8>> = (1..=6).map(|n| endomorphism(7 * n)).collect();
    let mut unique = Vec::<Vec<u8>>::new();
    for f in generated {
        if !unique.contains(&f) {
            unique.push(f);
        }
    }
    assert_eq!(unique.len(), 6);
    assert_eq!(endomorphism(42), p);
}

#[test]
fn theorem_alif_has_mu_two_and_lambda_six_mod36() {
    let (seq, mu, lambda) = orbit_mu_lambda(1);
    assert_eq!(seq, vec![1, 2, 4, 8, 16, 32, 28, 20]);
    assert_eq!(mu, 2);
    assert_eq!(lambda, 6);
}

#[test]
fn theorem_nonzero_mod9_square_sum_partitions_as_159_plus_45() {
    let mut o6_square_sum = 0u64;
    let mut o2_square_sum = 0u64;

    for r in 1u64..=8 {
        match profile_mod9(r).orbit {
            Mod9Orbit::O6 => o6_square_sum += r * r,
            Mod9Orbit::O2 => o2_square_sum += r * r,
            Mod9Orbit::O1 => panic!("nonzero residue cannot be O1"),
        }
    }

    assert_eq!(o6_square_sum, 159);
    assert_eq!(o2_square_sum, 45);
    assert_eq!(o6_square_sum + o2_square_sum, 204);
    assert_eq!(3u64.pow(2) + 6u64.pow(2), 45);
    assert_eq!((1u64..=9).sum::<u64>(), 45);
}
