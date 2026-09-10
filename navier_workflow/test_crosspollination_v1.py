from navier_workflow.crosspollination_v1 import synthesize_shared_state


def candidate(cid, digest, assumptions, obligations):
    return {
        "candidate_id": cid,
        "lane_id": cid,
        "claim": f"claim-{cid}",
        "claim_scope": "SURROGATE_ONLY",
        "assumptions": assumptions,
        "source_coordinates": [f"source:{cid}"],
        "dependencies": [],
        "open_obligations": obligations,
        "known_failure_modes": [],
        "falsification_attempts": [],
        "artifact_digest": digest,
    }


def test_synthesis_preserves_assumptions_and_provenance():
    a = candidate("a", "a" * 64, ["periodic"], ["lemma-A"])
    b = candidate("b", "b" * 64, ["whole-space"], [])
    shared = synthesize_shared_state([a, b])
    assert shared["imports"][0]["artifact_digest"] == "a" * 64
    assert shared["imports"][0]["assumptions"] == ["periodic"]
    assert shared["imports"][1]["assumptions"] == ["whole-space"]


def test_conflicting_assumptions_are_not_flattened():
    a = candidate("a", "a" * 64, ["periodic"], [])
    b = candidate("b", "b" * 64, ["whole-space"], [])
    shared = synthesize_shared_state([a, b])
    assert shared["assumption_sets"] == {
        "a" * 64: ["periodic"],
        "b" * 64: ["whole-space"],
    }


def test_surrogate_import_cannot_promote_target():
    a = candidate("a", "a" * 64, [], [])
    shared = synthesize_shared_state([a])
    assert shared["claim_promotion"] == "BLOCKED"
    assert shared["authority_effect"] == "NONE"
