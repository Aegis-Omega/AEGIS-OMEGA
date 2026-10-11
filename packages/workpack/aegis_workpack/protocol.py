#!/usr/bin/env python3
"""AEGIS WorkPack v0.1 — offline, read-only, model-neutral work receipt verifier.

Proof boundary: verifies file bytes and narrow structural checks ONLY.
Does not validate science, creative quality, identities or authorization.
"""
import argparse
import csv
import hashlib
import io
import json
import os
from pathlib import Path
import re
import stat
import sys

SCHEMA = "aegis.workpack.v1"
DOMAINS = {"code", "science", "data", "operations", "design", "writing"}
AUTHORITIES = {"read_only", "branch_only", "operator_required"}
SHA256 = re.compile(r"[0-9a-f]{64}\Z")
MAX_ARTIFACT_BYTES = 8 * 1024 * 1024
MAX_MANIFEST_BYTES = 256 * 1024
MAX_ARTIFACTS = 50
MAX_CHECKS = 100


class Invalid(ValueError):
    pass


def require(predicate, reason):
    if not predicate:
        raise Invalid(reason)


def _strict_pairs(pairs):
    result = {}
    for k, v in pairs:
        require(k not in result, "DUPLICATE_JSON_KEY")
        result[k] = v
    return result


def read_json(path, cap=MAX_MANIFEST_BYTES):
    with open(path, "rb") as f:
        raw = f.read(cap + 1)
    require(len(raw) <= cap, "JSON_TOO_LARGE")
    try:
        return json.loads(raw.decode("utf-8"), object_pairs_hook=_strict_pairs,
                          parse_constant=lambda _: (_ for _ in ()).throw(Invalid("NONFINITE_JSON")))
    except (UnicodeDecodeError, json.JSONDecodeError) as e:
        raise Invalid("INVALID_JSON") from e


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True,
                      separators=(",", ":"), allow_nan=False).encode("utf-8")


def sha(value):
    return hashlib.sha256(value).hexdigest()


def valid_path(path):
    return (isinstance(path, str) and 1 <= len(path) <= 240
            and "\\" not in path and not path.startswith("/")
            and all(p not in ("", ".", "..") for p in path.split("/"))
            and not any(ord(c) < 32 for c in path))


def _artifact_bytes(root, name, cap=MAX_ARTIFACT_BYTES):
    """Read a bounded file under workspace without following symlinks.

    POSIX: dirfd + O_NOFOLLOW closes parent-component symlink races.
    Other OS: precheck + read; not race-proof against concurrent writers.
    """
    require(valid_path(name), "ARTIFACT_PATH_INVALID")
    root = Path(root).resolve(strict=True)
    require(root.is_dir(), "ROOT_NOT_DIRECTORY")
    parts = name.split("/")
    if os.name == "posix" and hasattr(os, "O_NOFOLLOW"):
        flags = os.O_RDONLY | os.O_NOFOLLOW
        directory = os.open(root, os.O_RDONLY | os.O_DIRECTORY)
        try:
            for part in parts[:-1]:
                next_fd = os.open(part, flags | os.O_DIRECTORY, dir_fd=directory)
                os.close(directory)
                directory = next_fd
            fd = os.open(parts[-1], flags, dir_fd=directory)
            try:
                require(stat.S_ISREG(os.fstat(fd).st_mode), "ARTIFACT_NOT_REGULAR_FILE")
                with os.fdopen(fd, "rb", closefd=False) as f:
                    raw = f.read(cap + 1)
            finally:
                os.close(fd)
        except OSError as e:
            raise Invalid("UNSAFE_OR_MISSING_ARTIFACT") from e
        finally:
            os.close(directory)
    else:
        current = root
        for i, part in enumerate(parts):
            current = current / part
            mode = os.lstat(current).st_mode
            require(not stat.S_ISLNK(mode), "SYMLINK_FORBIDDEN")
            require(stat.S_ISDIR(mode) if i < len(parts) - 1 else stat.S_ISREG(mode),
                    "ARTIFACT_NOT_REGULAR_FILE")
        with open(current, "rb") as f:
            raw = f.read(cap + 1)
    require(len(raw) <= cap, "ARTIFACT_TOO_LARGE")
    return raw


