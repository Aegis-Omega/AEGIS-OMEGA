#!/usr/bin/env bash
set -euo pipefail

PROJECT_ID="${PROJECT_ID:-aegisomegav1}"
REPOSITORY_ID="${AEGIS_GITHUB_REPOSITORY_ID:-1095915905}"
REPOSITORY_OWNER_ID="${AEGIS_GITHUB_OWNER_ID:-288768655}"
PROVIDER_RESOURCE="${GCP_WORKLOAD_IDENTITY_PROVIDER:-}"
SERVICE_ACCOUNT="${GCP_SERVICE_ACCOUNT:-}"
MODE="plan"

usage() {
  cat <<'USAGE'
Usage: scripts/gcp-wif-repair-plan.sh [options]

Default mode is read-only plan/verification. No Google Cloud mutation occurs.

Options:
  --project ID                 GCP project ID (default: aegisomegav1)
  --repository-id ID           Immutable GitHub repository ID (default: 1095915905)
  --repository-owner-id ID     Immutable GitHub organization ID (default: 288768655)
  --provider-resource NAME     Full workload identity provider resource name.
                               Defaults to GCP_WORKLOAD_IDENTITY_PROVIDER.
  --service-account EMAIL      Deployment service account.
                               Defaults to GCP_SERVICE_ACCOUNT.
  --apply                      Apply the provider mapping/condition and add the
                               repository_id principalSet binding. Requires
                               AEGIS_APPROVE_GCP_IAM_MUTATION=YES.
  -h, --help                   Show this help.

This script never creates or uses a long-lived service-account key.
USAGE
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --project) PROJECT_ID="$2"; shift 2 ;;
    --repository-id) REPOSITORY_ID="$2"; shift 2 ;;
    --repository-owner-id) REPOSITORY_OWNER_ID="$2"; shift 2 ;;
    --provider-resource) PROVIDER_RESOURCE="$2"; shift 2 ;;
    --service-account) SERVICE_ACCOUNT="$2"; shift 2 ;;
    --apply) MODE="apply"; shift ;;
    -h|--help) usage; exit 0 ;;
    *) echo "ERROR: unknown argument: $1" >&2; usage >&2; exit 2 ;;
  esac
done

command -v gcloud >/dev/null 2>&1 || {
  echo "ERROR: gcloud is required." >&2
  exit 10
}
command -v python3 >/dev/null 2>&1 || {
  echo "ERROR: python3 is required." >&2
  exit 11
}

[[ -n "$PROVIDER_RESOURCE" ]] || {
  echo "ERROR: provider resource is required via --provider-resource or GCP_WORKLOAD_IDENTITY_PROVIDER." >&2
  exit 12
}
[[ -n "$SERVICE_ACCOUNT" ]] || {
  echo "ERROR: service account is required via --service-account or GCP_SERVICE_ACCOUNT." >&2
  exit 13
}

