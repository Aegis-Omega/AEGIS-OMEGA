#!/usr/bin/env python3
"""AEGIS Ω Temporal Elasticity Receipt V1 — bounded, fail-closed verifiers.

A PASS validates only the declared evidence receipt. It never grants authority,
releases execution, establishes physical-time deformation, or upgrades the scalar
analytics score. Numerical evidence is carried as decimal strings; JSON floats are
forbidden in signed payloads.
"""
from __future__ import annotations

import base64, binascii, copy, hashlib, json, re, unicodedata
from datetime import datetime
from decimal import Decimal, InvalidOperation, localcontext
from typing import Callable, Mapping

RECEIPT_TYPE = "TEMPORAL_ELASTICITY_RECEIPT_V1"
SPECIFICATION = "AEGIS_OMEGA_TEMPORAL_ELASTICITY_V1"
CLAIM_PROMOTION = "FAIL_CLOSED_OUTSIDE_DECLARED_COMPONENT_BOUNDARIES"
CANONICALIZATION = "AEGIS_JSON_CANONICAL_V1"
HASH_RE = re.compile(r"^[0-9a-f]{64}$")
ML_DSA = {"ML-DSA-44", "ML-DSA-65", "ML-DSA-87"}
SLH_DSA = {
    f"SLH-DSA-{h}-{n}{s}"
    for h in ("SHA2", "SHAKE") for n in (128, 192, 256) for s in ("s", "f")
}
PQVerifier = Callable[[Mapping[str, str], bytes], bool]
ProvenanceVerifier = Callable[[Mapping[str, str]], bool]


def _gate(name, valid, passed, status, value=None, *codes):
    return {"name": name, "evidence_valid": valid, "gate_passed": passed,
            "status": status, "value": value, "reason_codes": list(codes)}


def _fail(name, status, code):
    return _gate(name, False, False, status, None, code)


def _exact(prefix, obj, required, optional=()):
    if not isinstance(obj, Mapping):
        raise ValueError(f"{prefix}_OBJECT_REQUIRED")
    keys, required, optional = set(obj), set(required), set(optional)
    missing, extra = sorted(required - keys), sorted(keys - required - optional)
    if missing:
        raise ValueError(f"{prefix}_MISSING_FIELDS:" + ",".join(missing))
    if extra:
        raise ValueError(f"{prefix}_UNDECLARED_FIELDS:" + ",".join(extra))


def _d(x, code):
    if not isinstance(x, str):
        raise ValueError(code)
    try:
        x = Decimal(x)
    except InvalidOperation as exc:
        raise ValueError(code) from exc
    if not x.is_finite():
        raise ValueError(code)
    return x


def _ds(x):
    if x == 0:
        return "0"
    with localcontext() as ctx:
        ctx.prec = 50
        return str(+x.normalize())


def _series(obj, t_key, v_key, u_key=None, prefix="SERIES"):
    raw_t, raw_v = obj.get(t_key), obj.get(v_key)
    raw_u = obj.get(u_key) if u_key else None
    if not isinstance(raw_t, list) or len(raw_t) < 2:
        raise ValueError(f"{prefix}_TIMES_REQUIRED")
    if not isinstance(raw_v, list) or len(raw_v) != len(raw_t):
        raise ValueError(f"{prefix}_LENGTH_MISMATCH")
    if u_key and (not isinstance(raw_u, list) or len(raw_u) != len(raw_t)):
        raise ValueError(f"{prefix}_LENGTH_MISMATCH")
    t = [_d(x, f"{prefix}_TIME_INVALID") for x in raw_t]
    if not all(b > a for a, b in zip(t, t[1:])):
        raise ValueError(f"{prefix}_TIME_NOT_STRICTLY_INCREASING")
    v = [_d(x, f"{prefix}_VALUE_INVALID") for x in raw_v]
    u = [_d(x, f"{prefix}_UNCERTAINTY_INVALID") for x in raw_u] if u_key else None
    return t, v, u


