import pathlib
import sys
import unittest

MODULE_DIR = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(MODULE_DIR))

import cross_domain_collision as cdc
import cross_domain_coverage as cov
import cross_domain_epoch as epoch
import cross_domain_ingest as ingest
import cross_domain_registry_adapters as adapters


UNICODE_FIXTURE = b"# DerivedGeneralCategory-17.0.0.txt\n0041 ; Lu\n0378..0379 ; Cn\n"
NCBI_MATCH = b'{"esearchresult":{"count":"1","retmax":"2","retstart":"0","idlist":["42"],"querytranslation":"42[UID] OR 43[UID]"}}'


def criterion():
    return cdc.CollisionCriterionV1(
        universe_min=0,
        universe_max=100000,
        registry_set=("unicode", "ncbi-gene"),
        transform_set=("INTEGER_IDENTITY_EXTERNAL_LOOKUP_KEY_V1",),
        independence_rule_id="UNIQUE_DOMAIN_ID_V1",
        score_function_id="UNIQUE_EXTERNAL_DOMAINS_V1",
        control_generator_id="PY_RANDOM_UNIFORM_INT_V1",
        control_seed=1234,
        control_count=8,
        promotion_threshold=None,
        criterion_text="prospective-adapter-test-v1",
    )


def unicode_capture(raw=UNICODE_FIXTURE, *, release="17.0.0", status=200):
    contract = adapters.unicode_source_contract_v1()
    return ingest.capture_source_bytes(
        source_id=contract.source_id,
        source_contract_sha256=contract.contract_sha256,
        request_identity=contract.source_locator,
        request_subject_sha256s=(),
        source_version_or_release=release,
        response_status=status,
        media_type="text/plain",
        raw_content=raw,
        observed_at="2026-08-25T00:00:00Z",
        producer_id="test",
        attempt_index=0,
    )


def ncbi_fixture(raw=NCBI_MATCH, *, status=200):
    subjects = (cdc.IntegerSubjectV1(42), cdc.IntegerSubjectV1(43))
    request_identity, ordered = adapters.make_ncbi_batch_request(subjects)
    contract = adapters.ncbi_gene_source_contract_v1()
    capture = ingest.capture_source_bytes(
        source_id=contract.source_id,
        source_contract_sha256=contract.contract_sha256,
        request_identity=request_identity,
        request_subject_sha256s=tuple(s.subject_sha256 for s in ordered),
        source_version_or_release="observed-2026-08-25",
        response_status=status,
        media_type="application/json",
        raw_content=raw,
        observed_at="2026-08-25T00:00:00Z",
        producer_id="test",
        attempt_index=0,
    )
    return subjects, ordered, capture


