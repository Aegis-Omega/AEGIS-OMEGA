"""RH screenshot incident: regression for previously known fixed moment-zero packets.

These fixtures pin *source blobs*, not unexecuted claims about Lean kernel status.
The required-source contract is independently held, not declared by the model.
"""
import copy
import hashlib
import unittest

from agents.source_reuse_preflight import canonical, evaluate

HEAD = "9400ccba6aacb8af062fd485dc12a67adade5b1f"
DETECTOR = "github:formal-conjectures:AEGISOverlay/RHDetectingPacketV1.lean"
DENSE = "github:formal-conjectures:AEGISOverlay/RHFixedPacketDenseShiftV1.lean"
TRIGRAM = "github:formal-conjectures:AEGISOverlay/RHNarrowDetectingTrigramDenseV1.lean"
PINS = {
    DETECTOR: "6fcdae47dd965b546dd4757178892b80fa4a79f2",
    DENSE: "33586b0f3a7f7cc764c78f370870924c6082d2ef",
    TRIGRAM: "3adb4d70fc6b4bb8002aa38221ec176b9c75f40a",
}


def asset(asset_id, revision, disposition="REJECT", evidence="CONTENT_READ"):
    return {
        "asset_id": asset_id, "surface": "github", "revision": revision,
        "evidence": evidence, "disposition": disposition,
        "reason": "This is claimed irrelevant to the new theorem, without independent review",
        "access": "PUBLIC", "tenant": "aegis-omega",
    }


def manifest():
    # Agent claims full GitHub/Drive inspection but omits the older PR branches.
    return {
        "task_id": "Aegis-Omega/AEGIS-OMEGA#758",
        "source_head": HEAD, "tenant": "aegis-omega", "intent": "PROPOSE_NEW",
        "as_of": "2026-11-16T15:00:00Z", "max_age_hours": 24,
        "required_surfaces": ["github", "drive"],
        "surfaces": [
            {"name": "github", "state": "SEARCHED_COMPLETE", "observed_at": "2026-11-16T14:00:00Z"},
            {"name": "drive", "state": "SEARCHED_COMPLETE", "observed_at": "2026-11-16T14:00:00Z"},
        ],
        "assets": [asset("github:AEGIS-OMEGA:docs/REPO_MAP.md", "a" * 40)],
    }


class TestScreenshotIncident(unittest.TestCase):
    def test_baseline_false_novelty_reproduced(self):
        # This describes the old behavior on the exact original 773 code.
        # The improved path MUST NOT change the legacy no-contract signature.
        r = evaluate(manifest())
        self.assertEqual(r["outcome"], "READY_FOR_AUTHORITY_REVIEW")
        self.assertEqual(r["provenance"], "CALLER_REPORTED_NOT_INDEPENDENTLY_ATTESTED")
        self.assertEqual(r["authority_effect"], "NONE")

    def test_fails_closed_if_existing_fixed_packet_omitted(self):
        r = evaluate(manifest(), required_asset_pins=PINS)
        self.assertEqual(r["outcome"], "HOLD")
        self.assertIn("REQUIRED_PRIOR_ART_MISSING:" + DETECTOR, r["blockers"])
        self.assertIn("REQUIRED_PRIOR_ART_MISSING:" + DENSE, r["blockers"])
        self.assertIn("REQUIRED_PRIOR_ART_MISSING:" + TRIGRAM, r["blockers"])

    def test_wrong_commit_or_blob_cannot_satisfy_required_source(self):
        m = manifest()
        m["assets"].append(asset(DENSE, "f" * 40))
        r = evaluate(m, required_asset_pins={DENSE: PINS[DENSE]})
        self.assertIn("REQUIRED_PRIOR_ART_REVISION_MISMATCH:" + DENSE, r["blockers"])

    def test_filename_only_not_evidence_of_theorem_inspection(self):
        m = manifest()
        m["assets"].append(asset(DENSE, PINS[DENSE], evidence="SOURCE_SEEN"))
        r = evaluate(m, required_asset_pins={DENSE: PINS[DENSE]})
        self.assertIn("REQUIRED_PRIOR_ART_CONTENT_UNREAD:" + DENSE, r["blockers"])

    def test_model_supplied_rejection_does_not_clear_prior_equivalence(self):
        m = manifest()
        m["assets"].append(asset(DENSE, PINS[DENSE]))
        r = evaluate(m, required_asset_pins={DENSE: PINS[DENSE]})
        self.assertEqual(r["outcome"], "HOLD")
        self.assertIn("PRIOR_ART_REJECTION_NEEDS_INDEPENDENT_REVIEW:" + DENSE, r["blockers"])

    def test_reuse_still_blocks_reinvented_packet(self):
        m = manifest()
        m["assets"].append(asset(DETECTOR, PINS[DETECTOR], disposition="REUSE"))
        r = evaluate(m, required_asset_pins={DETECTOR: PINS[DETECTOR]})
        self.assertIn("DUPLICATE_BUILD_WHEN_REUSE_EXISTS:" + DETECTOR, r["blockers"])

    def test_existing_result_reuse_remains_eligible(self):
        m = manifest()
        m["intent"] = "USE_EXISTING"
        m["assets"] = [asset(DETECTOR, PINS[DETECTOR], disposition="REUSE")]
        r = evaluate(m, required_asset_pins={DETECTOR: PINS[DETECTOR]})
        self.assertEqual(r["outcome"], "READY_FOR_AUTHORITY_REVIEW")
        self.assertEqual(r["authority_effect"], "NONE")
        self.assertEqual(r["skill_promotion"], "DENIED")

    def test_unrelated_task_not_blocked_by_rh_only_contract(self):
        # The scope of the trusted contract is task-specific, not universal.
        r = evaluate(manifest(), required_asset_pins={})
        self.assertEqual(r["outcome"], "READY_FOR_AUTHORITY_REVIEW")

    def test_model_cannot_add_authoritative_contract_field(self):
        m = manifest()
        m["required_asset_pins"] = {}
        with self.assertRaisesRegex(ValueError, "MANIFEST_FIELDS_INVALID"):
            evaluate(m)

    def test_malformed_contract_denied(self):
        for pins in ({DETECTOR: "main"}, {"bad key!": "a" * 40}, {DETECTOR: 3}):
            with self.subTest(pins=pins):
                with self.assertRaisesRegex(ValueError, "INVALID_REQUIRED_ASSET_PINS"):
                    evaluate(manifest(), required_asset_pins=pins)

    def test_source_contract_is_hash_bound_and_replay_deterministic(self):
        m = manifest()
        a = evaluate(m, required_asset_pins=PINS)
        b = evaluate(copy.deepcopy(m), required_asset_pins=dict(reversed(list(PINS.items()))))
        self.assertEqual(a, b)
        self.assertEqual(a["required_asset_pins_sha256"], hashlib.sha256(canonical(PINS)).hexdigest())
        h = a["receipt_hash"]
        self.assertEqual(h, hashlib.sha256(canonical({k: v for k, v in a.items() if k != "receipt_hash"})).hexdigest())
        self.assertNotIn("GRANTED", str(a))


if __name__ == "__main__":
    unittest.main()
