import inspect
import json
import math
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

from aegis_omega.cudaq_self_witness import (
    AUTHORITY_CLASS,
    OBSERVABLE_NAMES,
    BackendSpec,
    BackendUnavailableException,
    DifferentialGateTolerance,
    ProtocolViolation,
    SelfWitnessEngine,
    map_hash_to_angles,
)


DUMMY_SELF_HASH = "8fa6cc600d75cd78a518a8b5b08cfb9f4e665c3016769820d37616d319cdee8a"
SOURCE_SHA = "98e7ec038cb1e8a8722b5dcc3346a56d9da9801a"
SCHEMA_PATH = Path(__file__).resolve().parents[3] / "schemas" / "quantum-self-digest-receipt.v1.schema.json"


def _observables(z0: float = 0.5) -> dict[str, float]:
    return {
        "Z0": z0,
        "Z1": 0.5,
        "Z2": 0.5,
        "Z3": 0.5,
        "Z0Z1": 0.25,
        "Z2Z3": 0.25,
        "X0X1X2X3": 0.1,
    }


def _deterministic_executor(backend: BackendSpec, _thetas: tuple[float, ...]) -> dict[str, float]:
    assert backend.execution_mode == "ANALYTIC_STATEVECTOR"
    return _observables(0.5 if backend.target == "qpp-cpu" else 0.50000001)


def test_deterministic_angle_mapping_is_half_open() -> None:
    first = map_hash_to_angles(DUMMY_SELF_HASH)
    second = map_hash_to_angles(DUMMY_SELF_HASH)

    assert first == second
    assert len(first.words_u32) == 8
    assert len(first.angles_rad) == 8
    assert all(0 <= word <= 0xFFFFFFFF for word in first.words_u32)
    assert all(0.0 <= theta < 2.0 * math.pi for theta in first.angles_rad)


def test_max_u32_chunk_never_maps_to_two_pi() -> None:
    encoding = map_hash_to_angles("ff" * 32)
    assert all(theta < 2.0 * math.pi for theta in encoding.angles_rad)


def test_invalid_or_noncanonical_hash_is_rejected() -> None:
    with pytest.raises(ValueError):
        map_hash_to_angles("00" * 31)
    with pytest.raises(ValueError):
        map_hash_to_angles(DUMMY_SELF_HASH.upper())


def test_differential_gate_passes_within_tolerance_and_has_no_authority() -> None:
    engine = SelfWitnessEngine(
        tolerance=DifferentialGateTolerance(epsilon_max_abs_diff=1e-5),
        executor=_deterministic_executor,
    )
    result = engine.run_witness_cycle(DUMMY_SELF_HASH, source_sha=SOURCE_SHA)
    receipt = result["receipt"]

    assert receipt["differential_gate_status"] == "PASS"
    assert receipt["authority_class"] == AUTHORITY_CLASS == "NONE"
    assert receipt["authority_effect"] == "NONE"
    assert receipt["quantum_physical_advantage"] == "NOT_ESTABLISHED"
    assert receipt["rh_status"] == "NOT_PROVEN"
    assert set(receipt["observables_a"]) == set(OBSERVABLE_NAMES)
    assert receipt["backend_b_config"]["options"] == {"option": "fp64"}
    assert len(result["receipt_digest"]) == 64
    assert "purity" not in json.dumps(receipt).lower()


def test_receipt_is_rfc8785_deterministic_and_schema_valid() -> None:
    engine = SelfWitnessEngine(executor=_deterministic_executor)
    first = engine.run_witness_cycle(DUMMY_SELF_HASH, source_sha=SOURCE_SHA)
    second = engine.run_witness_cycle(DUMMY_SELF_HASH, source_sha=SOURCE_SHA)

    assert first == second
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(schema)
    Draft202012Validator(schema).validate(first["receipt"])


def test_differential_gate_fails_above_tolerance() -> None:
    def executor(backend: BackendSpec, _thetas: tuple[float, ...]) -> dict[str, float]:
        return _observables(0.5 if backend.target == "qpp-cpu" else 0.51)

    engine = SelfWitnessEngine(
        tolerance=DifferentialGateTolerance(epsilon_max_abs_diff=1e-4),
        executor=executor,
    )
    receipt = engine.run_witness_cycle(DUMMY_SELF_HASH, source_sha=SOURCE_SHA)["receipt"]

    assert receipt["differential_gate_status"] == "FAIL"
    assert receipt["max_discrepancy"] >= 0.01 - 1e-15
    assert receipt["authority_class"] == "NONE"


