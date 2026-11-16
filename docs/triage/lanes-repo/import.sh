#!/usr/bin/env bash
# Fetch every lane in lanes.txt from AEGIS-OMEGA, check its head SHA, and write
# one verified git bundle with full history: aegis-lanes.bundle (+ .sha256).
set -euo pipefail
src=${SRC:-https://github.com/Aegis-Omega/AEGIS-OMEGA.git}
list=${1:-lanes.txt}
rm -rf lanes.git && git init -q --bare lanes.git
while read -r pr branch sha; do
  git -C lanes.git fetch -q --no-tags "$src" "refs/heads/${branch}:refs/heads/${branch}"
  got=$(git -C lanes.git rev-parse "refs/heads/${branch}")
  if [ "$got" != "$sha" ]; then echo "#${pr} ${branch}: head ${got}, lanes.txt says ${sha}" >&2; exit 1; fi
done < "$list"
git -C lanes.git bundle create "$PWD/aegis-lanes.bundle" --all
git -C lanes.git bundle verify "$PWD/aegis-lanes.bundle" >/dev/null
sha256sum aegis-lanes.bundle > aegis-lanes.bundle.sha256
echo "bundle: $(wc -c < aegis-lanes.bundle) bytes, $(wc -l < "$list") lanes"
