from __future__ import annotations

from dataclasses import asdict, dataclass
from hashlib import sha256
import json
from pathlib import Path
import re
from typing import Any, Iterable


IMMUTABLE_REF_RE = re.compile(r"^[0-9a-f]{40,64}$")
USES_RE = re.compile(r"^\s*(?:-\s*)?uses:\s*([^\s#]+)")
KEY_VALUE_RE = re.compile(r"^([A-Za-z0-9_.-]+):\s*(.*?)\s*$")


@dataclass(frozen=True)
class ActionDependencyV1:
    reference: str
    pin_class: str


@dataclass(frozen=True)
class WorkflowSurfaceV1:
    path: str
    source_sha256: str
    name: str
    triggers: list[str]
    permissions: dict[str, str]
    declared_runner_requirements: list[str]
    action_dependencies: list[ActionDependencyV1]
    provider_model_surfaces: list[str]
    findings: list[str]
    uses_oidc: bool
    uses_attestations: bool
    uses_artifacts: bool
    authority_sensitive: bool

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _indent(line: str) -> int:
    return len(line) - len(line.lstrip(" "))


def _clean_scalar(value: str) -> str:
    value = value.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
        return value[1:-1]
    return value


def _strip_comment(line: str) -> str:
    match = re.search(r"\s+#", line)
    return line[: match.start()].rstrip() if match else line.rstrip()


def _inline_list(value: str) -> list[str]:
    value = value.strip()
    if value.startswith("[") and value.endswith("]"):
        body = value[1:-1]
        return sorted({_clean_scalar(item.strip()) for item in body.split(",") if item.strip()})
    if not value:
        return []
    return [_clean_scalar(value)]


def classify_action_ref(reference: str) -> str:
    if reference.startswith("./"):
        return "LOCAL_PATH"
    if reference.startswith("docker://"):
        return "CONTAINER_IMAGE"
    if "@" not in reference:
        return "UNPINNED"
    ref = reference.rsplit("@", 1)[1]
    if IMMUTABLE_REF_RE.fullmatch(ref):
        return "IMMUTABLE_COMMIT"
    return "MUTABLE_REF"


def _top_level_name(lines: list[str], fallback: str) -> str:
    for raw in lines:
        line = _strip_comment(raw)
        if _indent(line) != 0:
            continue
        match = KEY_VALUE_RE.match(line)
        if match and match.group(1) == "name":
            return _clean_scalar(match.group(2)) or fallback
    return fallback


def _top_level_triggers(lines: list[str]) -> list[str]:
    for index, raw in enumerate(lines):
        line = _strip_comment(raw)
        if _indent(line) != 0:
            continue
        match = KEY_VALUE_RE.match(line)
        if not match or match.group(1) != "on":
            continue
        inline = _inline_list(match.group(2))
        if inline:
            return sorted(set(inline))
        child_lines: list[tuple[int, str]] = []
        for following in lines[index + 1 :]:
            cleaned = _strip_comment(following)
            if not cleaned.strip():
                continue
            indent = _indent(cleaned)
            if indent == 0:
                break
            child_lines.append((indent, cleaned.strip()))
        if not child_lines:
            return []
        first_indent = min(indent for indent, _ in child_lines)
        triggers: set[str] = set()
        for indent, child in child_lines:
            if indent != first_indent:
                continue
            child_match = KEY_VALUE_RE.match(child)
            if child_match:
                triggers.add(child_match.group(1))
            elif child.startswith("-"):
                triggers.add(_clean_scalar(child[1:].strip()))
        return sorted(triggers)
    return []


def _permissions(lines: list[str]) -> dict[str, str]:
    rank = {"none": 0, "read": 1, "write": 2}
    collected: dict[str, str] = {}
    for index, raw in enumerate(lines):
        line = _strip_comment(raw)
        stripped = line.strip()
        if not stripped.startswith("permissions:"):
            continue
        base_indent = _indent(line)
        scalar = stripped.split(":", 1)[1].strip()
        if scalar:
            collected["*"] = _clean_scalar(scalar)
            continue
        for following in lines[index + 1 :]:
            cleaned = _strip_comment(following)
            if not cleaned.strip():
                continue
            indent = _indent(cleaned)
            if indent <= base_indent:
                break
            match = KEY_VALUE_RE.match(cleaned.strip())
            if not match:
                continue
            key, value = match.group(1), _clean_scalar(match.group(2))
            if not value:
                continue
            previous = collected.get(key)
            if previous is None or rank.get(value, 1) > rank.get(previous, 1):
                collected[key] = value
    return {key: collected[key] for key in sorted(collected)}


