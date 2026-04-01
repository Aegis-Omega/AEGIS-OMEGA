#!/usr/bin/env python3
"""
SWARM OS — Endpoint Smoke Test
Starts the server, tests all endpoints, then stops.
Exit code 0 = all tests passed.
"""
import subprocess
import sys
import time
import json
import urllib.request
import urllib.error
import os

BASE = "http://localhost:8000"
SERVER_PROC = None

def start_server():
    global SERVER_PROC
    root = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(root)  # parent of swarm/
    SERVER_PROC = subprocess.Popen(
        [sys.executable, os.path.join(root, "server.py")],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        cwd=project_root
    )
    # Wait for server to be ready
    for i in range(20):
        time.sleep(1)
        if SERVER_PROC.poll() is not None:
            # Server crashed
            out, err = SERVER_PROC.communicate()
            print(f"SERVER CRASHED (code {SERVER_PROC.returncode})")
            print(f"STDOUT: {out.decode()}")
            print(f"STDERR: {err.decode()}")
            return False
        try:
            urllib.request.urlopen(f"{BASE}/health", timeout=2)
            return True
        except Exception:
            pass
    return False

def stop_server():
    if SERVER_PROC:
        SERVER_PROC.terminate()
        SERVER_PROC.wait(timeout=5)

def get(path):
    req = urllib.request.Request(f"{BASE}{path}")
    with urllib.request.urlopen(req, timeout=10) as r:
        return r.status, json.loads(r.read().decode())

def get_html(path):
    req = urllib.request.Request(f"{BASE}{path}")
    with urllib.request.urlopen(req, timeout=10) as r:
        return r.status, r.read().decode()

def post(path, data):
    body = json.dumps(data).encode()
    req = urllib.request.Request(
        f"{BASE}{path}", data=body,
        headers={"Content-Type": "application/json"}
    )
    with urllib.request.urlopen(req, timeout=10) as r:
        return r.status, json.loads(r.read().decode())

def test(label, fn):
    try:
        fn()
        print(f"  ✓ {label}")
        return True
    except Exception as e:
        print(f"  ✗ {label} — {e}")
        return False

def run_tests():
    results = []

    # GET /
    def t_canvas():
        status, html = get_html("/")
        assert status == 200, f"status={status}"
        assert "Quantum Singularity" in html, "Missing title"
        assert "d3.min.js" in html, "Missing D3.js"
    results.append(test("GET /  → HTML canvas with D3.js", t_canvas))

    # GET /health
    def t_health():
        status, data = get("/health")
        assert status == 200
        assert "status" in data
    results.append(test("GET /health → status field present", t_health))

    # GET /graph
    def t_graph():
        status, data = get("/graph")
        assert status == 200
        assert "hyperedges" in data or "node_count" in data
    results.append(test("GET /graph → hyperedges or node_count", t_graph))

    # GET /spectral
    def t_spectral():
        status, data = get("/spectral")
        assert status == 200
        assert "lambda1" in data or "rem_cycles" in data
    results.append(test("GET /spectral → lambda1 or rem_cycles", t_spectral))

    # POST /ingest
    def t_ingest():
        triplet = {
            "subject": "test_node_a",
            "relation": "verifies",
            "object": "test_node_b",
            "context": ["smoke_test"]
        }
        status, data = post("/ingest", triplet)
        assert status == 200
        assert "crystallized" in str(data.get("status", "")) or "nodes" in data or "ok" in data
    results.append(test("POST /ingest → crystallize triplet", t_ingest))

    # POST /rem
    def t_rem():
        status, data = post("/rem", {})
        assert status == 200
    results.append(test("POST /rem → trigger REM cycle", t_rem))

    # GET /graph after ingest
    def t_graph_after():
        status, data = get("/graph")
        assert status == 200
        nodes = set()
        for he in data.get("hyperedges", []):
            for n in he.get("nodes", []):
                nodes.add(n)
        assert "test_node_a" in nodes or data.get("node_count", 0) > 0
    results.append(test("GET /graph → ingested nodes visible", t_graph_after))

    return all(results)

if __name__ == "__main__":
    print("\n╔════════════════════════════════════════╗")
    print("║  SWARM OS — Endpoint Smoke Test        ║")
    print("╚════════════════════════════════════════╝\n")

    print("Starting server...")
    if not start_server():
        print("ERROR: Server failed to start within 20s")
        stop_server()
        sys.exit(1)

    print(f"Server ready at {BASE}\n")

    try:
        ok = run_tests()
    finally:
        print("\nStopping server...")
        stop_server()

    print()
    if ok:
        print("═══ ALL TESTS PASSED ═══")
        sys.exit(0)
    else:
        print("═══ SOME TESTS FAILED ═══")
        sys.exit(1)
