# AEGIS UWP-13 — Safe HTTPS Research Collector (candidate)

**Issue:** #765 · **PR:** #766 (draft) · **Authority:** NONE · **Status:** NOT_ADMITTED.

This extends the existing `scripts/research_intelligence.py` intake without introducing a new dispatcher. It is a bounded, opt-in public-source collector; **not** a 24/7 browsing agent, publisher-authentication oracle, or model training service.

## Reference engineering

- OWASP SSRF guidance: https://cheatsheetseries.owasp.org/cheatsheets/Server_Side_Request_Forgery_Prevention_Cheat_Sheet.html
- MCP 2026-07-28 security: https://github.com/modelcontextprotocol/modelcontextprotocol/blob/main/docs/docs/2026-07-28/tutorials/security/security_best_practices.mdx

Applied measures: exact HTTPS host allowlist; reject userinfo, ports, query tokens, fragments, IP literal targets, and private/mapped/mixed DNS results. Check **every** resolved IP, then connect to one validated **numeric IP** with TLS SNI and hostname verification still bound to the original host. No secondary hostname resolution, environment proxies, automatic redirects, cookies, auth headers or script execution.

## Offline tests

```sh
python3 -m unittest discover -s scripts -p 'test_research_collector.py' -v
```

The new suite has **33 native stdlib test methods** using an injected fake DNS resolver and network transport. It includes URL failures, DNS rebinding preconditions, redirect failures, body limits, forged metadata, UTF-8 failures and output contract cases. **No public live HTTPS request was executed during the replay.**

## Opt-in capture

```sh
python3 scripts/research_collector.py \
  'https://docs.example.org/public-article' \
  --allow-host docs.example.org --allow-network \
  --output /tmp/aegis-research-capture.json
```

No network without `--allow-network`. One URL per invocation. Result is JSON and can be converted into the existing offline scout source entry via `packet_source(capture, source_id)`. File output is local, explicitly named, and uses exclusive create; no write to production.

Maximum response: 131072 bytes; excerpt: 16000 UTF-8 bytes; socket timeout: 8 seconds per I/O stage. The **public CLI** now supervises DNS/TLS/HTTP acquisition in a killable, isolated Python subprocess under a total **worker runtime deadline** (default 20 seconds; configurable 1–120). Direct programmatic `acquire()` remains *unbounded* and must be invoked only by a separately supervised trusted runner. OS process creation itself is not a strict preemptible deadline, and output publication by the parent occurs after worker completion. Unsupported redirects, media types, compression, encodings, oversize responses or egress failure remain denied, not retried with unsafe fallbacks.

## Evidence limits

A successful HTTPS/TLS connection and `full_body_sha256` support **integrity of locally observed bytes**, not publisher identity or accuracy of its scientific claims. Local timestamps aren't notarized. Source text remains **untrusted data**, never tool instructions. Outputs explicitly mark `publisher_identity=NOT_INDEPENDENTLY_AUTHENTICATED`, `claim_truth=NOT_VERIFIED`, `authority_effect=NONE`.

Still open: real live capture on trusted egress, strict wall-clock deadline, attested collector identity, signed snapshots, source-use/throttling policy, URL fuzzing and independent review, exact-head hosted CI and protected-main signing/admission. No continuous scheduling, training ingestion or autonomous promotion is claimed.
## HTTP message framing integrity (2026-10-11)

A targeted regression exposed **a real prior false capture**: an HTTP/1.1 server advertising `Content-Length: 99` could close its TLS connection after only 5 bytes; the collector previously hashed and reported those five bytes as a successfully retrieved complete snapshot. In mock-framing tests, contradictory `Content-Length` and `Transfer-Encoding` metadata could also be accepted.

The collector now distinguishes HTTP framing **before any capture is issued or signed**:

- For an explicit `Content-Length`, require the exact decoded bytes received to match the announced length. Premature EOF is denied as `INCOMPLETE_RESPONSE_BODY`; contradictory mock transport length is denied as `CONTENT_LENGTH_MISMATCH`.
- Reject simultaneous `Content-Length` and `Transfer-Encoding` as `AMBIGUOUS_TRANSFER_FRAMING`, and reject unsupported transfer codings. `chunked` is accepted only where Python's `http.client.HTTPResponse` has actually enabled chunked decoding.
- Continue to reject Content-Encoding compression, unsupported content types, redirects, malformed lengths, zero-byte bodies, and responses over 128 KiB.
- Real localhost TLS integration tests verify that a truncated body is denied and a valid chunked body decodes successfully. These use a temporary test CA, **not** an external website.

Exact-head local Python 3.13.5 full replay: **177/177 tests PASS**. The eight additional HTTP-framing unit tests first showed **5 distinct failures** on the previous code; after the patch all eight passed, alongside two new real TLS integration tests. Local full logs and source digests are in the standalone replay archive.

