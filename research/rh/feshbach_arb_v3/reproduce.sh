#!/bin/bash
# Rebuild the L = 9/5 inputs and blocks, check them against the pinned hashes, run both certifiers and the tests.
# Needs python3 with python-flint 0.9.0 and numpy.  usage: ./reproduce.sh [g0] [v9] [split] [uniform] [check]
# (no argument = everything; the integer tau layer always runs first, ~20 s; each block set ~3 min and ~0.75 GB;
#  cert_congr on the 799-dim joint block ~75 s per mu and ~1.6 GB)
set -euo pipefail
cd "$(dirname "$0")"; PY=${PY:-python3}; T=${*:-g0 v9 split uniform check}
AF=$PWD/tau80/alpha_L95_NP16000_P120.json; DF=$PWD/tau80/diag_L95_N400_P120.json
has() { [[ " $T " == *" $1 "* ]]; }
# integer tau layer (fixed point 2^120, directed rounding): alpha_n for n <= 16000 and the diagonal CC/XC for n <= 400
(cd tau80 && ALPHA_OUT=$AF $PY -I tau80.py 16000 120 92 && DIAG_OUT=$DF $PY -I diag80.py 400 120 94)
echo "d5374e046cb004bb68ac20da220737cc882318e2ff7984f77a21252e846d90eb  $AF
efae4a0a5488521f19ed55603b6415a29cacb23d5a28fa1b40d157f36179f126  $DF" | sha256sum -c -
blocks() { local d=runs/$1; shift; mkdir -p $d; cp src/cvs_entries.py src/v8p.py $d/
  (cd $d && env ALPHA_FILE=$AF DIAG_FILE=$DF DROP_POLE=1 TAIL_ORDER=8 ROW_CHUNK=1000 OPENBLAS_NUM_THREADS=1 "$@" $PY -I v8p.py 1.8 400 16000 > blocks.out 2> err.out); }
has g0 && blocks v8i_18g0full TAIL_WEIGHTS=global GLOBAL_MIX=0 SCHUR_MU=4.2e-17 CINF=0.97991957971 RITZ=1
has v9 && blocks v8i_18v9w TAIL_WEIGHTS=fixed AEGIS_TAIL_WEIGHTS_JSON=$PWD/weights/weights_L18_v9.json
has split && blocks v8p_18fix PARITY_STREAM=1 PARITY_SPLIT=fixed TAIL_WEIGHTS=uniform $(cat weights/w_renorm_g0.env)
has uniform && blocks v8p_18par PARITY_SPLIT=uniform TAIL_WEIGHTS=uniform
if has check; then
  for m in manifests/*.json; do b=$($PY -I -c "import json,sys; print(json.load(open(sys.argv[1]))['blocks'])" $m)
    [ -f "manifests/$b" ] && $PY -I -c "import json,sys,hashlib; m=json.load(open(sys.argv[1])); h=hashlib.sha256(open(sys.argv[2],'rb').read()).hexdigest(); print(('OK  ' if h==m['blocks_sha256'] else 'MISMATCH ')+sys.argv[2]); sys.exit(h!=m['blocks_sha256'])" $m manifests/$b; done
  e=manifests/L18_even_renorm_g0.json; o=manifests/L18_odd_renorm_g0.json; j=manifests/L18_joint_g0.json; v=manifests/L18_joint_v9.json
  for c in schur_mid cert_congr; do
    $PY -I src/$c.py --manifest $e 4.23e-17; $PY -I src/$c.py --manifest $o 5e-17; $PY -I src/$c.py --manifest $j 4.21e-17
    $PY -I src/$c.py --manifest $v 4.05e-17
    for x in "$e 4.24e-17" "$j 4.22e-17" "$v 4.1e-17"; do if $PY -I src/$c.py --manifest $x; then echo "UNEXPECTED PASS: $c $x"; exit 1; fi; done
  done
  $PY -I tests/test_certifiers.py --real
fi
