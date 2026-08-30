"""AEGIS proof-carrying Trace SDK.

This is not an observability log and a trace is never authority by itself.
The SDK records a deterministic, hash-bound execution/evidence graph whose
spans can bind existing Decision/Execution/Effect/Admission receipts without
collapsing their epistemic semantics.

Core rules:

* model/tool/external outputs remain evidence-only;
* Decision authority cannot be reinterpreted as Effect or Admission authority;
* only an ADMISSION span carrying ADMISSION_AUTHORITY may advance the tracked
  control-state root;
* causal dependencies must point to already-completed spans;
* structural parentage is checked as an acyclic graph;
* raw payloads are never stored by this module -- callers bind digests;
* exported bundles are independently replay-verifiable from JSON alone.

The canonical hashing primitive is the repository-local ``canonical_hash``.
No RFC 8785/JCS conformance claim is introduced here.
"""
from __future__ import annotations

import contextvars
import json
import re
import threading
from dataclasses import asdict, dataclass, field
from typing import Any, Iterable, Sequence

from harness.sdk.sovereign_execution import canonical_hash

TRACE_BUNDLE_KIND = "AEGIS_PROOF_TRACE_BUNDLE_V1"
TRACE_HEADER_KIND = "AEGIS_PROOF_TRACE_HEADER_V1"
TRACE_SEMANTICS = "TRACE_IS_EVIDENCE_CONTAINER_NOT_AUTHORITY"

MODEL = "MODEL"
TOOL = "TOOL"
HANDOFF = "HANDOFF"
GUARDRAIL = "GUARDRAIL"
DECISION = "DECISION"
EXECUTION = "EXECUTION"
EFFECT = "EFFECT"
ADMISSION = "ADMISSION"
MEMORY = "MEMORY"
HERITAGE = "HERITAGE"
JOINT_FAILURE = "JOINT_FAILURE"
VERIFIER = "VERIFIER"
EXTERNAL = "EXTERNAL"
CUSTOM = "CUSTOM"
SPAN_KINDS = {
    MODEL,
    TOOL,
    HANDOFF,
    GUARDRAIL,
    DECISION,
    EXECUTION,
    EFFECT,
    ADMISSION,
    MEMORY,
    HERITAGE,
    JOINT_FAILURE,
    VERIFIER,
    EXTERNAL,
    CUSTOM,
}

NO_AUTHORITY = "NONE"
DECISION_AUTHORITY = "DECISION_AUTHORITY"
ADMISSION_AUTHORITY = "ADMISSION_AUTHORITY"
AUTHORITY_CLASSES = {NO_AUTHORITY, DECISION_AUTHORITY, ADMISSION_AUTHORITY}

EVIDENCE_ONLY_KINDS = {
    MODEL,
    TOOL,
    HANDOFF,
    GUARDRAIL,
    EXECUTION,
    EFFECT,
    MEMORY,
    HERITAGE,
    JOINT_FAILURE,
    VERIFIER,
    EXTERNAL,
    CUSTOM,
}

T0 = "T0"
T1 = "T1"
T2 = "T2"
EPISTEMIC_TIERS = {T0, T1, T2}

OK = "OK"
ERROR = "ERROR"
DENIED = "DENIED"
DEFERRED = "DEFERRED"
REVERIFY = "REVERIFY"
SPAN_STATUSES = {OK, ERROR, DENIED, DEFERRED, REVERIFY}

ZERO_HASH = "0" * 64
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
GIT_RE = re.compile(r"^[0-9a-f]{40,64}$")
SAFE_ID_RE = re.compile(r"^[A-Za-z0-9._:/@+#=-]+$")


class ProofTraceError(ValueError):
    """Fail-closed Trace SDK error with a stable machine-readable code."""

    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


def _require_hash(name: str, value: str) -> None:
    if not isinstance(value, str) or not SHA256_RE.fullmatch(value):
        raise ProofTraceError(f"{name}:INVALID_SHA256")


def _require_git(name: str, value: str) -> None:
    if not isinstance(value, str) or not GIT_RE.fullmatch(value):
        raise ProofTraceError(f"{name}:INVALID_GIT_OBJECT")


def _require_id(name: str, value: str) -> None:
    if not isinstance(value, str) or not value or not SAFE_ID_RE.fullmatch(value):
        raise ProofTraceError(f"{name}:INVALID_ID")


def _require_optional_id(name: str, value: str | None) -> None:
    if value is not None:
        _require_id(name, value)


def _require_optional_hash(name: str, value: str | None) -> None:
    if value is not None:
        _require_hash(name, value)


def _require_unique_hashes(name: str, values: Sequence[str]) -> None:
    for value in values:
        _require_hash(name, value)
    if len(set(values)) != len(values):
        raise ProofTraceError(f"{name}:DUPLICATE")