def _runner_requirements(lines: list[str]) -> list[str]:
    values: set[str] = set()
    for index, raw in enumerate(lines):
        cleaned = _strip_comment(raw)
        if "runs-on:" not in cleaned:
            continue
        _, after = cleaned.split("runs-on:", 1)
        base_indent = _indent(cleaned)
        values.update(item for item in _inline_list(after) if item)
        if after.strip():
            continue
        for following in lines[index + 1 :]:
            child = _strip_comment(following)
            if not child.strip():
                continue
            indent = _indent(child)
            if indent <= base_indent:
                break
            match = KEY_VALUE_RE.match(child.strip())
            if not match or match.group(1) not in {"group", "labels"}:
                continue
            values.update(item for item in _inline_list(match.group(2)) if item)
    return sorted(values)


def _action_dependencies(lines: list[str]) -> list[ActionDependencyV1]:
    refs: set[str] = set()
    for raw in lines:
        match = USES_RE.match(_strip_comment(raw))
        if match:
            refs.add(_clean_scalar(match.group(1)))
    return [ActionDependencyV1(reference=ref, pin_class=classify_action_ref(ref)) for ref in sorted(refs)]


def _provider_surfaces(
    text: str,
    permissions: dict[str, str],
    dependencies: Iterable[ActionDependencyV1],
) -> tuple[list[str], list[str]]:
    """Return only strong runtime integration signals."""
    lowered = text.lower()
    dep_refs = "\n".join(dep.reference.lower() for dep in dependencies)
    surfaces: set[str] = set()
    findings: set[str] = set()

    if permissions.get("models") == "read" or "actions/ai-inference@" in dep_refs:
        surfaces.add("github-models-retired")
        findings.add("RETIRED_GITHUB_MODELS_SURFACE")

    strong_signals: dict[str, tuple[str, ...]] = {
        "github-copilot": ("github/copilot", "copilot_api_key", "copilot_token"),
        "openai": ("api.openai.com", "openai_api_key", "openai_base_url", "openai_model"),
        "anthropic": ("api.anthropic.com", "anthropic_api_key", "anthropic_base_url", "anthropic_model", "anthropics/"),
        "deepseek": ("api.deepseek.com", "deepseek_api_key", "deepseek_base_url", "deepseek_model"),
        "gemma": ("gemma_model", "gemma_model_path", "google/gemma"),
        "ollama": ("ollama_host", "localhost:11434", "127.0.0.1:11434", "ollama serve"),
        "dashscope-qwen": ("dashscope_api_key", "dashscope.aliyuncs.com", "dashscope_base_url", "qwen_model"),
        "azure-foundry": ("azure_openai_api_key", "azure_openai_endpoint", "openai.azure.com", "azure_ai_foundry", "azure_foundry"),
        "google-vertex-gemini": ("gemini_api_key", "vertex_ai", "vertexai", "aiplatform.googleapis.com", "generativelanguage.googleapis.com"),
        "aws-bedrock": ("bedrock-runtime", "aws_bedrock", "bedrock_model_id"),
        "mistral": ("api.mistral.ai", "mistral_api_key", "mistral_model"),
        "xai-grok": ("api.x.ai", "xai_api_key", "xai_model"),
        "hugging-face": ("api-inference.huggingface.co", "huggingface_hub_token", "hf_token"),
    }
    combined_runtime_text = lowered + "\n" + dep_refs
    for surface, signals in strong_signals.items():
        if any(signal in combined_runtime_text for signal in signals):
            surfaces.add(surface)

    return sorted(surfaces), sorted(findings)


