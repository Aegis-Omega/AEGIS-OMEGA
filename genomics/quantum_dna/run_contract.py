"""Artifact-bound preflight checks; passing grants no scientific or execution authority.

V1 inputs H and localized rho0 are real decimal-string matrices. This input format
does not restrict the evolved rho(t): Hamiltonian dynamics generally make it complex.
Ablation checks cover changed Hamiltonian entries; they do not prove that separate
runs kept every other condition fixed or that a matrix was regenerated from DNA.
"""

import argparse
import hashlib
import json
import re
from decimal import Decimal, InvalidOperation
from pathlib import Path, PurePosixPath


class ContractError(ValueError):
    """The run contract is malformed, unbound, or scientifically inconsistent."""


def _require(condition, message):
    if not condition:
        raise ContractError(message)


def _keys(value, keys, label):
    _require(isinstance(value, dict) and set(value) == set(keys.split()),
             label + ": unexpected or missing fields")


def _decimal(value, label, strings=True):
    _require(type(value) is str if strings else type(value) in (str, int, float, Decimal),
             label + ": expected decimal" + (" string" if strings else ""))
    try:
        result = Decimal(str(value))
    except (InvalidOperation, ValueError):
        raise ContractError(label + ": invalid decimal") from None
    _require(result.is_finite() and result.copy_abs() <= Decimal("1e30") and
             (result == 0 or result.adjusted() >= -300), label + ": nonfinite or excessive value")
    return result


def _object_pairs(pairs):
    result = {}
    for key, value in pairs:
        _require(key not in result, "duplicate JSON key")
        result[key] = value
    return result


def _matrix(descriptor, root, dimension, label):
    _keys(descriptor, "path sha256", label)
    relative = descriptor["path"]
    _require(type(relative) is str and relative and "\\" not in relative and "\x00" not in relative,
             label + ": invalid artifact path")
    path = PurePosixPath(relative)
    _require(not path.is_absolute() and all(p not in ("", ".", "..") for p in relative.split("/")),
             label + ": artifact path must be bounded and relative")
    candidate = root.joinpath(*path.parts)
    _require(not any(root.joinpath(*path.parts[:i]).is_symlink() for i in range(1, len(path.parts) + 1)),
             label + ": symbolic links are not permitted")
    _require(candidate.resolve().is_relative_to(root) and candidate.is_file(), label + ": missing or unbounded artifact")
    _require(type(descriptor["sha256"]) is str and re.fullmatch(r"[0-9a-f]{64}", descriptor["sha256"]),
             label + ": invalid SHA256")
    try:
        _require(candidate.stat().st_size <= 2_000_000, label + ": artifact too large")
        raw = candidate.read_bytes()
        _require(hashlib.sha256(raw).hexdigest() == descriptor["sha256"], label + ": digest mismatch")
        value = json.loads(raw, object_pairs_hook=_object_pairs)
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise ContractError(label + ": unreadable JSON artifact") from error
    _require(type(value) is list and len(value) == dimension, label + ": wrong matrix dimension")
    _require(all(type(row) is list and len(row) == dimension for row in value), label + ": non-square matrix")
    return [[_decimal(entry, label) for entry in row] for row in value]


def _symmetric(matrix, label):
    _require(all(matrix[i][j] == matrix[j][i] for i in range(len(matrix)) for j in range(i)),
             label + ": matrix is not real Hermitian")


def classical_criteria(gamma_eV, coupling_ratio, population_error,
                       normalized_coherence, comparison_samples):
    """Operational sampled comparator gate, never a thermal or universal crossover."""
    gamma = _decimal(gamma_eV, "gamma", False)
    _require(gamma > 0, "classical comparator requires gamma > 0")
    metrics = [_decimal(value, "classical metric", False) for value in
               (coupling_ratio, population_error, normalized_coherence)]
    _require(all(value >= 0 for value in metrics), "negative classical metric")
    _require(type(comparison_samples) is int and comparison_samples >= 0, "invalid comparison sample count")
    return comparison_samples > 0 and all(value <= bound for value, bound in
        zip(metrics, (Decimal("0.1"), Decimal("0.05"), Decimal("0.05"))))