def canonical_bytes(value):
    def check(v):
        if isinstance(v, float):
            raise TypeError("FLOAT_IN_HASHED_RECEIPT_FORBIDDEN")
        if isinstance(v, Mapping):
            if not all(isinstance(k, str) for k in v):
                raise TypeError("NON_STRING_JSON_KEY")
            for x in v.values(): check(x)
        elif isinstance(v, (list, tuple)):
            for x in v: check(x)
    check(value)
    text = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return unicodedata.normalize("NFC", text).encode()


def signed_payload_bytes(receipt):
    payload = copy.deepcopy(dict(receipt)); payload.pop("integrity", None)
    return canonical_bytes(payload)


def signed_payload_sha256(receipt):
    return hashlib.sha256(signed_payload_bytes(receipt)).hexdigest()


def verify_blp_declared_pair(b):
    name = "BLP_DECLARED_PAIR"
    try:
        _exact("BLP", b, {"state_pair_id","times_s","trace_distances","uncertainties","epsilon"})
        if not str(b["state_pair_id"]).strip(): raise ValueError("BLP_STATE_PAIR_ID_REQUIRED")
        _, values, u = _series(b, "times_s", "trace_distances", "uncertainties", "BLP")
        eps = _d(b["epsilon"], "BLP_EPSILON_INVALID")
        if eps < 0: raise ValueError("BLP_EPSILON_NEGATIVE")
        for x, e in zip(values, u):
            if e < 0: raise ValueError("BLP_UNCERTAINTY_NEGATIVE")
            if x < 0 or x > 1: raise ValueError("BLP_TRACE_DISTANCE_OUT_OF_RANGE")
            if x-e < 0 or x+e > 1: raise ValueError("BLP_CONFIDENCE_INTERVAL_OUT_OF_RANGE")
        lower = sum((max((b1-e1)-(a+e0), Decimal(0))
                     for a,b1,e0,e1 in zip(values,values[1:],u,u[1:])), Decimal(0))
        status = "BLP_BACKFLOW_FOR_DECLARED_PAIR" if lower > eps else "NO_BLP_BACKFLOW_ESTABLISHED"
        return _gate(name, True, True, status, _ds(lower))
    except (ValueError, TypeError) as exc:
        return _fail(name, "BLP_EVIDENCE_INVALID", str(exc))


def verify_spectral_concentration(s):
    name = "SPECTRAL_CONCENTRATION"
    try:
        fields={"concentration_model","convention_id","statistic_id","dimensionless_c","observed","uncertainty","admissible_min","admissible_max","s_c"}
        _exact("SPECTRAL", s, fields)
        if s["concentration_model"] != "SLEPIAN_LANDAU_POLLACK": raise ValueError("SPECTRAL_MODEL_UNSUPPORTED")
        if not str(s["convention_id"]).strip(): raise ValueError("SPECTRAL_CONVENTION_REQUIRED")
        if not str(s["statistic_id"]).strip(): raise ValueError("SPECTRAL_STATISTIC_REQUIRED")
        c,o,u,lo,hi,scale = (_d(s[k], f"SPECTRAL_{k.upper()}_INVALID") for k in ("dimensionless_c","observed","uncertainty","admissible_min","admissible_max","s_c"))
        if c <= 0: raise ValueError("SPECTRAL_C_NONPOSITIVE")
        if u < 0: raise ValueError("SPECTRAL_UNCERTAINTY_NEGATIVE")
        if hi < lo: raise ValueError("SPECTRAL_ADMISSIBLE_INTERVAL_REVERSED")
        if scale <= 0: raise ValueError("SPECTRAL_SCALE_NONPOSITIVE")
        delta = max(lo-(o-u), (o+u)-hi, Decimal(0))/scale
        ok = delta == 0
        return _gate(name, True, ok, "SPECTRAL_CONSISTENT" if ok else "SPECTRAL_CONSISTENCY_FAIL", _ds(delta), *(() if ok else ("SPECTRAL_ADMISSIBLE_REGION_EXCEEDED",)))
    except (ValueError, TypeError) as exc:
        return _fail(name, "SPECTRAL_EVIDENCE_INVALID", str(exc))


