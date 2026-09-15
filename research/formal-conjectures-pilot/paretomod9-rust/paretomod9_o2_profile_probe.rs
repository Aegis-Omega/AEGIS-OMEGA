use aegis_cl_psi::abjad_encoder::{mode_a_delta, mode_a_dominates, Mod9Orbit, ParetoModeAError};

#[test]
fn mode_a_o2_profile_is_fail_closed() {
    assert_eq!(
        mode_a_delta(Mod9Orbit::O2, Mod9Orbit::O1),
        Err(ParetoModeAError::ProfileUndefined)
    );
    assert_eq!(
        mode_a_delta(Mod9Orbit::O1, Mod9Orbit::O2),
        Err(ParetoModeAError::ProfileUndefined)
    );
    assert_eq!(
        mode_a_dominates(Mod9Orbit::O2, Mod9Orbit::O1),
        Err(ParetoModeAError::ProfileUndefined)
    );
}
