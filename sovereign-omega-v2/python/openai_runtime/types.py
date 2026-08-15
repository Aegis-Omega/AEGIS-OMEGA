from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class RuntimeErrorCode(str, Enum):
    RUNTIME_DISABLED = "RUNTIME_DISABLED"
    API_KEY_MISSING = "API_KEY_MISSING"
    MODEL_MISSING = "MODEL_MISSING"
    INVALID_CONFIG = "INVALID_CONFIG"
    INVALID_REQUEST = "INVALID_REQUEST"
    UNAUTHORIZED = "UNAUTHORIZED"
    UNKNOWN_CAPABILITY = "UNKNOWN_CAPABILITY"
    CAPABILITY_NOT_GRANTED = "CAPABILITY_NOT_GRANTED"
    TOOL_NOT_REGISTERED = "TOOL_NOT_REGISTERED"
    TOOL_NOT_ALLOWED = "TOOL_NOT_ALLOWED"
    ACTION_CLASS_EXCEEDED = "ACTION_CLASS_EXCEEDED"
    APPROVAL_REQUIRED = "APPROVAL_REQUIRED"
    EVIDENCE_MISSING = "EVIDENCE_MISSING"
    RECEIPT_INCOMPLETE = "RECEIPT_INCOMPLETE"
    SDK_UNAVAILABLE = "SDK_UNAVAILABLE"
    SDK_ERROR = "SDK_ERROR"
    INVALID_FINAL_OUTPUT = "INVALID_FINAL_OUTPUT"


class ActionClass(str, Enum):
    D0 = "D0"
    D1 = "D1"
    D2 = "D2"
    D3 = "D3"
    D4 = "D4"


class RunStatus(str, Enum):
    SUCCEEDED = "SUCCEEDED"
    DENIED = "DENIED"
    FAILED = "FAILED"


class SpecialistOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    summary: str = Field(min_length=1)
    evidence: list[str] = Field(default_factory=list)
    uncertainties: list[str] = Field(default_factory=list)
    recommended_action: str | None = None


class OmegaManagerOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    synthesis: str = Field(min_length=1)
    evidence: list[str] = Field(default_factory=list)
    unresolved: list[str] = Field(default_factory=list)
    recommended_actions: list[str] = Field(default_factory=list)


class OmegaRunRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    input: str = Field(min_length=1)
    allowed_capabilities: list[str] = Field(default_factory=list)
    allowed_tools: list[str] = Field(default_factory=list)
    action_class: ActionClass = ActionClass.D0
    approvals: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)
    fallback_allowed: bool = False

    @field_validator("input")
    @classmethod
    def _non_blank_input(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("input must not be blank")
        return value

    @field_validator("allowed_capabilities", "allowed_tools", "approvals")
    @classmethod
    def _normalize_string_lists(cls, value: list[str]) -> list[str]:
        normalized: list[str] = []
        seen: set[str] = set()
        for raw in value:
            item = raw.strip()
            if not item:
                raise ValueError("list values must not be blank")
            if item not in seen:
                seen.add(item)
                normalized.append(item)
        return normalized


class OmegaRunContext(BaseModel):
    model_config = ConfigDict(extra="forbid")

    execution_id: str = Field(min_length=1)
    caller_email: str = Field(min_length=1)
    caller_tier: str = Field(min_length=1)
    model: str = Field(min_length=1)
    request_digest: str = Field(pattern=r"^[0-9a-f]{64}$")


class AuthorityDecision(BaseModel):
    model_config = ConfigDict(extra="forbid")

    admitted: bool
    code: RuntimeErrorCode | None = None
    reason: str = ""

    @model_validator(mode="after")
    def _decision_is_explicit(self) -> "AuthorityDecision":
        if self.admitted and self.code is not None:
            raise ValueError("admitted decisions cannot carry a denial code")
        if not self.admitted and self.code is None:
            raise ValueError("denied decisions require a denial code")
        return self


class ToolEvidence(BaseModel):
    model_config = ConfigDict(extra="forbid")

    tool: str = Field(min_length=1)
    success: bool
    result_digest: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    evidence_digests: list[str] = Field(default_factory=list)
    mutates: bool = False
    target_digest: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    pre_state_digest: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    post_state_digest: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")

    @field_validator("evidence_digests")
    @classmethod
    def _evidence_hashes(cls, value: list[str]) -> list[str]:
        for digest in value:
            if len(digest) != 64 or any(ch not in "0123456789abcdef" for ch in digest):
                raise ValueError("evidence digests must be lowercase SHA-256 hex")
        return value


class ToolCallRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")

    tool: str
    status: str
    evidence_digests: list[str] = Field(default_factory=list)


class OmegaRunResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    execution_id: str = Field(min_length=1)
    status: RunStatus
    model: str = Field(min_length=1)
    final_output: OmegaManagerOutput | None = None
    specialists_used: list[str] = Field(default_factory=list)
    tool_calls: list[ToolCallRecord] = Field(default_factory=list)
    evidence_digests: list[str] = Field(default_factory=list)
    trace_id: str | None = None
    receipt_digest: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    denial_code: str | None = None
    error_code: RuntimeErrorCode | None = None
    usage: dict[str, int] | None = None
    is_replay_reconstructable: bool = True

    @model_validator(mode="after")
    def _status_contract(self) -> "OmegaRunResult":
        if self.status == RunStatus.SUCCEEDED:
            if self.final_output is None:
                raise ValueError("successful result requires final_output")
            if self.denial_code is not None or self.error_code is not None:
                raise ValueError("successful result cannot carry denial/error code")
        else:
            if self.final_output is not None:
                raise ValueError("denied/failed result cannot carry final_output")
        return self