def scan_workflow_text(path: str, text: str) -> WorkflowSurfaceV1:
    lines = text.splitlines()
    name = _top_level_name(lines, Path(path).name)
    triggers = _top_level_triggers(lines)
    permissions = _permissions(lines)
    runners = _runner_requirements(lines)
    dependencies = _action_dependencies(lines)
    provider_surfaces, findings = _provider_surfaces(text, permissions, dependencies)
    mutable = [dep for dep in dependencies if dep.pin_class in {"MUTABLE_REF", "UNPINNED"}]
    if mutable:
        findings.append("MUTABLE_ACTION_REF")
    authority_sensitive = any(value == "write" for value in permissions.values())
    if mutable and authority_sensitive:
        findings.append("MUTABLE_ACTION_REF_AUTHORITY_SENSITIVE")
    lower_refs = "\n".join(dep.reference.lower() for dep in dependencies)
    uses_oidc = permissions.get("id-token") == "write"
    uses_attestations = "actions/attest@" in lower_refs or permissions.get("attestations") == "write"
    uses_artifacts = (
        "actions/upload-artifact@" in lower_refs
        or "actions/download-artifact@" in lower_refs
        or permissions.get("artifact-metadata") == "write"
    )
    return WorkflowSurfaceV1(
        path=path,
        source_sha256=sha256(text.encode("utf-8")).hexdigest(),
        name=name,
        triggers=triggers,
        permissions=permissions,
        declared_runner_requirements=runners,
        action_dependencies=dependencies,
        provider_model_surfaces=provider_surfaces,
        findings=sorted(set(findings)),
        uses_oidc=uses_oidc,
        uses_attestations=uses_attestations,
        uses_artifacts=uses_artifacts,
        authority_sensitive=authority_sensitive,
    )


def _canonical_observations(items: list[dict[str, Any]] | None) -> list[dict[str, Any]]:
    if not items:
        return []
    copies = [json.loads(json.dumps(item, sort_keys=True)) for item in items]
    return sorted(copies, key=lambda item: json.dumps(item, sort_keys=True, separators=(",", ":")))


def build_runner_observation(
    *,
    candidate_sha: str,
    run_id: str,
    run_attempt: str,
    job: str,
    runner_name: str,
    runner_os: str,
    runner_arch: str,
    runner_environment: str,
) -> dict[str, str]:
    values = {
        "candidate_sha": candidate_sha,
        "workflow_run_id": run_id,
        "workflow_run_attempt": run_attempt,
        "job": job,
        "runner_name": runner_name,
        "runner_os": runner_os,
        "runner_arch": runner_arch,
        "runner_environment": runner_environment,
    }
    for field, value in values.items():
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"{field} is required")
    return {
        "observation_kind": "EXECUTED_RUNNER_OBSERVATION_V1",
        "authority": "EXECUTED_RUN_EVIDENCE_NOT_RUNNER_REGISTRATION_AUTHORITY",
        **{field: value.strip() for field, value in values.items()},
    }


