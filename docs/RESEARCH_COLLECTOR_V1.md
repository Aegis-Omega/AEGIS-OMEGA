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

Maximum response: 131072 bytes; excerpt: 16000 UTF-8 bytes; socket timeout: 8 seconds per I/O stage. There is **no hard end-to-end deadline**, which must be supplied by the trusted runner before general release. Unsupported redirects, media types, compression, encodings, oversize responses or egress failure remain denied, not retried with unsafe fallbacks.

## Evidence limits

A successful HTTPS/TLS connection and `full_body_sha256` support **integrity of locally observed bytes**, not publisher identity or accuracy of its scientific claims. Local timestamps aren't notarized. Source text remains **untrusted data**, never tool instructions. Outputs explicitly mark `publisher_identity=NOT_INDEPENDENTLY_AUTHENTICATED`, `claim_truth=NOT_VERIFIED`, `authority_effect=NONE`.

Still open: real live capture on trusted egress, strict wall-clock deadline, attested collector identity, signed snapshots, source-use/throttling policy, URL fuzzing and independent review, exact-head hosted CI and protected-main signing/admission. No continuous scheduling, training ingestion or autonomous promotion is claimed.