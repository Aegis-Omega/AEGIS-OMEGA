import pathlib
import sys
import unittest

MODULE_DIR = pathlib.Path(__file__).resolve().parents[1]
REPO_ROOT = pathlib.Path(__file__).resolve().parents[3]
sys.path.insert(0, str(MODULE_DIR))
import cross_domain_collision as cdc
import research_invariants as ri

FIXTURE_PATH = REPO_ROOT / ".aegis" / "cross-domain" / "fixtures" / "65010-v1.json"


class CrossDomainFixtureTests(unittest.TestCase):
    def test_65010_fixture_replays_offline_to_two_external_domains(self):
        replay = cdc.replay_fixture_bundle(FIXTURE_PATH)
        self.assertEqual(replay.subject.value, 65010)
        self.assertEqual(replay.subject.hex_upper, "FDF2")
        self.assertEqual(replay.subject.unicode_codepoint_label, "U+FDF2")
        self.assertEqual(replay.collision.provenance, cdc.SelectionProvenance.RETROSPECTIVE)
        self.assertEqual(replay.collision.independent_external_domain_count, 2)
        self.assertTrue(replay.collision.cross_registry_collision)
        self.assertEqual(replay.current_status, "CROSS_REGISTRY_COLLISION")

    def test_65010_fixture_replay_is_digest_identical(self):
        a = cdc.replay_fixture_bundle(FIXTURE_PATH)
        b = cdc.replay_fixture_bundle(FIXTURE_PATH)
        self.assertEqual(a.subject.subject_sha256, b.subject.subject_sha256)
        self.assertEqual(
            tuple(s.content_sha256 for s in a.snapshots),
            tuple(s.content_sha256 for s in b.snapshots),
        )
        self.assertEqual(
            tuple(o.observation_sha256 for o in a.observations),
            tuple(o.observation_sha256 for o in b.observations),
        )
        self.assertEqual(a.collision.receipt_sha256, b.collision.receipt_sha256)
        self.assertEqual(
            tuple(t.transition_sha256 for t in a.status_history),
            tuple(t.transition_sha256 for t in b.status_history),
        )

    def test_snapshot_key_mismatch_fails_before_observation(self):
        subject = cdc.IntegerSubjectV1(65010)
        transform = cdc.TransformSpecV1(
            "INTEGER_TO_UNICODE_CODEPOINT_V1",
            "1",
            "IntegerSubjectV1",
            "UnicodeCodePointLabel",
            "map an integer in [0, 0x10FFFF] to uppercase U+ code-point notation",
        )
        snapshot = cdc.RegistrySnapshotV1(
            registry_id="unicode",
            registry_version_or_release="Unicode-16.0.0",
            query_key="U+FDF3",
            query_key_type="unicode-codepoint",
            result_kind="assigned-codepoint-record",
            canonical_result={"codepoint": "U+FDF3", "name": "wrong key"},
            source_locator="fixture://wrong",
            source_observed_at="2026-08-25",
            ingestion_producer_id="test",
        )
        with self.assertRaises(ValueError):
            cdc.verify_snapshot_observation(
                subject=subject,
                snapshot=snapshot,
                transform=transform,
                evidence_class=cdc.EvidenceClass.STANDARD_CODEPOINT_MAPPING,
                normalized_claim="wrong mapping",
            )

    def test_retrospective_status_ceiling_blocks_null_survived(self):
        replay = cdc.replay_fixture_bundle(FIXTURE_PATH)
        journal = ri.StatusJournalV1("fixture-65010")
        cdc.append_collision_status(
            journal,
            "OBSERVED",
            [replay.collision.receipt_sha256],
            replay.criterion.criterion_sha256,
            "fixture observed",
        )
        cdc.append_collision_status(
            journal,
            "EXACT_MAPPING",
            [s.content_sha256 for s in replay.snapshots],
            replay.criterion.criterion_sha256,
            "frozen mappings verified",
        )
        cdc.append_collision_status(
            journal,
            "CROSS_REGISTRY_COLLISION",
            [replay.collision.receipt_sha256],
            replay.criterion.criterion_sha256,
            "two independent external domains",
        )
        with self.assertRaises(PermissionError):
            cdc.append_collision_status(
                journal,
                "NULL_SURVIVED",
                [replay.collision.receipt_sha256],
                replay.criterion.criterion_sha256,
                "retrospective cannot promote",
            )
        with self.assertRaises(PermissionError):
            cdc.append_collision_status(
                journal,
                "STRUCTURAL_RELATION",
                [replay.collision.receipt_sha256],
                replay.criterion.criterion_sha256,
                "statistics cannot mint mechanism",
            )


if __name__ == "__main__":
    unittest.main()
