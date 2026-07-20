from __future__ import annotations

from hashlib import sha256
from pathlib import Path
import sys
import unittest

ADAPTER_DIR = Path(__file__).resolve().parents[1] / "adapters"
sys.path.insert(0, str(ADAPTER_DIR))

from provider_evidence import (  # noqa: E402
    ExternalReference,
    ModelProvenance,
    ProviderEvidenceError,
    normalize_provider_evidence,
    to_authority_evidence,
)


ZERO = sha256(b"").hexdigest()
ONE = sha256(b"1").hexdigest()
COMMIT = "a" * 40
CONTAINER = "sha256:" + "b" * 64


class ProviderEvidenceTests(unittest.TestCase):
    def normalize(self, **overrides):
        values = {
            "provider": "github",
            "capability": "repo.read",
            "request_digest": ZERO,
            "response_digest": ONE,
            "status": "SUCCEEDED",
            "evidence_tier": "T1",
            "external_reference": ExternalReference(
                kind="commit",
                id="Aegis-Omega/AEGIS-OMEGA",
                revision=COMMIT,
            ),
            "observed_at": "2026-07-20T19:00:00Z",
        }
        values.update(overrides)
        return normalize_provider_evidence(**values)

    def test_evidence_is_deterministic_and_non_authoritative(self):
        first = self.normalize()
        second = self.normalize()
        self.assertEqual(first.evidence_digest, second.evidence_digest)
        self.assertFalse(first.grants_authority)
        self.assertFalse(to_authority_evidence(first)["grants_authority"])

    def test_dataverse_requires_etag(self):
        with self.assertRaises(ProviderEvidenceError):
            self.normalize(
                provider="dataverse",
                capability="entity.read",
                external_reference=ExternalReference(kind="row", id="account:1", revision="v1"),
            )

    def test_sharepoint_requires_drive_item_and_etag(self):
        evidence = self.normalize(
            provider="sharepoint",
            capability="knowledge.read",
            external_reference=ExternalReference(
                kind="drive_item",
                id="drive/item",
                revision="version-7",
                etag='"etag-7"',
            ),
        )
        self.assertEqual(evidence.provider, "sharepoint")

    def test_huggingface_requires_pinned_revision_and_model_provenance(self):
        with self.assertRaises(ProviderEvidenceError):
            self.normalize(
                provider="huggingface",
                capability="model.read",
                external_reference=ExternalReference(kind="model", id="aegis/model", revision="main"),
            )

    def test_nvidia_requires_nim_endpoint_and_container_digest(self):
        evidence = self.normalize(
            provider="nvidia",
            capability="inference.run",
            evidence_tier="T2",
            external_reference=ExternalReference(
                kind="nim_inference",
                id="sol-nim-primary",
                revision="2.0.8",
                endpoint="https://nim.internal/v1/chat/completions",
            ),
            model_provenance=ModelProvenance(
                model_id="openai/gpt-oss-20b",
                revision=COMMIT,
                runtime="nvidia-nim-vllm",
                hardware_profile="h100-sxm",
                container_digest=CONTAINER,
            ),
        )
        self.assertEqual(evidence.external_reference.kind, "nim_inference")

    def test_wolfram_requires_result_checksum(self):
        with self.assertRaises(ProviderEvidenceError):
            self.normalize(
                provider="wolfram",
                capability="invariant.evaluate",
                external_reference=ExternalReference(
                    kind="wolfram_result",
                    id="query-1",
                    revision="engine-2026",
                ),
            )

    def test_figma_rejects_unknown_reference_kind(self):
        with self.assertRaises(ProviderEvidenceError):
            self.normalize(
                provider="figma",
                capability="design.read",
                external_reference=ExternalReference(kind="file", id="abc", revision="123"),
            )

    def test_failed_provider_call_remains_evidence_not_authority(self):
        evidence = self.normalize(status="FAILED")
        self.assertEqual(evidence.status, "FAILED")
        self.assertFalse(evidence.grants_authority)


if __name__ == "__main__":
    unittest.main()
