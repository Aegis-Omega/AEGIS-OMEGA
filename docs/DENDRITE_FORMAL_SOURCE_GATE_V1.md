# AEGIS formal source gate v1: exact-HEAD local verification

Scope: **informational source-byte validation**, not mathematical proof
verification, sender authentication, deployment, or agent execution.

This gate extends the existing formal source producer in
[formal-conjectures PR #82](https://github.com/tarikskalic33/formal-conjectures/pull/82)
and the local authenticated dendrite relay in
[AEGIS PR #773](https://github.com/Aegis-Omega/AEGIS-OMEGA/pull/773).
It does not introduce a new coordinator, kernel, message bus or authority path.

## Why it exists

HMAC-SHA256 proves that a holder of the shared relay key sealed the local
packet. It does **not** prove that the packet corresponds to a real Git source
file. The gate prevents a packet with invented source bytes from being accepted
as an exact-HEAD local file match.

## Preconditions

- A separate trusted local checkout of `tarikskalic33/formal-conjectures`.
- Local `HEAD` exactly matches the `source_head` carried by the producer's
  JSON. An old packet must be read against its **original** checkout head;
  advancing the checkout intentionally causes a denial.
- `remote.origin.url` in the local repository configuration must be an allowed
  GitHub URL for `tarikskalic33/formal-conjectures`. This checks only locally
  configured metadata; it does **not** independently authenticate GitHub.
- A repository-relative, allowlisted `.lean` path, normally
  `FormalConjectures/Millennium/RiemannHypothesis.lean`.
- The path must resolve to an ordinary `100644` Git blob at HEAD, <=1 MiB.
- Existing strict six-field producer JSON, <=8192 bytes.
- Optional relay publishing/reading requires the existing private local spool
  and operator-controlled HMAC key as documented in
  `docs/DENDRITE_LOCAL_TRANSPORT_V1.md`. Do not commit secrets.

## Operator reproduction

In the exact-head formal-conjectures checkout:

```sh
python3 scripts/export_aegis_dendrite.py --repo . \
  > /tmp/aegis_formal_source.json
```

In the AEGIS-OMEGA PR #773 checkout:

```sh
# 1. Verify committed source and excerpt before any mailbox write.
python3 -m agents.dendrite_formal_gate verify \
  /tmp/aegis_formal_source.json \
  --repo /absolute/path/to/formal-conjectures

# 2. Explicitly publish authenticated LOCAL informational packets.
python3 -m agents.dendrite_formal_gate publish \
  /tmp/aegis_formal_source.json \
  --repo /absolute/path/to/formal-conjectures \
  --root "$HOME/.aegis-dendrite-inbox" \
  --key-file "$HOME/.config/aegis/dendrite-relay.key" \
  --key-id operator_relay

# 3. Another process independently checks BOTH HMAC and source bytes.
python3 -m agents.dendrite_formal_gate read engineering \
  --repo /absolute/path/to/formal-conjectures \
  --root "$HOME/.aegis-dendrite-inbox" \
  --key-file "$HOME/.config/aegis/dendrite-relay.key" \
  --key-id operator_relay
```

## Fail-closed checks

Missing/unknown fields, path traversal, symlinks or nonregular Git tree entries,
source length/digest mismatch, incorrect HEAD, unexpected local remote URL,
altered excerpt, missing/mismatching HMAC, and quarantine spill into unauthorized
recipients are denied.

The receiver reconstructs source data from the verified inert envelope. Nothing
from the packet is used as a subprocess command, tool instruction, or authority
credential. Subprocess calls are fixed `git` argument arrays with 15-second
timeouts; the file-size check runs before loading source bytes.

## Boundaries

- Status `LOCAL_GIT_HEAD_SOURCE_BYTES_MATCHED` is narrower than verified
  GitHub authorship, trusted commit signature, Lean compilation, theorem proof,
  scientific claim validation or canonical operational admission.
- A maliciously manipulated local Git clone, including its remote URL metadata,
  remains outside this gate's trust guarantees. Offline cryptographic publisher
  identity is not established.
- Hashes are consistency checks, HMAC covers **local relay** identity only.
- No network transport, remote agent delivery, automatic execution or payments.
- Local producer/consumer require access to the exact source checkout. The gate
  cannot validate arbitrary remote repos merely from a claimed SHA.
- No change to the official RH theorem or proof body.
- Native CI may still be blocked before job execution; zero-step failures are
  **not** accepted as code-pass evidence.

## Test

```sh
python3 -m unittest agents.tests.test_dendrite_formal_gate -v
```

Sixteen new adversarial tests were executed locally, alongside the prior 98
dendrite tests. GitHub commit and blob identity must be rebound after every
new branch change; independently executed exact-head checks remain required
before PR admission.

The added forged-relay test deliberately signs an altered Lean excerpt using
an otherwise valid HMAC key: the strict reader still denies it because local
Git source bytes do not match. A second test confirms a formerly matching
packet is denied after the checkout moves to a different exact HEAD.
