"""Fail-closed validator for the AEGIS RH spectral/operator registry V1."""
from __future__ import annotations
import json
from pathlib import Path
from typing import Any, Mapping

ALLOWED_CLASSES = {
    "ESTABLISHED_MATH",
    "AEGIS_FORMAL_RESULT",
    "AEGIS_DERIVED_RESULT",
    "CONDITIONAL_THEOREM",
    "OPEN_CONSTRUCTION",
    "ENVIRONMENT_RECEIPT",
    "SECURITY_SUBSTRATE",
}
FORBIDDEN_GENERIC = {"VERIFIED", "PASS"}

class RegistryError(ValueError):
    pass

def load_registry(path: Path) -> dict[str, Any]:
    value=json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value,dict):
        raise RegistryError("top level must be object")
    return value

def validate_registry(registry: Mapping[str,Any]) -> dict[str,Any]:
    if registry.get("schema")!="AEGIS_RH_SPECTRAL_OPERATOR_REGISTRY_V1":
        raise RegistryError("schema")
    if registry.get("authority_effect")!="NONE":
        raise RegistryError("authority leak")
    claims=registry.get("claims")
    if not isinstance(claims,list) or not claims:
        raise RegistryError("claims missing")
    ids=set(); by_id={}
    for claim in claims:
        if not isinstance(claim,dict):
            raise RegistryError("claim not object")
        cid=claim.get("id")
        if not isinstance(cid,str) or not cid or cid in ids:
            raise RegistryError("claim id")
        ids.add(cid); by_id[cid]=claim
        if claim.get("claim_class") not in ALLOWED_CLASSES:
            raise RegistryError(f"{cid}: class")
        if claim.get("status") in FORBIDDEN_GENERIC:
            raise RegistryError(f"{cid}: ambiguous generic status forbidden")

    for cid in (
        "HILBERT_POLYA_OPERATOR_K",
        "FREDHOLM_DET2_CONSTRUCTION",
        "SPECTRAL_IDENTITY_FK_EQ_XI",
    ):
        if by_id[cid].get("claim_class")!="OPEN_CONSTRUCTION":
            raise RegistryError(f"{cid}: must remain open construction")
        if by_id[cid].get("status")!="NOT_ESTABLISHED":
            raise RegistryError(f"{cid}: premature promotion")

    s2=by_id["S2_CONDITIONAL_SPECTRAL_RH"]
    if s2.get("claim_class")!="CONDITIONAL_THEOREM":
        raise RegistryError("S2 must remain conditional")
    if len(s2.get("required_open_premises",[])) < 4:
        raise RegistryError("S2 open premises incomplete")

    upstream=by_id["FORMALCONJECTURES_UPSTREAM_BUILD"]
    if upstream.get("job_count")!=8907 or upstream.get("candidate_binding")!="NOT_ESTABLISHED":
        raise RegistryError("upstream build authority leak")

    disp=registry.get("global_disposition",{})
    if disp.get("rh_proven") is not False:
        raise RegistryError("RH promoted")
    if disp.get("spectral_identity_fk_eq_xi_established") is not False:
        raise RegistryError("spectral identity promoted")
    if disp.get("authority_effect")!="NONE":
        raise RegistryError("global authority leak")

    return {
        "status":"PASS",
        "claim_count":len(ids),
        "open_spectral_targets":3,
        "authority_effect":"NONE",
    }

if __name__=="__main__":
    root=Path(__file__).resolve().parents[2]
    reg=load_registry(root/"governance"/"rh-spectral-operator-registry-v1.json")
    print(json.dumps(validate_registry(reg),sort_keys=True))