def digest_payload(value: Any) -> str:
    """Return a domain-separated digest without persisting the supplied value."""

    return canonical_hash("AEGIS_TRACE_PAYLOAD_DIGEST_V1", value)


def trace_id_from_nonce(*, workflow_name: str, source_commit: str, deterministic_nonce: str) -> str:
    _require_id("workflow_name", workflow_name)
    _require_git("source_commit", source_commit)
    _require_id("deterministic_nonce", deterministic_nonce)
    root = canonical_hash(
        "AEGIS_TRACE_ID_V1",
        {
            "workflow_name": workflow_name,
            "source_commit": source_commit,
            "deterministic_nonce": deterministic_nonce,
        },
    )
    return f"trace_{root[:32]}"


@dataclass(frozen=True)
class TraceHeaderV1:
    trace_kind: str
    trace_semantics: str
    trace_id: str
    workflow_name: str
    group_id: str | None
    source_commit: str
    policy_commitment: str
    genesis_control_state_root: str
    metadata_digest: str

    def __post_init__(self) -> None:
        if self.trace_kind != TRACE_HEADER_KIND:
            raise ProofTraceError("TRACE_HEADER_KIND_MISMATCH")
        if self.trace_semantics != TRACE_SEMANTICS:
            raise ProofTraceError("TRACE_SEMANTICS_MISMATCH")
        _require_id("trace_id", self.trace_id)
        _require_id("workflow_name", self.workflow_name)
        _require_optional_id("group_id", self.group_id)
        _require_git("source_commit", self.source_commit)
        _require_hash("policy_commitment", self.policy_commitment)
        _require_hash("genesis_control_state_root", self.genesis_control_state_root)
        _require_hash("metadata_digest", self.metadata_digest)

    @property
    def root(self) -> str:
        return canonical_hash("AEGIS_PROOF_TRACE_HEADER_ROOT_V1", asdict(self))


@dataclass(frozen=True)
class SpanHandleV1:
    trace_root: str
    span_id: str
    allocation_order: int
    name: str
    span_kind: str
    parent_span_id: str | None
    causal_parent_ids: tuple[str, ...]
    captured_control_state_root: str
    start_context_digest: str

    def __post_init__(self) -> None:
        _require_hash("trace_root", self.trace_root)
        _require_id("span_id", self.span_id)
        if isinstance(self.allocation_order, bool) or self.allocation_order < 1:
            raise ProofTraceError("SPAN_ALLOCATION_ORDER_INVALID")
        _require_id("name", self.name)
        if self.span_kind not in SPAN_KINDS:
            raise ProofTraceError("SPAN_KIND_UNSUPPORTED")
        _require_optional_id("parent_span_id", self.parent_span_id)
        for parent in self.causal_parent_ids:
            _require_id("causal_parent_id", parent)
        if len(set(self.causal_parent_ids)) != len(self.causal_parent_ids):
            raise ProofTraceError("CAUSAL_PARENT_DUPLICATE")
        if self.parent_span_id == self.span_id or self.span_id in self.causal_parent_ids:
            raise ProofTraceError("SPAN_SELF_PARENT_FORBIDDEN")
        _require_hash("captured_control_state_root", self.captured_control_state_root)
        _require_hash("start_context_digest", self.start_context_digest)


