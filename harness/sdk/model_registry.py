from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Mapping, Sequence


MODEL_OUTPUT_AUTHORITY = "EVIDENCE_ONLY"
DEFAULT_EXECUTABLE_STATUSES = frozenset({"active", "active_legacy"})
CANDIDATE_STATUS = "candidate"
REMOTE_SURFACE = "remote_api"
LOCAL_SURFACE = "local_checkpoint"
PUBLIC_MIRRORED_VERIFIED = "MIRRORED_VERIFIED"
PRIVATE_MIRRORED_VERIFIED = "PRIVATE_MIRRORED_VERIFIED"
LOCAL_WEIGHT_KINDS = frozenset({"PUBLIC_OPEN_WEIGHTS", "PRIVATE_OPERATOR_WEIGHTS"})


class ModelRegistryError(RuntimeError):
    """Raised when model selection cannot be proven safe from registry state."""


@dataclass(frozen=True)
class ModelCandidate:
    model_id: str
    provider: str
    status: str
    capabilities: tuple[str, ...]
    recommended_roles: tuple[str, ...]
    artifact_package: str
    execution_surfaces: tuple[str, ...]
    authority: str = MODEL_OUTPUT_AUTHORITY


class ModelCapabilityRegistry:
    """Deterministic, fail-closed model/provider/artifact resolver.

    Artifact existence and artifact publicity are deliberately separate. Public
    open weights and operator-private weights can both satisfy a local execution
    surface once their respective mirror state and local bytes are verified.

    Nothing selected here gains authorization, admission, effect, or state
    transition authority.
    """

    def __init__(self, payload: Mapping[str, object], artifact_payload: Mapping[str, object]) -> None:
        self._payload = payload
        self._artifact_payload = artifact_payload
        self._assert_constitutional_invariants()

    @classmethod
    def load(
        cls,
        path: Path | str | None = None,
        artifact_path: Path | str | None = None,
    ) -> "ModelCapabilityRegistry":
        repo_root = Path(__file__).resolve().parents[2]
        registry_path = Path(path) if path is not None else repo_root / "config" / "model-capability-registry.v1.json"
        model_artifact_path = Path(artifact_path) if artifact_path is not None else repo_root / "models" / "model-artifacts.v1.json"
        try:
            payload = json.loads(registry_path.read_text(encoding="utf-8"))
            artifact_payload = json.loads(model_artifact_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise ModelRegistryError(f"cannot load model registry/artifacts: {exc}") from exc
        if not isinstance(payload, dict) or not isinstance(artifact_payload, dict):
            raise ModelRegistryError("model registry and artifact index roots must be objects")
        return cls(payload, artifact_payload)

    def _assert_constitutional_invariants(self) -> None:
        if self._payload.get("authority_rule") != "MODEL_OUTPUT_IS_EVIDENCE_NOT_AUTHORITY":
            raise ModelRegistryError("registry authority rule is missing or changed")
        if self._artifact_payload.get("authority_rule") != "WEIGHTS_AND_MODEL_OUTPUTS_ARE_EVIDENCE_NOT_AUTHORITY":
            raise ModelRegistryError("model artifact authority rule is missing or changed")
        policy = self._mapping("selection_policy")
        if policy.get("fail_closed") is not True:
            raise ModelRegistryError("registry must fail closed")
        if policy.get("require_explicit_model_registration") is not True:
            raise ModelRegistryError("explicit model registration is required")
        if policy.get("allow_unknown_models") is not False:
            raise ModelRegistryError("unknown models must remain denied")
        storage = self._artifact_mapping("storage_policy")
        if storage.get("local_execution_requires_verified_hydration") is not True:
            raise ModelRegistryError("local execution must require verified model hydration")
        if storage.get("public_repository_plaintext_private_weights_forbidden") is not True:
            raise ModelRegistryError("private plaintext weights must remain excluded from the public repository")

    def _mapping(self, key: str) -> Mapping[str, object]:
        value = self._payload.get(key)
        if not isinstance(value, dict):
            raise ModelRegistryError(f"registry field {key!r} must be an object")
        return value

    def _artifact_mapping(self, key: str) -> Mapping[str, object]:
        value = self._artifact_payload.get(key)
        if not isinstance(value, dict):
            raise ModelRegistryError(f"artifact index field {key!r} must be an object")
        return value

    @property
    def roles(self) -> Mapping[str, object]:
        return self._mapping("roles")

    @property
    def providers(self) -> Mapping[str, object]:
        return self._mapping("providers")

    @property
    def models(self) -> Mapping[str, object]:
        return self._mapping("models")

    @property
    def artifact_packages(self) -> Mapping[str, object]:
        return self._artifact_mapping("packages")

    def get_model(self, model_id: str) -> ModelCandidate:
        raw = self.models.get(model_id)
        if not isinstance(raw, dict):
            raise ModelRegistryError(f"unknown or malformed model: {model_id}")
        provider = raw.get("provider")
        status = raw.get("status")
        capabilities = raw.get("capabilities")
        recommended_roles = raw.get("recommended_roles")
        artifact_package = raw.get("artifact_package")
        execution_surfaces = raw.get("execution_surfaces")
        if not isinstance(provider, str) or provider not in self.providers:
            raise ModelRegistryError(f"model {model_id} has unknown provider")
        if not isinstance(status, str):
            raise ModelRegistryError(f"model {model_id} has invalid status")
        if not isinstance(capabilities, list) or not all(isinstance(x, str) for x in capabilities):
            raise ModelRegistryError(f"model {model_id} has invalid capabilities")
        if not isinstance(recommended_roles, list) or not all(isinstance(x, str) for x in recommended_roles):
            raise ModelRegistryError(f"model {model_id} has invalid recommended_roles")
        if not isinstance(artifact_package, str) or artifact_package not in self.artifact_packages:
            raise ModelRegistryError(f"model {model_id} has unknown artifact package")
        if not isinstance(execution_surfaces, list) or not execution_surfaces or not all(isinstance(x, str) for x in execution_surfaces):
            raise ModelRegistryError(f"model {model_id} has invalid execution surfaces")

        package = self.artifact_packages[artifact_package]
        if not isinstance(package, dict) or package.get("provider") != provider:
            raise ModelRegistryError(f"model {model_id} artifact/provider binding is inconsistent")

        return ModelCandidate(
            model_id=model_id,
            provider=provider,
            status=status,
            capabilities=tuple(sorted(capabilities)),
            recommended_roles=tuple(sorted(recommended_roles)),
            artifact_package=artifact_package,
            execution_surfaces=tuple(sorted(execution_surfaces)),
        )

    def _surface_is_ready(self, candidate: ModelCandidate, surface: str) -> bool:
        if surface not in candidate.execution_surfaces:
            return False
        if surface == REMOTE_SURFACE:
            return True
        if surface != LOCAL_SURFACE:
            return False

        package = self.artifact_packages.get(candidate.artifact_package)
        if not isinstance(package, dict):
            return False
        availability = package.get("weight_availability")
        if availability not in LOCAL_WEIGHT_KINDS:
            return False
        mirror = package.get("mirror")
        if not isinstance(mirror, dict):
            return False
        expected = PRIVATE_MIRRORED_VERIFIED if availability == "PRIVATE_OPERATOR_WEIGHTS" else PUBLIC_MIRRORED_VERIFIED
        return mirror.get("state") == expected

    def resolve(
        self,
        role: str,
        *,
        extra_required_capabilities: Sequence[str] = (),
        exclude_providers: Iterable[str] = (),
        executable_statuses: Iterable[str] = DEFAULT_EXECUTABLE_STATUSES,
        include_candidates: bool = False,
        execution_surface: str | None = None,
        require_artifact_ready: bool = True,
    ) -> tuple[ModelCandidate, ...]:
        raw_role = self.roles.get(role)
        if not isinstance(raw_role, dict):
            raise ModelRegistryError(f"unknown role: {role}")
        if execution_surface is not None and execution_surface not in {REMOTE_SURFACE, LOCAL_SURFACE}:
            raise ModelRegistryError(f"unknown execution surface: {execution_surface}")

        required = raw_role.get("required_capabilities")
        if not isinstance(required, list) or not all(isinstance(x, str) for x in required):
            raise ModelRegistryError(f"role {role} has invalid required_capabilities")

        required_set = set(required) | set(extra_required_capabilities)
        denied_providers = set(exclude_providers)
        allowed_statuses = set(executable_statuses)
        if include_candidates:
            allowed_statuses.add(CANDIDATE_STATUS)

        privacy_requirement = raw_role.get("privacy_requirement")
        forced_surface = LOCAL_SURFACE if privacy_requirement == "local_only" else execution_surface
        candidates: list[ModelCandidate] = []
        for model_id in sorted(self.models):
            candidate = self.get_model(model_id)
            if candidate.status not in allowed_statuses:
                continue
            if candidate.provider in denied_providers:
                continue
            if role not in candidate.recommended_roles:
                continue
            if not required_set.issubset(set(candidate.capabilities)):
                continue

            if privacy_requirement == "local_only":
                provider = self.providers.get(candidate.provider)
                if not isinstance(provider, dict) or provider.get("transport") != "openai_compatible_local":
                    continue

            if forced_surface is not None:
                if forced_surface not in candidate.execution_surfaces:
                    continue
                if require_artifact_ready and not self._surface_is_ready(candidate, forced_surface):
                    continue
            elif require_artifact_ready and not any(
                self._surface_is_ready(candidate, surface) for surface in candidate.execution_surfaces
            ):
                continue

            candidates.append(candidate)

        return tuple(candidates)

    def require_one(self, role: str, **kwargs: object) -> ModelCandidate:
        candidates = self.resolve(role, **kwargs)
        if not candidates:
            raise ModelRegistryError(f"no admitted model satisfies role {role!r}")
        return candidates[0]

    def require_provider_diversity(
        self,
        role: str,
        *,
        compared_provider: str,
        include_candidates: bool = False,
        execution_surface: str | None = None,
        require_artifact_ready: bool = True,
    ) -> tuple[ModelCandidate, ...]:
        if compared_provider not in self.providers:
            raise ModelRegistryError(f"unknown compared provider: {compared_provider}")
        return self.resolve(
            role,
            exclude_providers=(compared_provider,),
            include_candidates=include_candidates,
            execution_surface=execution_surface,
            require_artifact_ready=require_artifact_ready,
        )
