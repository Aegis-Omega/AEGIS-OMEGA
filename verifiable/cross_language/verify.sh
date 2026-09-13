#!/usr/bin/env bash
# AEGIS-Ω cross-runtime replay proof.
# Python produces the genomics certificate; Node and Rust — two INDEPENDENT
# re-implementations of the v2 profile + SHA-256 + the hash chain — must reproduce
# its terminal hash byte-for-byte. Exit 0 = the certificate is runtime-invariant.
set -euo pipefail
cd "$(dirname "$0")"

echo "── 1/3  Python (reference producer) ─────────────────────────"
"${PYTHON:-python3}" emit_fixture.py

echo "── 2/3  Node.js (independent re-chainer) ────────────────────"
node rechain.mjs

echo "── 3/3  Rust (independent re-chainer) ───────────────────────"
# Always rebuild so the executed binary matches the current source — a stale
# target/ binary must never be able to report a false MATCH for an integrity check.
# Prefer the offline cargo cache (local dev); fall back to a networked build (CI).
( cd rust_rechain && (cargo build --locked --offline --release >/dev/null 2>&1 || cargo build --locked --release) )
rust_rechain/target/release/rechain stages.json
"${PYTHON:-python3}" test_replay_profiles.py

echo "─────────────────────────────────────────────────────────────"
echo "RESULT: identical terminal hash across Python, Node.js, and Rust."
echo "        The genomics certificate is a runtime-invariant object."
