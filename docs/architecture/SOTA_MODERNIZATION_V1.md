# SOTA Modernization V1

This lane modernizes AEGIS Omega incrementally without widening authority or silently changing scientific semantics.

## Invariants

- protected `main` is never mutated directly;
- modernization work is split into reviewable, exact-head transitions;
- mathematical theorem statements, proof claims, cognitive anchors and authority policy are out of scope unless a dedicated later slice explicitly binds them;
- dependency and toolchain changes must be deterministic and lockfile-backed;
- GitHub Actions used by new modernization lanes are immutable-SHA pinned;
- production JavaScript targets an active LTS Node release, not the Current channel.

## Phase order

1. **Foundation** — toolchain pins, valid devcontainer, root dependency determinism, machine-checkable contract.
2. **CI supply chain** — replace floating GitHub Action tags with immutable SHAs and normalize runtime versions.
3. **JavaScript workspace** — converge package-manager policy, remove duplicate/stale lockfiles, centralize shared TypeScript/ESLint/Vite configuration.
4. **Sovereign runtime** — separately migrate React/TypeScript/ESLint only after full Gate-8 compatibility evidence.
5. **Python** — introduce modern `pyproject.toml`/locked environments per deployable boundary and eliminate unconstrained runtime installs.
6. **Rust** — establish explicit toolchain/MSRV and evaluate Rust 2024 edition migrations crate-by-crate.
7. **Containers** — digest-pin production bases where supported, run as non-root, add reproducible health/build contracts.
8. **Repository architecture** — collapse duplicated product scaffolds into explicit apps/packages/tooling boundaries without deleting historical evidence.

## Foundation status

The initial slice is intentionally behavior-neutral. It pins Node 24.21.0 LTS and npm 11.19.0 for the root toolchain, removes the root `latest` dependency range, repairs malformed devcontainer JSON, removes stale `frontend` workspace metadata from the root lockfile, and adds a read-only CI contract.

`authority_effect = NONE`
