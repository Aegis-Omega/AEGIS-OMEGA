#!/usr/bin/env python3
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
app=(ROOT/"tactical/src/App.tsx").read_text()
hook=(ROOT/"tactical/src/hooks/useArchiveRuntime.ts").read_text()
panel=(ROOT/"tactical/src/components/ArchiveRuntimePanel.tsx").read_text()

required_hook=[
    "/platform/archive/runtime/status",
    "/platform/archive/runtime/arc?",
    "'x-api-key': apiKey",
    "JSON.stringify([[1, 2], [3, 4]])",
    "JSON.stringify([[2, 4], [1, 3]])",
    "authority_effect !== 'NONE'",
]
missing=[item for item in required_hook if item not in hook]
if missing:
    raise SystemExit("missing archive runtime consumer contract: "+", ".join(missing))

for forbidden in ("method: 'POST'", "method: 'PUT'", "method: 'DELETE'"):
    if forbidden in hook:
        raise SystemExit("mutation method present in archive runtime hook: "+forbidden)

if "ArchiveRuntimePanel" not in app or "useArchiveRuntime(apiKey)" not in app:
    raise SystemExit("ArchiveRuntimePanel not wired into Tactical App")

if app.index("<ArchiveRuntimePanel") < app.index("<BridgeStatus"):
    raise SystemExit("archive runtime panel must follow core bridge telemetry")

for token in ("AUTHORITY_EFFECT", "NETWORK_AUTHORITY", "PERSISTENT_STATE", "VERIFY_ROT90_2X2"):
    if token not in panel:
        raise SystemExit("panel missing bounded evidence token: "+token)

print("TACTICAL_ARCHIVE_RUNTIME_CONTRACT=PASS")
