from aegis_interface.consensus import PHI_QUORUM, reach_consensus
from aegis_interface.ir import lower
from aegis_interface.parser import parse

V1 = """
variant Tier { bronze, silver, gold }
record Snap { id: string, tier: Tier, note: option<string> }
"""

# Backward-compatible proposal: add an optional field. All obligations hold vs V1.
PROPOSAL = """
variant Tier { bronze, silver, gold }
record Snap { id: string, tier: Tier, note: option<string>, extra: option<u32> }
"""

# A divergent agent whose local schema makes the proposal a retype (breaking).
DIVERGENT = """
variant Tier { bronze, silver, gold }
record Snap { id: string, tier: Tier, note: option<string>, extra: string }
"""


def ir(src):
    return lower(parse(src))


def test_all_agents_aligned_commits():
    agents = [("a", ir(V1)), ("b", ir(V1)), ("c", ir(V1))]
    result = reach_consensus(agents, ir(PROPOSAL))
    assert result.committed
    assert result.ratio == 1.0


def test_consensus_is_over_obligations_not_votes():
    # 'extra' is `string` locally but `option<u32>` in the proposal -> retype for c,
    # violating TypeSafetyPreserved + SerializationInvariant (2 of 4 obligations).
    agents = [("a", ir(V1)), ("b", ir(V1)), ("c", ir(DIVERGENT))]
    result = reach_consensus(agents, ir(PROPOSAL))
    # a,b: 4/4 each = 8; c: 2/4 -> total 10/12
    assert result.verified == 10
    assert result.total == 12
    assert result.committed  # 0.833 >= 1/phi


def test_critical_obligation_failure_can_block():
    # Single agent for whom the proposal is breaking: 2/4 obligations = 0.5 < 1/phi.
    agents = [("c", ir(DIVERGENT))]
    result = reach_consensus(agents, ir(PROPOSAL))
    assert result.ratio == 0.5
    assert not result.committed


def test_threshold_is_phi():
    agents = [("a", ir(V1))]
    result = reach_consensus(agents, ir(PROPOSAL))
    assert result.threshold == PHI_QUORUM
