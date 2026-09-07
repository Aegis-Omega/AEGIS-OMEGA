import importlib


def test_qm_red_001_scheduler_production_module_exists():
    module = importlib.import_module("agents.quantummanifold.scheduler")
    assert module is not None