def build_manifest(
    repo_root: Path,
    candidate_sha: str,
    historical_observations: list[dict[str, Any]] | None = None,
    executed_runner_observations: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    if not candidate_sha or not candidate_sha.strip():
        raise ValueError("candidate_sha is required")
    candidate_sha = candidate_sha.strip()

    executed = _canonical_observations(executed_runner_observations)
    for observation in executed:
        if observation.get("observation_kind") != "EXECUTED_RUNNER_OBSERVATION_V1":
            raise ValueError("executed runner observation kind is invalid")
        if observation.get("authority") != "EXECUTED_RUN_EVIDENCE_NOT_RUNNER_REGISTRATION_AUTHORITY":
            raise ValueError("executed runner observation authority is invalid")
        if observation.get("candidate_sha") != candidate_sha:
            raise ValueError("executed runner observation subject mismatch")

    root = Path(repo_root)
    workflow_dir = root / ".github" / "workflows"
    paths: list[Path] = []
    if workflow_dir.is_dir():
        paths.extend(workflow_dir.glob("*.yml"))
        paths.extend(workflow_dir.glob("*.yaml"))
    paths = sorted(set(paths), key=lambda path: path.as_posix())
    surfaces: list[WorkflowSurfaceV1] = []
    for path in paths:
        relative = ".github/workflows/" + path.name
        surfaces.append(scan_workflow_text(relative, path.read_text(encoding="utf-8")))
    current = [surface.to_dict() for surface in surfaces]
    runners = sorted({item for surface in surfaces for item in surface.declared_runner_requirements})
    providers = sorted({item for surface in surfaces for item in surface.provider_model_surfaces})
    findings = sorted({item for surface in surfaces for item in surface.findings})
    dependencies = [
        {"workflow_path": surface.path, "reference": dep.reference, "pin_class": dep.pin_class}
        for surface in surfaces
        for dep in surface.action_dependencies
    ]
    dependencies.sort(key=lambda item: (item["workflow_path"], item["reference"]))
    return {
        "schema_version": "1.0.0",
        "manifest_kind": "GITHUB_SUBSTRATE_MANIFEST_V1",
        "candidate_sha": candidate_sha,
        "authority": "EVIDENCE_ONLY_NOT_RUNNER_REGISTRATION_AUTHORITY",
        "current_tree_workflow_count": len(current),
        "current_tree_workflows": current,
        "declared_runner_requirements": runners,
        "registered_runner_inventory_status": "NOT_CHECKED",
        "executed_runner_observations": executed,
        "action_dependencies": dependencies,
        "provider_model_surfaces": providers,
        "historical_workflow_observations": _canonical_observations(historical_observations),
        "findings": findings,
    }


def validate_manifest(manifest: dict[str, Any]) -> dict[str, list[str]]:
    violations: set[str] = set()
    warnings: set[str] = set()
    if manifest.get("manifest_kind") != "GITHUB_SUBSTRATE_MANIFEST_V1":
        violations.add("INVALID_MANIFEST_KIND")
    if not str(manifest.get("candidate_sha", "")).strip():
        violations.add("MISSING_CANDIDATE_SHA")
    if manifest.get("authority") != "EVIDENCE_ONLY_NOT_RUNNER_REGISTRATION_AUTHORITY":
        violations.add("INVALID_AUTHORITY_BOUNDARY")

    current = manifest.get("current_tree_workflows")
    if not isinstance(current, list):
        violations.add("CURRENT_TREE_WORKFLOWS_NOT_LIST")
        current = []
    paths = [item.get("path") for item in current if isinstance(item, dict)]
    if len(paths) != len(set(paths)) or paths != sorted(paths):
        violations.add("CURRENT_TREE_WORKFLOWS_NOT_UNIQUE_SORTED")
    if manifest.get("current_tree_workflow_count") != len(current):
        violations.add("CURRENT_TREE_WORKFLOW_COUNT_MISMATCH")

    current_paths = {path for path in paths if isinstance(path, str)}
    for item in current:
        if not isinstance(item, dict):
            violations.add("MALFORMED_CURRENT_TREE_WORKFLOW")
            continue
        path = str(item.get("path", "UNKNOWN"))
        findings = set(item.get("findings") or [])
        if "RETIRED_GITHUB_MODELS_SURFACE" in findings:
            violations.add(f"RETIRED_GITHUB_MODELS_SURFACE:{path}")
        if "MUTABLE_ACTION_REF_AUTHORITY_SENSITIVE" in findings:
            warnings.add(f"MUTABLE_ACTION_REF_AUTHORITY_SENSITIVE:{path}")
        if path == ".github/workflows/github-substrate-census.yml":
            for dep in item.get("action_dependencies") or []:
                if dep.get("pin_class") not in {"IMMUTABLE_COMMIT", "LOCAL_PATH"}:
                    violations.add(f"CENSUS_WORKFLOW_MUTABLE_DEPENDENCY:{dep.get('reference', 'UNKNOWN')}")

    historical = manifest.get("historical_workflow_observations") or []
    for observation in historical:
        if not isinstance(observation, dict):
            violations.add("MALFORMED_HISTORICAL_WORKFLOW_OBSERVATION")
            continue
        path = observation.get("workflow_path")
        if observation.get("observed_as") == "HISTORICAL_ONLY_BUT_CURRENT" and path in current_paths:
            violations.add(f"HISTORICAL_CURRENT_UNIVERSE_CONFLICT:{path}")

    candidate_sha = manifest.get("candidate_sha")
    executed = manifest.get("executed_runner_observations") or []
    if not isinstance(executed, list):
        violations.add("EXECUTED_RUNNER_OBSERVATIONS_NOT_LIST")
        executed = []
    for observation in executed:
        if not isinstance(observation, dict):
            violations.add("MALFORMED_EXECUTED_RUNNER_OBSERVATION")
            continue
        if observation.get("candidate_sha") != candidate_sha:
            violations.add("EXECUTED_RUNNER_OBSERVATION_SUBJECT_MISMATCH")
        if observation.get("authority") != "EXECUTED_RUN_EVIDENCE_NOT_RUNNER_REGISTRATION_AUTHORITY":
            violations.add("INVALID_EXECUTED_RUNNER_OBSERVATION_AUTHORITY")

    if manifest.get("registered_runner_inventory_status") != "NOT_CHECKED":
        warnings.add("REGISTERED_RUNNER_INVENTORY_REQUIRES_EXTERNAL_BINDING")

    return {"violations": sorted(violations), "warnings": sorted(warnings)}
