"""The cognitive manifest must not depend on which branch generated it.

Before this invariant existed, provenance.source_ref carried the branch name and
fed state_hash, so every branch produced different bytes for an identical skills
tree. Every long-lived branch therefore conflicted with main on .claude.json --
measured on eleven pull requests in one evening, and on no other file.

The manifest is a statement about the skills tree. The branch that happened to
run CI is not part of that statement; git already records it.
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
GENERATOR = REPO_ROOT / "scripts" / "build-cognitive-manifest.py"
PARENT_HASH = "0" * 64


def _load_generator():
    spec = importlib.util.spec_from_file_location("_manifest_gen", GENERATOR)
    module = importlib.util.module_from_spec(spec)
    sys.modules["_manifest_gen"] = module
    spec.loader.exec_module(module)
    return module


def test_manifest_bytes_are_identical_across_branches() -> None:
    gen = _load_generator()
    a, a_hashes = gen.build_manifest(
        REPO_ROOT, source_ref="feat/some-branch", parent_state_hash=PARENT_HASH
    )
    b, b_hashes = gen.build_manifest(
        REPO_ROOT, source_ref="fix/an-entirely-different-branch", parent_state_hash=PARENT_HASH
    )
    assert gen.render_manifest(a) == gen.render_manifest(b), (
        "two branches produced different manifest bytes for one skills tree"
    )
    assert a_hashes == b_hashes
    assert a["state_hash"] == b["state_hash"]


def test_state_hash_still_tracks_the_skills_tree() -> None:
    """Branch-invariance must not become hash-blindness."""
    gen = _load_generator()
    base, _ = gen.build_manifest(
        REPO_ROOT, source_ref="whatever", parent_state_hash=PARENT_HASH
    )
    moved, _ = gen.build_manifest(
        REPO_ROOT, source_ref="whatever", parent_state_hash="1" * 64
    )
    assert base["state_hash"] != moved["state_hash"], (
        "state_hash ignored parent_state_hash; the chain is no longer anchored"
    )
