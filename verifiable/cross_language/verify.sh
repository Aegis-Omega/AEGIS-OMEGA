#!/usr/bin/env bash
# AEGIS-Ω cross-runtime replay proof.
# Python produces the genomics certificate; Node and Rust — two INDEPENDENT
# re-implementations of RFC 8785 canon + SHA-256 + the hash chain — must reproduce
# its terminal hash byte-for-byte. Exit 0 = the certificate is runtime-invariant.
set -euo pipefail
cd "$(dirname "$0")"

echo "── 1/3  Python (reference producer) ─────────────────────────"
python3 emit_fixture.py

echo "── 2/3  Node.js (independent re-chainer) ────────────────────"
node rechain.mjs

echo "── 3/3  Rust (independent re-chainer) ───────────────────────"
if [ ! -x rust_rechain/target/release/rechain ]; then
  # Prefer the offline cargo cache (local dev); fall back to a networked build (CI).
  ( cd rust_rechain && (cargo build --offline --release >/dev/null 2>&1 || cargo build --release >/dev/null 2>&1) )
fi
rust_rechain/target/release/rechain stages.json

echo "─────────────────────────────────────────────────────────────"
echo "RESULT: identical terminal hash across Python, Node.js, and Rust."
echo "        The genomics certificate is a runtime-invariant object."
