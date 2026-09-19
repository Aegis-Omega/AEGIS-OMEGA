#!/usr/bin/env python3
"""Validate externally anchored proof evidence; this program is NOT a proof checker.

All JSON is UTF-8, duplicate-key/NaN free. Exact object fields are checked except
the upstream lake-manifest object. Commits are 40 lowercase hex; digests are
64 lowercase hex. Subject digest uses sorted compact JSON, ensure_ascii=False.

Subject: repository, source_head, target={declaration, elaborated_type_sha256,
statement_bundle_sha256}, environment={lean_version, mathlib_commit,
dependencies:{package:commit}}. Dependencies excludes mathlib.
Policy: schema=EXACT_TARGET_POLICY_V1, the four Subject fields, allowed_axioms,
required_artifact_roles, replay_adapter={name,commit}, independent_kernel=
{name,version}, trusted_observation_sha256=[digest].
Receipt: schema=EXACT_TARGET_PROOF_RECEIPT_V1, subject, subject_sha256,
evidence_kind=EXECUTED, authority_effect=NONE, artifacts={role:{path,sha256}}.
Observation: schema=EXACT_TARGET_OBSERVATION_V1, subject_sha256,
artifact_sha256={role:digest}, replay_adapter, evidence_kind=EXECUTED,
result=REPLAY_COMPLETED. Its digest must also occur in the policy.

Reports share subject_sha256, declaration, elaborated_type_sha256,
statement_bundle_sha256, proof_export_sha256, result=PASS, native_trust=false.
axiom_report: schema=EXACT_TARGET_AXIOM_REPORT_V1; transitive_axioms=[name].
comparator_report: schema=EXACT_TARGET_COMPARATOR_REPORT_V1;
comparison=EXACT_TARGET. independent_kernel_report:
schema=EXACT_TARGET_KERNEL_REPORT_V1; kernel={name,version},
replay_kind=INDEPENDENT_KERNEL, proof_object_checked=true.
source_tree_manifest: schema=EXACT_TARGET_SOURCE_TREE_V1, source_head,
files={relative_path:digest}; every listed file is hashed.
lean_toolchain: leanprover/lean4:v<lean_version> (optional final whitespace).
lake_manifest: upstream JSON packages list, each with name and rev; its exact
package-to-revision map must equal mathlib plus Subject dependencies. When its
top-level name is mathlib, packages instead equals only Subject dependencies;
the trusted controller binds that root commit in environment.mathlib_commit.

Artifact files must be nonempty regular files, at most 64 MiB each, with clean
relative POSIX paths and no symlink components. Reports are parsed from hashed
artifact bytes. External policy/observation pins MUST come from a trusted
controller, independently of the candidate. Hashes do not authenticate their
issuer; accepting candidate-selected pins destroys this trust boundary. This
gate checks consistency, not Lean/NanoDa execution or source-to-commit ancestry.
Only the independently trusted observation vouches for replay and provenance.
"""

import argparse
import hashlib
import json
import os
import re
import stat
import sys

ROLES = (
    "source_tree_manifest", "lean_toolchain", "lake_manifest", "elaborated_type",
    "statement_bundle", "proof_export", "build_log", "axiom_report",
    "comparator_report", "independent_kernel_report",
)
STANDARD_AXIOMS = frozenset(("propext", "Classical.choice", "Quot.sound"))
SUBJECT_KEYS = {"repository", "source_head", "target", "environment"}
MAX_BYTES = 64 * 1024 * 1024


class GateError(ValueError):
    pass


def require(condition, message):
    if not condition:
        raise GateError(message)


def exact(obj, keys, label):
    require(type(obj) is dict and set(obj) == set(keys), label + ": invalid fields")


def string(value, label):
    require(type(value) is str and bool(value.strip()), label + ": expected nonempty string")
    return value


def hex_value(value, size, label):
    require(type(value) is str and re.fullmatch("[0-9a-f]{" + str(size) + "}", value),
            label + ": invalid lowercase hexadecimal value")
    return value


def strings(value, label):
    require(type(value) is list and all(type(x) is str for x in value), label + ": invalid list")
    require(len(set(value)) == len(value), label + ": duplicate value")
    return value


def digest(data):
    return hashlib.sha256(data).hexdigest()


def canonical(obj):
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False,
                      allow_nan=False).encode("utf-8")


def parse(data, label):
    def pairs(items):
        out = {}
        for key, value in items:
            require(key not in out, label + ": duplicate JSON key " + key)
            out[key] = value
        return out

    def invalid(value):
        raise GateError(label + ": invalid JSON constant " + value)

    try:
        return json.loads(data.decode("utf-8"), object_pairs_hook=pairs, parse_constant=invalid)
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise GateError(label + ": invalid UTF-8 JSON") from exc


def consume(fd, label):
    with os.fdopen(fd, "rb") as stream:
        require(stat.S_ISREG(os.fstat(stream.fileno()).st_mode), label + ": not a regular file")
        data = stream.read(MAX_BYTES + 1)
    require(0 < len(data) <= MAX_BYTES, label + ": empty or exceeds 64 MiB")
    return data


