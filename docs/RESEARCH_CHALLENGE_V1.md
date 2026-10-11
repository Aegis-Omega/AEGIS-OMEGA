# UWP-13 — Verifier-issued source challenge (draft candidate)

**Issue #765 · PR #766 · parent #734 / benchmark #757.** This is a candidate local evidence protocol, **not** a live production agent, permission grant, independent web capture witness, or trusted remote attestation.

## Falsified gap

Existing bound HMAC v2 + single-use SQLite rejects a replayed *receipt fingerprint*, but by itself supplies no trustworthy challenge stating that a purported capture followed a verifier request. The supplier might sign an arbitrarily authored capture after the fact. A verifier-chosen unpredictable nonce limits reuse of detached endorsements, but **still does not prove that HTTP I/O occurred** (OWASP execution-evidence guidance).

## Three isolated operations

1. `issue_challenge(...)` — called only by an independently protected verifier. Generate `secrets.token_hex(32)` (256-bit unpredictable value) and persist **only its SHA-256**, the exact task, repo head and allowed source IDs, issuance time and expiry in the **existing owner-protected local SQLite ledger**. Expiry is at most 300 seconds. Requires an explicit existing private ledger directory.
2. `endorse_capture(...)` — caller holding the existing HMAC key verifies a signed v2 source capture and signs a **domain-separated response** binding the verifier nonce, capture-receipt SHA-256, exact task ID, repo commit SHA, source ID and signer key ID. This operation is not an independent observer and can be forged by a compromised key holder.
3. `admit_challenged_once(...)` — uses an externally supplied trust key and clock to validate the existing offline research packet, then within a **single `BEGIN IMMEDIATE` transaction** requires that the nonce exists in the same ledger, task/head/all cited IDs match its stored issuance record, is unexpired and unconsumed, every signed capture reports a time at or after issuance, every response HMAC verifies, and no complete capture fingerprint has ever been consumed. Consume **nonce and all receipt fingerprints atomically**. Any failure rolls back every mutation.

`research_intelligence.evaluate()` stays pure/read-only. The prior `admit_once()` still exists as a **weaker structural-only** path and MUST NOT be treated as evidence of a verifier challenge. Nothing silently promotes its output to production authority.

## Native deterministic replay

Run from the checked-out exact PR SHA:

```sh
PYTHONWARNINGS='error::ResourceWarning' python3 -m unittest discover -s scripts -p 'test_research*.py' -q
python3 -m unittest discover -s scripts -p 'test_research_challenge.py' -v
```

Python stdlib, no network or secrets from production. **159/159 local tests PASS** (previous 137 + 22 challenge tests). Synthetic test clock and openly published `bytes(range(32))` HMAC key are used **only for falsification**. Cases include: unknown/mismatched/expired nonce, old capture predating issuance, altered response MAC, different nonce with the same response, wrong signer, task/source rebinding, one-time use, 1 winner in a 12-thread race, 1 winner in a 4-independent-process race, all-or-nothing rollback and rejection of reused captures even with a new issued nonce. A subprocess test initially failed because it implicitly depended on `PYTHONPATH`; corrected it to set the module directory explicitly and reran the full suite without special environment setup.

## Unproven / forbidden promotions

- **Critical:** The signer may fabricate a post-challenge timestamp or claim that HTTP completed when it did not. OWASP distinguishes a fresh *assertion* from a witnessed action. Only an independent boundary observer (e.g., trusted egress gateway) can add stronger execution evidence.
- The verifier service and signing-key holder **are not isolated or independently authenticated here**. Any actor who can alter/reset the SQLite ledger, issue challenges at will or choose a new ledger can defeat some anti-replay guarantees. The path/owner check is a local candidate, not a fully race-proof host trust boundary or globally anchored append-only ledger.
- The code deliberately does not expose a production CLI for challenge issuance. Task authorization, operator approval, billing limits and key lifecycle need a separately reviewed trusted runtime; a research agent must never mint its own admissible challenge.
- No genuine public HTTPS capture was executed here; no publisher identity attested; no claim truth independently verified; no multi-host crash/consensus/power-loss guarantee; no real user-task success, blinded frontier competitor comparison or superiority is asserted.
- Hosted native CI, code-review signature and protected-main admission remain separate requirements. Draft PR only. **No new secret, production change, merge or deployment.**

References: [OWASP Execution Evidence](https://cheatsheetseries.owasp.org/cheatsheets/Verifying_Third_Party_Agent_Execution_Evidence_Cheat_Sheet.html) and [SLSA v1.2 verification](https://slsa.dev/spec/v1.2/verifying-artifacts).
