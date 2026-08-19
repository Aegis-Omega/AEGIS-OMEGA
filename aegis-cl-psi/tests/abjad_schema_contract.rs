use aegis_cl_psi::abjad_capability_bridge::{
    bridge_observation, AbjadCapabilityEncodingV1, CalligraphicObservationV1,
};
use serde_json::{json, Value};

const INPUT_SCHEMA: &str = include_str!("../../schemas/calligraphic-observation.v1.schema.json");
const OUTPUT_SCHEMA: &str = include_str!("../../schemas/abjad-capability-encoding.v1.schema.json");
const FIXTURE: &str = include_str!("../../test-vectors/calligraphic-language/arabic-v1.json");

fn properties(schema: &Value) -> &serde_json::Map<String, Value> {
    schema["properties"].as_object().expect("schema properties")
}

#[test]
fn input_schema_contract_is_closed_and_value_free() {
    let schema: Value = serde_json::from_str(INPUT_SCHEMA).unwrap();
    assert_eq!(schema["$schema"], "https://json-schema.org/draft/2020-12/schema");
    assert_eq!(schema["properties"]["record_kind"]["const"], "CALLIGRAPHIC_OBSERVATION_V1");
    assert_eq!(schema["properties"]["schema_version"]["const"], "1.0.0");
    assert_eq!(schema["additionalProperties"], false);
    assert!(schema["required"].as_array().unwrap().iter().any(|v| v == "abjad_system"));

    let candidate = &schema["$defs"]["reading_candidate"];
    let grapheme = &schema["$defs"]["grapheme"];
    assert_eq!(candidate["additionalProperties"], false);
    assert_eq!(grapheme["additionalProperties"], false);
    assert!(!properties(grapheme).contains_key("abjad_value"));

    let letters = grapheme["properties"]["abjad_letter"]["enum"].as_array().unwrap();
    assert_eq!(letters.len(), 28);
}

#[test]
fn output_schema_has_no_authority_or_receipt_surface() {
    let schema: Value = serde_json::from_str(OUTPUT_SCHEMA).unwrap();
    assert_eq!(schema["properties"]["record_kind"]["const"], "ABJAD_CAPABILITY_ENCODING_V1");
    assert_eq!(schema["properties"]["derivation_kind"]["const"], "DETERMINISTIC_FROM_UNTRUSTED_OBSERVATION");
    assert_eq!(schema["properties"]["epistemic_ceiling"]["const"], "T2");
    assert_eq!(schema["additionalProperties"], false);

    let text = OUTPUT_SCHEMA.to_ascii_lowercase();
    for forbidden in [
        "selected_candidate",
        "authority",
        "decision_receipt",
        "execution_receipt",
        "effect_receipt",
        "execution_success",
        "effect_proof",
    ] {
        assert!(!text.contains(forbidden), "forbidden schema vocabulary: {forbidden}");
    }
}

#[test]
fn typed_input_rejects_top_level_authority_injection() {
    let fixture: Value = serde_json::from_str(FIXTURE).unwrap();
    let mut injected = fixture["tariq"]["observation"].clone();
    injected["authority"] = json!("PERMIT");
    assert!(serde_json::from_value::<CalligraphicObservationV1>(injected).is_err());
}

#[test]
fn typed_input_rejects_grapheme_abjad_value_injection() {
    let fixture: Value = serde_json::from_str(FIXTURE).unwrap();
    let mut injected = fixture["tariq"]["observation"].clone();
    injected["reading_candidates"][0]["graphemes"][0]["abjad_value"] = json!(999);
    assert!(serde_json::from_value::<CalligraphicObservationV1>(injected).is_err());
}

#[test]
fn typed_output_rejects_authority_injection() {
    let fixture: Value = serde_json::from_str(FIXTURE).unwrap();
    let tariq: CalligraphicObservationV1 =
        serde_json::from_value(fixture["tariq"]["observation"].clone()).unwrap();
    let output = bridge_observation(&tariq).unwrap();
    let mut injected = serde_json::to_value(output).unwrap();
    injected["authority"] = json!("PERMIT");
    assert!(serde_json::from_value::<AbjadCapabilityEncodingV1>(injected).is_err());
}

#[test]
fn fixture_round_trips_tariq_and_preserves_ambiguity() {
    let fixture: Value = serde_json::from_str(FIXTURE).unwrap();

    let tariq: CalligraphicObservationV1 = serde_json::from_value(fixture["tariq"]["observation"].clone()).unwrap();
    let tariq_output: AbjadCapabilityEncodingV1 = bridge_observation(&tariq).unwrap();
    let expected = &fixture["tariq"]["expected"];
    let encoded = &tariq_output.candidate_encodings[0];
    assert_eq!(encoded.derived_abjad_values, vec![9, 1, 200, 100]);
    assert_eq!(encoded.abjad_sum, expected["abjad_sum"].as_u64().unwrap());
    assert_eq!(encoded.abjad_product, expected["abjad_product"].as_u64().unwrap());
    assert_eq!(encoded.name_node as u64, expected["name_node"].as_u64().unwrap());

    let ambiguous: CalligraphicObservationV1 = serde_json::from_value(fixture["ambiguity"]["observation"].clone()).unwrap();
    let ambiguous_output = bridge_observation(&ambiguous).unwrap();
    assert!(ambiguous_output.ambiguity_preserved);
    let ids = ambiguous_output.candidate_encodings.iter().map(|c| c.candidate_id.as_str()).collect::<Vec<_>>();
    assert_eq!(ids, vec!["first", "second"]);
    assert_eq!(ambiguous_output.candidate_encodings[0].graphemes[0].dot_evidence, aegis_cl_psi::abjad_capability_bridge::DotEvidence::NotVisible);
    assert_eq!(ambiguous_output.candidate_encodings[0].graphemes[0].dot_count, 0);
}
