import importlib

import pytest


def _graph_module():
    return importlib.import_module("agents.quantummanifold.graph")


def _base_graph():
    return {
        "nodes": [
            {"id": "claim-a", "type": "CLAIM", "content_digest": "a" * 64},
            {"id": "obligation-b", "type": "OBLIGATION", "content_digest": "b" * 64},
        ],
        "edges": [
            {"source": "claim-a", "target": "obligation-b", "type": "DEPENDS_ON"},
        ],
    }


def test_valid_typed_dag_is_accepted():
    _graph_module().validate_typed_dag(_base_graph())


def test_qm_red_005_unknown_node_type_fails_closed():
    graph = _base_graph()
    graph["nodes"][0]["type"] = "UNKNOWN"
    with pytest.raises(ValueError, match="^UNKNOWN_NODE_TYPE$"):
        _graph_module().validate_typed_dag(graph)


def test_qm_red_006_unknown_edge_type_fails_closed():
    graph = _base_graph()
    graph["edges"][0]["type"] = "UNKNOWN"
    with pytest.raises(ValueError, match="^UNKNOWN_EDGE_TYPE$"):
        _graph_module().validate_typed_dag(graph)


def test_qm_red_007_cycle_fails_closed():
    graph = _base_graph()
    graph["edges"].append(
        {"source": "obligation-b", "target": "claim-a", "type": "BLOCKS"}
    )
    with pytest.raises(ValueError, match="^GRAPH_CYCLE_DETECTED$"):
        _graph_module().validate_typed_dag(graph)


def test_qm_red_008_node_id_collision_with_nonidentical_content_fails_closed():
    graph = _base_graph()
    graph["nodes"].append(
        {"id": "claim-a", "type": "CLAIM", "content_digest": "c" * 64}
    )
    with pytest.raises(ValueError, match="^NODE_ID_COLLISION$"):
        _graph_module().validate_typed_dag(graph)


def test_qm_red_009_dangling_edge_fails_closed():
    graph = _base_graph()
    graph["edges"].append(
        {"source": "claim-a", "target": "missing-node", "type": "SUPPORTED_BY"}
    )
    with pytest.raises(ValueError, match="^DANGLING_EDGE$"):
        _graph_module().validate_typed_dag(graph)