def test_backend_unavailable_raises_and_never_fabricates_receipt() -> None:
    def unavailable(_backend: BackendSpec, _thetas: tuple[float, ...]) -> dict[str, float]:
        raise BackendUnavailableException("BACKEND_UNAVAILABLE")

    engine = SelfWitnessEngine(executor=unavailable)
    with pytest.raises(BackendUnavailableException, match="BACKEND_UNAVAILABLE"):
        engine.run_witness_cycle(DUMMY_SELF_HASH, source_sha=SOURCE_SHA)


def test_non_finite_observable_is_protocol_violation() -> None:
    def executor(_backend: BackendSpec, _thetas: tuple[float, ...]) -> dict[str, float]:
        values = _observables()
        values["Z2"] = math.nan
        return values

    engine = SelfWitnessEngine(executor=executor)
    with pytest.raises(ProtocolViolation, match="non-finite"):
        engine.run_witness_cycle(DUMMY_SELF_HASH, source_sha=SOURCE_SHA)


def test_v1_rejects_physical_qpu_target_instead_of_reusing_statevector_gate() -> None:
    engine = SelfWitnessEngine(executor=lambda _backend, _thetas: _observables())
    with pytest.raises(ProtocolViolation, match="simulator-only"):
        engine.run_witness_cycle(
            DUMMY_SELF_HASH,
            source_sha=SOURCE_SHA,
            backend_b=BackendSpec(target="quantinuum", execution_mode="SHOT_BASED_QPU"),
        )


def test_v1_rejects_backend_options_not_representable_by_schema() -> None:
    engine = SelfWitnessEngine(executor=lambda _backend, _thetas: _observables())

    with pytest.raises(ProtocolViolation, match="qpp-cpu options"):
        engine.run_witness_cycle(
            DUMMY_SELF_HASH,
            source_sha=SOURCE_SHA,
            backend_a=BackendSpec(target="qpp-cpu", options=(("unexpected", "1"),)),
        )

    with pytest.raises(ProtocolViolation, match="nvidia options"):
        engine.run_witness_cycle(
            DUMMY_SELF_HASH,
            source_sha=SOURCE_SHA,
            backend_b=BackendSpec(
                target="nvidia",
                options=(("option", "fp64"), ("unexpected", "1")),
            ),
        )


def test_execute_observable_set_restores_callers_previous_cudaq_target(monkeypatch) -> None:
    import aegis_omega.cudaq_self_witness as sw

    class FakeResult:
        def expectation(self) -> float:
            return 0.0

    class FakeOp:
        def __mul__(self, _other):
            return self

    class FakeSpin:
        @staticmethod
        def z(_index: int) -> FakeOp:
            return FakeOp()

        @staticmethod
        def x(_index: int) -> FakeOp:
            return FakeOp()

    previous_target = object()
    calls: list[tuple] = []

    class FakeCudaq:
        @staticmethod
        def has_target(_target: str) -> bool:
            return True

        @staticmethod
        def get_target():
            calls.append(("get_target",))
            return previous_target

        @staticmethod
        def set_target(target, **kwargs) -> None:
            calls.append(("set_target", target, kwargs))

        @staticmethod
        def observe(_kernel, operators, _thetas, *, shots_count: int):
            assert shots_count == -1
            return [FakeResult() for _ in operators]

        @staticmethod
        def reset_target() -> None:
            calls.append(("reset_target",))

    monkeypatch.setattr(sw, "CUDAQ_AVAILABLE", True)
    monkeypatch.setattr(sw, "cudaq", FakeCudaq())
    monkeypatch.setattr(sw, "spin", FakeSpin())
    monkeypatch.setattr(sw, "self_witness_kernel", object())

    values = sw.execute_observable_set(
        BackendSpec.qpp_cpu(),
        map_hash_to_angles(DUMMY_SELF_HASH).angles_rad,
    )

    assert tuple(values) == OBSERVABLE_NAMES
    assert ("get_target",) in calls
    assert calls[-1] == ("set_target", previous_target, {})
    assert not any(call[0] == "reset_target" for call in calls)


def test_engine_constructor_exposes_no_executor_override() -> None:
    assert "executor" not in inspect.signature(SelfWitnessEngine).parameters


def test_source_sha_must_be_exact_lowercase_commit() -> None:
    engine = SelfWitnessEngine(executor=lambda _backend, _thetas: _observables())
    with pytest.raises(ValueError, match="source_sha"):
        engine.run_witness_cycle(DUMMY_SELF_HASH, source_sha="98e7ec03")
