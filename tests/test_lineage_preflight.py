import json, subprocess, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "lineage_preflight.py"

def run(*args):
    return subprocess.run([sys.executable, str(SCRIPT), *args], cwd=ROOT, text=True, capture_output=True, check=False)

def test_known_collision_fails_closed():
    r = run("--proposed-name","PAPO","--semantic-role","new component")
    assert r.returncode == 3
    assert "LINEAGE_CONFLICT_REVIEW_REQUIRED" in r.stderr

def test_known_collision_requires_ack():
    r = run("--proposed-name","PAPO","--semantic-role","reviewed successor","--acknowledge-conflict")
    assert r.returncode == 0
    p = json.loads(r.stdout)
    assert p["known_conflicts"] >= 1 and p["conflicts_acknowledged"] is True

def test_p0_vcg_cannot_be_acknowledged_away():
    r = run("--proposed-name","VCG","--semantic-role","new metric","--acknowledge-conflict")
    assert r.returncode == 5
    assert "P0_LINEAGE_CONFLICT_UNRESOLVED" in r.stderr
    assert "VCG_SEMANTIC_OVERLOAD" in r.stderr

def test_p0_autopoiesis_cannot_be_acknowledged_away():
    r = run("--proposed-name","autopoiesis","--semantic-role","agent instruction","--acknowledge-conflict")
    assert r.returncode == 5
    assert "P0_LINEAGE_CONFLICT_UNRESOLVED" in r.stderr
    assert "AUTOPOIESIS_TIER_CONFLICT" in r.stderr

def test_incomplete_artifact_discovery_blocks():
    r = run("--proposed-name","fresh-component","--semantic-role","new role","--artifact-scan-verdict","INCOMPLETE")
    assert r.returncode == 4
    assert "ARTIFACT_DISCOVERY_INCOMPLETE" in r.stderr

def test_fresh_name_passes_collision_gate_only():
    r = run("--proposed-name","lineage-fixture-noncollision","--semantic-role","ci fixture","--artifact-scan-verdict","NO_MATCHES_IN_COMPLETE_REPO_SCAN")
    assert r.returncode == 0
    p = json.loads(r.stdout)
    assert p["known_conflicts"] == 0
    assert "active PR lineage" in p["next_required_evidence"]
