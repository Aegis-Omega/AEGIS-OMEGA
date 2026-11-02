# aegis-research-lanes

The proof/, research/, evidence/ and integration/ lanes closed in Aegis-Omega/AEGIS-OMEGA on 2026-11-02 (#742), kept here so that the product repository carries only product and runtime code.

## Contents

- `lanes.txt`: PR number, branch and head SHA of each of the 43 lanes.
- `import.sh`: fetches every lane from AEGIS-OMEGA, checks its head against `lanes.txt`, and writes one verified git bundle with full history.
- `.github/workflows/import-lanes.yml`: runs `import.sh` on push to main and publishes the bundle as release `lanes-2026-11-02`.

## Restore a lane

```
gh release download lanes-2026-11-02 -R Aegis-Omega/aegis-research-lanes
sha256sum -c aegis-lanes.bundle.sha256
git fetch aegis-lanes.bundle 'refs/heads/*:refs/remotes/lanes/*'
```

## One-time setup

This kit is kept in AEGIS-OMEGA at `docs/triage/lanes-repo/`. The Claude GitHub App cannot create repositories, so:

1. The operator creates an empty public repository `Aegis-Omega/aegis-research-lanes` in the web UI.
2. An agent copies `README.md`, `lanes.txt` and `import.sh` to its root, and `import-lanes.yml` to `.github/workflows/`, on main.
3. The workflow runs as soon as Actions run in the organization (#735). Once the release exists and its checksum verifies, the 43 branches can be deleted from AEGIS-OMEGA (web UI).
