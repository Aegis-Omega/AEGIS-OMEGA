# PROJECT STATE: AEGIS-Omega Constitutional Runtime

## REPOSITORY
Branch: claude/aegis-setup-Lx7Ji
Operator: Tarik Skalic (tarikskalic33@gmail.com), Bihac, Bosnia-Herzegovina
Hardware: AMD RX 570, 8GB RAM
License: AGPL-3.0 (Copyright 2025 Tarik Skalic)

## MONOREPO LAYOUT
```
/sovereign-omega-v2/   TypeScript governance runtime (Layer A)
/aegis-cl-psi/         Rust CL-Psi inference crate (6 phases, EU AI Act)
/aegis-runtime/        Rust Seven-Pillar distributed agent runtime
/cockpit/              AI chat UI + telemetry integration
/platform-picker/      Commercial product ($19, Vercel)
/hook-generator/       Commercial product ($19, Vercel)
/content-calendar/     Commercial product ($19, Vercel)
/hub/                  Landing page connecting all 3 products
/packages/shared/      Shared infrastructure (DashScope, hooks, components)
/studio/               AEGIS Studio — constitutional observability (projection only)
```

## COMPLETED GATES (1-200)
All 200 gates complete. 2703 TypeScript tests + 121 aegis-cl-psi Rust + 55 aegis-runtime Rust.
Gate 8 (full test + typecheck + build) PASSES on sovereign-omega-v2.

Key layers built:
- T0: canonicalize (RFC 8785), hashing (SHA-256), ledger chain, WASM replay equivalence
- T1: Martingale (E[S_{n+1}|F_n]=S_n), Fibonacci scheduler, Lyapunov monitor
- T2: BFT swarm consensus (1/phi threshold), multi-model swarm router, CorpusEngine,
      RALPH loop executor, Skill Harness, Federation seams, Simulation stubs,
      CL-Psi 6-phase inference (SGM, LUT-KAN, RWKV-7, DEVS, SAHOO, CCIL),
      Seven-Pillar Rust runtime (StateAnchor, DomainFirewall, AffineCanvas,
      SemanticGraph, ValidationDFA, GossipEmitter, HysteresisFilter),
      Sovereign Cognition Constitution (4 directives, FounderRecord)

## HOLONIC TRIAD (PROVEN)
Same 1/phi = 0.6180339887 threshold governs all three surfaces:
- Martingale: adaptive_ratio > 1/phi -> entropy_bounded=false -> mutation suspended
- SwarmConvergence: vote_count/total > 1/phi -> quorum_reached=true
- SwarmRouter: response agreement > 1/phi -> consensus_response_hash emitted
62/100 > 1/phi (quorum); 61/100 < 1/phi (no quorum)

## CONSTITUTIONAL HASH CHAIN
- Every record: is_replay_reconstructable=true, deepFrozen, hashValue-linked
- FounderRecord: genesis_sequence=0n, constitution_hash seals 4 directives
- TRACEABILITY.md: complete layer-by-layer audit trail (Gates 1-200)

## KEY FILES
- sovereign-omega-v2/src/constitutional/directives.ts  — 4 SovereignDirectives
- sovereign-omega-v2/src/constitutional/founder.ts     — FounderRecord + verify
- sovereign-omega-v2/src/constitutional/martingale.ts  — certifyMartingale()
- sovereign-omega-v2/src/constitutional/reduction.ts   — admitAbstraction() T4/T5 gate
- sovereign-omega-v2/src/consensus/swarm.ts            — tallyVotes() at 1/phi
- sovereign-omega-v2/src/agents/coordination/swarm-router.ts — multi-model BFT routing
- sovereign-omega-v2/src/corpus-engine/pipeline.ts     — processDocument() RALPH pipeline
- sovereign-omega-v2/src/agents/executor/loop.ts       — RalphExecutor Fibonacci-paced
- sovereign-omega-v2/src/skill-harness/catalog.ts      — SkillCatalog
- aegis-runtime/src/lib.rs                             — Seven Pillars entry point
- aegis-cl-psi/src/lib.rs                             — CL-Psi inference crate
- sovereign-omega-v2/python/bridge.py                  — HTTP bridge port 7890

## FROZEN FILES (NEVER MODIFY)
- sovereign-omega-v2/python/gate.py   SHA256: bbe942b819594fd522b421bb9d3aa084735a873d526f35a1e782f31346f3d0fc
- sovereign-omega-v2/python/dna.py    SHA256: cd30ddd5db0403b0e64fb30ce53e0373997fc53cb900a26167eef7d0b69cf8d8
- sovereign-omega-v2/python/router.py SHA256: 8c06ed37a7d95d9de9129c32a426fe5c2b0cd960c2cf5c84c71726b72e6cf941

## ENVIRONMENT VARIABLES (secrets NOT committed)
- VITE_DASHSCOPE_API_KEY — buyer supplies; never commit
- VITE_DASHSCOPE_BASE_URL=https://dashscope-intl.aliyuncs.com/compatible-mode/v1
- VITE_DASHSCOPE_MODEL=qwen-plus (default)
- AEGIS_CHECKPOINT_PATH=/app/data/aegis_checkpoint.json
- SOVEREIGN_BRIDGE_PORT=7890
- AEGIS_GOSSIP_UDP_PORT=9090

## BUILD COMMANDS
```bash
# sovereign-omega-v2 Gate 8
cd sovereign-omega-v2 && npm run test && npm run typecheck && npm run build

# Rust crates
cd aegis-cl-psi && cargo test && cargo build --release
cd aegis-runtime && cargo test && cargo build --release

# Commercial products
cd cockpit && npm install && npm run build
cd platform-picker && npm install && npm run build
cd hook-generator && npm install && npm run build
cd content-calendar && npm install && npm run build
cd hub && npm install && npm run build

# Python bridge
python sovereign-omega-v2/python/bridge.py
```
