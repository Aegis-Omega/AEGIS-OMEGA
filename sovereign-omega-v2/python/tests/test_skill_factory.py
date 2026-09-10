#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from unittest import TestCase, main

ROOT = Path(__file__).resolve().parents[3]
SCRIPT = ROOT / "scripts" / "build-skill-factory.py"
TAXONOMY = ROOT / "knowledge" / "skill-taxonomy.v1.json"


def load_factory():
    spec = importlib.util.spec_from_file_location("build_skill_factory", SCRIPT)
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load skill factory")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class SkillFactoryTests(TestCase):
    def test_factory_emits_2048_unique_candidates_deterministically(self):
        factory = load_factory()
        taxonomy = json.loads(TAXONOMY.read_text(encoding="utf-8"))
        first = factory.build_registry(taxonomy)
        second = factory.build_registry(taxonomy)
        self.assertEqual(first, second)
        self.assertEqual(first["candidate_count"], 2048)
        ids = [item["skill_id"] for item in first["skills"]]
        self.assertEqual(len(ids), len(set(ids)))

    def test_candidates_have_zero_authority_until_evidence_promotes_them(self):
        factory = load_factory()
        taxonomy = json.loads(TAXONOMY.read_text(encoding="utf-8"))
        registry = factory.build_registry(taxonomy)
        self.assertEqual(registry["admitted_count"], 0)
        self.assertTrue(all(item["status"] == "CANDIDATE" for item in registry["skills"]))
        self.assertTrue(all(item["authority_effect"] == "NONE" for item in registry["skills"]))
        self.assertTrue(all(item["minimum_validated_runs"] >= 1 for item in registry["skills"]))


if __name__ == "__main__":
    main()
