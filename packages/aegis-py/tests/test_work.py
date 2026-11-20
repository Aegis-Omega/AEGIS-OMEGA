"""Offline workflow-pack tests; no network, secrets, or external dependencies."""
from __future__ import annotations

import io
import json
import os
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

from aegis.cli import main
from aegis.packs import PACKS, get_pack
from aegis.work import (
    SCHEMA_V0,
    SCHEMA_V1,
    export_pack,
    migrate_pack,
    run_work_command,
    validate_pack,
)


class WorkflowPackTests(unittest.TestCase):
    def test_three_synthetic_samples_validate_and_verify_offline(self) -> None:
        for name in ("code", "data", "science"):
            with self.subTest(name=name):
                pack = get_pack(name)
                self.assertTrue(validate_pack(pack)["valid"])
                self.assertEqual(
                    json.loads(run_work_command("verify", name))["verification"],
                    "EMBEDDED_ARTIFACT_DIGESTS_VALID",
                )

    def test_sample_pack_is_importable_and_copy_is_independent(self) -> None:
        self.assertEqual(set(PACKS), {"code", "data", "science"})
        pack = get_pack("code")
        pack["permissions"] = "write"
        self.assertEqual(get_pack("code")["permissions"], "read_only")

    def test_simulation_is_explicitly_non_executing(self) -> None:
        result = json.loads(run_work_command("simulate", "science"))
        self.assertEqual(result["execution"], "NOT_EXECUTED")
        self.assertTrue(all(step["status"] == "NOT_EXECUTED" for step in result["steps"]))
        self.assertEqual(result["acceptance"][0]["status"], "NOT_EVALUATED")
        self.assertEqual(result["authority_effect"], "NONE")

    def test_embedded_artifact_tampering_is_rejected(self) -> None:
        pack = get_pack("data")
        pack["artifacts"][0]["content"] += "tampered\n"
        with self.assertRaisesRegex(ValueError, "SHA-256 mismatch"):
            validate_pack(pack)

    def test_non_read_only_authority_is_rejected(self) -> None:
        pack = get_pack("code")
        pack["permissions"] = "write"
        with self.assertRaisesRegex(ValueError, "read_only"):
            validate_pack(pack)

    def test_invalid_domain_type_is_rejected(self) -> None:
        pack = get_pack("code")
        pack["domain"] = []
        with self.assertRaisesRegex(ValueError, "domain"):
            validate_pack(pack)

    def test_schema_migration_sets_only_read_only_default(self) -> None:
        legacy = get_pack("code")
        legacy["schema"] = SCHEMA_V0
        del legacy["permissions"]
        migrated = migrate_pack(legacy)
        self.assertEqual(migrated["schema"], SCHEMA_V1)
        self.assertEqual(migrated["permissions"], "read_only")
        self.assertTrue(validate_pack(migrated)["valid"])

    def test_schema_migration_refuses_explicit_permission_override(self) -> None:
        legacy = get_pack("code")
        legacy["schema"] = SCHEMA_V0
        with self.assertRaisesRegex(ValueError, "permissions field"):
            migrate_pack(legacy)

    def test_duplicate_json_keys_are_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "duplicate.json"
            path.write_text('{"schema":"a","schema":"b"}', encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "duplicate JSON key"):
                run_work_command("validate", str(path))

    def test_export_is_deterministic_json_without_file_writes(self) -> None:
        first = export_pack(get_pack("science"))
        second = export_pack(get_pack("science"))
        self.assertEqual(first, second)
        self.assertEqual(json.loads(first)["schema"], SCHEMA_V1)

    def test_cli_runs_without_key_or_network(self) -> None:
        output = io.StringIO()
        with patch.dict(os.environ, {"AEGIS_API_KEY": ""}), \
             patch("urllib.request.urlopen") as urlopen, \
             redirect_stdout(output):
            self.assertEqual(main(["work", "simulate", "code"]), 0)
        urlopen.assert_not_called()
        self.assertEqual(json.loads(output.getvalue())["execution"], "NOT_EXECUTED")

    def test_cli_exports_each_sample_as_json(self) -> None:
        for operation in ("validate", "plan", "simulate", "verify", "export"):
            with self.subTest(operation=operation):
                output = io.StringIO()
                with redirect_stdout(output):
                    self.assertEqual(main(["work", operation, "data"]), 0)
                self.assertEqual(json.loads(output.getvalue())["schema"], SCHEMA_V1)


if __name__ == "__main__":
    unittest.main()