def validate_contract(contract, artifact_root):
    """Validate metadata and artifacts; return None. No run, registration or admission."""
    _keys(contract, "schema model_id sequence complement site_order hamiltonian rho0 collapse_operators "
          "units dephasing solver output_grid randomness interpretation ablation", "contract")
    _require(contract["schema"] == "AEGIS_QDNA_RUN_CONTRACT_V1", "unknown contract schema")
    model = contract["model_id"]
    _require(model in ("SWEEP_ONE_HOLE_ELM_6D", "REFERENCE_2P_ELM_GROUND_37D"), "unknown model")
    sweep = model == "SWEEP_ONE_HOLE_ELM_6D"
    dimension = 6 if sweep else 37
    sequence = contract["sequence"]
    _require(type(sequence) is str and sequence in ("GCG", "GTG", "GAG", "GGG"), "unknown sequence")
    _require(sweep or sequence == "GCG", "reference model requires GCG")
    complement = sequence.translate(str.maketrans("ACGT", "TGCA"))
    _require(contract["complement"] == complement, "complement is aligned 3-prime to 5-prime")
    expected_sites = [f"{strand}:{i + 1}:{base}" for strand, bases in
                      (("upper", sequence), ("lower", complement)) for i, base in enumerate(bases)]
    _require(contract["site_order"] == expected_sites, "site ordering mismatch")
    _keys(contract["units"], "hamiltonian time collapse", "units")
    _require(contract["units"] == {"hamiltonian": "eV", "time": "fs", "collapse": "fs^-1/2"}, "unit mismatch")
    noise = contract["dephasing"]
    _keys(noise, "kind gamma_eV rate_fs_inverse hbar_eV_fs", "dephasing")
    _require(noise["kind"] == "LOCAL_PROJECTOR_PURE_DEPHASING", "uncalibrated bath type")
    gamma, rate, hbar = [_decimal(noise[key], key) for key in ("gamma_eV", "rate_fs_inverse", "hbar_eV_fs")]
    _require(gamma >= 0 and rate >= 0 and hbar > 0, "invalid gamma, rate or hbar")
    _require(abs(hbar - Decimal("0.6582119569")) <= Decimal("1e-9"), "hbar unit/value mismatch")
    _require((rate == 0) == (gamma == 0) and abs(rate * hbar - gamma) <= gamma * Decimal("1e-9"), "gamma/rate mismatch")
    solver = contract["solver"]
    _keys(solver, "name version rtol atol versions", "solver")
    _require(all(type(solver[key]) is str and solver[key].strip() for key in ("name", "version")), "missing solver identity")
    _keys(solver["versions"], "python qdna qutip scipy numpy", "versions")
    _require(all(type(v) is str and v.strip() for v in solver["versions"].values()), "missing dependency version")
    _require(all(0 < _decimal(solver[key], key) < 1 for key in ("rtol", "atol")), "invalid solver tolerance")
    grid = contract["output_grid"]
    _keys(grid, "start_fs end_fs count spacing_fs integration", "output grid")
    start, end, spacing = [_decimal(grid[key], key) for key in ("start_fs", "end_fs", "spacing_fs")]
    _require(type(grid["count"]) is int and 2 <= grid["count"] <= 10_000_000, "invalid output count")
    _require(start == 0 and end > start and spacing > 0 and
             abs(spacing * (grid["count"] - 1) - (end - start)) <= Decimal("1e-9"), "inconsistent output grid")
    _require(grid["integration"] == "ADAPTIVE_INTERNAL_OUTPUT_GRID_ONLY", "output grid is not a fixed integration step")
    _keys(contract["randomness"], "mode seed", "randomness")
    _require(contract["randomness"] == {"mode": "NONE_DETERMINISTIC", "seed": None}, "v1 requires deterministic dynamics")
    interpretation = contract["interpretation"]
    _keys(interpretation, "trap_present temperature_K biological_effect authority_promotion", "interpretation")
    _require(type(interpretation["trap_present"]) is bool and interpretation["trap_present"] == (not sweep), "trap/model mismatch")
    _require(interpretation["temperature_K"] is None and interpretation["biological_effect"] == "NOT_ESTABLISHED"
             and interpretation["authority_promotion"] is False, "metadata cannot grant thermal, biological or admission claims")
    root = Path(artifact_root).resolve()
    hamiltonian = _matrix(contract["hamiltonian"], root, dimension, "Hamiltonian")
    initial = _matrix(contract["rho0"], root, dimension, "rho0")
    _symmetric(hamiltonian, "Hamiltonian")
    _symmetric(initial, "rho0")
    _require(sum(initial[i][i] for i in range(dimension)) == 1 and
             all(initial[i][i] >= 0 for i in range(dimension)), "rho0 diagonal/trace invalid")
    # V1 localized pure state proves positivity. 2P basis: vacuum=0; (e_i,h_j)=1+6*i+j.
    occupied = 0 if sweep else 1
    _require(all(initial[i][j] == int(i == j == occupied) for i in range(dimension)
                 for j in range(dimension)), "v1 requires localized initial state in declared model basis")
    descriptors = contract["collapse_operators"]
    _require(type(descriptors) is list and len(descriptors) <= 1369, "invalid collapse operator list")
    collapses = [_matrix(item, root, dimension, "collapse") for item in descriptors]
    if sweep:
        _require(len(collapses) == (6 if gamma > 0 else 0), "sweep requires one dephasing projector per site")
        for site, matrix in enumerate(collapses):
            _require(all(matrix[i][j] == 0 for i in range(6) for j in range(6) if (i, j) != (site, site)), "nonprojector sweep collapse")
            _require(matrix[site][site] > 0 and abs(matrix[site][site] ** 2 - rate) <= rate * Decimal("1e-9"), "collapse amplitude/rate mismatch")
    else:
        _require(gamma == 0 and len(collapses) > 0, "reference requires zero dephasing and recombination operators")
        _require(all(hamiltonian[0][i] == hamiltonian[i][0] == 0 for i in range(37)), "reference vacuum Hamiltonian mismatch")
        _require(all(any(c[0][j] != 0 for j in range(1, 37)) and c[0][0] == 0 and
                     all(c[i][j] == 0 for i in range(1, 37) for j in range(37)) for c in collapses), "reference collapse must feed absorbing vacuum")
    ablation = contract["ablation"]
    if ablation is not None:
        _require(sweep, "v1 ablations apply only to one-hole sweep")
        _keys(ablation, "base_hamiltonian allowed_entries", "ablation")
        base = _matrix(ablation["base_hamiltonian"], root, dimension, "base Hamiltonian")
        _symmetric(base, "base Hamiltonian")
        entries = ablation["allowed_entries"]
        _require(type(entries) is list and entries, "ablation allow-list is empty")
        allowed = set()
        for pair in entries:
            _require(type(pair) is list and len(pair) == 2 and all(type(i) is int and 0 <= i < dimension for i in pair), "invalid ablation index")
            i, j = pair
            _require(i <= j and (i, j) not in allowed, "ablation indices must be unique upper-triangle pairs")
            allowed.add((i, j))
        changed = {(i, j) for i in range(dimension) for j in range(i, dimension) if base[i][j] != hamiltonian[i][j]}
        _require(changed == allowed, "ablation changed undeclared entries or omitted declared changes")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("contract", type=Path)
    parser.add_argument("--artifact-root", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        def reject_constant(value):
            raise ContractError("nonfinite JSON constant: " + value)
        contract = json.loads(args.contract.read_bytes(), object_pairs_hook=_object_pairs,
                              parse_constant=reject_constant)
        validate_contract(contract, args.artifact_root)
    except (ContractError, OSError, UnicodeError, ValueError, TypeError, RuntimeError) as error:
        parser.exit(2, "QuantumDNA preflight DENY: " + str(error) + "\n")
    print(json.dumps({"status": "PREFLIGHT_PASS", "execution": "NOT_PERFORMED",
                      "authority_promotion": False, "scope": "DECLARED_MATRIX_CONTRACT_ONLY"}, sort_keys=True))


if __name__ == "__main__":
    main()
