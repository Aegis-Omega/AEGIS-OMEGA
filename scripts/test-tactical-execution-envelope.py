#!/usr/bin/env python3
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
hook=(ROOT/"tactical/src/hooks/useExecution.ts").read_text()
parser=(ROOT/"tactical/src/lib/platformEnvelope.ts").read_text()

required_hook=[
  "parsePlatformEnvelope<ExecutionInitResult>(body)",
  "envelope.execution_id !== envelope.data.execution_id",
  "executionId = envelope.data.execution_id",
  "streamUrl   = envelope.data.stream_url",
  "PLATFORM_STREAM_URL_MISSING",
]
missing=[x for x in required_hook if x not in hook]
if missing:
  raise SystemExit("execution envelope fix missing: "+", ".join(missing))

for forbidden in (
  "const data = await res.json() as { execution_id: string; stream_url: string }",
  "executionId = data.execution_id",
  "streamUrl   = data.stream_url",
):
  if forbidden in hook:
    raise SystemExit("legacy raw execution-init parsing remains: "+forbidden)

required_parser=[
  "PLATFORM_CONTRACT_VERSION_MISMATCH",
  "PLATFORM_EXECUTION_ID_INVALID",
  "PLATFORM_TIMESTAMP_INVALID",
  "PLATFORM_REPLAY_FLAG_INVALID",
  "PLATFORM_DATA_MISSING",
]
for token in required_parser:
  if token not in parser:
    raise SystemExit("platform envelope parser missing "+token)

print("TACTICAL_EXECUTION_ENVELOPE_CONTRACT=PASS")
