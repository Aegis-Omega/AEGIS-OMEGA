#!/usr/bin/env python3
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
docker = (ROOT / "sovereign-omega-v2" / "Dockerfile").read_text()
cloud = (ROOT / "sovereign-omega-v2" / "cloudbuild.yaml").read_text()
req = (ROOT / "sovereign-omega-v2" / "python" / "requirements.txt").read_text()
bridge = (ROOT / "sovereign-omega-v2" / "python" / "bridge.py").read_text()

required = [
    "COPY sovereign-omega-v2/python/requirements.txt ./python/requirements.txt",
    "COPY sovereign-omega-v2/python/ ./python/",
    "COPY harness/sdk/archive_runtime.py ./harness/sdk/archive_runtime.py",
    "COPY swarm_os/arc/dsl/ ./swarm_os/arc/dsl/",
    "COPY swarm_os/swarm/swarm_core.py ./swarm_os/swarm/swarm_core.py",
    "COPY swarm_os/swarm/config.py ./swarm_os/swarm/config.py",
    "COPY swarm_os/biology/cybernetic_core.py ./swarm_os/biology/cybernetic_core.py",
    "ENV PYTHONPATH=/app:/app/python",
]
missing = [item for item in required if item not in docker]
if missing:
    raise SystemExit("missing Docker image bindings: " + ", ".join(missing))

if "- sovereign-omega-v2/Dockerfile" not in cloud:
    raise SystemExit("cloudbuild missing explicit Dockerfile")
if not any(line.strip() == "- ." for line in cloud.splitlines()):
    raise SystemExit("cloudbuild is not rooted at repository context")
if any(line.strip() == "- sovereign-omega-v2/" for line in cloud.splitlines()):
    raise SystemExit("legacy narrow build context still active")
if "numpy>=" not in req:
    raise SystemExit("numpy missing from bridge runtime dependencies")

for forbidden in ("swarm_os/arc/data/", "swarm_os/benchmark/", "free-claude-code/"):
    if forbidden in docker:
        raise SystemExit("forbidden archive surface copied into image: " + forbidden)

post = bridge.split("    def do_POST(self):", 1)[1].split("    def do_GET(self):", 1)[0]
get = bridge.split("    def do_GET(self):", 1)[1].split("    def do_DELETE(self):", 1)[0]
if "/platform/archive/runtime" not in post:
    raise SystemExit("archive runtime POST compute route missing")
if "dispatch_archive_runtime_post" not in post:
    raise SystemExit("bounded POST dispatcher not called")
if "_platform_verify_api_key(api_key)" not in post:
    raise SystemExit("compute POST route lacks API-key verifier")
if "length > 4096" not in post:
    raise SystemExit("archive runtime body-size guard missing")
if "/platform/archive/runtime" not in get:
    raise SystemExit("archive runtime GET status route missing")
if "dispatch_archive_runtime_get" not in get:
    raise SystemExit("bounded GET status dispatcher not called")
if "Cache-Control" not in bridge or "no-store" not in bridge:
    raise SystemExit("archive runtime no-store response contract missing")

if "compute requires POST JSON" not in (ROOT / "sovereign-omega-v2" / "python" / "archive_runtime_api.py").read_text():
    raise SystemExit("GET-compute denial contract missing")

print("ARCHIVE_RUNTIME_BRIDGE_CONTRACT=PASS")