@dataclass(frozen=True)
class TraceSpanV1:
    trace_root: str
    span_id: str
    sequence: int
    allocation_order: int
    name: str
    span_kind: str
    parent_span_id: str | None
    causal_parent_ids: tuple[str, ...]
    status: str
    authority_class: str
    epistemic_tier: str
    transition_id: str | None
    input_digest: str | None
    output_digest: str | None
    receipt_roots: tuple[str, ...]
    evidence_roots: tuple[str, ...]
    control_state_before: str
    control_state_after: str
    observed_pre_state_root: str | None
    observed_post_state_root: str | None
    error_code: str | None
    external_system: str | None
    external_ref_digest: str | None
    start_context_digest: str

    def __post_init__(self) -> None:
        _require_hash("trace_root", self.trace_root)
        _require_id("span_id", self.span_id)
        if isinstance(self.sequence, bool) or self.sequence < 1:
            raise ProofTraceError("SPAN_SEQUENCE_INVALID")
        if isinstance(self.allocation_order, bool) or self.allocation_order < 1:
            raise ProofTraceError("SPAN_ALLOCATION_ORDER_INVALID")
        _require_id("name", self.name)
        if self.span_kind not in SPAN_KINDS:
            raise ProofTraceError("SPAN_KIND_UNSUPPORTED")
        _require_optional_id("parent_span_id", self.parent_span_id)
        for parent in self.causal_parent_ids:
            _require_id("causal_parent_id", parent)
        if len(set(self.causal_parent_ids)) != len(self.causal_parent_ids):
            raise ProofTraceError("CAUSAL_PARENT_DUPLICATE")
        if self.parent_span_id == self.span_id or self.span_id in self.causal_parent_ids:
            raise ProofTraceError("SPAN_SELF_PARENT_FORBIDDEN")
        if self.status not in SPAN_STATUSES:
            raise ProofTraceError("SPAN_STATUS_UNSUPPORTED")
        if self.authority_class not in AUTHORITY_CLASSES:
            raise ProofTraceError("SPAN_AUTHORITY_CLASS_UNSUPPORTED")
        if self.epistemic_tier not in EPISTEMIC_TIERS:
            raise ProofTraceError("SPAN_EPISTEMIC_TIER_UNSUPPORTED")
        _require_optional_hash("transition_id", self.transition_id)
        _require_optional_hash("input_digest", self.input_digest)
        _require_optional_hash("output_digest", self.output_digest)
        _require_unique_hashes("receipt_root", self.receipt_roots)
        _require_unique_hashes("evidence_root", self.evidence_roots)
        _require_hash("control_state_before", self.control_state_before)
        _require_hash("control_state_after", self.control_state_after)
        _require_optional_hash("observed_pre_state_root", self.observed_pre_state_root)
        _require_optional_hash("observed_post_state_root", self.observed_post_state_root)
        _require_optional_id("error_code", self.error_code)
        _require_optional_id("external_system", self.external_system)
        _require_optional_hash("external_ref_digest", self.external_ref_digest)
        _require_hash("start_context_digest", self.start_context_digest)

        if self.span_kind in EVIDENCE_ONLY_KINDS and self.authority_class != NO_AUTHORITY:
            raise ProofTraceError("EVIDENCE_ONLY_SPAN_CANNOT_CARRY_AUTHORITY")
        if self.span_kind == DECISION and self.authority_class not in {NO_AUTHORITY, DECISION_AUTHORITY}:
            raise ProofTraceError("DECISION_SPAN_AUTHORITY_CLASS_INVALID")
        if self.span_kind == ADMISSION and self.authority_class not in {NO_AUTHORITY, ADMISSION_AUTHORITY}:
            raise ProofTraceError("ADMISSION_SPAN_AUTHORITY_CLASS_INVALID")
        if self.authority_class == DECISION_AUTHORITY and self.span_kind != DECISION:
            raise ProofTraceError("DECISION_AUTHORITY_KIND_MISMATCH")
        if self.authority_class == ADMISSION_AUTHORITY and self.span_kind != ADMISSION:
            raise ProofTraceError("ADMISSION_AUTHORITY_KIND_MISMATCH")

        transition_bound_kinds = {DECISION, EXECUTION, EFFECT, ADMISSION}
        if self.span_kind in transition_bound_kinds and self.transition_id is None:
            raise ProofTraceError("TRANSITION_BOUND_SPAN_MISSING_TRANSITION_ID")

        if self.authority_class in {DECISION_AUTHORITY, ADMISSION_AUTHORITY} and not self.receipt_roots:
            raise ProofTraceError("AUTHORITY_SPAN_RECEIPT_BINDING_REQUIRED")
        if self.span_kind == EFFECT and not (self.receipt_roots or self.evidence_roots):
            raise ProofTraceError("EFFECT_SPAN_EVIDENCE_BINDING_REQUIRED")

        if self.span_kind != ADMISSION and self.control_state_after != self.control_state_before:
            raise ProofTraceError("NON_ADMISSION_CONTROL_STATE_MUTATION_FORBIDDEN")
        if (
            self.span_kind == ADMISSION
            and self.control_state_after != self.control_state_before
            and self.authority_class != ADMISSION_AUTHORITY
        ):
            raise ProofTraceError("CONTROL_STATE_ADVANCE_REQUIRES_ADMISSION_AUTHORITY")

        if self.external_system is None and self.external_ref_digest is not None:
            raise ProofTraceError("EXTERNAL_REF_WITHOUT_SYSTEM")
        if self.external_system is not None and self.external_ref_digest is None:
            raise ProofTraceError("EXTERNAL_SYSTEM_WITHOUT_REF")

    @property
    def root(self) -> str:
        return canonical_hash("AEGIS_PROOF_TRACE_SPAN_V1", asdict(self))


@dataclass(frozen=True)
class TraceCommitV1:
    sequence: int
    span_id: str
    span_root: str
    prior_commit_root: str

    def __post_init__(self) -> None:
        if isinstance(self.sequence, bool) or self.sequence < 1:
            raise ProofTraceError("TRACE_COMMIT_SEQUENCE_INVALID")
        _require_id("span_id", self.span_id)
        _require_hash("span_root", self.span_root)
        _require_hash("prior_commit_root", self.prior_commit_root)

    @property
    def root(self) -> str:
        return canonical_hash("AEGIS_PROOF_TRACE_COMMIT_V1", asdict(self))


