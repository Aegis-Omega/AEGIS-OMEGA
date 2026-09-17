import copy
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location(
    "validate_rh_audit_bindings", ROOT / "scripts/validate-rh-audit.py"
)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError("cannot load RH audit validator")
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class RhAuditBindingTests(unittest.TestCase):
    def setUp(self):
        self.dag_data = json.loads(MODULE.DAG.read_text())
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.dag = Path(temporary.name) / "RH_PROOF_OBLIGATION_DAG_V1.json"
        self.patch = patch.object(MODULE, "DAG", self.dag)
        self.patch.start()
        self.addCleanup(self.patch.stop)

    def validate_mutation(self, mutate):
        dag = copy.deepcopy(self.dag_data)
        mutate(dag)
        self.dag.write_text(json.dumps(dag))
        with self.assertRaises(ValueError):
            MODULE.validate_dag()

    def test_audit_base_and_node_heads_are_bound(self):
        cases = {
            "missing audit base": lambda d: d.pop("audit_base"),
            "invalid audit base": lambda d: d.update(audit_base="not-a-head"),
            "mismatched node head": lambda d: d["nodes"][0].update(exact_head="0" * 40),
        }
        for name, mutate in cases.items():
            with self.subTest(case=name):
                self.validate_mutation(mutate)

    def test_frontier_obligation_names_a_dag_node(self):
        cases = {
            "missing frontier obligation": lambda d: d.pop("frontier_obligation"),
            "unknown frontier obligation": lambda d: d.update(frontier_obligation="RH_D_UNKNOWN"),
        }
        for name, mutate in cases.items():
            with self.subTest(case=name):
                self.validate_mutation(mutate)


if __name__ == "__main__":
    unittest.main()
