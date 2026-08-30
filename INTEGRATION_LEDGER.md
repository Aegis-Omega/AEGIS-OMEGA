# Integration Ledger

The checked-in file is a pointer, not a current classification snapshot.

Authoritative integration evidence is generated for each candidate commit by `.github/workflows/integration-ledger.yml` using `scripts/integration_ledger.py`. The workflow publishes paired artifacts:

- `INTEGRATION_LEDGER.md`
- `INTEGRATION_LEDGER.json`

Each artifact is bound to the full repository commit SHA, Git tree SHA, source timestamp, schema version, generator version, and generator SHA-256 digest. The workflow fails when the generated commit does not exactly match the admitted candidate SHA.

Local regeneration:

```bash
SOURCE_DATE_EPOCH="$(git show -s --format=%ct HEAD)" \
python3 scripts/integration_ledger.py \
  --write \
  --output-dir artifacts/integration-ledger \
  --expected-sha "$(git rev-parse HEAD)"
```

Do not hand-edit or promote classifications from an older artifact. Retrieve the workflow artifact for the exact commit being evaluated.
