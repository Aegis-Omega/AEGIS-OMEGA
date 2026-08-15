from __future__ import annotations

from .authority import AuthorityGate
from .types import AuthorityDecision, OmegaRunRequest, RuntimeErrorCode, ToolEvidence


class EvidenceValidationError(ValueError):
    def __init__(self, code: RuntimeErrorCode, message: str):
        super().__init__(message)
        self.code = code


def validate_tool_input(
    tool_name: str,
    request: OmegaRunRequest,
    gate: AuthorityGate,
) -> AuthorityDecision:
    """Validate one local tool call against the request's explicit authority envelope."""
    if tool_name not in request.allowed_tools:
        return AuthorityDecision(
            admitted=False,
            code=RuntimeErrorCode.TOOL_NOT_ALLOWED,
            reason=f"tool is outside request allowlist: {tool_name}",
        )
    return gate.evaluate(request)


def validate_tool_output(evidence: ToolEvidence) -> ToolEvidence:
    """Fail closed when a tool claims success without digest-bound evidence."""
    if not evidence.success:
        return evidence

    if evidence.result_digest is None:
        raise EvidenceValidationError(
            RuntimeErrorCode.EVIDENCE_MISSING,
            f"successful tool result has no result digest: {evidence.tool}",
        )
    if not evidence.evidence_digests:
        raise EvidenceValidationError(
            RuntimeErrorCode.EVIDENCE_MISSING,
            f"successful tool result has no evidence digests: {evidence.tool}",
        )

    if evidence.mutates:
        missing = [
            name
            for name, value in (
                ("target_digest", evidence.target_digest),
                ("pre_state_digest", evidence.pre_state_digest),
                ("post_state_digest", evidence.post_state_digest),
            )
            if value is None
        ]
        if missing:
            raise EvidenceValidationError(
                RuntimeErrorCode.EVIDENCE_MISSING,
                f"mutation evidence incomplete for {evidence.tool}: {', '.join(missing)}",
            )

    return evidence
