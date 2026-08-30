#!/usr/bin/env bash
# wire-custom-domain.sh
#
# RETIRED / FAIL-CLOSED GUARD
#
# aegis-vertex.aegisomega.com is canonically owned by the Cloudflare Worker
# declared in /wrangler.jsonc:
#
#   { "pattern": "aegis-vertex.aegisomega.com", "custom_domain": true }
#
# The previous version of this script provisioned a GCP HTTPS load balancer and
# instructed operators to point the same hostname at its static IP. That creates
# two competing authorities for one production hostname and can break the
# Cloudflare Worker custom-domain binding/TLS provisioning.
#
# This file intentionally refuses to recreate or rebind the legacy GCP route.
# Existing GCP resources are NOT deleted here; deletion is a separate,
# explicitly-authorized infrastructure action.

set -euo pipefail

DOMAIN="aegis-vertex.aegisomega.com"
CANONICAL_OWNER="Cloudflare Worker: aegisomega"
CANONICAL_CONFIG="wrangler.jsonc"

cat >&2 <<EOF
REFUSED: retired GCP custom-domain wiring must not run.

Domain          : ${DOMAIN}
Canonical owner : ${CANONICAL_OWNER}
Canonical config: ${CANONICAL_CONFIG}

Reason: binding this hostname to the legacy GCP load balancer would conflict
with the production Cloudflare Worker custom domain and can reintroduce DNS/TLS
failures.

No infrastructure was changed.
EOF

exit 64