def verify_coherence_revival(c):
    name = "COHERENCE_REVIVAL"
    try:
        fields={"coherence_measure","basis","state_estimator","uncertainty_model","times_s","values","uncertainties","value_min","value_max","epsilon"}
        _exact("COHERENCE", c, fields)
        for f in ("coherence_measure","basis","state_estimator","uncertainty_model"):
            if not str(c[f]).strip(): raise ValueError(f"COHERENCE_{f.upper()}_REQUIRED")
        _, values, u = _series(c, "times_s", "values", "uncertainties", "COHERENCE")
        lo,hi,eps = (_d(c[k], f"COHERENCE_{k.upper()}_INVALID") for k in ("value_min","value_max","epsilon"))
        if hi < lo: raise ValueError("COHERENCE_RANGE_REVERSED")
        if eps < 0: raise ValueError("COHERENCE_EPSILON_NEGATIVE")
        for x,e in zip(values,u):
            if e < 0: raise ValueError("COHERENCE_UNCERTAINTY_NEGATIVE")
            if x-e < lo or x+e > hi: raise ValueError("COHERENCE_CONFIDENCE_INTERVAL_OUT_OF_RANGE")
        lower = sum((max((b-e1)-(a+e0), Decimal(0))
                     for a,b,e0,e1 in zip(values,values[1:],u,u[1:])), Decimal(0))
        status = "COHERENCE_REVIVAL_OBSERVED" if lower > eps else "NO_COHERENCE_REVIVAL_ESTABLISHED"
        return _gate(name, True, True, status, _ds(lower))
    except (ValueError, TypeError) as exc:
        return _fail(name, "COHERENCE_EVIDENCE_INVALID", str(exc))


def verify_tau_adaptation(a):
    name = "TAU_ADAPTATION"
    try:
        _exact("TAU", a, {"times_s","tau_values_s","epsilon"})
        _, tau, _ = _series(a, "times_s", "tau_values_s", None, "TAU")
        eps = _d(a["epsilon"], "TAU_EPSILON_INVALID")
        if eps < 0: raise ValueError("TAU_EPSILON_NEGATIVE")
        if any(x <= 0 for x in tau): raise ValueError("TAU_VALUE_NONPOSITIVE")
        with localcontext() as ctx:
            ctx.prec=50; total=sum((abs((b/a0).ln()) for a0,b in zip(tau,tau[1:])), Decimal(0))
        status = "NUMERICAL_TIME_RESOLUTION_ADAPTED" if total > eps else "NO_NUMERICAL_ADAPTATION_OBSERVED"
        return _gate(name, True, True, status, _ds(total))
    except (ValueError, TypeError, InvalidOperation) as exc:
        return _fail(name, "TAU_EVIDENCE_INVALID", str(exc))


