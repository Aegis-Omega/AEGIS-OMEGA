import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest

from openai_runtime.config import OpenAIRuntimeConfig, RuntimeConfigError
from openai_runtime.types import RuntimeErrorCode


def _base_env():
    return {
        "AEGIS_OPENAI_RUNTIME_ENABLED": "true",
        "OPENAI_API_KEY": "test-key-not-real",
        "OPENAI_PRIMARY_MODEL": "gpt-5.6-sol",
    }


def test_disabled_runtime_fails_closed():
    env = _base_env()
    env["AEGIS_OPENAI_RUNTIME_ENABLED"] = "false"
    with pytest.raises(RuntimeConfigError) as exc:
        OpenAIRuntimeConfig.from_env(env)
    assert exc.value.code == RuntimeErrorCode.RUNTIME_DISABLED


def test_missing_api_key_fails_closed():
    env = _base_env()
    env.pop("OPENAI_API_KEY")
    with pytest.raises(RuntimeConfigError) as exc:
        OpenAIRuntimeConfig.from_env(env)
    assert exc.value.code == RuntimeErrorCode.API_KEY_MISSING


def test_missing_model_fails_closed():
    env = _base_env()
    env.pop("OPENAI_PRIMARY_MODEL")
    with pytest.raises(RuntimeConfigError) as exc:
        OpenAIRuntimeConfig.from_env(env)
    assert exc.value.code == RuntimeErrorCode.MODEL_MISSING


@pytest.mark.parametrize(
    ("name", "value"),
    [
        ("AEGIS_OPENAI_MAX_TURNS", "0"),
        ("AEGIS_OPENAI_MAX_TURNS", "-1"),
        ("AEGIS_OPENAI_MAX_TURNS", "nan"),
        ("AEGIS_OPENAI_MAX_TOOL_CONCURRENCY", "0"),
        ("AEGIS_OPENAI_MAX_TOOL_CONCURRENCY", "-3"),
        ("AEGIS_OPENAI_MAX_TOOL_CONCURRENCY", "nope"),
    ],
)
def test_invalid_positive_integer_config_is_rejected(name, value):
    env = _base_env()
    env[name] = value
    with pytest.raises(RuntimeConfigError) as exc:
        OpenAIRuntimeConfig.from_env(env)
    assert exc.value.code == RuntimeErrorCode.INVALID_CONFIG


def test_sensitive_tracing_defaults_false_and_bounds_are_applied():
    cfg = OpenAIRuntimeConfig.from_env(_base_env())
    assert cfg.trace_sensitive_data is False
    assert cfg.max_turns == 12
    assert cfg.max_tool_concurrency == 2
    assert cfg.model == "gpt-5.6-sol"


def test_api_key_is_redacted_from_config_repr():
    cfg = OpenAIRuntimeConfig.from_env(_base_env())
    assert "test-key-not-real" not in repr(cfg)
