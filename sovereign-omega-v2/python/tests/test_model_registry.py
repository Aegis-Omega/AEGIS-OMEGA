from __future__ import annotations

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


def test_unknown_model_fails_closed() -> None:
    with pytest.raises(ModelRegistryError):
        registry().get_model("future-unregistered-model")


def test_candidate_models_are_not_executable_by_default() -> None:
    assert registry().resolve("planner") == ()
    with pytest.raises(ModelRegistryError):
        registry().require_one("planner")


def test_legacy_active_qwen_remains_remote_executor_only() -> None:
    candidates = registry().resolve("coder", execution_surface=REMOTE_SURFACE)
    assert [c.model_id for c in candidates] == ["qwen-plus"]
    assert candidates[0].execution_surfaces == (REMOTE_SURFACE,)
    assert candidates[0].authority == MODEL_OUTPUT_AUTHORITY == "EVIDENCE_ONLY"


def test_candidate_planners_can_be_inspected_without_activation() -> None:
    candidates = registry().resolve(
        "planner",
        include_candidates=True,
        execution_surface=REMOTE_SURFACE,
    )
    ids = {candidate.model_id for candidate in candidates}
    assert "gpt-5.6-sol" in ids
    assert "claude-opus-5" in ids
    assert "claude-sonnet-5" in ids
    assert "deepseek-v4-pro" in ids


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