def _metadata(r, provenance_verifier):
    name="METADATA"
    required={"receipt_type","receipt_version","specification","epistemic_class","physical_time_deformation","retrocausality","macroscopic_time_reversal","authority_effect","claim_promotion","primary_witness","scalar_score_authority","receipt_id","created_at","source","uncertainty","blp","spectral","coherence","tau_adaptation","integrity"}
    try:
        _exact("RECEIPT", r, required, {"scalar_score"})
        constants={"receipt_type":RECEIPT_TYPE,"receipt_version":"1.0.0","specification":SPECIFICATION,"epistemic_class":"MATHEMATICALLY_BOUNDED_SPECIFICATION","physical_time_deformation":"NOT_CLAIMED","retrocausality":"NOT_ESTABLISHED","macroscopic_time_reversal":"NOT_ESTABLISHED","authority_effect":"NONE","claim_promotion":CLAIM_PROMOTION,"primary_witness":"VECTOR_VALUED","scalar_score_authority":"ANALYTICS_ONLY"}
        for k,v in constants.items():
            if r[k] != v: raise ValueError(f"{k.upper()}_CONTRACT_VIOLATION")
        if not str(r["receipt_id"]).strip(): raise ValueError("RECEIPT_ID_REQUIRED")
        try: dt=datetime.fromisoformat(r["created_at"].replace("Z","+00:00"))
        except Exception as exc: raise ValueError("CREATED_AT_INVALID") from exc
        if dt.tzinfo is None: raise ValueError("CREATED_AT_TIMEZONE_REQUIRED")
        src=r["source"]; _exact("SOURCE",src,{"class","dataset_digest_sha256"},{"provenance_uri","external_admission_receipt_sha256"})
        if src["class"] not in {"SYNTHETIC","SIMULATION","EMPIRICAL"}: raise ValueError("SOURCE_CLASS_INVALID")
        if not HASH_RE.fullmatch(str(src["dataset_digest_sha256"])) or src["dataset_digest_sha256"] == "0"*64: raise ValueError("SOURCE_DATASET_DIGEST_INVALID")
        if src["class"] == "EMPIRICAL":
            if not str(src.get("provenance_uri","")).strip(): raise ValueError("EMPIRICAL_PROVENANCE_URI_REQUIRED")
            ext=src.get("external_admission_receipt_sha256","")
            if not HASH_RE.fullmatch(str(ext)) or ext == "0"*64: raise ValueError("EMPIRICAL_ADMISSION_RECEIPT_REQUIRED")
            if provenance_verifier is None: return _gate(name,True,False,"EMPIRICAL_PROVENANCE_UNVERIFIED",None,"EMPIRICAL_PROVENANCE_VERIFIER_UNAVAILABLE")
            try: admitted=bool(provenance_verifier(dict(src)))
            except Exception: return _gate(name,True,False,"EMPIRICAL_PROVENANCE_UNVERIFIED",None,"EMPIRICAL_PROVENANCE_VERIFICATION_ERROR")
            if not admitted: return _gate(name,True,False,"EMPIRICAL_PROVENANCE_REJECTED",None,"EMPIRICAL_PROVENANCE_REJECTED")
        u=r["uncertainty"]; _exact("UNCERTAINTY",u,{"confidence_level","method"})
        level=_d(u["confidence_level"],"CONFIDENCE_LEVEL_INVALID")
        if not 0 < level < 1: raise ValueError("CONFIDENCE_LEVEL_OUT_OF_RANGE")
        if not str(u["method"]).strip(): raise ValueError("UNCERTAINTY_METHOD_REQUIRED")
        if "scalar_score" in r:
            sc=r["scalar_score"]; _exact("SCALAR_SCORE",sc,{"value","status"})
            if sc["status"] != "ANALYTICS_ONLY": raise ValueError("SCALAR_SCORE_AUTHORITY_VIOLATION")
            _d(sc["value"],"SCALAR_SCORE_VALUE_INVALID")
        return _gate(name,True,True,"METADATA_BOUND",src["class"])
    except (ValueError,TypeError) as exc:
        return _fail(name,"METADATA_INVALID",str(exc))


