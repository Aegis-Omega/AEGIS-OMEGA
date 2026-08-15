import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from openai_runtime.bridge_endpoint import handle_omega_run
from openai_runtime.runtime import SDKRunObservation
from openai_runtime.types import OmegaManagerOutput, RunStatus, RuntimeErrorCode


def _enabled_env():
    return {
        "AEGIS_OPENAI_RUNTIME_ENABLED": "true",
        "OPENAI_API_KEY": "test-key-not-real",
        "OPENAI_PRIMARY_MODEL": "gpt-5.6-sol",
        "AEGIS_OPENAI_MAX_TURNS": "5",
        "AEGIS_OPENAI_MAX_TOOL_CONCURRENCY": "2",
    }


def _verify_ok(_key):
    return "operator@example.invalid", "operator"


class FakeRunner:
    def __init__(self):
        self.calls = 0

    def run(self, *, config, request, context):
        self.calls += 1
        return SDKRunObservation(
            final_output=OmegaManagerOutput(synthesis="bounded result"),
            trace_id="trace_" + "d" * 32,
            usage={"requests": 1, "input_tokens": 10, "output_tokens": 4, "total_tokens": 14},
        )


def test_authentication_happens_before_runtime_configuration():
    def reject(_key):
        raise ValueError("bad key")

    status, body = handle_omega_run(
        data={"input": "x", "allowed_capabilities": ["research-synthesis"]},
        api_key="bad",
        verify_api_key=reject,
        env={},
    )
    assert status == 401
    assert body["error_code"] == RuntimeErrorCode.UNAUTHORIZED.value


def test_malformed_request_is_rejected_without_runner_call():
    runner = FakeRunner()
    status, body = handle_omega_run(
        data={"input": "   ", "unknown": True},
        api_key="aegis_test",
        verify_api_key=_verify_ok,
        env=_enabled_env(),
        runner=runner,
    )
    assert status == 400
    assert body["error_code"] == RuntimeErrorCode.INVALID_REQUEST.value
    assert runner.calls == 0


def test_disabled_runtime_is_rejected_before_runner_call():
    runner = FakeRunner()
    env = _enabled_env()
    env["AEGIS_OPENAI_RUNTIME_ENABLED"] = "false"
    status, body = handle_omega_run(
        data={"input": "x", "allowed_capabilities": ["research-synthesis"]},
        api_key="aegis_test",
        verify_api_key=_verify_ok,
        env=env,
        runner=runner,
    )
    assert status == 503
    assert body["error_code"] == RuntimeErrorCode.RUNTIME_DISABLED.value
    assert runner.calls == 0


def test_tier_capability_policy_denies_before_model_call():
    runner = FakeRunner()
    status, body = handle_omega_run(
        data={"input": "x", "allowed_capabilities": ["implementation-proposal"]},
        api_key="aegis_test",
        verify_api_key=_verify_ok,
        env=_enabled_env(),
        runner=runner,
    )
    assert status == 403
    assert body["status"] == RunStatus.DENIED.value
    assert body["error_code"] == RuntimeErrorCode.CAPABILITY_NOT_GRANTED.value
    assert runner.calls == 0


def test_v1_rejects_non_d0_action_even_without_tools():
    runner = FakeRunner()
    status, body = handle_omega_run(
        data={
            "input": "x",
            "allowed_capabilities": ["research-synthesis"],
            "action_class": "D1",
        },
        api_key="aegis_test",
        verify_api_key=_verify_ok,
        env=_enabled_env(),
        runner=runner,
    )
    assert status == 403
    assert body["error_code"] == RuntimeErrorCode.ACTION_CLASS_EXCEEDED.value
    assert runner.calls == 0


def test_v1_rejects_any_requested_external_tool():
    runner = FakeRunner()
    status, body = handle_omega_run(
        data={
            "input": "x",
            "allowed_capabilities": ["research-synthesis"],
            "allowed_tools": ["shell"],
        },
        api_key="aegis_test",
        verify_api_key=_verify_ok,
        env=_enabled_env(),
        runner=runner,
    )
    assert status == 403
    assert body["error_code"] == RuntimeErrorCode.TOOL_NOT_REGISTERED.value
    assert runner.calls == 0


def test_structured_success_returns_observed_model_trace_and_usage():
    runner = FakeRunner()
    status, body = handle_omega_run(
        data={"input": "x", "allowed_capabilities": ["research-synthesis"]},
        api_key="aegis_test",
        verify_api_key=_verify_ok,
        env=_enabled_env(),
        runner=runner,
    )
    assert status == 200
    assert body["status"] == RunStatus.SUCCEEDED.value
    assert body["model"] == "gpt-5.6-sol"
    assert body["trace_id"] == "trace_" + "d" * 32
    assert body["usage"]["total_tokens"] == 14
    assert body["final_output"]["synthesis"] == "bounded result"
    assert runner.calls == 1


def test_dev_bypass_identity_is_rejected_for_paid_omega_runtime():
    runner = FakeRunner()
    status, body = handle_omega_run(
        data={"input": "x", "allowed_capabilities": ["research-synthesis"]},
        api_key="aegis_anything_goes",
        verify_api_key=lambda _key: ("dev@local", "explorer"),
        env=_enabled_env(),
        runner=runner,
    )
    assert status == 401
    assert body["error_code"] == RuntimeErrorCode.UNAUTHORIZED.value
    assert runner.calls == 0