@dataclass(frozen=True)
class ProofTraceBundleV1:
    bundle_kind: str
    header: TraceHeaderV1
    spans: tuple[TraceSpanV1, ...]
    commits: tuple[TraceCommitV1, ...]
    final_control_state_root: str
    artifact_manifest_root: str
    terminal_commit_root: str

    def __post_init__(self) -> None:
        if self.bundle_kind != TRACE_BUNDLE_KIND:
            raise ProofTraceError("TRACE_BUNDLE_KIND_MISMATCH")
        _require_hash("final_control_state_root", self.final_control_state_root)
        _require_hash("artifact_manifest_root", self.artifact_manifest_root)
        _require_hash("terminal_commit_root", self.terminal_commit_root)

    @property
    def root(self) -> str:
        return canonical_hash("AEGIS_PROOF_TRACE_BUNDLE_ROOT_V1", asdict(self))

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["bundle_root"] = self.root
        return payload

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), sort_keys=True, separators=(",", ":"), ensure_ascii=False)


@dataclass(frozen=True)
class TraceVerificationV1:
    valid: bool
    errors: tuple[str, ...]
    span_count: int
    artifact_count: int
    recomputed_final_control_state_root: str
    recomputed_artifact_manifest_root: str
    recomputed_terminal_commit_root: str
    bundle_root: str


_CURRENT_SPAN: contextvars.ContextVar[tuple[str, str] | None] = contextvars.ContextVar(
    "aegis_proof_trace_current_span", default=None
)


