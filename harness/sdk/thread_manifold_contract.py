"""Resolve the Thread-as-QuantumManifold notation against the Phase-1 kernel.

The contract in ``harness/policies/thread-manifold-contract.v1.json`` names
geometric symbols and says which repository primitive each one denotes. A named
binding proves nothing on its own: this module resolves every binding against
the live dataclasses, so a symbol pointing at a type or field that does not
exist is a failure rather than a sentence someone believed.

Nothing here grants authority. ``authority_effect`` is checked, never set.
"""
from __future__ import annotations

import dataclasses
import importlib
import json
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
CONTRACT_PATH = REPO_ROOT / "harness" / "policies" / "thread-manifold-contract.v1.json"

SOURCE_BOUND = "SOURCE_BOUND"
DERIVED_FORMALIZATION = "DERIVED_FORMALIZATION"
TUNNELING = "AUTHORITY_TUNNELING_ATTEMPT"


class ThreadManifoldContractError(RuntimeError):
    def __init__(self, reason_code: str) -> None:
        super().__init__(reason_code)
        self.reason_code = reason_code


def load_contract(path: Path | None = None) -> dict[str, Any]:
    return json.loads((path or CONTRACT_PATH).read_text(encoding="utf-8"))


def _resolve_type(binding: dict[str, Any]) -> type:
    module = importlib.import_module(binding["module"])
    obtained = getattr(module, binding["type"], None)
    if obtained is None or not dataclasses.is_dataclass(obtained):
        raise ThreadManifoldContractError("BINDING_TYPE_UNRESOLVED")
    return obtained


def unresolved_bindings(contract: dict[str, Any] | None = None) -> list[str]:
    """Return the symbols whose declared binding does not exist in the kernel.

    A binding may name a policy key instead of a type; those are resolved
    against the policy file the binding itself names, for the same reason.
    """
    contract = contract or load_contract()
    missing: list[str] = []
    for binding in contract["bindings"]:
        symbol = binding["symbol"]
        if "policy_key" in binding:
            policy = json.loads((REPO_ROOT / binding["policy_file"]).read_text(encoding="utf-8"))
            if binding["policy_key"] not in policy:
                missing.append(symbol)
            continue
        try:
            resolved = _resolve_type(binding)
        except (ThreadManifoldContractError, ModuleNotFoundError):
            missing.append(symbol)
            continue
        field = binding.get("field")
        if field is not None and field not in {f.name for f in dataclasses.fields(resolved)}:
            missing.append(symbol)
    return missing


def plane_of(symbol: str, contract: dict[str, Any] | None = None) -> str:
    contract = contract or load_contract()
    for binding in contract["bindings"]:
        if binding["symbol"] == symbol:
            return binding["plane"]
    raise ThreadManifoldContractError("SYMBOL_NOT_IN_CONTRACT")


def derived_symbols(contract: dict[str, Any] | None = None) -> set[str]:
    contract = contract or load_contract()
    return {row["symbol"] for row in contract["derived_formalizations"]}


def authority_plane_violations(proposal: Any, contract: dict[str, Any] | None = None) -> list[str]:
    """Return the authority fields of ``proposal`` that are not pinned.

    Empty means the authority plane is intact. This never repairs a proposal:
    a violation is reported so the caller can refuse it, which is the whole
    point of keeping the plane separate from anything the scheduler optimises.
    """
    contract = contract or load_contract()
    plane = contract["authority_plane"]
    violations = []
    for field, expected in plane["fields"].items():
        if not hasattr(proposal, field):
            violations.append(field)
            continue
        if getattr(proposal, field) != expected:
            violations.append(field)
    return violations


def refuse_if_tunneled(proposal: Any, contract: dict[str, Any] | None = None) -> None:
    if authority_plane_violations(proposal, contract):
        raise ThreadManifoldContractError(TUNNELING)
