# QuantumDNA witness and next-run contract

This integration registers an immutable interpretation audit in the repository
ClaimsLedger. It does not register an admitted Control-Plane execution, supply the
missing mathematical document, or run another QuantumDNA experiment.

## Evidence and status

`evidence/source_audit.json` is the original audit, unchanged. Its source receipt
links the standalone numerical run at
`b0a840015f92f39ddae65beb7393bf2c91aa816e`. The ten included artifacts are checked
against the pinned audit and receipt. This gate verifies that archived subset;
it does not rerun the solver or reverify every one of the original 86 outputs.

`docs/quantum-dna-witness-ledger.json` contains a deterministic SHA-256 chain.
Each entry binds the complete claim, evidence scope, limitations, source context,
sequence and previous-entry hash. The validator reconstructs the expected
semantics from pinned evidence: recomputing hashes cannot promote a rejected
interpretation. The projection in `docs/claims.json` must agree exactly.
The implementation commit must be an ancestor of HEAD and contain byte-identical
gate and test sources. This is repository integrity, not a signature, operator
authorization, independent review or scientific truth guarantee.

| Boundary | Required interpretation |
|---|---|
| Reference versus sweep | 37-state electron/hole ELM plus vacuum is separate from the six-site one-hole ELM sweep. |
| 1BNA provenance | Packaged parameter replay; residues A2/A3/A4 paired with B23/B22/B21. Raw-PDB parameter regeneration and original publication trajectory matching are not established. |
| GTG coherence at 25 fs | C_l1 = 0.21646991105146732 at 0.1 eV; 0.1438771953946045 at 0.5 eV. Both fail the specified asymptotic coupling criterion. |
| Dephasing | Gamma = gamma / hbar, with hbar in eV fs. Local projector dephasing supplies no bath temperature. |
| Sequence mechanism | Detuning and couplings both vary: GTG/GCG central offsets 1.0/0.8 eV and absolute H23 0.028/0.001 eV. Matrix ablations are required before causal attribution. |
| GGG population | Finite-time occupancy; the sweep contains no irreversible absorbing trap. The reference vacuum describes recombination. |
| Commutator | -i[A,B] is traceless Hermitian. Both eigenvalue signs require a nonzero operator; the zero operator is the exception. Neither is uniformly strictly positive over all finite-dimensional states. |
| Fourier decay | Fixed-parameter Riemann–Lebesgue decay supplies no uniform spectral-gap conclusion. |
| Zeros | A nonzero derivative at an independently established zero means transverse crossing, not zero exclusion. |
| Authority and biology | No promotion; no verified cellular consequence; the second mathematical document is absent. |

## Commands

From the repository root, using Python 3.12 and Node 20:

```bash
python -m unittest discover -s genomics/quantum_dna -p 'test_*.py' -v
node scripts/validate-claims.mjs
python -m genomics.quantum_dna.run_contract path/to/contract.json --artifact-root path/to/artifacts
```

The existing `claims-ledger` CI workflow runs the tests and integrated validator.
A future simulation runner must call `validate_contract(contract, artifact_root)`
before integration and retain the accepted contract and artifact hashes in its
run receipt. The current CLI returns `PREFLIGHT_PASS`, `execution=NOT_PERFORMED`
and `authority_promotion=false`; it does not launch the simulation.

The full contract fixture is in `test_run_contract.py`. Schema
`AEGIS_QDNA_RUN_CONTRACT_V1` requires exact key sets, decimal-string quantities,
SHA-256 descriptors for H, rho0 and collapse matrices, sequence/complement/site
ordering, solver and dependency versions, tolerances, explicit output sampling,
and deterministic randomness with seed null. Artifact paths must remain within
the declared root; symlinks, unknown fields and duplicate JSON keys are rejected.

V1 accepts real Hermitian H and a localized real rho0. Evolved rho(t) remains
complex Hermitian; a real initial state does not justify discarding imaginary
coherences. The sweep requires six actual local dephasing projectors for positive
gamma, with their squared amplitudes bound to Gamma. The reference has no
dephasing and requires collapse operators feeding the vacuum.

Ablation `allowed_entries` lists unique upper-triangle matrix indices. The actual
changed entries must equal that list, including Hermitian counterparts. This
checks H changes only: a causal comparison must additionally keep the baseline
rho0, dephasing, solver and measurement definition fixed. Sequence labels alone
do not prove the supplied Hamiltonian was generated from that sequence.

`classical_criteria` requires positive gamma, a nonempty sampled comparison
window, coupling/gamma <= 0.1, population error <= 0.05 and normalized coherence
<= 0.05. Callers must compute the metrics after 5/Gamma using the prescribed
classical comparator; the helper does not derive them or establish a universal
transition to classical transport. Deterministic solver repeats are numerical
checks, not independent biological samples or a statistical test of H1.

## Updating the evidence

Keep historical sources unchanged. Review changes to gate semantics and commit
the implementation first. Generate a new witness using
`python genomics/quantum_dna/claims_gate.py --generate EXACT_IMPLEMENTATION_COMMIT`,
project its complete claim objects into `docs/claims.json`, and preserve ID parity
with `docs/CLAIMS_LEDGER.md`. Commit that registration separately. Run the commands
above on the final candidate. A changed source requires a new reviewed evidence
version; changing a hash alone is not sufficient.