class ProofTrace:
    """Thread-safe builder for one proof-carrying trace."""

    def __init__(self, header: TraceHeaderV1):
        self.header = header
        self._lock = threading.RLock()
        self._allocation_order = 0
        self._active: dict[str, SpanHandleV1] = {}
        self._spans: list[TraceSpanV1] = []
        self._spans_by_id: dict[str, TraceSpanV1] = {}
        self._control_state_root = header.genesis_control_state_root
        self._closed = False

    @property
    def trace_root(self) -> str:
        return self.header.root

    @property
    def current_control_state_root(self) -> str:
        with self._lock:
            return self._control_state_root

    @property
    def span_count(self) -> int:
        with self._lock:
            return len(self._spans)

    def _require_open(self) -> None:
        if self._closed:
            raise ProofTraceError("TRACE_ALREADY_CLOSED")

    def start_span(
        self,
        *,
        name: str,
        span_kind: str,
        parent_span_id: str | None = None,
        causal_parent_ids: Iterable[str] = (),
        start_context: Any = None,
    ) -> SpanHandleV1:
        _require_id("name", name)
        if span_kind not in SPAN_KINDS:
            raise ProofTraceError("SPAN_KIND_UNSUPPORTED")
        with self._lock:
            self._require_open()
            current = _CURRENT_SPAN.get()
            if parent_span_id is None and current is not None and current[0] == self.trace_root:
                parent_span_id = current[1]
            if parent_span_id is not None and parent_span_id not in self._active and parent_span_id not in self._spans_by_id:
                raise ProofTraceError("STRUCTURAL_PARENT_UNKNOWN")

            causal = tuple(causal_parent_ids)
            if len(set(causal)) != len(causal):
                raise ProofTraceError("CAUSAL_PARENT_DUPLICATE")
            for parent in causal:
                if parent not in self._spans_by_id:
                    raise ProofTraceError("CAUSAL_PARENT_NOT_COMPLETED")

            self._allocation_order += 1
            span_id_root = canonical_hash(
                "AEGIS_PROOF_TRACE_SPAN_ID_V1",
                {
                    "trace_root": self.trace_root,
                    "allocation_order": self._allocation_order,
                    "name": name,
                    "span_kind": span_kind,
                },
            )
            span_id = f"span_{span_id_root[:32]}"
            handle = SpanHandleV1(
                trace_root=self.trace_root,
                span_id=span_id,
                allocation_order=self._allocation_order,
                name=name,
                span_kind=span_kind,
                parent_span_id=parent_span_id,
                causal_parent_ids=causal,
                captured_control_state_root=self._control_state_root,
                start_context_digest=digest_payload(start_context),
            )
            self._active[span_id] = handle
            return handle

    def finish_span(
        self,
        handle: SpanHandleV1,
        *,
        status: str = OK,
        authority_class: str = NO_AUTHORITY,
        epistemic_tier: str = T2,
        transition_id: str | None = None,
        input_digest: str | None = None,
        output_digest: str | None = None,
        receipt_roots: Iterable[str] = (),
        evidence_roots: Iterable[str] = (),
        control_state_after: str | None = None,
        observed_pre_state_root: str | None = None,
        observed_post_state_root: str | None = None,
        error_code: str | None = None,
        external_system: str | None = None,
        external_ref_digest: str | None = None,
    ) -> TraceSpanV1:
        with self._lock:
            self._require_open()
            active = self._active.get(handle.span_id)
            if active != handle or handle.trace_root != self.trace_root:
                raise ProofTraceError("SPAN_HANDLE_NOT_ACTIVE")

            sequence = len(self._spans) + 1
            before = handle.captured_control_state_root
            after = before if control_state_after is None else control_state_after

            if handle.span_kind == ADMISSION and before != self._control_state_root:
                raise ProofTraceError("ADMISSION_CONTROL_STATE_STALE")

            span = TraceSpanV1(
                trace_root=self.trace_root,
                span_id=handle.span_id,
                sequence=sequence,
                allocation_order=handle.allocation_order,
                name=handle.name,
                span_kind=handle.span_kind,
                parent_span_id=handle.parent_span_id,
                causal_parent_ids=handle.causal_parent_ids,
                status=status,
                authority_class=authority_class,
                epistemic_tier=epistemic_tier,
                transition_id=transition_id,
                input_digest=input_digest,
                output_digest=output_digest,
                receipt_roots=tuple(receipt_roots),
                evidence_roots=tuple(evidence_roots),
                control_state_before=before,
                control_state_after=after,
                observed_pre_state_root=observed_pre_state_root,
                observed_post_state_root=observed_post_state_root,
                error_code=error_code,
                external_system=external_system,
                external_ref_digest=external_ref_digest,
                start_context_digest=handle.start_context_digest,
            )
            self._spans.append(span)
            self._spans_by_id[span.span_id] = span
            del self._active[span.span_id]
            if span.span_kind == ADMISSION:
                self._control_state_root = span.control_state_after
            return span

    def record_span(self, *, name: str, span_kind: str, **finish_kwargs: Any) -> TraceSpanV1:
        handle = self.start_span(name=name, span_kind=span_kind)
        return self.finish_span(handle, **finish_kwargs)

    def record_external_span(
        self,
        *,
        external_system: str,
        external_trace_id: str,
        external_span_id: str,
        name: str,
        payload: Any = None,
        parent_span_id: str | None = None,
        causal_parent_ids: Iterable[str] = (),
    ) -> TraceSpanV1:
        """Import an external observability span as T2 evidence only.

        External trace/span identifiers are committed through a digest and are
        not reinterpreted as AEGIS authority or receipt identity.
        """

        _require_id("external_system", external_system)
        if not external_trace_id or not external_span_id:
            raise ProofTraceError("EXTERNAL_TRACE_IDENTITY_MISSING")
        handle = self.start_span(
            name=name,
            span_kind=EXTERNAL,
            parent_span_id=parent_span_id,
            causal_parent_ids=causal_parent_ids,
            start_context={"external_system": external_system},
        )
        return self.finish_span(
            handle,
            status=OK,
            authority_class=NO_AUTHORITY,
            epistemic_tier=T2,
            output_digest=digest_payload(payload),
            external_system=external_system,
            external_ref_digest=digest_payload(
                {
                    "system": external_system,
                    "trace_id": external_trace_id,
                    "span_id": external_span_id,
                }
            ),
        )

    def span(
        self,
        *,
        name: str,
        span_kind: str,
        parent_span_id: str | None = None,
        causal_parent_ids: Iterable[str] = (),
        start_context: Any = None,
    ) -> "SpanScopeV1":
        return SpanScopeV1(
            trace=self,
            name=name,
            span_kind=span_kind,
            parent_span_id=parent_span_id,
            causal_parent_ids=tuple(causal_parent_ids),
            start_context=start_context,
        )

    def close(self) -> ProofTraceBundleV1:
        with self._lock:
            self._require_open()
            if self._active:
                raise ProofTraceError("TRACE_HAS_ACTIVE_SPANS")

            commits: list[TraceCommitV1] = []
            prior = ZERO_HASH
            for span in self._spans:
                commit = TraceCommitV1(
                    sequence=span.sequence,
                    span_id=span.span_id,
                    span_root=span.root,
                    prior_commit_root=prior,
                )
                commits.append(commit)
                prior = commit.root

            artifacts = sorted(
                {
                    root
                    for span in self._spans
                    for root in (*span.receipt_roots, *span.evidence_roots)
                }
            )
            manifest = canonical_hash("AEGIS_TRACE_ARTIFACT_MANIFEST_V1", {"roots": artifacts})
            bundle = ProofTraceBundleV1(
                bundle_kind=TRACE_BUNDLE_KIND,
                header=self.header,
                spans=tuple(self._spans),
                commits=tuple(commits),
                final_control_state_root=self._control_state_root,
                artifact_manifest_root=manifest,
                terminal_commit_root=prior,
            )
            verification = verify_trace_bundle(bundle)
            if not verification.valid:
                raise ProofTraceError(f"TRACE_CLOSE_VERIFICATION_FAILED:{verification.errors[0]}")
            self._closed = True
            return bundle