def validate_contract(contract):
    require(isinstance(contract, dict) and contract.get("schema") == SCHEMA, "SCHEMA_INVALID")
    require(isinstance(contract.get("task_id"), str) and
            re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{2,79}", contract["task_id"]), "TASK_ID_INVALID")
    require(contract.get("domain") in DOMAINS, "DOMAIN_INVALID")
    require(contract.get("authority") in AUTHORITIES, "AUTHORITY_INVALID")
    require(isinstance(contract.get("objective"), str) and
            12 <= len(contract["objective"].strip()) <= 1500, "OBJECTIVE_INVALID")
    prod = contract.get("producer")
    require(isinstance(prod, dict) and isinstance(prod.get("agent"), str) and
            1 <= len(prod["agent"].strip()) <= 128, "PRODUCER_INVALID")
    artifacts = contract.get("artifacts")
    require(isinstance(artifacts, list) and 1 <= len(artifacts) <= MAX_ARTIFACTS, "ARTIFACTS_INVALID")
    paths = set()
    for a in artifacts:
        require(isinstance(a, dict) and valid_path(a.get("path")), "ARTIFACT_PATH_INVALID")
        require(a["path"] not in paths, "DUPLICATE_ARTIFACT")
        paths.add(a["path"])
        require(isinstance(a.get("sha256"), str) and SHA256.fullmatch(a["sha256"]), "ARTIFACT_HASH_INVALID")
    checks = contract.get("checks")
    require(isinstance(checks, list) and 1 <= len(checks) <= MAX_CHECKS, "CHECKS_INVALID")
    ids = set()
    for c in checks:
        require(isinstance(c, dict) and isinstance(c.get("id"), str) and
                re.fullmatch(r"A[1-9][0-9]*", c["id"]) and c["id"] not in ids, "CHECK_ID_INVALID")
        ids.add(c["id"])
        require(c.get("artifact") in paths, "CHECK_ARTIFACT_UNDECLARED")
        require(c.get("kind") in {"sha256", "json_keys", "csv_columns", "text_contains", "independent_review"},
                "CHECK_KIND_UNSUPPORTED")
        if c["kind"] == "json_keys":
            require(isinstance(c.get("keys"), list) and 1 <= len(c["keys"]) <= 50
                    and all(isinstance(x, str) and x for x in c["keys"]), "JSON_KEYS_INVALID")
        if c["kind"] == "csv_columns":
            require(isinstance(c.get("columns"), list) and 1 <= len(c["columns"]) <= 50
                    and all(isinstance(x, str) and x for x in c["columns"])
                    and type(c.get("min_rows")) is int and 0 <= c["min_rows"] <= 100000, "CSV_COLUMNS_INVALID")
        if c["kind"] == "text_contains":
            require(isinstance(c.get("value"), str) and 1 <= len(c["value"]) <= 500,
                    "TEXT_VALUE_INVALID")
    return contract


def _evaluate(check, raw):
    kind = check["kind"]
    if kind == "sha256":
        return "PASS", "BYTE_INTEGRITY_ONLY"
    if kind == "independent_review":
        return "BLOCKED", "AUTHENTICATED_REVIEW_UNAVAILABLE_OFFLINE"
    try:
        text = raw.decode("utf-8")
        if kind == "text_contains":
            return ("PASS", "STRUCTURE_ONLY") if check["value"] in text else ("FAIL", "TEXT_NOT_PRESENT")
        if kind == "json_keys":
            data = json.loads(text, object_pairs_hook=_strict_pairs)
            valid = isinstance(data, dict) and all(k in data for k in check["keys"])
            return ("PASS", "STRUCTURE_ONLY") if valid else ("FAIL", "JSON_KEYS_NOT_PRESENT")
        if kind == "csv_columns":
            reader = csv.reader(io.StringIO(text, newline=""))
            header = next(reader, None)
            require(header and len(set(header)) == len(header), "CSV_HEADER_INVALID")
            count = 0
            for row in reader:
                require(len(row) == len(header), "CSV_ROW_WIDTH_INVALID")
                count += 1
                require(count <= 100000, "CSV_ROW_LIMIT")
            valid = all(k in header for k in check["columns"]) and count >= check["min_rows"]
            return ("PASS", "STRUCTURE_ONLY") if valid else ("FAIL", "CSV_CRITERION_NOT_MET")
    except (UnicodeDecodeError, json.JSONDecodeError, csv.Error, Invalid) as e:
        return "FAIL", str(e) if isinstance(e, Invalid) else "ARTIFACT_PARSE_FAILED"
    return "BLOCKED", "UNSUPPORTED_EVALUATION"


def verify(root, manifest):
    """No writes. A PASS never means independent quality or permission to deploy."""
    report = {"schema": "aegis.workpack.receipt.v1", "authority_effect": "NONE",
              "disposition": "NOT_ADMITTED", "artifact_integrity": "UNVERIFIED",
              "domain_quality": "UNVERIFIED", "checks": [], "artifacts": []}
    try:
        task = validate_contract(manifest)
        report.update({"task_id": task["task_id"], "domain": task["domain"],
                       "contract_sha256": sha(canonical(task)), "authority": task["authority"],
                       "producer_claimed": task["producer"]["agent"]})
        artifacts = {}
        all_match = True
        for entry in task["artifacts"]:
            path = entry["path"]
            try:
                raw = _artifact_bytes(root, path)
                digest = sha(raw)
                ok = digest == entry["sha256"]
                artifacts[path] = raw if ok else None
                report["artifacts"].append({"path": path, "result": "PASS" if ok else "FAIL",
                                            "expected_sha256": entry["sha256"], "actual_sha256": digest})
                all_match &= ok
            except (Invalid, OSError) as e:
                all_match = False
                artifacts[path] = None
                report["artifacts"].append({"path": path, "result": "FAIL", "reason": str(e)})
        report["artifact_integrity"] = "PASS" if all_match else "FAIL"
        # Research is compulsory for delivery readiness. Old v0.1 manifests
        # remain inspectable for artifact integrity, but are NOT complete work.
        from .research_loop import audit_research
        research = audit_research(root, task.get("research"))
        report["research"] = research
        report["delivery_readiness"] = (
            "RESEARCH_AND_FALSIFICATION_REPORTED_UNATTESTED"
            if research["status"] == "LOCAL_PACKET_COMPLETE_UNATTESTED"
            and research.get("falsification_outcome_reported") != "NOT_RUN"
            else "BLOCKED_UNRUN_FALSIFICATION" if
            research["status"] == "LOCAL_PACKET_COMPLETE_UNATTESTED"
            else "BLOCKED_RESEARCH_OR_COMPARISON")
        for check in task["checks"]:
            raw = artifacts.get(check["artifact"])
            if raw is None:
                status, reason = "FAIL", "ARTIFACT_INTEGRITY_NOT_VERIFIED"
            else:
                status, reason = _evaluate(check, raw)
            report["checks"].append({"id": check["id"], "kind": check["kind"],
                                     "artifact": check["artifact"], "result": status, "reason": reason})
        results = [c["result"] for c in report["checks"]]
        report["disposition"] = ("LOCAL_INTEGRITY_AND_STRUCTURE_VERIFIED" if
                                 all_match and all(x == "PASS" for x in results)
                                 else "NOT_ADMITTED")
        report["replayable"] = True
    except (Invalid, OSError, TypeError, ValueError) as e:
        report["reason"] = str(e)
        report["contract"] = "INVALID"
    return report


def cli(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("workspace", help="Directory containing artefacts and manifest.json")
    parser.add_argument("--manifest", default="manifest.json", help="Manifest file in workspace")
    parser.add_argument("--output", help="Optional receipt output path (otherwise stdout)")
    parser.add_argument("--integrity-only", action="store_true",
                        help="Diagnostic backward-compatibility mode; bypasses research delivery requirement")
    ns = parser.parse_args(argv)
    try:
        require(valid_path(ns.manifest), "MANIFEST_PATH_INVALID")
        raw = _artifact_bytes(ns.workspace, ns.manifest, MAX_MANIFEST_BYTES)
        try:
            data = json.loads(raw.decode("utf-8"), object_pairs_hook=_strict_pairs,
                              parse_constant=lambda _: (_ for _ in ()).throw(Invalid("NONFINITE_JSON")))
        except (UnicodeDecodeError, json.JSONDecodeError) as e:
            raise Invalid("INVALID_JSON") from e
        result = verify(ns.workspace, data)
    except (Invalid, OSError) as e:
        result = {"schema": "aegis.workpack.receipt.v1", "disposition": "NOT_ADMITTED",
                  "authority_effect": "NONE", "reason": str(e)}
    rendered = json.dumps(result, indent=2, sort_keys=True) + "\n"
    if ns.output:
        Path(ns.output).write_text(rendered, encoding="utf-8")
    print(rendered, end="")
    return 0 if (result["disposition"] == "LOCAL_INTEGRITY_AND_STRUCTURE_VERIFIED"
                 and (ns.integrity_only or result.get("delivery_readiness") ==
                      "RESEARCH_AND_FALSIFICATION_REPORTED_UNATTESTED")) else 1


if __name__ == "__main__":
    sys.exit(cli())