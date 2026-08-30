//! AEGIS-Ω CL-Ψ CLI — JSON inference endpoint
//! EPISTEMIC TIER: T2
//!
//! Reads a JSON payload from stdin, runs one Phase6Orchestrator step,
//! and writes a JSON result to stdout. Called by bridge.py /inference.
//!
//! Usage: aegis_cl_psi --json  (reads JSON from stdin)

use aegis_cl_psi::orchestrator_phase6::Phase6Orchestrator;
use serde::Deserialize;

#[derive(Deserialize)]
struct InferenceRequest {
    #[serde(default)]
    activations: Vec<f32>,
    #[serde(default)]
    observed: Vec<f32>,
    #[serde(default = "default_vocab")]
    vocab_size: usize,
    #[serde(default)]
    blocked: Vec<usize>,
}

fn default_vocab() -> usize {
    32
}

fn main() {
    let args: Vec<String> = std::env::args().collect();
    let json_mode = args.iter().any(|a| a == "--json");

    if !json_mode {
        eprintln!("Usage: aegis_cl_psi --json");
        eprintln!("  Reads JSON from stdin: {{\"activations\":[...], \"observed\":[...], \"vocab_size\": N, \"blocked\":[...]}}");
        std::process::exit(1);
    }

    let mut input = String::new();
    if let Err(e) = std::io::Read::read_to_string(&mut std::io::stdin(), &mut input) {
        let err = serde_json::json!({"status": "error", "reason": format!("stdin read failed: {}", e)});
        println!("{}", err);
        std::process::exit(0);
    }

    let req: InferenceRequest = match serde_json::from_str(&input) {
        Ok(r) => r,
        Err(e) => {
            let err = serde_json::json!({"status": "error", "reason": format!("json parse failed: {}", e)});
            println!("{}", err);
            std::process::exit(0);
        }
    };

    let activations = if req.activations.is_empty() {
        vec![0.1f32; req.vocab_size.max(4)]
    } else {
        req.activations
    };
    let observed = if req.observed.is_empty() {
        activations.clone()
    } else {
        req.observed
    };

    let mut orch = Phase6Orchestrator::new(activations.len(), &req.blocked);
    let output = orch.step(&activations, &observed);

    match serde_json::to_string(&output) {
        Ok(json) => println!("{}", json),
        Err(e) => {
            let err = serde_json::json!({"status": "error", "reason": format!("serialize failed: {}", e)});
            println!("{}", err);
        }
    }
}