@dataclass
class SpanScopeV1:
    """Context-manager span scope; timings are intentionally non-authoritative."""

    trace: ProofTrace
    name: str
    span_kind: str
    parent_span_id: str | None = None
    causal_parent_ids: tuple[str, ...] = ()
    start_context: Any = None
    handle: SpanHandleV1 | None = field(default=None, init=False)
    completed_span: TraceSpanV1 | None = field(default=None, init=False)
    _token: contextvars.Token[tuple[str, str] | None] | None = field(default=None, init=False)
    _status: str = field(default=OK, init=False)
    _authority_class: str = field(default=NO_AUTHORITY, init=False)
    _epistemic_tier: str = field(default=T2, init=False)
    _transition_id: str | None = field(default=None, init=False)
    _input_digest: str | None = field(default=None, init=False)
    _output_digest: str | None = field(default=None, init=False)
    _receipt_roots: list[str] = field(default_factory=list, init=False)
    _evidence_roots: list[str] = field(default_factory=list, init=False)
    _control_state_after: str | None = field(default=None, init=False)
    _observed_pre_state_root: str | None = field(default=None, init=False)
    _observed_post_state_root: str | None = field(default=None, init=False)
    _error_code: str | None = field(default=None, init=False)
    _external_system: str | None = field(default=None, init=False)
    _external_ref_digest: str | None = field(default=None, init=False)

    def __enter__(self) -> "SpanScopeV1":
        self.handle = self.trace.start_span(
            name=self.name,
            span_kind=self.span_kind,
            parent_span_id=self.parent_span_id,
            causal_parent_ids=self.causal_parent_ids,
            start_context=self.start_context,
        )
        self._token = _CURRENT_SPAN.set((self.trace.trace_root, self.handle.span_id))
        return self

    @property
    def span_id(self) -> str:
        if self.handle is None:
            raise ProofTraceError("SPAN_SCOPE_NOT_ENTERED")
        return self.handle.span_id

    def bind_transition(self, transition_id: str) -> None:
        _require_hash("transition_id", transition_id)
        self._transition_id = transition_id

    def bind_receipt(self, receipt_root: str) -> None:
        _require_hash("receipt_root", receipt_root)
        if receipt_root not in self._receipt_roots:
            self._receipt_roots.append(receipt_root)

    def bind_evidence(self, evidence_root: str) -> None:
        _require_hash("evidence_root", evidence_root)
        if evidence_root not in self._evidence_roots:
            self._evidence_roots.append(evidence_root)

    def bind_input(self, value: Any) -> None:
        self._input_digest = digest_payload(value)

    def bind_output(self, value: Any) -> None:
        self._output_digest = digest_payload(value)

    def set_status(self, status: str, *, error_code: str | None = None) -> None:
        if status not in SPAN_STATUSES:
            raise ProofTraceError("SPAN_STATUS_UNSUPPORTED")
        _require_optional_id("error_code", error_code)
        self._status = status
        self._error_code = error_code

    def set_authority(self, authority_class: str) -> None:
        if authority_class not in AUTHORITY_CLASSES:
            raise ProofTraceError("SPAN_AUTHORITY_CLASS_UNSUPPORTED")
        self._authority_class = authority_class

    def set_epistemic_tier(self, tier: str) -> None:
        if tier not in EPISTEMIC_TIERS:
            raise ProofTraceError("SPAN_EPISTEMIC_TIER_UNSUPPORTED")
        self._epistemic_tier = tier

    def observe_state(self, *, pre_state_root: str, post_state_root: str) -> None:
        _require_hash("observed_pre_state_root", pre_state_root)
        _require_hash("observed_post_state_root", post_state_root)
        self._observed_pre_state_root = pre_state_root
        self._observed_post_state_root = post_state_root

    def advance_control_state(self, next_state_root: str) -> None:
        _require_hash("next_state_root", next_state_root)
        self._control_state_after = next_state_root

    def bind_external_ref(self, *, system: str, trace_id: str, span_id: str) -> None:
        _require_id("external_system", system)
        if not trace_id or not span_id:
            raise ProofTraceError("EXTERNAL_TRACE_IDENTITY_MISSING")
        self._external_system = system
        self._external_ref_digest = digest_payload(
            {"system": system, "trace_id": trace_id, "span_id": span_id}
        )

    def __exit__(self, exc_type, exc, tb) -> bool:
        assert self.handle is not None
        try:
            if exc_type is not None:
                self._status = ERROR
                if self._error_code is None:
                    self._error_code = "UNHANDLED_EXCEPTION"
            self.completed_span = self.trace.finish_span(
                self.handle,
                status=self._status,
                authority_class=self._authority_class,
                epistemic_tier=self._epistemic_tier,
                transition_id=self._transition_id,
                input_digest=self._input_digest,
                output_digest=self._output_digest,
                receipt_roots=tuple(self._receipt_roots),
                evidence_roots=tuple(self._evidence_roots),
                control_state_after=self._control_state_after,
                observed_pre_state_root=self._observed_pre_state_root,
                observed_post_state_root=self._observed_post_state_root,
                error_code=self._error_code,
                external_system=self._external_system,
                external_ref_digest=self._external_ref_digest,
            )
        finally:
            if self._token is not None:
                _CURRENT_SPAN.reset(self._token)
        return False


