import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from openai_runtime.authority import AuthorityGate, ToolPolicy
from openai_runtime.types import ActionClass, OmegaRunRequest, RuntimeErrorCode


REGISTERED_CAPS = {
    "research-synthesis",
    "adversarial-verification",
    "implementation-proposal",
}


def _gate(active_grants=None, tools=None, approvals=None):
    return AuthorityGate(
        registered_capabilities=REGISTERED_CAPS,
        active_grants=set(active_grants or []),
        registered_tools=dict(tools or {}),
        approvals=set(approvals or []),
    )


def test_unknown_capability_is_denied():
    req = OmegaRunRequest(input="x", allowed_capabilities=["root-shell"])
    decision = _gate(active_grants={"root-shell"}).evaluate(req)
    assert decision.admitted is False
    assert decision.code == RuntimeErrorCode.UNKNOWN_CAPABILITY


def test_ungranted_capability_is_denied():
    req = OmegaRunRequest(input="x", allowed_capabilities=["research-synthesis"])
    decision = _gate().evaluate(req)
    assert decision.admitted is False
    assert decision.code == RuntimeErrorCode.CAPABILITY_NOT_GRANTED


def test_unregistered_tool_is_denied_before_model_call():
    req = OmegaRunRequest(
        input="x",
        allowed_capabilities=["research-synthesis"],
        allowed_tools=["unknown-tool"],
    )
    decision = _gate(active_grants={"research-synthesis"}).evaluate(req)
    assert decision.admitted is False
    assert decision.code == RuntimeErrorCode.TOOL_NOT_REGISTERED


def test_tool_requiring_undeclared_capability_is_denied():
    tools = {
        "propose-patch": ToolPolicy(
            name="propose-patch",
            required_capability="implementation-proposal",
            max_action_class=ActionClass.D1,
        )
    }
    req = OmegaRunRequest(
        input="x",
        allowed_capabilities=["research-synthesis"],
        allowed_tools=["propose-patch"],
        action_class=ActionClass.D1,
    )
    decision = _gate(active_grants={"research-synthesis", "implementation-proposal"}, tools=tools).evaluate(req)
    assert decision.admitted is False
    assert decision.code == RuntimeErrorCode.TOOL_NOT_ALLOWED


def test_action_class_above_tool_ceiling_is_denied():
    tools = {
        "read-evidence": ToolPolicy(
            name="read-evidence",
            required_capability="research-synthesis",
            max_action_class=ActionClass.D0,
        )
    }
    req = OmegaRunRequest(
        input="x",
        allowed_capabilities=["research-synthesis"],
        allowed_tools=["read-evidence"],
        action_class=ActionClass.D2,
    )
    decision = _gate(active_grants={"research-synthesis"}, tools=tools).evaluate(req)
    assert decision.admitted is False
    assert decision.code == RuntimeErrorCode.ACTION_CLASS_EXCEEDED


def test_mutating_tool_requires_explicit_approval():
    tools = {
        "apply-patch": ToolPolicy(
            name="apply-patch",
            required_capability="implementation-proposal",
            max_action_class=ActionClass.D2,
            requires_approval=True,
            approval_id="approve:apply-patch",
            mutates=True,
        )
    }
    req = OmegaRunRequest(
        input="x",
        allowed_capabilities=["implementation-proposal"],
        allowed_tools=["apply-patch"],
        action_class=ActionClass.D2,
    )
    decision = _gate(active_grants={"implementation-proposal"}, tools=tools).evaluate(req)
    assert decision.admitted is False
    assert decision.code == RuntimeErrorCode.APPROVAL_REQUIRED


def test_read_only_d0_with_registered_granted_capability_is_admitted():
    req = OmegaRunRequest(
        input="verify evidence",
        allowed_capabilities=["research-synthesis", "adversarial-verification"],
        action_class=ActionClass.D0,
    )
    decision = _gate(active_grants={"research-synthesis", "adversarial-verification"}).evaluate(req)
    assert decision.admitted is True
    assert decision.code is None
