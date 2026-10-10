import json
from types import SimpleNamespace

from aegis.evidence import check_claims, claims_schema, verified_answer
from aegis.receipts import Recorder, verify

# The toy variant from the research registry (LEGACY-INTERPRETATION-01): the
# structured record says C>T of uncertain significance; the legacy narrative
# said A>T pathogenic.
EVIDENCE = [{"position": 5, "reference": "C", "alternate": "T",
             "read_support": 2, "classification": "uncertain_significance"}]


def fake_client(output, stop_reason="end_turn"):
    sent = {}

    def create(**kw):
        sent.update(kw)
        return SimpleNamespace(stop_reason=stop_reason,
                               content=[SimpleNamespace(type="text", text=json.dumps(output))])
    return SimpleNamespace(beta=SimpleNamespace(messages=SimpleNamespace(create=create))), sent


def test_faithful_claims_are_consistent():
    assert check_claims(EVIDENCE, [dict(EVIDENCE[0])], "position")["status"] == "consistent"


def test_legacy_contradiction_is_caught_field_by_field():
    claim = dict(EVIDENCE[0], reference="A", classification="pathogenic")
    v = check_claims(EVIDENCE, [claim], "position")
    assert v["status"] == "contradicted"
    assert {(f["field"], f["claimed"]) for f in v["findings"]} == {
        ("reference", "A"), ("classification", "pathogenic")}


def test_claim_about_a_record_that_does_not_exist_is_fabricated():
    v = check_claims(EVIDENCE, [dict(EVIDENCE[0], position=99)], "position")
    assert v["findings"] == [{"claim": 0, "kind": "fabricated", "position": 99}]


def test_schema_is_typed_from_evidence_and_rejects_floats():
    item = claims_schema(EVIDENCE, "position")["properties"]["claims"]["items"]
    assert item["properties"]["read_support"] == {"type": "integer"}
    assert item["additionalProperties"] is False
    try:
        claims_schema([{"position": 1, "af": 0.5}], "position")
        raise AssertionError("float accepted")
    except TypeError:
        pass


def test_verified_answer_binds_the_verdict_into_the_receipt(tmp_path):
    bad = {"answer": "Pathogenic A>T at position 5.",
           "claims": [dict(EVIDENCE[0], reference="A", classification="pathogenic")]}
    client, sent = fake_client(bad)
    rec = Recorder(tmp_path / "r.json")
    out = verified_answer(client, rec, question="Summarise.", evidence=EVIDENCE, key="position")
    assert out["verdict"]["status"] == "contradicted"
    assert sent["model"] == "claude-opus-5-5"
    assert sent["output_config"]["format"]["type"] == "json_schema"
    assert verify(tmp_path / "r.json")["valid"]

    good = {"answer": "C>T of uncertain significance.", "claims": [dict(EVIDENCE[0])]}
    client, _ = fake_client(good)
    out2 = verified_answer(client, rec, question="Summarise.", evidence=EVIDENCE, key="position")
    assert out2["verdict"]["status"] == "consistent"
    # Different verdicts give different response digests in the chain.
    assert out["receipt"]["response_digest"] != out2["receipt"]["response_digest"]


def test_refusal_is_recorded_not_parsed(tmp_path):
    client, _ = fake_client({}, stop_reason="refusal")
    out = verified_answer(client, Recorder(tmp_path / "r.json"), question="q",
                          evidence=EVIDENCE, key="position")
    assert out["verdict"]["status"] == "refused" and out["answer"] is None
