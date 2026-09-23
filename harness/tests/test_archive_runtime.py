from pathlib import Path
import sys

import pytest

from harness.sdk.archive_runtime import ArchiveRuntimeAdapter, ArchiveRuntimeError

ROOT = Path(__file__).resolve().parents[2]


def test_arc_transform_executes_recovered_rot90_without_authority():
    result = ArchiveRuntimeAdapter(ROOT).arc_transform(operation_id=1, grid=[[1, 2], [3, 4]])
    assert result["operation"] == "ROT90"
    assert result["output"] == [[2, 4], [1, 3]]
    assert result["authority_effect"] == "NONE"


def test_swarm_observation_is_ephemeral_and_audited():
    result = ArchiveRuntimeAdapter(ROOT).swarm_observe(subject="alpha", relation="relates_to", obj="beta")
    assert result["edge_id_present"] is True
    assert result["node_count"] == 3
    assert result["edge_count"] == 1
    assert result["audit_entry_count"] >= 3
    assert result["persistent_state"] is False
    assert result["network_access"] is False
    assert result["authority_effect"] == "NONE"


def test_biology_probe_executes_bounded_path():
    result = ArchiveRuntimeAdapter(ROOT).biology_probe(stimulus="normal input")
    assert result["sensory_output"] == "normal input"
    assert result["entropy"] > 3.0
    assert result["pathogen_detected"] is False
    assert result["authority_effect"] == "NONE"


def test_adapter_fails_closed_when_recovered_runtime_missing(tmp_path):
    with pytest.raises(ArchiveRuntimeError, match="RECOVERED_RUNTIME_MISSING"):
        ArchiveRuntimeAdapter(tmp_path)


def test_arc_rejects_malformed_grid():
    adapter = ArchiveRuntimeAdapter(ROOT)
    with pytest.raises(ArchiveRuntimeError, match="ARC_GRID_NON_RECTANGULAR"):
        adapter.arc_transform(operation_id=0, grid=[[1, 2], [3]])


def test_adapter_does_not_mutate_sys_path():
    before = tuple(sys.path)
    adapter = ArchiveRuntimeAdapter(ROOT)
    adapter.arc_transform(operation_id=1, grid=[[1, 2], [3, 4]])
    adapter.swarm_observe(subject="alpha", relation="relates_to", obj="beta")
    adapter.biology_probe(stimulus="normal input")
    assert tuple(sys.path) == before
