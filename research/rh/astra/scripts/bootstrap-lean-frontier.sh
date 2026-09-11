#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"; source "$ROOT/env/rh-frontier.env"; WORK="${AEGIS_LEAN_WORKDIR:-$ROOT/.formal-provider}"; rm -rf "$WORK"
git clone --filter=blob:none "https://github.com/$LI_CRITERION_REPO.git" "$WORK"; git -C "$WORK" checkout --detach "$LI_CRITERION_SHA"
python3 - "$WORK/lakefile.lean" <<'PINPY'
import os,sys
from pathlib import Path
p=Path(sys.argv[1]); t=p.read_text(); old=os.environ['LI_CRITERION_ORIGINAL_MATHLIB_SHA']; new=os.environ['MATHLIB_SHA']
if old not in t: raise SystemExit('DENY original Mathlib pin missing from provider lakefile')
p.write_text(t.replace(old,new))
PINPY
printf '%s\n' "$LEAN_TOOLCHAIN" > "$WORK/lean-toolchain"; rm -f "$WORK/lake-manifest.json"
command -v elan >/dev/null 2>&1 || { echo 'DENY elan missing; install exact elan v1.4.2' >&2; exit 2; }
(cd "$WORK" && lake update mathlib && lake exe cache get && lake build Hadamard.OrderOne.TailEstimates Lc.LiCriterion.XiGrowth Lc.LiCriterion.HadamardSummabilityBridge)
echo 'PASS exact provider formal environment bootstrapped'