# Expected resource form:
# projects/123456789/locations/global/workloadIdentityPools/POOL/providers/PROVIDER
if [[ "$PROVIDER_RESOURCE" =~ ^(//iam\.googleapis\.com/)?projects/([0-9]+)/locations/global/workloadIdentityPools/([a-z0-9-]+)/providers/([a-z0-9-]+)$ ]]; then
  PROVIDER_PROJECT_NUMBER="${BASH_REMATCH[2]}"
  POOL_ID="${BASH_REMATCH[3]}"
  PROVIDER_ID="${BASH_REMATCH[4]}"
else
  echo "ERROR: unrecognized provider resource format." >&2
  exit 14
fi

ACTIVE_ACCOUNT="$(gcloud auth list --filter=status:ACTIVE --format='value(account)' | head -n1)"
[[ -n "$ACTIVE_ACCOUNT" ]] || {
  echo "ERROR: gcloud has no active account. Authenticate before running this script." >&2
  exit 15
}

TARGET_PROJECT_NUMBER="$(gcloud projects describe "$PROJECT_ID" --format='value(projectNumber)')"
[[ -n "$TARGET_PROJECT_NUMBER" ]] || {
  echo "ERROR: could not resolve project number for $PROJECT_ID." >&2
  exit 16
}
[[ "$TARGET_PROJECT_NUMBER" == "$PROVIDER_PROJECT_NUMBER" ]] || {
  echo "ERROR: provider project number does not match $PROJECT_ID; refusing cross-project mutation." >&2
  exit 17
}

CURRENT_JSON="$(gcloud iam workload-identity-pools providers describe "$PROVIDER_ID" \
  --project="$PROJECT_ID" \
  --location=global \
  --workload-identity-pool="$POOL_ID" \
  --format=json)"

readarray -t DERIVED < <(PROVIDER_JSON="$CURRENT_JSON" python3 - <<'PY'
import json, os
p = json.loads(os.environ['PROVIDER_JSON'])
m = dict(p.get('attributeMapping') or {})
subject = m.get('google.subject')
if subject != 'assertion.sub':
    raise SystemExit(f"REFUSE: expected google.subject=assertion.sub, observed {subject!r}")
m['attribute.repository_id'] = 'assertion.repository_id'
m['attribute.repository_owner_id'] = 'assertion.repository_owner_id'
print(','.join(f'{k}={m[k]}' for k in sorted(m)))
print(p.get('attributeCondition') or '')
PY
)

DESIRED_MAPPING="${DERIVED[0]}"
CURRENT_CONDITION="${DERIVED[1]:-}"
DESIRED_CONDITION="assertion.repository_owner_id=='${REPOSITORY_OWNER_ID}' && assertion.repository_id=='${REPOSITORY_ID}'"
DESIRED_MEMBER="principalSet://iam.googleapis.com/projects/${PROVIDER_PROJECT_NUMBER}/locations/global/workloadIdentityPools/${POOL_ID}/attribute.repository_id/${REPOSITORY_ID}"

cat <<EOF2
GCP WIF repair plan
  mode:                 $MODE
  project:              $PROJECT_ID
  provider pool:        $POOL_ID
  provider id:          $PROVIDER_ID
  github repository id: $REPOSITORY_ID
  github owner id:      $REPOSITORY_OWNER_ID
  current condition:    ${CURRENT_CONDITION:-<empty>}
  desired condition:    $DESIRED_CONDITION
  desired principal:    $DESIRED_MEMBER

Provider mapping after merge (existing mappings preserved):
  $DESIRED_MAPPING
EOF2

if [[ "$MODE" == "plan" ]]; then
  cat <<'EOF2'

PLAN_ONLY: no Google Cloud state changed.
To apply, rerun with --apply and AEGIS_APPROVE_GCP_IAM_MUTATION=YES.
EOF2
  exit 0
fi

[[ "${AEGIS_APPROVE_GCP_IAM_MUTATION:-}" == "YES" ]] || {
  echo "ERROR: --apply requires AEGIS_APPROVE_GCP_IAM_MUTATION=YES." >&2
  exit 30
}

BEFORE_SHA256="$(printf '%s' "$CURRENT_JSON" | sha256sum | awk '{print $1}')"

gcloud iam workload-identity-pools providers update-oidc "$PROVIDER_ID" \
  --project="$PROJECT_ID" \
  --location=global \
  --workload-identity-pool="$POOL_ID" \
  --attribute-mapping="$DESIRED_MAPPING" \
  --attribute-condition="$DESIRED_CONDITION" \
  --quiet

gcloud iam service-accounts add-iam-policy-binding "$SERVICE_ACCOUNT" \
  --project="$PROJECT_ID" \
  --role=roles/iam.workloadIdentityUser \
  --member="$DESIRED_MEMBER" \
  --quiet >/dev/null

AFTER_JSON="$(gcloud iam workload-identity-pools providers describe "$PROVIDER_ID" \
  --project="$PROJECT_ID" \
  --location=global \
  --workload-identity-pool="$POOL_ID" \
  --format=json)"
AFTER_SHA256="$(printf '%s' "$AFTER_JSON" | sha256sum | awk '{print $1}')"

AFTER_JSON="$AFTER_JSON" DESIRED_CONDITION="$DESIRED_CONDITION" python3 - <<'PY'
import json, os
p = json.loads(os.environ['AFTER_JSON'])
m = p.get('attributeMapping') or {}
expected = {
    'google.subject': 'assertion.sub',
    'attribute.repository_id': 'assertion.repository_id',
    'attribute.repository_owner_id': 'assertion.repository_owner_id',
}
for key, value in expected.items():
    if m.get(key) != value:
        raise SystemExit(f'POSTCONDITION_FAILED: {key}={m.get(key)!r}')
if p.get('attributeCondition') != os.environ['DESIRED_CONDITION']:
    raise SystemExit('POSTCONDITION_FAILED: attributeCondition mismatch')
PY

cat > gcp_wif_repair_receipt.json <<EOF2
{
  "schema": "aegis.gcp.wif_repair.v1",
  "project_id": "$PROJECT_ID",
  "provider_project_number": "$PROVIDER_PROJECT_NUMBER",
  "pool_id": "$POOL_ID",
  "provider_id": "$PROVIDER_ID",
  "repository_id": "$REPOSITORY_ID",
  "repository_owner_id": "$REPOSITORY_OWNER_ID",
  "attribute_condition": "$DESIRED_CONDITION",
  "principal_set": "$DESIRED_MEMBER",
  "provider_before_sha256": "$BEFORE_SHA256",
  "provider_after_sha256": "$AFTER_SHA256",
  "authority": "IAM_REPAIR_EXPLICIT_APPLY",
  "long_lived_key_used": false
}
EOF2

python3 - <<'PY'
import hashlib
from pathlib import Path
p = Path('gcp_wif_repair_receipt.json')
print(p.read_text(), end='')
print('receipt_file_sha256=' + hashlib.sha256(p.read_bytes()).hexdigest())
PY

echo "APPLIED: provider identity condition and repository_id service-account binding updated."
echo "NEXT: rerun GCP WIF Read-Only Preflight; do not deploy until that lane is GREEN."
