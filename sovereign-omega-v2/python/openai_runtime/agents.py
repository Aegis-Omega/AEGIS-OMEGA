from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .types import OmegaManagerOutput, SpecialistOutput


class AgentsSDKUnavailable(RuntimeError):
    pass


def _agent_class():
    try:
        from agents import Agent
    except ImportError as exc:
        raise AgentsSDKUnavailable(
            "openai-agents is required for live AEGIS OpenAI orchestration"
        ) from exc
    return Agent


@dataclass(frozen=True, slots=True)
class SpecialistSet:
    research: Any
    verification: Any
    implementation: Any

    def all(self) -> tuple[Any, Any, Any]:
        return (self.research, self.verification, self.implementation)


def build_specialists(model: str) -> SpecialistSet:
    Agent = _agent_class()

    research = Agent(
        name="AEGIS Research Specialist",
        model=model,
        instructions=(
            "Analyze only the evidence supplied in the run context. Distinguish observed facts, "
            "inferences, and unresolved questions. Do not claim external verification unless an "
            "AEGIS-governed tool supplied evidence for it. Return structured output only."
        ),
        output_type=SpecialistOutput,
        tools=[],
    )

    verification = Agent(
        name="AEGIS Verification Specialist",
        model=model,
        instructions=(
            "Act as an adversarial verifier. Look for contradictions, missing evidence, hidden "
            "assumptions, and overclaimed authority. Prefer downgrade or unresolved status over "
            "unsupported certainty. Return structured output only."
        ),
        output_type=SpecialistOutput,
        tools=[],
    )

    implementation = Agent(
        name="AEGIS Implementation Specialist",
        model=model,
        instructions=(
            "Produce bounded implementation proposals from admitted evidence and constraints. "
            "Do not perform external effects, grant yourself tools, or imply that a proposal was "
            "executed. Return structured output only."
        ),
        output_type=SpecialistOutput,
        tools=[],
    )

    return SpecialistSet(
        research=research,
        verification=verification,
        implementation=implementation,
    )


def build_omega_manager(
    model: str,
    specialists: SpecialistSet,
    allowed_capabilities: set[str] | frozenset[str] | None = None,
):
    Agent = _agent_class()

    allowed = (
        {"research-synthesis", "adversarial-verification", "implementation-proposal"}
        if allowed_capabilities is None
        else set(allowed_capabilities)
    )
    tools = []
    if "research-synthesis" in allowed:
        tools.append(specialists.research.as_tool(
            tool_name="research_specialist",
            tool_description="Analyze admitted evidence and identify grounded research conclusions.",
            max_turns=4,
            needs_approval=False,
        ))
    if "adversarial-verification" in allowed:
        tools.append(specialists.verification.as_tool(
            tool_name="verification_specialist",
            tool_description="Adversarially verify claims, assumptions, and evidence sufficiency.",
            max_turns=4,
            needs_approval=False,
        ))
    if "implementation-proposal" in allowed:
        tools.append(specialists.implementation.as_tool(
            tool_name="implementation_specialist",
            tool_description="Propose bounded implementation actions without performing external effects.",
            max_turns=4,
            needs_approval=False,
        ))

    return Agent(
        name="AEGIS Omega Manager",
        model=model,
        instructions=(
            "You are the AEGIS Omega manager. You retain ownership of the final synthesis. "
            "Use specialists when they materially improve evidence quality. Never expand the "
            "authority envelope, invent tool execution, or promote an unsupported claim. "
            "Treat AGI/ASI/superintelligence as hypotheses requiring evidence, not self-issued status. "
            "Return the final synthesis as the structured output schema."
        ),
        output_type=OmegaManagerOutput,
        tools=tools,
    )