**Not resolved by this patch:** DNS resolution, TLS handshake and slowly delivered headers/bodies may still lack a reliable **end-to-end wall-clock deadline** despite socket-level timeouts; use a separate trusted process timeout before production deployment. A digest does not independently authenticate publisher ownership, claim truth or actual collector-runner integrity. Hosted CI, independent security review and protected-main admission remain separate blockers.

## Supervised CLI worker (2026-10-11)

A real defect remained after the HTTP-framing fix: Python `http.client` socket timeouts cover individual blocking operations, **not elapsed time across DNS, handshake, headers and a slow-drip response**. A peer that sends small updates faster than each socket timeout can keep acquisition alive indefinitely (see Python issue [29422](https://bugs.python.org/issue29422) and [http.client documentation](https://docs.python.org/3/library/http.client.html)).

**Implementation**: The normal CLI always validates URL, host allowlist, signing context and deadline **before** launching a subprocess. Only the child executes DNS/TLS/HTTP and reads an externally protected signing key if configured. The parent invokes a fixed Python `-I` bootstrap with no shell, strips untrusted inherited `PYTHONPATH`, `SSL_CERT_FILE` and proxy environment entries, and calls `subprocess.run(..., timeout=...) `. On a timeout Python kills and reaps its direct child; the parent discards all partial stdout and returns `TOTAL_DEADLINE_EXCEEDED`. No `--output` is forwarded to the child: after a successful exit the parent validates the complete worker JSON and source/hostname coherence before writing its own explicitly named output file. A user-facing unbudgeted `--_capture-worker` option was explicitly **not** introduced.

CLI example (one explicitly authorized public host; **not actually fetched in this replay**):

```sh
python3 scripts/research_collector.py 'https://docs.example.org/public' \
  --allow-network --allow-host docs.example.org --deadline-seconds 20 \
  --output /tmp/research-capture.json
```

**Native local results**: Python 3.13.5, `PYTHONWARNINGS=error::ResourceWarning python3 -m unittest discover -s scripts -p 'test_research*.py' -q`: **193/193 PASS** (177 prior + 16 new). A real OS child sleeping beyond one second was terminated; a second child emitted a partial `stdout` prefix then stalled and was also terminated; both yielded `TOTAL_DEADLINE_EXCEEDED` rather than evidence. Other regressions cover zero output file on deadline, malformed/nonzero child output rejection, correct parent publication after validation, deny-before-spawn on host mismatch, sanitized Python/TLS environment, invalid budget ranges and no direct unbudgeted CLI worker flag.

**Limits**: This is a timeout for the subprocess worker after process creation; it is **not** a mathematically strict deadline for uninterruptible operating-system process creation, parent-side output writes, or clients calling `acquire()` directly. It is not evidence of a live external website request, a protected process supervisor resistant to compromised same-UID code, external publisher authenticity or scientific claim truth. Independent public HTTPS smoke, isolated signer/verifier, hosted CI and review remain open.

## Atomic publication of completed capture evidence (2026-10-11)

**Reproduced previous bug:** after HTTPS worker completion, the public CLI opened its final `--output` file directly, and an injected disk-write failure left an observable **partial, invalid JSON evidence artifact** at the final path. Completing the HTTPS handshake and integrity digest is not sufficient if durable output publication can produce half a receipt.

**Smallest fix:** the supervisor now stages a complete UTF-8 JSON receipt as a mode-0600 temporary file in the destination directory, flushes and fsyncs it, and exclusively publishes it with `os.link(staging, destination)`. An existing destination, including a symlink, is **never overwritten**. Failed staging, fsync or link leaves no final receipt and removes the temporary file. A POSIX directory fsync follows the atomic link; this is a best-effort filesystem durability step, **not** a proven power-loss guarantee across all kernels, storage controllers or file systems. If hard links are unsupported, publication fails closed without silently falling back to non-atomic copying.

**Independent local replay:** Python 3 stdlib, `PYTHONWARNINGS=error::ResourceWarning python3 -m unittest discover -s scripts -p 'test_research*.py' -v` → **201/201 PASS** (193 earlier + 8 new atomic-publication regressions). Negative tests simulate a disk-write failure after nine bytes, file sync failure, link failure, an existing final artifact and a malicious final symlink. A 12-contender thread race produced **one exclusive winner**, and an output failure is returned as `OUTPUT_PUBLICATION_FAILED` (CLI exit 2). Original failing code's disk-failure reproduction left `{"auth...` at the final path; repaired code leaves no published artifact. All output publication is still **local** and operator-selected; no production writes.

**Limitations:** Hard-link atomicity is a local filesystem property, not a distributed transaction, a trusted publisher signature, or crash-proof remote replication. POSIX directory sync does not guarantee storage-device durability; a failure *after* the final link may leave a **complete** file with uncertain acknowledgment. An attacker with write permission to the entire output directory can still delete or replace published entries. Trusted runner isolation, immutable evidentiary store, public Internet smoke, signed/protected admission and hosted CI remain open. Relevant rationale: [atomicwrites design and fsync caveats](https://python-atomicwrites.readthedocs.io/en/stable/) and [Python os.link documentation](https://docs.python.org/3/library/os.html#os.link).
