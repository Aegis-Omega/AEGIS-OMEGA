# NVIDIA Scientific Substrate v2

Status: **T2 capability/execution-evidence substrate / authority NONE**

This document defines the NVIDIA-facing extension of `POLYGLOT-METACOGNITION-0`.
Catalogue presence is not execution evidence. Execution evidence is not proof,
knowledge admission, physical QPU access, or quantum advantage.

## Connector set

| Connector | AEGIS capability | Detection contract | Authority |
|---|---|---|---|
| NVIDIA Agent Intelligence Toolkit (legacy NAT path) | `AGENT_ORCHESTRATION` | `nat --version` + executable SHA-256 | `NONE` |
| NVIDIA NeMo Platform | `AGENT_PLATFORM` | `nemo --version` + executable SHA-256 | `NONE` |
| NVIDIA NeMo Fabric | `AGENT_RUNTIME_FABRIC` | import `nemo_fabric` + `nemo-fabric` version + module SHA-256 | `NONE` |
| NVIDIA BioNeMo Framework | `BIOMOLECULAR_TRAINING` | import `bionemo.fw` + `bionemo-fw` version + module SHA-256 | `NONE` |
| BioNeMo Inference Runtime (BioIR) | `BIOMOLECULAR_AI` | import `bionemo_ir` + version + module SHA-256 | `NONE` |
| NVIDIA CUDA-Q | `QUANTUM_PROGRAMMING` | package `cudaq` + version + digest | `NONE` |
| NVIDIA cuQuantum | `QUANTUM_SIMULATION` | package `cuquantum-python` / import `cuquantum` + version + digest | `NONE` |

Every admitted connector requires positive detection, a non-empty version,
SHA-256 runtime/module evidence, a SHA-256 capability receipt, and
`AUTHORITY_CLASS=NONE / AUTHORITY_EFFECT=NONE`. Absence fails closed; no mock
backend is synthesized.

## NeMo agent plane

The current agent-plane contract is:

```text
nemo-platform verified
  + nemo-fabric verified
  -> agent_platform.state = READY
```

`READY` is capability readiness only. `agent_platform.execution` remains
`NOT_ESTABLISHED` until an admitted `NvidiaAgentRunReceipt` exists.

Two execution contracts are intentionally separate:

- `NEMO_PLATFORM` requires exactly `nemo-platform + nemo-fabric` evidence.
- `NAT_LEGACY` requires exactly `nvidia-agent-toolkit` evidence.

Legacy NAT evidence cannot satisfy a current NeMo Platform execution receipt.
Successful agent execution remains `knowledge_admission = NOT_ESTABLISHED`.

## BioNeMo stack

BioNeMo Framework and BioNeMo Inference Runtime are distinct capabilities.
Framework presence never implies BioIR availability or GPU execution.

### Framework readiness

```text
bionemo-framework verified
  -> bionemo_stack.framework.state = READY
```

This establishes only the `bionemo.fw` / `bionemo-fw` software capability.
Training execution remains separately evidenced.

### Current agentic inference readiness

```text
nemo-platform verified
  + nemo-fabric verified
  + bionemo-ir verified
  -> bionemo_stack.agentic_inference.state = READY
```

Even at `READY`, both `gpu_execution` and `agent_execution` remain
`NOT_ESTABLISHED` until execution receipts exist.

`BioNemoExecutionReceipt` requires a concrete supported GPU-environment receipt,
BioIR connector evidence, exact task/model/input/output digests and an execution
receipt digest. The GPU receipt explicitly records BioIR driver compatibility;
unsupported driver evidence is denied rather than downgraded silently.

`NvidiaAgenticBioNemoReceipt` composes two independently admitted receipts:

```text
NvidiaAgentRunReceipt(runtime = NEMO_PLATFORM)
  + BioNemoExecutionReceipt(gpu_execution = ESTABLISHED_FOR_THIS_RECEIPT)
  + same task id
  + exact source receipt digests
  + handoff trace digest
  -> NEMO_PLATFORM_BIONEMO_IR
```

The join re-hashes and verifies both source receipts before composition. It
rejects cross-task splicing, stale/wrong receipt digests, legacy NAT substitution,
failed terminal state, malformed handoff evidence and authority-bearing inputs.
The resulting receipt still records `knowledge_admission = NOT_ESTABLISHED`.

## Quantum manifold

In this substrate, “quantum manifold” has a deliberately narrow,
machine-checkable meaning:

```text
CUDA-Q verified
  + cuQuantum verified
  -> CUDAQ_CUQUANTUM_SIMULATION_READY
```

CUDA-Q provides the heterogeneous quantum programming/backend abstraction and
cuQuantum provides NVIDIA quantum-simulation capability. The composite is a
software simulation substrate, not evidence of physical QPU access.

The repository also carries a dedicated live CPU-simulator receipt lane using a
pinned CUDA-Q runtime and `qpp-cpu`. That lane executes a Bell-state sample with
`cudaq.make_kernel()` and emits a digest-bound receipt artifact. It deliberately
does not contact a remote or hardware QPU.

Every simulation-level receipt keeps:

- `qpu_access = NOT_ESTABLISHED`,
- `quantum_advantage = NOT_ESTABLISHED`,
- `authority_scope = DIAGNOSTIC_ONLY`.

A future physical-QPU receipt must be a separate hardware-bound evidence class;
it cannot be inferred from CUDA-Q package presence or simulator success.

## Probe and execution boundaries

Current machine-level NVIDIA boundaries include:

- `NvidiaGpuEnvironmentReceipt`
- `BioNemoExecutionReceipt`
- `CudaQBackendReceipt`
- `NvidiaQuantumExecutionReceipt`
- `NvidiaAgentRunReceipt`
- `NvidiaAgenticBioNemoReceipt`

Probe adapters are shell-free and capability-specific. Runtime observations are
bound to executable/module digests and source receipt digests. Execution
admission performs anti-splicing checks before producing a new receipt.

No NVIDIA receipt directly promotes T2/T3 state into canonical T4 knowledge.
Existing verification/admission gates remain mandatory.

## Upstream references

- NVIDIA BioNeMo Inference Runtime: https://docs.nvidia.com/bionemo/inference-runtime/overview/
- BioNeMo Inference Runtime API: https://docs.nvidia.com/bionemo/inference-runtime/latest/references/api/
- NVIDIA BioNeMo Framework: https://docs.nvidia.com/bionemo-framework/
- NVIDIA NeMo Platform: https://docs.nvidia.com/nemo-platform/
- NVIDIA CUDA-Q: https://nvidia.github.io/cuda-quantum/latest/index.html
- CUDA-Q platform abstraction: https://nvidia.github.io/cuda-quantum/latest/specification/cudaq/platform.html
- NVIDIA cuQuantum: https://developer.nvidia.com/cuquantum
