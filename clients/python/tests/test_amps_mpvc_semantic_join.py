import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
LINTER_PATH = ROOT / "scripts" / "agent_governance_lint.py"


def load_governance_linter():
    spec = importlib.util.spec_from_file_location("agent_governance_lint", LINTER_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_amps_contract_is_compatible_with_hardened_mpvc_authority_api():
    linter = load_governance_linter()

    assert linter.lint_contract() == []
