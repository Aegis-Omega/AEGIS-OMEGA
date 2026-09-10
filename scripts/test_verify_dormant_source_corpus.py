#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import os
import shutil
import tempfile
import unittest
from pathlib import Path

import verify_dormant_source_corpus as verifier


class DormantCorpusVerifierTests(unittest.TestCase):
    def setUp(self) -> None:
        parent = Path("knowledge/source-corpora")
        parent.mkdir(parents=True, exist_ok=True)
        self.root = Path(tempfile.mkdtemp(prefix="test-corpus-", dir=parent))
        self.skills = self.root / "skills"
        (self.skills / "demo").mkdir(parents=True)
        self.skill = self.skills / "demo" / "SKILL.md"
        self.skill.write_text(
            "---\n"
            "name: demo\n"
            "license: Apache-2.0\n"
            "metadata:\n"
            "  publisher: google\n"
            "---\n\n"
            "Dormant fixture.\n",
            encoding="utf-8",
        )
        evidence = self.root / "evidence"
        evidence.mkdir()
        self.source_manifest = evidence / "source-manifest.json"
        self.source_manifest.write_text('{"skills":{"demo":{}}}\n', encoding="utf-8")
        self._write_provenance()

    def tearDown(self) -> None:
        shutil.rmtree(self.root, ignore_errors=True)

    def _records(self) -> list[dict[str, object]]:
        records = []
        for path in sorted(p for p in self.skills.rglob("*") if p.is_file() and not p.is_symlink()):
            data = path.read_bytes()
            records.append(
                {
                    "path": path.relative_to(self.skills).as_posix(),
                    "sha256": hashlib.sha256(data).hexdigest(),
                    "size_bytes": len(data),
                }
            )
        return records

    def _root_hash(self) -> str:
        payload = json.dumps(
            self._records(), ensure_ascii=False, sort_keys=True, separators=(",", ":")
        ).encode("utf-8")
        return hashlib.sha256(payload).hexdigest()

    def _write_provenance(self, **overrides: object) -> None:
        provenance = {
            "schema": verifier.SCHEMA,
            "corpus_id": "test-corpus",
            "repository": "Aegis-Omega/AEGIS-OMEGA",
            "source_pr": 240,
            "source_sha": "1" * 40,
            "source_prefix": ".agents/skills",
            "source_manifest_sha256": hashlib.sha256(self.source_manifest.read_bytes()).hexdigest(),
            "destination_prefix": self.root.relative_to(Path.cwd()).as_posix() + "/skills",
            "file_count": len(self._records()),
            "package_count": 1,
            "corpus_root_sha256": self._root_hash(),
            "licenses": {"Apache-2.0": 1},
            "publishers": {"google": 1},
            "epistemic_status": "UNVERIFIED_SOURCE_CORPUS",
            "activation_status": "DORMANT_NOT_DISCOVERABLE_BY_ACTIVE_SKILL_PATH",
            "execution_status": "SOURCE_BYTES_NOT_EXECUTED",
            "authority_effect": "NONE",
        }
        provenance.update(overrides)
        (self.root / "provenance.json").write_text(
            json.dumps(provenance, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )

    def test_valid_dormant_corpus_passes(self) -> None:
        receipt = verifier.verify(self.root)
        self.assertEqual(receipt["verification"], "PASS")
        self.assertEqual(receipt["authority_effect"], "NONE")

    def test_byte_tamper_is_denied(self) -> None:
        self.skill.write_text(self.skill.read_text(encoding="utf-8") + "tamper\n", encoding="utf-8")
        with self.assertRaisesRegex(verifier.CorpusVerificationError, "corpus_root_sha256 mismatch"):
            verifier.verify(self.root)

    def test_authority_widening_is_denied(self) -> None:
        self._write_provenance(authority_effect="EXECUTE")
        with self.assertRaisesRegex(verifier.CorpusVerificationError, "authority_effect must equal NONE"):
            verifier.verify(self.root)

    def test_activation_widening_is_denied(self) -> None:
        self._write_provenance(activation_status="ACTIVE")
        with self.assertRaisesRegex(
            verifier.CorpusVerificationError,
            "activation_status must equal DORMANT_NOT_DISCOVERABLE_BY_ACTIVE_SKILL_PATH",
        ):
            verifier.verify(self.root)

    def test_source_manifest_digest_splice_is_denied(self) -> None:
        self.source_manifest.write_text('{"skills":{"other":{}}}\n', encoding="utf-8")
        with self.assertRaisesRegex(verifier.CorpusVerificationError, "source manifest digest mismatch"):
            verifier.verify(self.root)

    @unittest.skipUnless(hasattr(os, "symlink"), "symlink unavailable")
    def test_symlink_is_denied(self) -> None:
        target = self.skills / "demo" / "payload.txt"
        target.write_text("payload\n", encoding="utf-8")
        link = self.skills / "demo" / "alias.txt"
        os.symlink(target.name, link)
        self._write_provenance()
        with self.assertRaisesRegex(verifier.CorpusVerificationError, "symlink forbidden"):
            verifier.verify(self.root)


if __name__ == "__main__":
    unittest.main()
