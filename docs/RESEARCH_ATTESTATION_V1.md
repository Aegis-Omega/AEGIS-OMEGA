# AEGIS UWP-13 — Collector-Origin Attestation v1 (candidate)

**Status:** branch-only, read-only source intake; **NOT_ADMITTED** for production, autonomous browsing, scientific truth or task-quality promotion. Depends on PR #766 and issue #765.

## Threat model and repair

Previously two arbitrary JSON entries with `acquisition: connector_capture` and valid self-computed SHA-256 digests could yield `READY_FOR_INDEPENDENT_TEST`. The SHA-256 only authenticated *bytes against themselves*, not the reported acquisition event.

Now `scripts/research_attestation.py` supports a 32-byte HMAC-SHA256 key held outside the model/tool/task packet in a protected collector/verifier runtime. After the network request, the collector signs its entire canonical receipt (URL, hostname, chosen public IP, UTC captured_at, TLS peer certificate digest, content digests, bytes/excerpt, HTTP metadata, explicit NOT_VERIFIED claims), using a domain-separated message. The offline scout receives the signed capture in the source's `capture_receipt`, checks MAC in constant time using **externally configured trusted keys**, compares source URL/content/timestamp/hash/hostname to the receipt, checks freshness against an independently supplied or system UTC clock, and counts only these verified captures toward the **test-readiness** quorum.

**Without trusted key configuration, no input can achieve `READY_FOR_INDEPENDENT_TEST`.** The command-line packet is never allowed to name its own verification secret. An intentionally forged or re-labelled capture, wrong signer, wrong key, untrusted clock or unsigned claim remains `NEEDS_RESEARCH` or is rejected. A receipt using the right MAC means only **the holder of that local key approved these bytes**. It does **not** prove that the holder ran the claimed code or that the external site and its claims are genuine.

Reference model: [SLSA provenance — builder identity and protected trust boundaries](https://slsa.dev/spec/v1.0/provenance) and [SLSA verifying artifacts](https://github.com/slsa-framework/slsa/blob/main/spec/verifying-artifacts.md). A local shared-secret MAC is **not** a SLSA attestation, publisher-issued signature, transparency record, HSM, OIDC workload identity or independently reviewed signed provenance.

## Native local replay

```bash
python3 -m unittest discover -s scripts -p 'test_research*.py' -q
python3 scripts/research_benchmark.py --legacy-source /path/to/exact-prior-git-blob.py
```

The test suite includes 24 explicit capture-attestation cases plus the previous 86 source/collector/TLS/benchmark cases; total **110/110 LOCAL PASS** on Python 3.13.5 at exact GitHub blobs. Tests intentionally use the public test-only key `bytes(range(32))` and simulated transport. **NEVER deploy this key.**

To use a real key, a trusted non-model operator must generate 32 unpredictable bytes in a private owner-only regular file with mode 0600, never commit or transmit it, configure an allowlisted signer ID and inject it into a protected runner:

```bash
# Example command syntax, NOT executed against public websites or production:
python3 scripts/research_collector.py 'https://docs.example.org/public-page' \
  --allow-host docs.example.org --allow-network \
  --signing-key-file /secure/collector.key --signing-key-id operator-collector-1 \
  --output /tmp/signed_capture.json

python3 scripts/research_intelligence.py /tmp/research_packet_with_receipts.json \
  --trust-key-file /secure/collector.key --trust-key-id operator-collector-1
```

The collector output must be converted to the corresponding source with `research_collector.packet_source(snapshot, source_id)` before assembling the research packet. Without `--trust-key-file` in the second command, all source evidence is **untrusted** for readiness.

## Boundaries still open

1. The signing key and verifier must be in protected, isolated runtimes inaccessible to research agents; otherwise a malicious agent possessing the key can self-sign fake captures. Key rotation, secure distribution, auditable key provenance, peer review and key storage remain unimplemented.
2. No real public HTTPS smoke or live resolver egress was executed. TLS handshake checks used a local test CA and loopback server; resolver was simulated.
3. Clock checking uses local runtime UTC and rejects packet `as_of_utc` drift beyond five minutes; clock itself isn't notarized. MACs are replayable inside the freshness window; there is no unique immutable capture ledger.
4. `connector_capture` status is only an internal locally keyed evidence claim. Source content is untrusted and must never become agent system instructions. No statement of publisher identity, source truth, semantic relevance, causation or measured task improvement follows.
5. Native exact-head hosted CI, independent security audit, signed protected-main integration and controlled live runtime are still **NOT_VERIFIED**.

### Next admission criteria

Use a connector or isolated capture runner with workload identity and a trusted signing root, external capture test with DNS/IP/redirect adversaries, authenticated raw evidence storage, and signed trace/replay bound to repo SHA before the status can be promoted beyond a tested branch candidate.
