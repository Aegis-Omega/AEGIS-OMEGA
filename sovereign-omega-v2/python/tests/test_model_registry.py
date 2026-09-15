from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT))

from harness.sdk.model_registry import (  # noqa: E402
    LOCAL_SURFACE,
    MODEL_OUTPUT_AUTHORITY,
    REMOTE_SURFACE,
    ModelCapabilityRegistry,
    ModelRegistryError,
)


def registry() -> ModelCapabilityRegistry:
    return ModelCapabilityRegistry.load()


def private_registry(*, mirror_state: str) -> ModelCapabilityRegistry:
    registry_payload = json.loads((REPO_ROOT / "config" / "model-capability-registry.v1.json").read_text(encoding="utf-8"))
    artifact_payload = json.loads((REPO_ROOT / "models" / "model-artifacts.v1.json").read_text(encoding="utf-8"))
    registry_payload = copy.deepcopy(registry_payload)
    artifact_payload = copy.deepcopy(artifact_payload)

    artifact_payload["packages"]["operator-private-test"] = {
        "family": "operator-private",
        "provider": "operator-local",
        "weight_availability": "PRIVATE_OPERATOR_WEIGHTS",
        "license": {"spdx": None, "redistribution_status": "PRIVATE_OPERATOR_ONLY"},
        "source": {
            "kind": "operator_private",
            "opaque_ref": "operator-vault:test",
            "revision": "a" * 64,
            "revision_kind": "PRIVATE_CONTENT_ROOT",
            "content_root_sha256": "a" * 64,
        },
        "checkpoint": {"declared_shard_count": 1, "complete_shard_digest_set": True},
        "files": [{"path": "weights.bin", "sha256": "b" * 64, "required_for_local_execution": True}],
        "checkout_path": "models/weights/operator-private-test",
        "mirror": {
            "state": mirror_state,
            "backend": "operator_private_store",
            "release_tag": None,
            "manifest_path": "models/releases/operator-private-test.release.json",
        },
    }
    registry_payload["models"]["operator-private-test"] = {
        "provider": "operator-local",
        "status": "active",
        "capabilities": ["local_execution", "structured_output"],
        "recommended_roles": ["local_private_executor"],
        "artifact_package": "operator-private-test",
        "execution_surfaces": ["local_checkpoint"],
    }
    return ModelCapabilityRegistry(registry_payload, artifact_payload)


def test_unknown_model_fails_closed() -> None:
    with pytest.raises(ModelRegistryError):
        registry().get_model("future-unregistered-model")


def test_candidate_models_are_not_executable_by_default() -> None:
    candidates = registry().resolve("planner")
    assert candidates
    assert all(candidate.status in {"active", "active_legacy"} for candidate in candidates)
    ids = {candidate.model_id for candidate in candidates}
    assert "gpt-5.6-sol" not in ids
    assert "claude-fable-5" not in ids
    assert "claude-opus-5" not in ids
    assert "claude-sonnet-5" not in ids
    assert "deepseek-v4-pro" not in ids
    assert "qwen3.8-max" not in ids


def test_legacy_inventory_remains_remote_and_evidence_only() -> None:
    candidates = registry().resolve("coder", execution_surface=REMOTE_SURFACE)
    by_id = {candidate.model_id: candidate for candidate in candidates}
    for model_id in (
        "claude-haiku-4-5-20251001",
        "claude-sonnet-4-6",
        "gpt-4o",
        "qwen-plus",
        "qwen3.7-plus",
    ):
        assert model_id in by_id
        assert by_id[model_id].execution_surfaces == (REMOTE_SURFACE,)
        assert by_id[model_id].authority == MODEL_OUTPUT_AUTHORITY == "EVIDENCE_ONLY"


def test_candidate_planners_can_be_inspected_without_activation() -> None:
    candidates = registry().resolve(
        "planner",
        include_candidates=True,
        execution_surface=REMOTE_SURFACE,
    )
    ids = {candidate.model_id for candidate in candidates}
    assert "gpt-5.6-sol" in ids
    assert "claude-fable-5" in ids
    assert "claude-opus-5" in ids
    assert "claude-sonnet-5" in ids
    assert "deepseek-v4-pro" in ids
    assert "qwen3.8-max" in ids


def test_local_gemma_is_not_routable_until_repo_mirror_is_verified() -> None:
    assert registry().resolve(
        "local_private_executor",
        include_candidates=True,
        execution_surface=LOCAL_SURFACE,
    ) == ()

    inspectable = registry().resolve(
        "local_private_executor",
        include_candidates=True,
        execution_surface=LOCAL_SURFACE,
        require_artifact_ready=False,
    )
    assert [candidate.model_id for candidate in inspectable] == ["gemma-4-local"]
    assert inspectable[0].artifact_package == "gemma-4-e2b-it-bf16"


def test_verified_private_weights_can_satisfy_local_surface_without_publicity() -> None:
    candidates = private_registry(mirror_state="PRIVATE_MIRRORED_VERIFIED").resolve(
        "local_private_executor",
        execution_surface=LOCAL_SURFACE,
    )
    assert [candidate.model_id for candidate in candidates] == ["operator-private-test"]
    assert candidates[0].provider == "operator-local"
    assert candidates[0].authority == "EVIDENCE_ONLY"


def test_private_weights_fail_closed_before_private_mirror_verification() -> None:
    candidates = private_registry(mirror_state="PRIVATE_SOURCE_REGISTERED_NOT_YET_MIRRORED").resolve(
        "local_private_executor",
        execution_surface=LOCAL_SURFACE,
    )
    assert candidates == ()


def test_incomplete_deepseek_checkpoint_cannot_route_locally() -> None:
    ready = registry().resolve(
        "coder",
        include_candidates=True,
        execution_surface=LOCAL_SURFACE,
    )
    assert all(not candidate.model_id.startswith("deepseek-v4") for candidate in ready)

    inspectable = registry().resolve(
        "coder",
        include_candidates=True,
        execution_surface=LOCAL_SURFACE,
        require_artifact_ready=False,
    )
    ids = {candidate.model_id for candidate in inspectable}
    assert "deepseek-v4-pro" in ids
    assert "deepseek-v4-flash" in ids


def test_adversarial_audit_can_require_provider_diversity() -> None:
    candidates = registry().require_provider_diversity(
        "adversarial_auditor",
        compared_provider="openai",
        include_candidates=True,
        execution_surface=REMOTE_SURFACE,
    )
    assert candidates
    assert all(candidate.provider != "openai" for candidate in candidates)


def test_unknown_execution_surface_fails_closed() -> None:
    with pytest.raises(ModelRegistryError):
        registry().resolve("coder", execution_surface="magic-transport")