class RegistryAdapterTests(unittest.TestCase):
    def test_epoch_contract_digests_match_source_factories(self):
        e = epoch.make_epoch_v1(seed=1, subject_count=8)
        self.assertEqual(
            e.registry_adapter_contract_sha256s,
            (
                adapters.unicode_adapter_contract_v1().contract_sha256,
                adapters.ncbi_gene_adapter_contract_v1().contract_sha256,
            ),
        )
        self.assertEqual(
            e.source_contract_sha256s,
            (
                adapters.unicode_source_contract_v1().contract_sha256,
                adapters.ncbi_gene_source_contract_v1().contract_sha256,
            ),
        )

    def test_unicode_non_cn_is_match_and_cn_is_no_match(self):
        c = criterion()
        assigned = adapters.probe_unicode_general_category(
            cdc.IntegerSubjectV1(0x41), c, unicode_capture()
        )
        unassigned = adapters.probe_unicode_general_category(
            cdc.IntegerSubjectV1(0x378), c, unicode_capture()
        )
        self.assertEqual(assigned.probe.receipt.outcome, cov.RegistryProbeOutcomeV1.MATCH)
        self.assertEqual(unassigned.probe.receipt.outcome, cov.RegistryProbeOutcomeV1.NO_MATCH)
        adapters.verify_source_verified_probe(assigned)
        adapters.verify_source_verified_probe(unassigned)

    def test_unicode_overlap_fails_closed(self):
        bad = b"0040..0042 ; Lu\n0041 ; Cn\n"
        with self.assertRaises(ValueError):
            adapters.probe_unicode_general_category(
                cdc.IntegerSubjectV1(0x41), criterion(), unicode_capture(bad)
            )

    def test_unicode_uncovered_or_wrong_release_is_not_negative_evidence(self):
        with self.assertRaises(ValueError):
            adapters.probe_unicode_general_category(
                cdc.IntegerSubjectV1(0x42), criterion(), unicode_capture()
            )
        with self.assertRaises(ValueError):
            adapters.probe_unicode_general_category(
                cdc.IntegerSubjectV1(0x41), criterion(), unicode_capture(release="16.0.0")
            )

    def test_ncbi_batch_is_sorted_unique_and_bounded(self):
        subjects = (
            cdc.IntegerSubjectV1(43),
            cdc.IntegerSubjectV1(42),
            cdc.IntegerSubjectV1(43),
        )
        identity, ordered = adapters.make_ncbi_batch_request(subjects)
        self.assertEqual(tuple(s.value for s in ordered), (42, 43))
        self.assertIn("42%5BUID%5D", identity)
        self.assertIn("43%5BUID%5D", identity)
        with self.assertRaises(ValueError):
            adapters.make_ncbi_batch_request(tuple(cdc.IntegerSubjectV1(i) for i in range(101)))

    def test_ncbi_uid_presence_and_absence_are_distinct(self):
        subjects, ordered, capture = ncbi_fixture()
        match = adapters.probe_ncbi_gene_esearch(subjects[0], criterion(), ordered, capture)
        no_match = adapters.probe_ncbi_gene_esearch(subjects[1], criterion(), ordered, capture)
        self.assertEqual(match.probe.receipt.outcome, cov.RegistryProbeOutcomeV1.MATCH)
        self.assertEqual(no_match.probe.receipt.outcome, cov.RegistryProbeOutcomeV1.NO_MATCH)
        adapters.verify_source_verified_probe(match)
        adapters.verify_source_verified_probe(no_match)

    def test_ncbi_unexpected_uid_fails_closed(self):
        raw = b'{"esearchresult":{"count":"1","retmax":"2","retstart":"0","idlist":["999"],"querytranslation":"42[UID] OR 43[UID]"}}'
        subjects, ordered, capture = ncbi_fixture(raw)
        with self.assertRaises(ValueError):
            adapters.probe_ncbi_gene_esearch(subjects[0], criterion(), ordered, capture)

    def test_ncbi_warning_truncation_or_transport_status_fails_closed(self):
        warning = b'{"esearchresult":{"count":"0","retmax":"2","retstart":"0","idlist":[],"warninglist":{"phrasesignored":["42[UID]"]},"querytranslation":"42[UID] OR 43[UID]"}}'
        subjects, ordered, capture = ncbi_fixture(warning)
        with self.assertRaises(ValueError):
            adapters.probe_ncbi_gene_esearch(subjects[0], criterion(), ordered, capture)

        truncated = b'{"esearchresult":{"count":"1","retmax":"0","retstart":"0","idlist":["42"],"querytranslation":"42[UID] OR 43[UID]"}}'
        subjects, ordered, capture = ncbi_fixture(truncated)
        with self.assertRaises(ValueError):
            adapters.probe_ncbi_gene_esearch(subjects[0], criterion(), ordered, capture)

        subjects, ordered, capture = ncbi_fixture(b"{}", status=429)
        with self.assertRaises(ValueError):
            adapters.probe_ncbi_gene_esearch(subjects[0], criterion(), ordered, capture)

    def test_ncbi_capture_cannot_splice_to_unrequested_subject(self):
        subjects, ordered, capture = ncbi_fixture()
        with self.assertRaises(ValueError):
            adapters.probe_ncbi_gene_esearch(
                cdc.IntegerSubjectV1(44), criterion(), ordered, capture
            )


if __name__ == "__main__":
    unittest.main()