def read_input(path):
    return consume(os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK), str(path))


def relative_parts(path):
    string(path, "artifact path")
    parts = path.split("/")
    require("\\" not in path and ":" not in path and "\x00" not in path and
            all(p not in ("", ".", "..") for p in parts), "unsafe artifact path")
    return parts


def read_artifact(root, path):
    parts = relative_parts(path)
    directory = os.open(root, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        for part in parts[:-1]:
            child = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=directory)
            os.close(directory)
            directory = child
        fd = os.open(parts[-1], os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=directory)
        return consume(fd, path)
    finally:
        os.close(directory)


def validate_subject(subject):
    exact(subject, SUBJECT_KEYS, "subject")
    string(subject["repository"], "repository")
    hex_value(subject["source_head"], 40, "source_head")
    target = subject["target"]
    exact(target, {"declaration", "elaborated_type_sha256", "statement_bundle_sha256"}, "target")
    string(target["declaration"], "declaration")
    for key in ("elaborated_type_sha256", "statement_bundle_sha256"):
        hex_value(target[key], 64, key)
    env = subject["environment"]
    exact(env, {"lean_version", "mathlib_commit", "dependencies"}, "environment")
    require(type(env["lean_version"]) is str and
            re.fullmatch(r"\d+\.\d+\.\d+(?:-rc\d+)?", env["lean_version"]), "invalid Lean version")
    hex_value(env["mathlib_commit"], 40, "mathlib_commit")
    require(type(env["dependencies"]) is dict and "mathlib" not in env["dependencies"],
            "invalid dependencies map")
    for name, commit in env["dependencies"].items():
        string(name, "dependency name")
        hex_value(commit, 40, "dependency commit")


