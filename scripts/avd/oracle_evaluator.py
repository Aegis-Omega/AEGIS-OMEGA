from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType
from typing import Mapping


class OracleEvaluationError(RuntimeError):
    pass


_EXPECTED: dict[str, frozenset[str]] = {
    "candidate_semantic": frozenset({"MUT_01", "MUT_02", "MUT_03", "MUT_04", "MUT_05", "MUT_06", "MUT_15"}),
    "proof_integrity": frozenset({"MUT_07", "MUT_08", "MUT_09", "MUT_10"}),
    "provenance_verifier": frozenset({"MUT_11", "MUT_12", "MUT_13", "MUT_14"}),
}


@dataclass(frozen=True)
class OracleEvaluationV1:
    _results: Mapping[str, Mapping[str, str]]

    @classmethod
    def from_results(cls, results: dict[str, dict[str, str]]) -> "OracleEvaluationV1":
        if set(results) != set(_EXPECTED):
            raise OracleEvaluationError("ORACLE_RESULT_SURFACE_MISMATCH:CATEGORIES")
        frozen: dict[str, Mapping[str, str]] = {}
        for category in sorted(_EXPECTED):
            values = results.get(category)
            if not isinstance(values, dict) or set(values) != set(_EXPECTED[category]):
                raise OracleEvaluationError(f"ORACLE_RESULT_SURFACE_MISMATCH:{category}")
            normalized: dict[str, str] = {}
            for mutation_id in sorted(_EXPECTED[category]):
                outcome = values[mutation_id]
                if outcome not in {"PASS", "FAIL"}:
                    raise OracleEvaluationError(f"INVALID_ORACLE_OUTCOME:{mutation_id}")
                normalized[mutation_id] = outcome
            frozen[category] = MappingProxyType(normalized)
        return cls(MappingProxyType(frozen))

    @property
    def all_required_passed(self) -> bool:
        return all(
            outcome == "PASS"
            for category in self._results.values()
            for outcome in category.values()
        )

    def to_dict(self) -> dict[str, dict[str, str]]:
        return {
            category: {key: values[key] for key in sorted(values)}
            for category, values in sorted(self._results.items())
        }