class TraceSDK:
    """Factory surface for deterministic proof traces."""

    @staticmethod
    def start_trace(
        *,
        workflow_name: str,
        source_commit: str,
        policy_commitment: str,
        genesis_control_state_root: str,
        deterministic_nonce: str,
        group_id: str | None = None,
        metadata: Any = None,
        trace_id: str | None = None,
    ) -> ProofTrace:
        resolved_trace_id = trace_id or trace_id_from_nonce(
            workflow_name=workflow_name,
            source_commit=source_commit,
            deterministic_nonce=deterministic_nonce,
        )
        header = TraceHeaderV1(
            trace_kind=TRACE_HEADER_KIND,
            trace_semantics=TRACE_SEMANTICS,
            trace_id=resolved_trace_id,
            workflow_name=workflow_name,
            group_id=group_id,
            source_commit=source_commit,
            policy_commitment=policy_commitment,
            genesis_control_state_root=genesis_control_state_root,
            metadata_digest=digest_payload(metadata),
        )
        return ProofTrace(header)


def _artifact_manifest(spans: Sequence[TraceSpanV1]) -> tuple[str, int]:
    roots = sorted({root for span in spans for root in (*span.receipt_roots, *span.evidence_roots)})
    return canonical_hash("AEGIS_TRACE_ARTIFACT_MANIFEST_V1", {"roots": roots}), len(roots)


def _has_structural_cycle(spans: Sequence[TraceSpanV1]) -> bool:
    parents = {span.span_id: span.parent_span_id for span in spans}
    visiting: set[str] = set()
    visited: set[str] = set()

    def visit(node: str) -> bool:
        if node in visited:
            return False
        if node in visiting:
            return True
        visiting.add(node)
        parent = parents.get(node)
        if parent is not None and parent in parents and visit(parent):
            return True
        visiting.remove(node)
        visited.add(node)
        return False

    return any(visit(node) for node in parents)


def verify_trace_bundle(bundle: ProofTraceBundleV1) -> TraceVerificationV1:
    """Independently replay and verify one exported trace bundle."""

    errors: list[str] = []
    spans = tuple(bundle.spans)
    span_by_id: dict[str, TraceSpanV1] = {}
    seq_by_id: dict[str, int] = {}

    if bundle.bundle_kind != TRACE_BUNDLE_KIND:
        errors.append("TRACE_BUNDLE_KIND_MISMATCH")

    expected_sequence = 1
    seen_allocations: set[int] = set()
    for span in spans:
        try:
            span.__post_init__()
        except ProofTraceError as exc:
            errors.append(f"SPAN_INVALID:{span.span_id}:{exc.code}")
            continue
        if span.trace_root != bundle.header.root:
            errors.append(f"SPAN_TRACE_ROOT_MISMATCH:{span.span_id}")
        if span.sequence != expected_sequence:
            errors.append(f"SPAN_SEQUENCE_GAP:{span.span_id}")
        expected_sequence += 1
        if span.span_id in span_by_id:
            errors.append(f"SPAN_ID_DUPLICATE:{span.span_id}")
        span_by_id[span.span_id] = span
        seq_by_id[span.span_id] = span.sequence
        if span.allocation_order in seen_allocations:
            errors.append(f"SPAN_ALLOCATION_DUPLICATE:{span.span_id}")
        seen_allocations.add(span.allocation_order)

    for span in spans:
        if span.parent_span_id is not None and span.parent_span_id not in span_by_id:
            errors.append(f"STRUCTURAL_PARENT_MISSING:{span.span_id}")
        for parent in span.causal_parent_ids:
            if parent not in span_by_id:
                errors.append(f"CAUSAL_PARENT_MISSING:{span.span_id}")
            elif seq_by_id[parent] >= span.sequence:
                errors.append(f"CAUSAL_PARENT_NOT_PRIOR:{span.span_id}")

    if _has_structural_cycle(spans):
        errors.append("STRUCTURAL_PARENT_CYCLE")

    if len(bundle.commits) != len(spans):
        errors.append("TRACE_COMMIT_COUNT_MISMATCH")
    prior = ZERO_HASH
    for index, span in enumerate(spans):
        if index >= len(bundle.commits):
            break
        commit = bundle.commits[index]
        if commit.sequence != span.sequence:
            errors.append(f"TRACE_COMMIT_SEQUENCE_MISMATCH:{span.span_id}")
        if commit.span_id != span.span_id:
            errors.append(f"TRACE_COMMIT_SPAN_ID_MISMATCH:{span.span_id}")
        if commit.span_root != span.root:
            errors.append(f"TRACE_COMMIT_SPAN_ROOT_MISMATCH:{span.span_id}")
        if commit.prior_commit_root != prior:
            errors.append(f"TRACE_COMMIT_CHAIN_MISMATCH:{span.span_id}")
        prior = commit.root

    if bundle.terminal_commit_root != prior:
        errors.append("TRACE_TERMINAL_COMMIT_ROOT_MISMATCH")

    current_state = bundle.header.genesis_control_state_root
    for span in spans:
        if span.span_kind == ADMISSION:
            if span.control_state_before != current_state:
                errors.append(f"ADMISSION_CONTROL_STATE_STALE:{span.span_id}")
            current_state = span.control_state_after
        elif span.control_state_after != span.control_state_before:
            errors.append(f"NON_ADMISSION_CONTROL_STATE_MUTATION:{span.span_id}")

    if bundle.final_control_state_root != current_state:
        errors.append("TRACE_FINAL_CONTROL_STATE_MISMATCH")

    manifest, artifact_count = _artifact_manifest(spans)
    if bundle.artifact_manifest_root != manifest:
        errors.append("TRACE_ARTIFACT_MANIFEST_MISMATCH")

    return TraceVerificationV1(
        valid=not errors,
        errors=tuple(errors),
        span_count=len(spans),
        artifact_count=artifact_count,
        recomputed_final_control_state_root=current_state,
        recomputed_artifact_manifest_root=manifest,
        recomputed_terminal_commit_root=prior,
        bundle_root=bundle.root,
    )


