"""AEGIS Ω omnidata evolution, issue #758 / PR #773.

Safe metadata-first registry + measured, lossless codec evolution for arbitrary
file bytes + domain-specific scientific gates. No dynamic code evaluation,
network, file rewrite, scientific claim promotion, or authority grant.

This does NOT assert that optimizing byte storage optimizes scientific models.
Every experimental claim must name an evaluator and independently held-out rows.
"""
from __future__ import annotations

import argparse
import bz2
import csv
import hashlib
import io
import json
import lzma
import math
import zipfile
import zlib
from decimal import Decimal, InvalidOperation, ROUND_HALF_EVEN
from pathlib import Path
from typing import Any

SCHEMA = "AEGIS_OMNIDATA_EVOLUTION_V1"
MAX_FILE_BYTES = 10_000_000
MAX_FILES = 5000
MAX_SAMPLE_BYTES = 65_536
CODECS = ("identity", "zlib1", "zlib6", "bz26", "lzma1")
COMPRESSION_ALGORITHMS = frozenset(CODECS)
SEVERE_LEAKAGE_THRESHOLD = 0.0
KNOWN_SCIENTIFIC = {
    "aegis_omega_benchmark_seed_results.csv": "agent_method_policy",
    "finite_bath_exact_unitary_crosscheck_scan_v1.csv": "finite_bath_policy",
    "ablation_contexts.csv": "ablation_policy_candidate",
    "mechanism_boundary_bath_family_transfer_scan_v2.csv": "secular_budget_candidate",
    "secular_coherence_ratio_fresh_holdout_rows_v1.csv": "secular_budget_claimed_holdout",
    "finite_bath_truncation_mode_convergence_scan_v1.csv": "truncation_stability_audit",
}
LEAKAGE_PAIRS = (
    ("mechanism_boundary_bath_family_transfer_scan_v2.csv",
     "secular_coherence_ratio_fresh_holdout_rows_v1.csv",
     ("bath_family", "s", "group", "J", "h", "beta", "lambda", "tau_factor", "t_eval")),
)


def canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=True, allow_nan=False).encode("ascii")


def digest(value: Any) -> str:
    return hashlib.sha256(canonical(value)).hexdigest()


