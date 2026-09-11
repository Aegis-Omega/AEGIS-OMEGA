from pathlib import Path
from scripts.audit_frontier import expected_frontier, forbidden_manual_paths

ROOT = Path(__file__).resolve().parents[1]

def test_frontier_pin_is_current_zero_counting_exact_head():
    cfg = expected_frontier(ROOT)
    assert cfg["branch"] == "proof/rh-zero-counting-bound-v1"
    assert cfg["sha"] == "c85a58ca753e5d99fc9f117e0dc481e1f2cf0bde"

def test_claude_manifest_is_never_a_manual_writer_target():
    assert ".claude.json" in forbidden_manual_paths()
