from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Mapping, Sequence


MODEL_OUTPUT_AUTHORITY = "EVIDENCE_ONLY"
DEFAULT_EXECUTABLE_STATUSES = frozenset({"active", "active_legacy"})
CANDIDATE_STATUS = "candidate"


class ModelRegistryError(RuntimeError):
    """Raised when model selection cannot be proven safe from registry state."""


@dataclass(frozen=True)
class ModelCandidate:
    model_id: str
    provider: str
    status: str
    capabilities: tuple[str, ...]
    recommended_roles: tuple[str, ...]
    authority: str = MODEL_OUTPUT_AUTHORITY


class ModelCapabilityRegistry:
    """Deterministic, fail-closed view of model/provider configuration.

    The registry selects *eligible inference candidates*. It never grants
    execution, admission, effect, or state-transition authority. Candidate
    models are excluded from normal routing until explicitly promoted to an
    executable status by a separately governed configuration change.
    """

    def __init__(self, payload: Mapping[str, object]) -> None:
        self._payload = payload
        self._assert_constitutional_invariants()

    @classmethod
    def load(cls, path: Path | str | None = None) -> "ModelCapabilityRegistry":
        if path is None:
            path = Path(__file__).resolve().parents[2] / "config" / "model-capability-registry.v1.json"
        registry_path = Path(path)
        try:
            payload = json.loads(registry_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise ModelRegistryError(f"cannot load model registry: {exc}") from exc
        if not isinstance(payload, dict):
            raise ModelRegistryError("model registry root must be an object")
        return cls(payload)

    def _assert_constitutional_invariants(self) -> None:
        if self._payload.get("authority_rule") != "MODEL_OUTPUT_IS_EVIDENCE_NOT_AUTHORITY":
            raise ModelRegistryError("registry authority rule is missing or changed")
        policy = self._mapping("selection_policy")
        if policy.get("fail_closed") is not True:
            raise ModelRegistryError("registry must fail closed")
        if policy.get("require_explicit_model_registration") is not True:
            raise ModelRegistryError("explicit model registration is required")
        if policy.get("allow_unknown_models") is not False:
            raise ModelRegistryError("unknown models must remain denied")

    def _mapping(self, key: str) -> Mapping[str, object]:
        value = self._payload.get(key)
        if not isinstance(value, dict):
            raise ModelRegistryError(f"registry field {key!r} must be an object")
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

    def get_model(self, model_id: str) -> ModelCandidate:
        raw = self.models.get(model_id)
        if not isinstance(raw, dict):
            raise ModelRegistryError(f"unknown or malformed model: {model_id}")
        provider = raw.get("provider")
        status = raw.get("status")
        capabilities = raw.get("capabilities")
        recommended_roles = raw.get("recommended_roles")
        if not isinstance(provider, str) or provider not in self.providers:
            raise ModelRegistryError(f"model {model_id} has unknown provider")
        if not isinstance(status, str):
            raise ModelRegistryError(f"model {model_id} has invalid status")
        if not isinstance(capabilities, list) or not all(isinstance(x, str) for x in capabilities):
            raise ModelRegistryError(f"model {model_id} has invalid capabilities")
        if not isinstance(recommended_roles, list) or not all(isinstance(x, str) for x in recommended_roles):
            raise ModelRegistryError(f"model {model_id} has invalid recommended_roles")
        return ModelCandidate(
            model_id=model_id,
            provider=provider,
            status=status,
            capabilities=tuple(sorted(capabilities)),
            recommended_roles=tuple(sorted(recommended_roles)),
        )

    def resolve(
        self,
        role: str,
        *,
        extra_required_capabilities: Sequence[str] = (),
        exclude_providers: Iterable[str] = (),
        executable_statuses: Iterable[str] = DEFAULT_EXECUTABLE_STATUSES,
        include_candidates: bool = False,
    ) -> tuple[ModelCandidate, ...]:
        raw_role = self.roles.get(role)
        if not isinstance(raw_role, dict):
            raise ModelRegistryError(f"unknown role: {role}")

        required = raw_role.get("required_capabilities")
        if not isinstance(required, list) or not all(isinstance(x, str) for x in required):
            raise ModelRegistryError(f"role {role} has invalid required_capabilities")

        required_set = set(required) | set(extra_required_capabilities)
        denied_providers = set(exclude_providers)
        allowed_statuses = set(executable_statuses)
        if include_candidates:
            allowed_statuses.add(CANDIDATE_STATUS)

        privacy_requirement = raw_role.get("privacy_requirement")
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
            candidates.append(candidate)

        return tuple(candidates)

    def require_one(
        self,
        role: str,
        **kwargs: object,
    ) -> ModelCandidate:
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
    ) -> tuple[ModelCandidate, ...]:
        if compared_provider not in self.providers:
            raise ModelRegistryError(f"unknown compared provider: {compared_provider}")
        return self.resolve(
            role,
            exclude_providers=(compared_provider,),
            include_candidates=include_candidates,
        )
