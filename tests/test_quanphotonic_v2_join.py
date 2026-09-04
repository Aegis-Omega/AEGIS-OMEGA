import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

PIPELINE = Path('scripts/aegis_empirical_pipeline_v2.py')
PROFILE = Path('governance/AEGIS_CANONICAL_DIGEST_PROFILE_V2.json')
JOIN_SCHEMA = Path('schemas/aegis-evidence-join.v2.biological.schema.json')


def load_pipeline():
    spec = importlib.util.spec_from_file_location('aegis_empirical_pipeline_v2', PIPELINE)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class EvidenceJoinV2Tests(unittest.TestCase):
    def test_profile_content_addresses_evidence_join_v2(self):
        profile = json.loads(PROFILE.read_text())
        self.assertEqual(profile['self_digest_fields']['AEGIS_EVIDENCE_JOIN_V2'], 'packet_digest_sha256')

    def test_join_schema_requires_context_and_covariate_binding(self):
        schema = json.loads(JOIN_SCHEMA.read_text())
        required = set(schema['required'])
        self.assertIn('biological_context_digest', required)
        self.assertIn('classical_covariate_manifest_digest', required)
        self.assertIn('packet_digest_sha256', required)

    def test_runner_emits_digest_bound_evidence_join_v2(self):
        m = load_pipeline()
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            paths = []
            for name in ['bio.json','cov.json','classical.bin','cal.json','measurement.json','raw.bin','raw-manifest.json','analysis.json']:
                p = root / name
                p.write_bytes(('fixture:' + name).encode())
                paths.append(p)
            joined = m.evidence_join(
                *paths,
                biological_context_digest='a' * 64,
                classical_covariate_manifest_digest='b' * 64,
            )
        self.assertEqual(joined['schema'], 'AEGIS_EVIDENCE_JOIN_V2')
        self.assertEqual(joined['biological_context_digest'], 'a' * 64)
        self.assertEqual(joined['classical_covariate_manifest_digest'], 'b' * 64)
        self.assertEqual(joined['packet_digest_sha256'], m.canonical_self_digest(joined, 'packet_digest_sha256'))
        scopes = {a['authority_scope'] for a in joined['artifacts']}
        self.assertIn('BIOLOGICAL_CONTEXT_MANIFEST', scopes)
        self.assertIn('CLASSICAL_COVARIATE_MANIFEST', scopes)
        self.assertIn('CLASSICAL_FEATURE_PAYLOAD', scopes)


if __name__ == '__main__':
    unittest.main()
