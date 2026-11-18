#!/usr/bin/env python3
"""Synthetic contract tests for scripts/gcp-wif-repair-plan.sh.

These tests never contact Google Cloud. A fake gcloud executable records every
invocation so the fail-closed mutation boundary can be asserted directly.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "gcp-wif-repair-plan.sh"
PROJECT_NUMBER = "123456789"
PROVIDER = (
    f"projects/{PROJECT_NUMBER}/locations/global/"
    "workloadIdentityPools/github-pool/providers/github-provider"
)
SERVICE_ACCOUNT = "deployer@aegisomegav1.iam.gserviceaccount.com"

FAKE_GCLOUD = r'''#!/usr/bin/env python3
import json
import os
from pathlib import Path
import sys

args = sys.argv[1:]
log = Path(os.environ["MOCK_GCLOUD_LOG"])
with log.open("a", encoding="utf-8") as fh:
    fh.write(json.dumps(args) + "\n")

marker = Path(os.environ["MOCK_GCLOUD_APPLIED"])
project_number = os.environ.get("MOCK_PROJECT_NUMBER", "123456789")
subject = os.environ.get("MOCK_GOOGLE_SUBJECT", "assertion.sub")

if args[:2] == ["auth", "list"]:
    print("operator@example.invalid")
    raise SystemExit(0)

if args[:2] == ["projects", "describe"]:
    print(project_number)
    raise SystemExit(0)

if args[:5] == ["iam", "workload-identity-pools", "providers", "describe", "github-provider"]:
    if marker.exists():
        payload = {
            "attributeMapping": {
                "google.subject": "assertion.sub",
                "attribute.repository": "assertion.repository",
                "attribute.repository_id": "assertion.repository_id",
                "attribute.repository_owner_id": "assertion.repository_owner_id",
            },
            "attributeCondition": (
                "assertion.repository_owner_id=='288768655' && "
                "assertion.repository_id=='1095915905'"
            ),
        }
    else:
        payload = {
            "attributeMapping": {
                "google.subject": subject,
                "attribute.repository": "assertion.repository",
            },
            "attributeCondition": "assertion.repository=='Aegis-Omega/AEGIS--'",
        }
    print(json.dumps(payload))
    raise SystemExit(0)

if args[:4] == ["iam", "workload-identity-pools", "providers", "update-oidc"]:
    marker.write_text("applied\n", encoding="utf-8")
    raise SystemExit(0)

if args[:3] == ["iam", "service-accounts", "add-iam-policy-binding"]:
    raise SystemExit(0)

print("unexpected fake gcloud invocation: " + repr(args), file=sys.stderr)
raise SystemExit(91)
'''


def read_calls(log: Path) -> list[list[str]]:
    if not log.exists():
        return []
    return [json.loads(line) for line in log.read_text().splitlines() if line.strip()]


def is_mutation(call: list[str]) -> bool:
    return (
        call[:4] == ["iam", "workload-identity-pools", "providers", "update-oidc"]
        or call[:3] == ["iam", "service-accounts", "add-iam-policy-binding"]
    )


def run_case(
    root: Path,
    *args: str,
    env_overrides: dict[str, str] | None = None,
) -> tuple[subprocess.CompletedProcess[str], list[list[str]], Path]:
    fake_bin = root / "bin"
    fake_bin.mkdir(exist_ok=True)
    fake = fake_bin / "gcloud"
    fake.write_text(FAKE_GCLOUD, encoding="utf-8")
    fake.chmod(0o755)

    log = root / "gcloud-calls.jsonl"
    applied = root / "applied.marker"
    log.unlink(missing_ok=True)
    applied.unlink(missing_ok=True)
    (root / "gcp_wif_repair_receipt.json").unlink(missing_ok=True)

    env = os.environ.copy()
    env.update(
        {
            "PATH": f"{fake_bin}{os.pathsep}{env['PATH']}",
            "GCP_WORKLOAD_IDENTITY_PROVIDER": PROVIDER,
            "GCP_SERVICE_ACCOUNT": SERVICE_ACCOUNT,
            "MOCK_GCLOUD_LOG": str(log),
            "MOCK_GCLOUD_APPLIED": str(applied),
        }
    )
    env.pop("AEGIS_APPROVE_GCP_IAM_MUTATION", None)
    if env_overrides:
        env.update(env_overrides)

    cp = subprocess.run(
        ["bash", str(SCRIPT), *args],
        cwd=root,
        env=env,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    return cp, read_calls(log), root / "gcp_wif_repair_receipt.json"


def assert_no_mutations(calls: list[list[str]]) -> None:
    mutations = [call for call in calls if is_mutation(call)]
    assert not mutations, f"unexpected mutation calls: {mutations}"


def main() -> None:
    assert SCRIPT.exists(), SCRIPT

    with tempfile.TemporaryDirectory(prefix="aegis-wif-test-") as td:
        root = Path(td)

        # 1. Default plan mode may inspect current state but must not mutate it.
        cp, calls, receipt = run_case(root)
        assert cp.returncode == 0, (cp.returncode, cp.stdout, cp.stderr)
        assert "PLAN_ONLY: no Google Cloud state changed." in cp.stdout
        assert "assertion.repository=='Aegis-Omega/AEGIS--'" in cp.stdout
        assert "attribute.repository_id=assertion.repository_id" in cp.stdout
        assert "attribute.repository_owner_id=assertion.repository_owner_id" in cp.stdout
        assert_no_mutations(calls)
        assert not receipt.exists()

        # 2. A provider from a different GCP project is rejected before describe/update.
        wrong_provider = (
            "projects/999999999/locations/global/"
            "workloadIdentityPools/github-pool/providers/github-provider"
        )
        cp, calls, receipt = run_case(root, "--provider-resource", wrong_provider)
        assert cp.returncode == 17, (cp.returncode, cp.stdout, cp.stderr)
        assert "refusing cross-project mutation" in cp.stderr
        assert_no_mutations(calls)
        assert not receipt.exists()

        # 3. Unexpected google.subject mapping must fail before mutation.
        cp, calls, receipt = run_case(
            root,
            env_overrides={"MOCK_GOOGLE_SUBJECT": "assertion.repository"},
        )
        assert cp.returncode != 0, (cp.returncode, cp.stdout, cp.stderr)
        assert "REFUSE: expected google.subject=assertion.sub" in (cp.stdout + cp.stderr)
        assert_no_mutations(calls)
        assert not receipt.exists()

        # 4. --apply alone is insufficient; explicit operator environment gate is required.
        cp, calls, receipt = run_case(root, "--apply")
        assert cp.returncode == 30, (cp.returncode, cp.stdout, cp.stderr)
        assert "AEGIS_APPROVE_GCP_IAM_MUTATION=YES" in cp.stderr
        assert_no_mutations(calls)
        assert not receipt.exists()

        # 5. Synthetic explicit apply exercises the exact intended two mutations and receipt.
        cp, calls, receipt = run_case(
            root,
            "--apply",
            env_overrides={"AEGIS_APPROVE_GCP_IAM_MUTATION": "YES"},
        )
        assert cp.returncode == 0, (cp.returncode, cp.stdout, cp.stderr)
        mutations = [call for call in calls if is_mutation(call)]
        assert len(mutations) == 2, mutations
        assert mutations[0][:4] == [
            "iam", "workload-identity-pools", "providers", "update-oidc"
        ]
        assert mutations[1][:3] == [
            "iam", "service-accounts", "add-iam-policy-binding"
        ]
        assert receipt.exists()
        data = json.loads(receipt.read_text())
        assert data["repository_id"] == "1095915905"
        assert data["repository_owner_id"] == "288768655"
        assert data["long_lived_key_used"] is False
        assert data["authority"] == "IAM_REPAIR_EXPLICIT_APPLY"

    print("PASS: 5/5 GCP WIF repair planner contracts")


if __name__ == "__main__":
    main()