def _integrity(i, payload, pq_verifier):
    name="INTEGRITY"
    try:
        _exact("INTEGRITY",i,{"canonicalization","digest_algorithm","payload_sha256","signature"})
        if i["canonicalization"] != CANONICALIZATION: raise ValueError("CANONICALIZATION_UNSUPPORTED")
        if i["digest_algorithm"] != "SHA-256": raise ValueError("DIGEST_ALGORITHM_UNSUPPORTED")
        expected=hashlib.sha256(payload).hexdigest(); actual=i["payload_sha256"]
        if not HASH_RE.fullmatch(str(actual)): raise ValueError("PAYLOAD_DIGEST_INVALID")
        if actual != expected: return _gate(name,True,False,"PAYLOAD_DIGEST_MISMATCH",None,"PAYLOAD_DIGEST_MISMATCH")
        sig=i["signature"]; _exact("PQ_SIGNATURE",sig,{"standard","algorithm","parameter_set","key_id","signature_b64"})
        if sig["standard"] == "FIPS_204":
            if sig["algorithm"] != "ML-DSA" or sig["parameter_set"] not in ML_DSA: raise ValueError("FIPS_204_SIGNATURE_PROFILE_INVALID")
        elif sig["standard"] == "FIPS_205":
            if sig["algorithm"] != "SLH-DSA" or sig["parameter_set"] not in SLH_DSA: raise ValueError("FIPS_205_SIGNATURE_PROFILE_INVALID")
        else: raise ValueError("PQ_SIGNATURE_STANDARD_UNSUPPORTED")
        if not str(sig["key_id"]).strip(): raise ValueError("PQ_SIGNATURE_KEY_ID_REQUIRED")
        try: base64.b64decode(sig["signature_b64"],validate=True)
        except (binascii.Error,ValueError,TypeError) as exc: raise ValueError("PQ_SIGNATURE_BASE64_INVALID") from exc
        if pq_verifier is None: return _gate(name,True,False,"PQ_SIGNATURE_UNVERIFIED",None,"PQ_SIGNATURE_VERIFIER_UNAVAILABLE")
        try: ok=bool(pq_verifier(dict(sig),payload))
        except Exception: return _gate(name,True,False,"PQ_SIGNATURE_UNVERIFIED",None,"PQ_SIGNATURE_VERIFICATION_ERROR")
        if not ok: return _gate(name,True,False,"PQ_SIGNATURE_INVALID",None,"PQ_SIGNATURE_INVALID")
        return _gate(name,True,True,"PQ_SIGNATURE_VERIFIED",actual)
    except (ValueError,TypeError) as exc:
        return _fail(name,"INTEGRITY_EVIDENCE_INVALID",str(exc))


def verify_receipt(receipt, *, pq_verifier=None, provenance_verifier=None):
    meta=_metadata(receipt,provenance_verifier)
    get=lambda k: receipt.get(k,{}) if isinstance(receipt,Mapping) else {}
    gates={"metadata":meta,"blp":verify_blp_declared_pair(get("blp")),"spectral":verify_spectral_concentration(get("spectral")),"coherence":verify_coherence_revival(get("coherence")),"tau_adaptation":verify_tau_adaptation(get("tau_adaptation"))}
    try: gates["integrity"]=_integrity(get("integrity"),signed_payload_bytes(receipt),pq_verifier)
    except Exception as exc: gates["integrity"]=_fail("INTEGRITY","INTEGRITY_EVIDENCE_INVALID",type(exc).__name__)
    valid=all(g["evidence_valid"] and g["gate_passed"] for g in gates.values())
    vector=None
    if all(gates[k]["evidence_valid"] for k in ("blp","spectral","coherence","tau_adaptation")):
        vector={"blp_declared_pair_backflow_lower_bound":gates["blp"]["value"],"delta_spectral":gates["spectral"]["value"],"coherence_revival_lower_bound":gates["coherence"]["value"],"a_tau_discrete":gates["tau_adaptation"]["value"]}
    return {"verification":"PASS" if valid else "DENY","temporal_elasticity_witness_valid":valid,"witness_vector":vector,"component_gates":gates,"reason_codes":sorted({c for g in gates.values() for c in g["reason_codes"]}),"execution_release":"BLOCKED","authority_effect":"NONE","physical_time_deformation":"NOT_CLAIMED","retrocausality":"NOT_ESTABLISHED","macroscopic_time_reversal":"NOT_ESTABLISHED","scalar_score_authority":"ANALYTICS_ONLY","claim_promotion":CLAIM_PROMOTION}
