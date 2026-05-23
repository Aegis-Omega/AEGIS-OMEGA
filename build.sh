#!/bin/bash
set -e
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

(cd "$ROOT/packages/shared"  && npm install)
(cd "$ROOT/platform-picker"  && npm install && npm run build)
(cd "$ROOT/hook-generator"   && npm install && npm run build)
(cd "$ROOT/content-calendar" && npm install && npm run build)
(cd "$ROOT/hub"              && npm install && npm run build)

mkdir -p "$ROOT/dist"
cp -r "$ROOT/hub/dist/."              "$ROOT/dist/"
mkdir -p "$ROOT/dist/platform-picker"  && cp -r "$ROOT/platform-picker/dist/."  "$ROOT/dist/platform-picker/"
mkdir -p "$ROOT/dist/hook-generator"   && cp -r "$ROOT/hook-generator/dist/."   "$ROOT/dist/hook-generator/"
mkdir -p "$ROOT/dist/content-calendar" && cp -r "$ROOT/content-calendar/dist/." "$ROOT/dist/content-calendar/"