def sha256(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def file_bytes(path: Path) -> bytes:
    if path.is_symlink() or not path.is_file():
        raise ValueError("NONREGULAR_OR_SYMLINK")
    if path.stat().st_size > MAX_FILE_BYTES:
        raise ValueError("FILE_EXCEEDS_BUDGET")
    with path.open("rb") as stream:
        raw = stream.read(MAX_FILE_BYTES + 1)
    if len(raw) > MAX_FILE_BYTES:
        raise ValueError("FILE_EXCEEDS_BUDGET")
    return raw


def extension_registry(catalog_path: str | Path | None = None) -> dict[str, tuple[str, str]]:
    """Read metadata-only extension definitions. No third-party parser execution."""
    if catalog_path is None:
        return {}
    doc = json.loads(file_bytes(Path(catalog_path)))
    if doc.get("schema") != "AEGIS_FORMAT_CATALOG_V1":
        raise ValueError("FORMAT_CATALOG_SCHEMA")
    result: dict[str, tuple[str, str]] = {}
    for category, formats in doc.get("groups", {}).items():
        if not isinstance(formats, dict):
            raise ValueError("FORMAT_CATALOG_GROUP")
        for fmt, aliases in formats.items():
            for alias in aliases:
                if not isinstance(alias, str) or not alias.startswith(".") or len(alias) > 24:
                    raise ValueError("FORMAT_ALIAS_INVALID")
                # Aliases may intentionally overlap (e.g., database .mdb vs Access).
                result.setdefault(alias.lower(), (category, fmt))
    return result


def classify(name: str, registry: dict[str, tuple[str, str]]) -> dict[str, str]:
    lower = name.lower()
    suffixes = sorted(registry, key=len, reverse=True)
    for suffix in suffixes:
        if lower.endswith(suffix):
            category, fmt = registry[suffix]
            return {"format": fmt, "category": category, "recognition": "CATALOG"}
    for compressed in (".gz", ".bz2", ".xz", ".zst", ".lz4"):
        if lower.endswith(compressed):
            for suffix in suffixes:
                if lower[:-len(compressed)].endswith(suffix):
                    category, fmt = registry[suffix]
                    return {"format": fmt+"+"+compressed[1:].upper(), "category": category,
                            "recognition": "CATALOG_COMPRESSED_VARIANT"}
    return {"format": "UNKNOWN", "category": "unknown", "recognition": "NOT_IN_CATALOG"}


def compress(raw: bytes, codec: str) -> bytes:
    if codec == "identity":
        return raw
    if codec == "zlib1":
        return zlib.compress(raw, 1)
    if codec == "zlib6":
        return zlib.compress(raw, 6)
    if codec == "bz26":
        return bz2.compress(raw, compresslevel=6)
    if codec == "lzma1":
        return lzma.compress(raw, preset=1)
    raise ValueError("UNKNOWN_CODEC")


def decompress(blob: bytes, codec: str) -> bytes:
    # Decoding is ONLY for blobs this process created; never decode arbitrary
    # third-party archives. Output bounded to the pinned source size.
    if codec == "identity":
        return blob
    if codec in {"zlib1", "zlib6"}:
        return zlib.decompress(blob)
    if codec == "bz26":
        return bz2.decompress(blob)
    if codec == "lzma1":
        return lzma.decompress(blob)
    raise ValueError("UNKNOWN_CODEC")



def bounded_decompress(blob: bytes, codec: str, max_bytes: int) -> bytes:
    """Bound decompressed bytes BEFORE materializing untrusted archive content."""
    if codec not in CODECS or type(max_bytes) is not int or not 0<=max_bytes<=MAX_FILE_BYTES:
        raise ValueError("DECODE_BUDGET_INVALID")
    if codec=="identity":
        if len(blob)>max_bytes:
            raise ValueError("DECODE_OUTPUT_TOO_LARGE")
        return blob
    if codec.startswith("zlib"):
        obj=zlib.decompressobj()
        out=obj.decompress(blob,max_bytes+1)
        if len(out)>max_bytes or not obj.eof or obj.unused_data or obj.unconsumed_tail:
            raise ValueError("DECODE_OUTPUT_OR_STREAM_INVALID")
        return out
    if codec=="bz26":
        obj=bz2.BZ2Decompressor()
    else:
        obj=lzma.LZMADecompressor()
    out=obj.decompress(blob,max_length=max_bytes+1)
    if len(out)>max_bytes or not obj.eof or obj.unused_data:
        raise ValueError("DECODE_OUTPUT_OR_STREAM_INVALID")
    return out


def evolution_of_bytes(raw: bytes) -> dict[str, Any]:
    """Generate, evaluate, select codec on sampled bytes; independently
    verify the selected transform EXACTLY on entire original. Baseline: identity.
    Fitness is bytes only; measured runtime is reported but not optimized.
    """
    n = len(raw)
    if n == 0:
        samples = raw
    elif n <= MAX_SAMPLE_BYTES:
        samples = raw
    else:
        # Deterministic 3-stratum sample; non-overlapping ranges.
        width = MAX_SAMPLE_BYTES // 3
        offsets = (0, max(0, n//2-width//2), n-width)
        samples = b"".join(raw[i:i+width] for i in offsets)
    rows = []
    for codec in CODECS:
        blob = compress(samples, codec)
        if decompress(blob, codec) != samples:
            raise ValueError("SAMPLED_ROUNDTRIP_MISMATCH")
        rows.append({"codec": codec, "bytes": len(blob), "deterministic_metric": "compressed_bytes"})
    # Deterministic tie break prioritizing no transformation.
    champion = min(rows, key=lambda v: (v["bytes"], CODECS.index(v["codec"])))
    best_codec = champion["codec"]
    full = compress(raw, best_codec)
    if decompress(full, best_codec) != raw or sha256(decompress(full, best_codec)) != sha256(raw):
        raise ValueError("FULL_BYTE_EXACTNESS_FAILED")
    # Samples can misrank codecs; keep identity when selected transform expands full data.
    if len(full) >= n:
        best_codec = "identity"
        full = raw
    return {"baseline_codec": "identity", "candidate_codec": best_codec,
            "source_bytes": n, "candidate_bytes": len(full),
            "saved_bytes": n-len(full),
            "sample_candidates": rows,
            "full_sha256_recovered": sha256(decompress(full, best_codec)),
            "roundtrip": "BYTE_EXACT_PASS", "fitness_unit": "COMPRESSED_BYTES",
            "research_benefit": "NOT_EVALUATED", "authority_effect": "NONE"}


def structural_inspection(path: Path, raw: bytes, classification: dict) -> dict:
    ext = path.suffix.lower()
    if ext in (".csv", ".tsv"):
        delimiter = "\t" if ext == ".tsv" else ","
        try:
            r = csv.reader(io.StringIO(raw.decode("utf-8-sig")), delimiter=delimiter, strict=True)
            headers = next(r)
            rows = list(r)
            if not headers or len(set(headers)) != len(headers) or any(len(row)!=len(headers) for row in rows):
                return {"parse": "REJECTED", "reason": "BAD_COLUMNS"}
            return {"parse": "STRUCTURAL_PASS", "row_count": len(rows),
                    "column_count": len(headers), "columns": headers[:128],
                    "missing_cells": sum(v == "" for row in rows for v in row),
                    "nonfinite_literals": sum(v.lower() in ("nan","inf","-inf","infinity") for row in rows for v in row)}
        except (UnicodeError, csv.Error, StopIteration):
            return {"parse": "REJECTED", "reason": "INVALID_TEXT_TABLE"}
    if ext == ".ipynb":
        try:
            notebook = json.loads(raw)
            cells = notebook["cells"]
            if type(cells) is not list or type(notebook["nbformat"]) is not int:
                raise ValueError("NOTEBOOK_INVALID")
            return {"parse": "STRUCTURAL_PASS", "cell_count": len(cells),
                    "code_cells": sum(c.get("cell_type")=="code" for c in cells),
                    "execution": "DISABLED_UNTRUSTED_NOTEBOOK"}
        except (KeyError, ValueError, TypeError, AttributeError):
            return {"parse": "REJECTED", "reason": "INVALID_NOTEBOOK"}
    if ext in (".xlsx", ".xlsm"):
        try:
            import openpyxl
        except ImportError:
            return {"parse": "NOT_INSPECTED", "reason": "OPENPYXL_NOT_INSTALLED"}
        try:
            workbook = openpyxl.load_workbook(io.BytesIO(raw), read_only=True,
                                               data_only=False, keep_links=False)
            sheet_names = list(workbook.sheetnames)
            workbook.close()
            return {"parse": "STRUCTURAL_PASS", "sheet_count": len(sheet_names),
                    "sheet_names": sheet_names[:100], "execution": "DISABLED_UNTRUSTED_MACROS"}
        except (ValueError, OSError, KeyError, EOFError, ImportError):
            return {"parse": "REJECTED", "reason": "INVALID_XLSX"}
    return {"parse": "NOT_INSPECTED", "reason": "NO_SAFE_DOMAIN_PARSER_INSTALLED",
            "recognition": classification["recognition"]}


def numeric_key(value: str) -> str:
    try:
        v = Decimal(value)
        if not v.is_finite():
            raise ValueError("NONFINITE_LEAKAGE_KEY")
        # Tolerance solely for finding *possible* leakage, NOT numerical proof.
        return str(v.quantize(Decimal("0.00000001"), rounding=ROUND_HALF_EVEN))
    except InvalidOperation:
        return value.strip()


def leakage_overlap(a_bytes: bytes, b_bytes: bytes, keys: tuple[str, ...]) -> dict:
    def values(raw: bytes) -> set[tuple[str, ...]]:
        r = csv.DictReader(io.StringIO(raw.decode("utf-8-sig")), strict=True)
        if r.fieldnames is None or not set(keys).issubset(set(r.fieldnames)):
            raise ValueError("LEAKAGE_KEYS_MISSING")
        return {tuple(numeric_key(row[k]) for k in keys) for row in r}
    a, b = values(a_bytes), values(b_bytes)
    overlap = len(a & b)
    return {"left_unique_configs": len(a), "right_unique_configs": len(b),
            "overlap_configs": overlap,
            "right_overlap_fraction": overlap/len(b) if b else None,
            "numeric_comparison": "ROUND_8DP_POTENTIAL_CONFIG_DUPLICATE",
            "independent_holdout": "DENIED" if overlap else "NOT_ESTABLISHED",
            "reason": "CONFIGURATIONS_OVERLAP" if overlap else "NO_MATCH_FOUND_NOT_INDEPENDENCE_PROOF",
            "scientific_promotion": "DENIED"}



def _finite_float(value: str, field: str) -> float:
    try:
        number = float(value)
    except (ValueError, TypeError) as exc:
        raise ValueError("INVALID_SCIENCE_FIELD:" + field) from exc
    if not math.isfinite(number):
        raise ValueError("NONFINITE_SCIENCE_FIELD:" + field)
    return number


def ablation_search(raw: bytes) -> dict[str, Any]:
    """Evolve bounded interpretable ablation-selection rules.

    Important: the source contains offline model diagnostics, not independent
    real-world experiments. Lambda is the independent *configuration* group.
    Numeric baseline/ablated errors are evaluation labels, not feature inputs.
    No claim of external generalization or solution to the source physics.
    """
    r = csv.DictReader(io.StringIO(raw.decode("utf-8-sig")), strict=True)
    needed = {"lambda", "R", "abs_sinc_chi_dom", "baseline_error", "ablated_error",
              "baseline_status", "ablated_status"}
    if r.fieldnames is None or not needed.issubset(r.fieldnames):
        raise ValueError("ABLATION_COLUMNS_MISSING")
    rows=[]
    for row in r:
        info={k:_finite_float(row[k],k) for k in
              ("lambda", "R", "abs_sinc_chi_dom", "baseline_error", "ablated_error")}
        if info["baseline_error"] < 0 or info["ablated_error"] < 0:
            raise ValueError("NEGATIVE_TRACE_ERROR")
        if row["baseline_status"] not in {"WITHIN_BUDGET", "OUTSIDE_BUDGET"} or \
           row["ablated_status"] not in {"WITHIN_BUDGET", "OUTSIDE_BUDGET"}:
            raise ValueError("ABLATION_STATUS_UNKNOWN")
        info["base_status"]=row["baseline_status"]
        info["cand_status"]=row["ablated_status"]
        rows.append(info)
    groups=sorted({v["lambda"] for v in rows})
    if len(groups)<5 or not rows:
        raise ValueError("ABLATION_GROUPS_INSUFFICIENT")
    train_g=set(groups[:-4]); valid_g=set(groups[-4:-2]); holdout_g=set(groups[-2:])
    split=lambda group:[r for r in rows if r["lambda"] in group]
    train,valid,holdout=split(train_g),split(valid_g),split(holdout_g)
    if any(not part for part in (train,valid,holdout)):
        raise ValueError("ABLATION_EMPTY_SPLIT")
    # The original datasets remain immutable. A generated policy chooses the
    # original baseline or one existing ablated approximation, never invents a
    # new physics result. Labels are inaccessible to the policy function.
    policies=[("baseline",), ("always_ablate",)]
    for feature in ("lambda", "R", "abs_sinc_chi_dom"):
        vals=sorted({v[feature] for v in train})
        for value in vals:
            for op in ("<=", ">"):
                policies.append((feature,op,value))
    def choice(policy, row):
        if policy[0]=="baseline": return False
        if policy[0]=="always_ablate": return True
        return row[policy[0]] <= policy[2] if policy[1]=="<=" else row[policy[0]] > policy[2]
    def score(policy,part):
        errs=[]; new_unsafe=0; ablated=0
        for row in part:
            select=choice(policy,row)
            ablated+=int(select)
            errs.append(row["ablated_error"] if select else row["baseline_error"])
            if select and row["base_status"]=="WITHIN_BUDGET" and row["cand_status"]=="OUTSIDE_BUDGET":
                new_unsafe+=1
        return {"mean_error":sum(errs)/len(errs),"regression_veto_count":new_unsafe,
                "rows":len(errs),"ablated_selected":ablated}
    safe_train=[p for p in policies if score(p,train)["regression_veto_count"]==0]
    baseline=("baseline",)
    train_champion=min(safe_train,key=lambda p:(score(p,train)["mean_error"],str(p)))
    val_safe=[p for p in safe_train if score(p,valid)["regression_veto_count"]==0]
    candidate=min(val_safe,key=lambda p:(score(p,valid)["mean_error"],score(p,train)["mean_error"],str(p)))
    if score(candidate,valid)["mean_error"] >= score(baseline,valid)["mean_error"]:
        candidate=baseline
    base_held=score(baseline,holdout); cand_held=score(candidate,holdout)
    independent_n=len(holdout_g)
    return {"task":"ABLATION_CONDITION_POLICY", "data_scope":"RECORDED_NUMERICAL_MODEL_DIAGNOSTIC",
            "source_sha256":sha256(raw), "policy_space":len(policies),
            "train_lambda_groups":sorted(train_g),"validation_lambda_groups":sorted(valid_g),
            "holdout_lambda_groups":sorted(holdout_g),"selected_policy":candidate,
            "train_champion":train_champion,"holdout_baseline":base_held,
            "holdout_candidate":cand_held,"holdout_delta_mean_error":cand_held["mean_error"]-base_held["mean_error"],
            "holdout_independent_configurations":independent_n,
            "holdout_regression":(cand_held["mean_error"]>base_held["mean_error"]+1e-12 or
                                  cand_held["regression_veto_count"]>0),
            "promotion":"DENIED", "min_independent_pairs_required":30,
            "external_test":"NOT_PERFORMED"}


def truncation_stability(raw: bytes) -> dict[str, Any]:
    """An adversarial robustness audit, not an evolved physical law."""
    r=csv.DictReader(io.StringIO(raw.decode("utf-8-sig")),strict=True)
    fields=("winner_ref_2lvl3mode", "winner_ref_3lvl3mode", "winner_ref_2lvl4mode")
    if r.fieldnames is None or not set(fields).issubset(r.fieldnames):
        raise ValueError("TRUNCATION_COLUMNS_MISSING")
    rows=list(r)
    for row in rows:
        if any(row[k] not in {"CG", "DAVIES"} for k in fields):
            raise ValueError("TRUNCATION_WINNER_INVALID")
    changes=sum(len({row[k] for k in fields})>1 for row in rows)
    return {"task":"NUMERICAL_TRUNCATION_SENSITIVITY",
            "source_sha256":sha256(raw), "rows":len(rows),
            "winner_changes_across_truncations":changes,
            "stable_winner_rows":len(rows)-changes,
            "independent_measurement":"NOT_ESTABLISHED", "promotion":"DENIED"}


def run(root: str | Path, *, catalog: str | Path | None = None,
        enable_selected_science: bool = True) -> dict[str, Any]:
    directory = Path(root).resolve(strict=True)
    if not directory.is_dir():
        raise ValueError("DATA_ROOT_NOT_DIRECTORY")
    registry = extension_registry(catalog)
    paths = sorted(x for x in directory.rglob("*") if x.is_file() or x.is_symlink())
    if len(paths) > MAX_FILES:
        raise ValueError("FILE_COUNT_EXCEEDS_BUDGET")
    records: list[dict[str, Any]] = []
    raw_by_name: dict[str, bytes] = {}
    for file in paths:
        rel = file.relative_to(directory).as_posix()
        if file.is_symlink():
            records.append({"source": rel, "status": "REJECTED_SYMLINK",
                            "scientific_status": "NOT_EVALUATED"})
            continue
        try:
            raw = file_bytes(file)
            classification = classify(file.name, registry)
            operation = evolution_of_bytes(raw)
            inspected = structural_inspection(file, raw, classification)
            role = KNOWN_SCIENTIFIC.get(file.name, "DISCOVERY_ONLY")
            record = {"source": rel, "source_sha256": sha256(raw),
                      "status": "BYTE_ROUNDTRIP_VERIFIED", "role": role,
                      "format": classification, "inspection": inspected,
                      "lossless_evolution": operation,
                      "scientific_status": "NOT_EVALUATED", "admission": "DENIED"}
            records.append(record)
            raw_by_name[file.name] = raw
        except (OSError, ValueError, MemoryError) as exc:
            records.append({"source": rel, "status": "REJECTED",
                            "reason_code": type(exc).__name__,
                            "scientific_status": "NOT_EVALUATED", "admission": "DENIED"})
    leakage=[]
    for left,right,keys in LEAKAGE_PAIRS:
        if left in raw_by_name and right in raw_by_name:
            proof = leakage_overlap(raw_by_name[left],raw_by_name[right],keys)
            leakage.append({"left":left,"right":right,**proof})
    domain_results=[]
    if enable_selected_science and "ablation_contexts.csv" in raw_by_name:
        domain_results.append(ablation_search(raw_by_name["ablation_contexts.csv"]))
    if enable_selected_science and "finite_bath_truncation_mode_convergence_scan_v1.csv" in raw_by_name:
        domain_results.append(truncation_stability(raw_by_name["finite_bath_truncation_mode_convergence_scan_v1.csv"]))
    if enable_selected_science:
        # Delegate actual finite-bath and agent decisions to the *existing*
        # evolution module rather than inventing a new independent evaluator.
        try:
            from agents.alphaevolve_data_fusion_v2 import evolve as existing_evolve
            required=("aegis_omega_benchmark_seed_results.csv",
                      "finite_bath_exact_unitary_crosscheck_scan_v1.csv")
            if all(v in raw_by_name for v in required):
                # The pre-existing module checks pinned source SHA-256 and
                # carries its own grouped evaluation and no-promotion gate.
                verified=existing_evolve(directory,generations=12)
                domain_results.append({"adapter":"existing_issue758_data_fusion_v2",
                                       "status":"EXECUTED_WITH_PINNED_SOURCES",
                                       "receipt_hash":verified["receipt_hash"],
                                       "agent_policy":verified["evolution"]["agent_policy"],
                                       "quantum_policy":verified["evolution"]["quantum_policy"],
                                       "promotion":"DENIED"})
        except ImportError:
            domain_results.append({"adapter":"existing_issue758_data_fusion_v2",
                                   "status":"NOT_AVAILABLE"})
    accepted=[x for x in records if x["status"]=="BYTE_ROUNDTRIP_VERIFIED"]
    body={"schema":SCHEMA,"files_seen":len(paths),"files_roundtrip_verified":len(accepted),
          "files_not_evolved":len(paths)-len(accepted),
          "source_total_bytes":sum(x["lossless_evolution"]["source_bytes"] for x in accepted),
          "compressed_total_bytes":sum(x["lossless_evolution"]["candidate_bytes"] for x in accepted),
          "saved_bytes":sum(x["lossless_evolution"]["saved_bytes"] for x in accepted),
          "dataset_records":records,"cross_dataset_leakage":leakage,
          "scientific_adapters":domain_results,
          "data_not_embedded_in_receipt":True,
          "candidate_scope":"LOSSLESS_DATA_PROCESSING_NOT_SCIENTIFIC_DISCOVERY",
          "independent_scientific_review":"NOT_PERFORMED",
          "scientific_promotion":"DENIED","authority_effect":"NONE",
          "production_effect":"NONE", "billing_effect":"NONE"}
    return {**body,"receipt_hash":digest(body)}




def _safe_relative_path(name: str) -> Path:
    p=Path(name)
    if (not isinstance(name,str) or not name or len(name)>512 or p.is_absolute()
        or "\\" in name or any(part in (".","..","") for part in name.split("/"))
        or name.startswith("/") or ":" in name):
        raise ValueError("UNSAFE_ARCHIVE_PATH")
    return p


def pack_archive(data_root: str | Path, result: dict, destination: str | Path) -> dict:
    """Create an actual lossless evolved dataset archive without altering source.

    ZIP stores pre-compressed codec payloads. The manifest records SHA256,
    exact path and codec; the archive MUST NOT be called a signed receipt.
    """
    root=Path(data_root).resolve(strict=True)
    dest=Path(destination)
    if dest.is_symlink() or dest.exists():
        raise ValueError("ARCHIVE_DESTINATION_EXISTS")
    items=[]
    for item in result["dataset_records"]:
        if item.get("status")!="BYTE_ROUNDTRIP_VERIFIED":
            raise ValueError("CANNOT_PACK_UNVERIFIED_SOURCE")
        relative=_safe_relative_path(item["source"])
        path=root/relative
        raw=file_bytes(path)
        if sha256(raw)!=item["source_sha256"]:
            raise ValueError("SOURCE_MUTATED_SINCE_EVOLUTION")
        codec=item["lossless_evolution"]["candidate_codec"]
        if codec not in CODECS:
            raise ValueError("ARCHIVE_CODEC_INVALID")
        blob=compress(raw,codec)
        if len(blob)!=item["lossless_evolution"]["candidate_bytes"]:
            raise ValueError("ARCHIVE_CODED_SIZE_MISMATCH")
        if decompress(blob,codec)!=raw:
            raise ValueError("ARCHIVE_LOSSLESS_FAILURE")
        items.append((relative.as_posix(),raw,codec,blob))
    if len({v[0] for v in items})!=len(items):
        raise ValueError("ARCHIVE_DUPLICATE_PATH")
    manifest={"schema":"AEGIS_OMNIDATA_LOSSLESS_ARCHIVE_V1",
              "origin_receipt_hash":result["receipt_hash"],
              "authentication":"NONE_INTERNAL_HASHES_ONLY",
              "files":[{"path":name,"codec":codec,"sha256":sha256(raw),
                        "source_size":len(raw),"compressed_size":len(blob)}
                       for name,raw,codec,blob in items]}
    dest.parent.mkdir(parents=True,exist_ok=True)
    try:
        with zipfile.ZipFile(dest,"x",compression=zipfile.ZIP_STORED) as zipped:
            zipped.writestr("manifest.json",canonical(manifest))
            for index,(_,_,codec,blob) in enumerate(items):
                zipped.writestr(f"objects/{index:06d}.bin",blob)
        verify_archive(dest,expected_manifest_sha=sha256(canonical(manifest)))
    except BaseException:
        dest.unlink(missing_ok=True)
        raise
    return {"archive_sha256":sha256(file_bytes(dest)),
            "manifest_sha256":sha256(canonical(manifest)),
            "files":len(items),"source_bytes":sum(len(v[1]) for v in items),
            "compressed_payload_bytes":sum(len(v[3]) for v in items),
            "archive_bytes":dest.stat().st_size,"recovery_verified":True}


def verify_archive(archive: str | Path, *, expected_manifest_sha: str | None = None,
                   restore_root: str | Path | None = None) -> dict:
    """Verify bounded codec payloads and optional safe reconstruction.

    No extraction APIs are used; every filename is independently checked,
    no symbolic links, no overwrite. A bare internal manifest is NOT signed.
    """
    path=Path(archive)
    total=0
    restored=[]
    with zipfile.ZipFile(path) as zipped:
        infos=zipped.infolist()
        if not infos or len(infos)>MAX_FILES+1 or any(i.file_size>MAX_FILE_BYTES for i in infos):
            raise ValueError("ARCHIVE_BOUNDS_INVALID")
        if len({x.filename for x in infos})!=len(infos):
            raise ValueError("ARCHIVE_DUPLICATE_ENTRIES")
        for info in infos:
            if (info.filename!="manifest.json" and not info.filename.startswith("objects/")):
                raise ValueError("ARCHIVE_UNEXPECTED_ENTRY")
            if (info.external_attr>>16)&0o170000 == 0o120000:
                raise ValueError("ARCHIVE_SYMLINK_FORBIDDEN")
        doc_bytes=zipped.read("manifest.json")
        if expected_manifest_sha is not None and sha256(doc_bytes)!=expected_manifest_sha:
            raise ValueError("EXTERNAL_MANIFEST_SHA_MISMATCH")
        doc=json.loads(doc_bytes)
        if doc.get("schema")!="AEGIS_OMNIDATA_LOSSLESS_ARCHIVE_V1":
            raise ValueError("ARCHIVE_SCHEMA_INVALID")
        files=doc.get("files")
        if type(files) is not list or not 0<=len(files)<=MAX_FILES:
            raise ValueError("ARCHIVE_FILE_LIST_INVALID")
        names=set()
        if set(zipped.namelist())!={"manifest.json"}|{f"objects/{i:06d}.bin" for i in range(len(files))}:
            raise ValueError("ARCHIVE_MEMBERS_MISMATCH")
        for index,item in enumerate(files):
            name=_safe_relative_path(item["path"])
            if str(name) in names or item["codec"] not in CODECS:
                raise ValueError("ARCHIVE_RECORD_INVALID")
            names.add(str(name))
            blob=zipped.read(f"objects/{index:06d}.bin")
            if len(blob)!=item["compressed_size"]:
                raise ValueError("ARCHIVE_PAYLOAD_SIZE")
            # Guard the expected output length before decompression; archives
            # are produced locally with bounded inputs and are not public-code loaders.
            if type(item["source_size"]) is not int or not 0<=item["source_size"]<=MAX_FILE_BYTES:
                raise ValueError("ARCHIVE_OUTPUT_BOUND")
            raw=bounded_decompress(blob,item["codec"],item["source_size"])
            if len(raw)!=item["source_size"] or sha256(raw)!=item["sha256"]:
                raise ValueError("ARCHIVE_CONTENT_MISMATCH")
            total+=len(raw)
            if restore_root is not None:
                target_root=Path(restore_root).resolve()
                target=target_root/name
                if target.is_symlink() or target.exists():
                    raise ValueError("RESTORE_TARGET_ALREADY_EXISTS")
                # Non-strict resolve guards against preexisting symlink parents.
                if not target.resolve().is_relative_to(target_root):
                    raise ValueError("RESTORE_PATH_ESCAPE")
                target.parent.mkdir(parents=True,exist_ok=True)
                target.write_bytes(raw)
                restored.append(name.as_posix())
    return {"verified_files":len(files),"source_bytes":total,
            "restored_files":len(restored),"authentication":"NONE_INTERNAL_HASHES_ONLY"}


def main() -> None:
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-root",type=Path,required=True)
    parser.add_argument("--format-catalog",type=Path,default=None)
    parser.add_argument("--output",type=Path,required=True)
    args=parser.parse_args()
    result=run(args.data_root,catalog=args.format_catalog)
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_bytes(json.dumps(result,sort_keys=True,indent=2,ensure_ascii=True,
                                      allow_nan=False).encode("utf-8"))
    print(json.dumps({"schema":SCHEMA,"files":result["files_seen"],
                      "byte_exact":result["files_roundtrip_verified"],
                      "saved_bytes":result["saved_bytes"],
                      "leakage":len(result["cross_dataset_leakage"]),
                      "receipt_hash":result["receipt_hash"]},sort_keys=True))


if __name__=="__main__":
    main()
