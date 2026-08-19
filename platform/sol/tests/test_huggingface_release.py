from __future__ import annotations

from pathlib import Path
import sys
import tempfile
import unittest

PREFLIGHT_DIR = Path(__file__).resolve().parents[1] / "huggingface"
sys.path.insert(0, str(PREFLIGHT_DIR))

from release_preflight import (  # noqa: E402
    ReleaseError,
    build_manifest,
    collect_release_files,
    load_release,
    require_pinned_revision,
)


COMMIT = "a" * 40


class HuggingFaceReleaseTests(unittest.TestCase):
    def test_requires_immutable_base_revision(self):
        with self.assertRaises(ReleaseError):
            require_pinned_revision("main")
        self.assertEqual(require_pinned_revision(COMMIT), COMMIT)

    def test_release_declares_no_weights_and_no_authority(self):
        release = load_release(PREFLIGHT_DIR / "ogemma-release.v1.json")
        self.assertEqual(release["artifact_kind"], "configuration-holon-no-weights")
        self.assertFalse(release["grants_authority"])

    def test_collect_rejects_weight_like_artifact(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "source").mkdir()
            (root / "card.md").write_text("safe", encoding="utf-8")
            (root / "source" / "weights.safetensors").write_bytes(b"weights")
            release = {
                "source_root": "source",
                "model_card": "card.md",
                "artifacts": ["weights.safetensors"],
                "forbidden_artifact_suffixes": [".safetensors"],
            }
            with self.assertRaises(ReleaseError):
                collect_release_files(root, release)

    def test_manifest_is_deterministic(self):
        release = load_release(PREFLIGHT_DIR / "ogemma-release.v1.json")
        first = build_manifest(release, [], COMMIT)
        second = build_manifest(release, [], COMMIT)
        self.assertEqual(first["manifest_digest"], second["manifest_digest"])
        self.assertFalse(first["grants_authority"])


if __name__ == "__main__":
    unittest.main()
