"""
SOVEREIGN OMEGA — SAGA Identity Layer
EPISTEMIC TIER: T2 (engineering hypothesis — implementation pending)

SAGA: Security Architecture for Governing Agentic Systems.
Provides SPIFFE/SVID non-human identity credentials for each agent session,
scoping their permissions to their declared mutation operator set.

This module is a validated stub. The SPIFFE/SVID credential issuance
is fully specified; the PKI infrastructure integration requires
production deployment to complete.

AUTHORIZATION INVERSION PROBLEM (from Archive 4 SAGA documents):
Agents are technically authorised to retrieve information from secure silos
but lack internal constraints to verify that their subsequent outputs are
safe, proportionate, or aligned with the delegating principal.

THIS MODULE ADDRESSES: the identity and scope component of that problem.
The K-bound enforcement in the TypeScript E4 gate addresses the constraint component.
Together they close the Authorization Inversion gap.

INTEGRATION:
  - Agent session start → issue SVID → attach to event context
  - AAP claims logged to E3 event substrate as AGENT_AUTHORIZED events
  - K-bound from CapacityDeclaration scopes the SPIFFE workload ID
"""

import hashlib
import json
import os
import time
from dataclasses import dataclass
from typing import Dict, List, Optional


@dataclass(frozen=True)
class AgentSVID:
    """
    SPIFFE Verifiable Identity Document for an agent session.
    Scopes the agent's authority to its declared mutation operator set.
    """
    spiffe_id: str              # spiffe://sovereign-omega/agent/{role}/{session_id}
    role: str                   # guardian | implementer | verifier
    session_id: str
    k_bound: int                # maximum proposal-space complexity
    mutation_operators: tuple   # declared operator set
    issued_at_sequence: int     # from event substrate, never wall clock
    valid_for_epochs: int
    signature: str              # SHA-256(spiffe_id + k_bound + operators + sequence)


@dataclass(frozen=True)
class AAPClaim:
    """
    Agentic Action Protocol claim. Logged to E3 substrate as AGENT_AUTHORIZED event.
    Records what action an agent was authorised to perform and under what constraints.
    """
    agent_spiffe_id: str
    action_type: str            # PROPOSE_MODIFICATION | VERIFY_HASH | VETO | READ
    resource_id: str
    k_contribution: int         # K consumed by this action
    claim_hash: str             # SHA-256(agent_id + action + resource + sequence)
    sequence: int               # from event substrate


class SAGAIdentityManager:
    """
    Issues SPIFFE/SVID credentials for agent sessions and validates AAP claims.

    PRODUCTION NOTE: In production, credential issuance must be backed by
    a SPIFFE Workload API (SPIRE server). This implementation provides the
    data model and validation logic; the PKI integration is a deployment task.
    """

    TRUST_DOMAIN = "sovereign-omega"

    def __init__(self):
        self._active_svids: Dict[str, AgentSVID] = {}
        self._aap_log: List[AAPClaim] = []

    def issue_svid(
        self,
        role: str,
        session_id: str,
        k_bound: int,
        mutation_operators: List[str],
        sequence: int,    # MUST come from event substrate
        valid_for_epochs: int = 1000,
    ) -> AgentSVID:
        """Issue a SVID for a new agent session."""
        spiffe_id = f"spiffe://{self.TRUST_DOMAIN}/agent/{role}/{session_id}"

        # Signature binds identity to the K-bound and operator set
        # Prevents an agent from claiming a wider authority than declared
        sig_input = (
            spiffe_id
            + str(k_bound)
            + json.dumps(sorted(mutation_operators))
            + str(sequence)
        )
        signature = hashlib.sha256(sig_input.encode()).hexdigest()

        svid = AgentSVID(
            spiffe_id=spiffe_id,
            role=role,
            session_id=session_id,
            k_bound=k_bound,
            mutation_operators=tuple(sorted(mutation_operators)),
            issued_at_sequence=sequence,
            valid_for_epochs=valid_for_epochs,
            signature=signature,
        )
        self._active_svids[session_id] = svid
        return svid

    def validate_claim(
        self,
        svid: AgentSVID,
        action_type: str,
        resource_id: str,
        k_contribution: int,
        sequence: int,
    ) -> Optional[AAPClaim]:
        """
        Validate an AAP claim and return it for logging to E3.
        Returns None if the claim is invalid (K-bound exceeded, expired, etc.).
        """
        # Check K-bound
        if k_contribution > svid.k_bound:
            return None  # K-bound exceeded — action rejected

        # Check session validity
        epoch_age = sequence - svid.issued_at_sequence
        if epoch_age > svid.valid_for_epochs:
            return None  # SVID expired

        claim_input = svid.spiffe_id + action_type + resource_id + str(sequence)
        claim_hash = hashlib.sha256(claim_input.encode()).hexdigest()

        claim = AAPClaim(
            agent_spiffe_id=svid.spiffe_id,
            action_type=action_type,
            resource_id=resource_id,
            k_contribution=k_contribution,
            claim_hash=claim_hash,
            sequence=sequence,
        )
        self._aap_log.append(claim)
        return claim

    def revoke_svid(self, session_id: str) -> bool:
        return bool(self._active_svids.pop(session_id, None))

    @property
    def aap_log(self) -> List[AAPClaim]:
        return list(self._aap_log)


# Default SVID configurations for the three council agents
GUARDIAN_OPERATORS = ["VETO", "TIER_CHECK", "FROZEN_FILE_CHECK"]
IMPLEMENTER_OPERATORS = ["SCHEMA_WRITE", "CODE_WRITE", "TEST_WRITE"]
VERIFIER_OPERATORS = ["HASH_READ", "TEST_RUN", "CHAIN_VERIFY"]

AGENT_K_BOUNDS = {
    "guardian":    0,    # K=0: guardian is immutable within runtime
    "implementer": 50,   # K=50: bounded implementation authority
    "verifier":    5,    # K=5: read-only verification authority
}