def bundle_from_json(payload: str) -> ProofTraceBundleV1:
    """Load a portable JSON bundle and re-materialize nominal typed objects."""

    try:
        raw = json.loads(payload)
    except json.JSONDecodeError as exc:
        raise ProofTraceError("TRACE_JSON_INVALID") from exc
    if not isinstance(raw, dict):
        raise ProofTraceError("TRACE_JSON_ROOT_NOT_OBJECT")

    supplied_root = raw.pop("bundle_root", None)
    header_raw = raw.get("header")
    spans_raw = raw.get("spans")
    commits_raw = raw.get("commits")
    if not isinstance(header_raw, dict) or not isinstance(spans_raw, list) or not isinstance(commits_raw, list):
        raise ProofTraceError("TRACE_JSON_STRUCTURE_INVALID")

    try:
        header = TraceHeaderV1(**header_raw)
        spans = tuple(
            TraceSpanV1(
                **{
                    **item,
                    "causal_parent_ids": tuple(item.get("causal_parent_ids", ())),
                    "receipt_roots": tuple(item.get("receipt_roots", ())),
                    "evidence_roots": tuple(item.get("evidence_roots", ())),
                }
            )
            for item in spans_raw
        )
        commits = tuple(TraceCommitV1(**item) for item in commits_raw)
        bundle = ProofTraceBundleV1(
            bundle_kind=raw["bundle_kind"],
            header=header,
            spans=spans,
            commits=commits,
            final_control_state_root=raw["final_control_state_root"],
            artifact_manifest_root=raw["artifact_manifest_root"],
            terminal_commit_root=raw["terminal_commit_root"],
        )
    except (KeyError, TypeError, ProofTraceError) as exc:
        if isinstance(exc, ProofTraceError):
            raise
        raise ProofTraceError("TRACE_JSON_STRUCTURE_INVALID") from exc

    if supplied_root is not None and supplied_root != bundle.root:
        raise ProofTraceError("TRACE_BUNDLE_ROOT_MISMATCH")
    return bundle


def openai_trace_metadata(bundle: ProofTraceBundleV1) -> dict[str, str]:
    """Return non-sensitive metadata suitable for an OpenAI Agents SDK trace.

    This does not export raw prompts, tool arguments, model outputs, or secrets.
    It only binds the OpenAI observability trace to the independently verifiable
    AEGIS proof-trace bundle.
    """

    return {
        "aegis_trace_id": bundle.header.trace_id,
        "aegis_trace_root": bundle.header.root,
        "aegis_bundle_root": bundle.root,
        "aegis_terminal_commit_root": bundle.terminal_commit_root,
        "aegis_policy_commitment": bundle.header.policy_commitment,
        "aegis_source_commit": bundle.header.source_commit,
    }
