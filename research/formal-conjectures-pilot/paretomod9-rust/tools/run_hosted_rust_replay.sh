#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PINS="$ROOT/PINS.json"
WORK="${RUNNER_TEMP:-/tmp}/aegis-paretomod9-rust-replay"
SRC="$WORK/source"
EVIDENCE="$ROOT/evidence"
rm -rf "$WORK"
mkdir -p "$WORK" "$EVIDENCE"

json_get() {
  python3 - "$PINS" "$1" <<'PY'
import json,sys
print(json.load(open(sys.argv[1]))[sys.argv[2]])
PY
}

SOURCE_HEAD="$(json_get historical_source_head)"
RUST_VERSION="$(python3 - "$PINS" <<'PY'
import json,sys
print(json.load(open(sys.argv[1]))['fresh_toolchain']['rust_version'])
PY
)"
RUST_COMMIT="$(python3 - "$PINS" <<'PY'
import json,sys
print(json.load(open(sys.argv[1]))['fresh_toolchain']['rustc_commit_hash'])
PY
)"

# Pin a concrete fresh replay toolchain. Historical CI used mutable @stable.
rustup toolchain install "$RUST_VERSION" --profile minimal
rustc "+$RUST_VERSION" --version --verbose | tee "$EVIDENCE/rustc-version.log"
cargo "+$RUST_VERSION" --version | tee "$EVIDENCE/cargo-version.log"
grep -F "release: $RUST_VERSION" "$EVIDENCE/rustc-version.log"
grep -F "commit-hash: $RUST_COMMIT" "$EVIDENCE/rustc-version.log"

# Materialize the historical source commit, not the helper branch implementation.
git clone --filter=blob:none --no-checkout https://github.com/Aegis-Omega/AEGIS-OMEGA.git "$SRC"
git -C "$SRC" fetch --depth 1 origin "$SOURCE_HEAD"
git -C "$SRC" checkout --detach FETCH_HEAD
test "$(git -C "$SRC" rev-parse HEAD)" = "$SOURCE_HEAD"

python3 - "$PINS" "$SRC" <<'PY'
import json, pathlib, subprocess, sys
pins=json.load(open(sys.argv[1])); root=pathlib.Path(sys.argv[2])
for rel, expected in pins['source_blobs'].items():
    got=subprocess.check_output(['git','-C',str(root),'hash-object',rel],text=True).strip()
    if got != expected:
        raise SystemExit(f'SOURCE_BLOB_MISMATCH {rel} expected={expected} got={got}')
    print('SOURCE_BLOB_OK', rel, got)
PY

test -z "$(git -C "$SRC" status --porcelain --untracked-files=no)"
sha256sum \
  "$SRC/aegis-cl-psi/src/abjad_encoder/v01.rs" \
  "$SRC/aegis-cl-psi/tests/abjad_encoder_v01_freeze.rs" \
  "$SRC/aegis-cl-psi/Cargo.toml" \
  "$SRC/aegis-cl-psi/Cargo.lock" \
  "$SRC/docs/specs/abjad-encoder-v0.1-canonical-freeze.md" \
  | tee "$EVIDENCE/source-sha256.txt"

export CARGO_INCREMENTAL=0
export CARGO_NET_RETRY=3
export RUSTFLAGS="-C opt-level=0"

cd "$SRC"
set -o pipefail
cargo "+$RUST_VERSION" test --locked --jobs 1 \
  --manifest-path aegis-cl-psi/Cargo.toml \
  --test abjad_encoder_v01_freeze -- --test-threads 1 \
  2>&1 | tee "$EVIDENCE/integration-test.log"
grep -Eq 'test result: ok\. 8 passed; 0 failed;' "$EVIDENCE/integration-test.log"

# Add exactly one ephemeral integration probe after exact-source verification.
cp "$ROOT/paretomod9_o2_profile_probe.rs" \
  "$SRC/aegis-cl-psi/tests/paretomod9_o2_profile_probe.rs"
sha256sum "$ROOT/paretomod9_o2_profile_probe.rs" | tee "$EVIDENCE/o2-probe-sha256.txt"
test -z "$(git -C "$SRC" diff --name-only)"

cargo "+$RUST_VERSION" test --locked --jobs 1 \
  --manifest-path aegis-cl-psi/Cargo.toml \
  --test paretomod9_o2_profile_probe -- --test-threads 1 \
  2>&1 | tee "$EVIDENCE/o2-probe.log"
grep -Eq 'test result: ok\. 1 passed; 0 failed;' "$EVIDENCE/o2-probe.log"

# The probe is untracked; historical tracked bytes must remain byte-identical.
test -z "$(git -C "$SRC" diff --name-only)"
python3 - "$PINS" "$SRC" <<'PY'
import json, pathlib, subprocess, sys
pins=json.load(open(sys.argv[1])); root=pathlib.Path(sys.argv[2])
for rel, expected in pins['source_blobs'].items():
    got=subprocess.check_output(['git','-C',str(root),'hash-object',rel],text=True).strip()
    if got != expected:
        raise SystemExit(f'POST_TEST_SOURCE_BLOB_MISMATCH {rel}')
print('POST_TEST_SOURCE_BLOBS_OK')
PY

cd "$ROOT"
python3 tools/make_receipt.py "$ROOT"
