// AEGIS-Ω cross-runtime replay — Rust re-chainer (sha2 + serde_json, offline crates).
//
// Reads stages.json, rebuilds the lineage from GENESIS with serde_json's canonical
// (BTreeMap-sorted, compact) serialization + SHA-256, and asserts it reproduces the
// Python-declared hashes byte-for-byte. Exit 0 = the genomics certificate replays
// identically on Rust — a third independent runtime.
use serde_json::{json, Value};
use sha2::{Digest, Sha256};
use std::process::exit;

const GENESIS: &str = "0000000000000000000000000000000000000000000000000000000000000000";

// Reject float in hashed state, exactly as Python canon() does — floats are a
// cross-platform non-determinism source.
fn reject_float(v: &Value) {
    match v {
        Value::Number(n) => {
            if n.is_f64() {
                eprintln!("float in hashed state is forbidden (non-deterministic)");
                exit(2);
            }
        }
        Value::Array(a) => a.iter().for_each(reject_float),
        Value::Object(o) => o.values().for_each(reject_float),
        _ => {}
    }
}

// Canonical bytes: serde_json compact form. Objects are BTreeMap-backed (default
// features), so keys emit in sorted order; numbers are integers; non-ASCII is raw
// UTF-8 — matching Python json.dumps(sort_keys=True, separators=(",",":"),
// ensure_ascii=False). The fixture is ASCII, so NFC normalization is the identity.
fn canon(v: &Value) -> Vec<u8> {
    reject_float(v);
    serde_json::to_string(v).expect("serialize").into_bytes()
}

fn sha256hex(bytes: &[u8]) -> String {
    let mut h = Sha256::new();
    h.update(bytes);
    h.finalize().iter().map(|b| format!("{:02x}", b)).collect()
}

fn main() {
    let path = std::env::args().nth(1).unwrap_or_else(|| "../stages.json".to_string());
    let raw = std::fs::read_to_string(&path).expect("read stages.json");
    let fixture: Value = serde_json::from_str(&raw).expect("parse stages.json");
    let stages = fixture["stages"].as_array().expect("stages array");
    let expected = &fixture["expected"];

    let mut prev = GENESIS.to_string();
    let mut stage_hashes: Vec<String> = Vec::new();
    for (i, rec) in stages.iter().enumerate() {
        let payload = json!({
            "stage": rec["stage"],
            "sequence": i,
            "previous_hash": prev,
            "output": rec["output"],
        });
        let h = sha256hex(&canon(&payload));
        stage_hashes.push(h.clone());
        prev = h;
    }

    let exp_terminal = expected["terminal"].as_str().unwrap_or("");
    let exp_stage: Vec<&str> = expected["stage_hashes"]
        .as_array().map(|a| a.iter().filter_map(|x| x.as_str()).collect())
        .unwrap_or_default();

    let ok = prev == exp_terminal
        && stage_hashes.len() == exp_stage.len()
        && stage_hashes.iter().zip(exp_stage.iter()).all(|(g, e)| g == e);

    println!("rust terminal   : {}", prev);
    println!("python terminal : {}", exp_terminal);
    if ok {
        println!("MATCH — genomics certificate replays byte-identically on Rust");
        exit(0);
    } else {
        println!("MISMATCH — cross-runtime divergence");
        exit(1);
    }
}