def validate(args):
    hex_value(args.policy_sha256, 64, "policy pin")
    hex_value(args.observation_sha256, 64, "observation pin")
    hex_value(args.expected_head, 40, "expected head")
    policy_bytes = read_input(args.policy)
    require(digest(policy_bytes) == args.policy_sha256, "policy digest does not match external pin")
    policy = parse(policy_bytes, "policy")
    exact(policy, SUBJECT_KEYS | {"schema", "allowed_axioms", "required_artifact_roles",
          "replay_adapter", "independent_kernel", "trusted_observation_sha256"}, "policy")
    require(policy["schema"] == "EXACT_TARGET_POLICY_V1", "unsupported policy schema")
    subject = {key: policy[key] for key in SUBJECT_KEYS}
    validate_subject(subject)
    require(subject["source_head"] == args.expected_head, "stale policy head")
    allowed = strings(policy["allowed_axioms"], "allowed_axioms")
    require(set(allowed) <= STANDARD_AXIOMS, "policy permits nonstandard axiom")
    require(set(strings(policy["required_artifact_roles"], "required_artifact_roles")) == set(ROLES),
            "policy must require every evidence role")
    exact(policy["replay_adapter"], {"name", "commit"}, "replay_adapter")
    string(policy["replay_adapter"]["name"], "adapter name")
    hex_value(policy["replay_adapter"]["commit"], 40, "adapter commit")
    exact(policy["independent_kernel"], {"name", "version"}, "independent_kernel")
    for value in policy["independent_kernel"].values():
        string(value, "kernel identifier")
    observation_pins = strings(policy["trusted_observation_sha256"], "trusted_observation_sha256")
    for pin in observation_pins:
        hex_value(pin, 64, "trusted observation digest")
    require(args.observation_sha256 in observation_pins, "observation is not approved by policy")
    observation_bytes = read_input(args.observation)
    require(digest(observation_bytes) == args.observation_sha256, "observation digest does not match external pin")
    observation = parse(observation_bytes, "observation")
    exact(observation, {"schema", "subject_sha256", "artifact_sha256", "replay_adapter",
                       "evidence_kind", "result"}, "observation")
    require(observation["schema"] == "EXACT_TARGET_OBSERVATION_V1" and
            observation["evidence_kind"] == "EXECUTED" and observation["result"] == "REPLAY_COMPLETED",
            "observation does not attest completed execution")
    require(observation["replay_adapter"] == policy["replay_adapter"], "unapproved replay adapter")
    subject_hash = digest(canonical(subject))
    require(observation["subject_sha256"] == subject_hash, "observation subject mismatch")
    exact(observation["artifact_sha256"], ROLES, "observation artifact digests")
    for value in observation["artifact_sha256"].values():
        hex_value(value, 64, "observed artifact digest")

    receipt = parse(read_input(args.receipt), "receipt")
    exact(receipt, {"schema", "subject", "subject_sha256", "evidence_kind", "authority_effect",
                   "artifacts"}, "receipt")
    require(receipt["schema"] == "EXACT_TARGET_PROOF_RECEIPT_V1", "unsupported receipt schema")
    validate_subject(receipt["subject"])
    require(receipt["subject"] == subject and receipt["subject_sha256"] == subject_hash,
            "receipt does not bind canonical subject")
    require(receipt["evidence_kind"] == "EXECUTED" and receipt["authority_effect"] == "NONE",
            "receipt must be executed evidence with authority_effect NONE")
    exact(receipt["artifacts"], ROLES, "receipt artifacts")
    artifacts, paths = {}, set()
    for role in ROLES:
        entry = receipt["artifacts"][role]
        exact(entry, {"path", "sha256"}, role)
        hex_value(entry["sha256"], 64, role + " digest")
        relative_parts(entry["path"])
        require(entry["path"] not in paths, "artifact roles must have distinct paths")
        paths.add(entry["path"])
        raw = read_artifact(args.evidence_root, entry["path"])
        require(digest(raw) == entry["sha256"] == observation["artifact_sha256"][role],
                role + ": artifact differs from receipt or trusted observation")
        artifacts[role] = raw
    target, env = subject["target"], subject["environment"]
    for role, field in (("elaborated_type", "elaborated_type_sha256"),
                        ("statement_bundle", "statement_bundle_sha256")):
        require(digest(artifacts[role]) == target[field], role + ": canonical target mismatch")
    require(artifacts["lean_toolchain"].decode("utf-8").strip() ==
            "leanprover/lean4:v" + env["lean_version"], "Lean toolchain mismatch")
    manifest = parse(artifacts["lake_manifest"], "lake_manifest")
    require(type(manifest) is dict and type(manifest.get("packages")) is list, "invalid lake_manifest")
    revisions = {}
    for package in manifest["packages"]:
        require(type(package) is dict, "invalid lake package")
        name = string(package.get("name"), "lake package name")
        require(name not in revisions, "duplicate lake package")
        revisions[name] = hex_value(package.get("rev"), 40, "lake package revision")
    expected_revisions = (env["dependencies"] if manifest.get("name") == "mathlib" else
                          {"mathlib": env["mathlib_commit"], **env["dependencies"]})
    require(revisions == expected_revisions,
            "lake dependency commits differ from policy")
    source = parse(artifacts["source_tree_manifest"], "source_tree_manifest")
    exact(source, {"schema", "source_head", "files"}, "source_tree_manifest")
    require(source["schema"] == "EXACT_TARGET_SOURCE_TREE_V1" and source["source_head"] == args.expected_head,
            "source manifest head/schema mismatch")
    require(type(source["files"]) is dict and bool(source["files"]), "empty source tree manifest")
    for path, expected in source["files"].items():
        hex_value(expected, 64, "source file digest")
        require(digest(read_artifact(args.evidence_root, path)) == expected, "source file hash mismatch")

    common = {"subject_sha256": subject_hash, "declaration": target["declaration"],
              "elaborated_type_sha256": target["elaborated_type_sha256"],
              "statement_bundle_sha256": target["statement_bundle_sha256"],
              "proof_export_sha256": digest(artifacts["proof_export"]), "result": "PASS"}
    reports = {}
    extras = {"axiom_report": {"transitive_axioms"}, "comparator_report": {"comparison"},
              "independent_kernel_report": {"kernel", "replay_kind", "proof_object_checked"}}
    schemas = {"axiom_report": "EXACT_TARGET_AXIOM_REPORT_V1",
               "comparator_report": "EXACT_TARGET_COMPARATOR_REPORT_V1",
               "independent_kernel_report": "EXACT_TARGET_KERNEL_REPORT_V1"}
    for role in extras:
        report = parse(artifacts[role], role)
        exact(report, set(common) | {"schema", "native_trust"} | extras[role], role)
        require(report["schema"] == schemas[role] and report["native_trust"] is False,
                role + ": wrong schema or native trust")
        require(all(report[key] == value for key, value in common.items()), role + ": report binding/result mismatch")
        reports[role] = report
    axioms = strings(reports["axiom_report"]["transitive_axioms"], "transitive_axioms")
    require(set(axioms) <= set(allowed), "transitive closure contains unapproved axiom")
    require(reports["comparator_report"]["comparison"] == "EXACT_TARGET", "comparison is not exact target")
    kernel = reports["independent_kernel_report"]
    require(kernel["kernel"] == policy["independent_kernel"] and
            kernel["replay_kind"] == "INDEPENDENT_KERNEL" and kernel["proof_object_checked"] is True,
            "independent proof-object replay missing or wrong kernel")
    return {"status": "PASS_EVIDENCE_VALIDATED", "authority_effect": "NONE",
            "subject_sha256": subject_hash, "source_head": args.expected_head,
            "policy_sha256": args.policy_sha256, "observation_sha256": args.observation_sha256}


class Parser(argparse.ArgumentParser):
    def error(self, message):
        raise GateError(message)


def main(argv=None):
    try:
        parser = Parser(description=__doc__)
        for name in ("receipt", "policy", "policy-sha256", "observation", "observation-sha256",
                     "evidence-root", "expected-head"):
            parser.add_argument("--" + name, required=True)
        result = validate(parser.parse_args(argv))
        code = 0
    except (ValueError, OSError, TypeError, RecursionError) as exc:
        result = {"status": "REJECTED", "authority_effect": "NONE", "reason": str(exc)}
        code = 1
    print(json.dumps(result, sort_keys=True))
    return code


if __name__ == "__main__":
    sys.exit(main())
