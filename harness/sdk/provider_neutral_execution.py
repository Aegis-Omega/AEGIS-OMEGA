"""Provider-neutral execution surface for AEGIS repository admission.

This module intentionally removes Claude-specific cognitive-anchor files from
workspace admission while preserving the existing fail-closed sovereign
execution implementation for identity, policy, evidence, receipts and leases.
"""
from __future__ import annotations

from harness.sdk import sovereign_execution as _legacy
from harness.sdk.sovereign_execution import (  # re-export stable runtime API
    ADMITTED,
    DENIED,
    D0,
    D1,
    D2,
    D3,
    D4,
    ZERO_HASH,
    ApprovalGrant,
    AuthorityEvaluator,
    AuthorityRequest,
    CapabilityEvidence,
    DurableExecutionRecord,
    DurableExecutionRegistry,
    EventEnvelope,
    ExecutionIdentityEnvelope,
    MutationReceipt,
    PolicyDecision,
    ReceiptChain,
    SovereignExecutionError,
    WriterLeaseManager,
    canonical_bytes,
    canonical_hash,
    compute_skill_registry_root,
    compute_workspace_binding,
    decision_dict,
    deterministic_redaction,
    git_remote,
    load_capability_registry,
    load_policy,
    make_mutation_receipt,
    sha256_hex,
)

__all__ = (
    "ADMITTED",
    "DENIED",
    "D0",
    "D1",
    "D2",
    "D3",
    "D4",
    "ZERO_HASH",
    "ApprovalGrant",
    "AuthorityEvaluator",
    "AuthorityRequest",
    "CapabilityEvidence",
    "DurableExecutionRecord",
    "DurableExecutionRegistry",
    "EventEnvelope",
    "ExecutionIdentityEnvelope",
    "MutationReceipt",
    "PolicyDecision",
    "ReceiptChain",
    "SovereignExecutionError",
    "WriterLeaseManager",
    "canonical_bytes",
    "canonical_hash",
    "compute_skill_registry_root",
    "compute_workspace_binding",
    "decision_dict",
    "deterministic_redaction",
    "git_remote",
    "load_capability_registry",
    "load_policy",
    "make_mutation_receipt",
    "sha256_hex",
    "REQUIRED_REPOSITORY_FILES",
    "verify_workspace",
)

REQUIRED_REPOSITORY_FILES = (
    "CONSTITUTIONAL_DECLARATION.md",
    "docs/claims.json",
)


def verify_workspace(*args, required_files=REQUIRED_REPOSITORY_FILES, **kwargs):
    """Verify repository identity without provider-specific anchor requirements."""
    return _legacy.verify_workspace(*args, required_files=required_files, **kwargs)
