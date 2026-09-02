# NVIDIA Scientific Substrate v1

Status: **T2 capability substrate / authority NONE**

This document defines the NVIDIA-facing extension of `POLYGLOT-METACOGNITION-0`.
It is deliberately capability-bound: catalogue presence is not execution evidence,
and execution evidence is not proof, knowledge admission, QPU access, or quantum
advantage.

## Connector set

| Connector | AEGIS capability | Detection contract | Authority |
|---|---|---|---|
| NVIDIA Agent Intelligence Toolkit | `AGENT_ORCHESTRATION` | `nat --version` | `NONE` |
| BioNeMo Inference Runtime (BioIR) | `BIOMOLECULAR_AI` | import `bionemo_ir` + version + executable/package digest | `NONE` |
| NVIDIA CUDA-Q | `QUANTUM_PROGRAMMING` | package `cudaq` + version + digest | `NONE` |
| NVIDIA cuQuantum | `QUANTUM_SIMULATION` | package `cuquantum-python` / import `cuquantum` + version + digest | `NONE` |

Every admitted connector requires:

1. positive detection observation,
2. non-empty version,
3. SHA-256 executable/package digest,
4. SHA-256 capability receipt digest,
5. `AUTHORITY_CLASS=NONE`,
6. `AUTHORITY_EFFECT=NONE`.

Absence fails closed as `TOOLCHAIN_UNAVAILABLE`; no mock backend is synthesized.

## BioNeMo agent fabric

`biomolecular_agent_fabric.state = READY` requires exact verified evidence for
both:

- `nvidia-agent-toolkit`, and
- `bionemo-ir`.

This state means only that the software connector pair is verified and can be
considered by an adapter-specific execution layer. It does **not** establish
that a supported NVIDIA GPU, driver, model weights, NGC credentials, or a
successful BioNeMo inference run exists. Therefore v1 fixes
`gpu_execution = NOT_ESTABLISHED` until a separate hardware/execution receipt
is introduced.

The current NVIDIA BioNeMo Inference Runtime documentation describes BioIR as a
Python library for accelerated biomolecular structure-model inference on NVIDIA
GPUs and documents `bionemo_ir` as the public import namespace. Release wheels
and runtime support remain environment-specific and must be attested separately.

## Quantum manifold

AEGIS previously used “quantum manifold” as a vision-layer term. In this v1
substrate it receives a narrow machine-checkable meaning:

```text
CUDA-Q verified
  + cuQuantum verified
  -> CUDAQ_CUQUANTUM_SIMULATION_READY
```

CUDA-Q supplies the heterogeneous CPU/GPU/QPU programming model and backend
abstraction. cuQuantum supplies GPU-accelerated quantum simulation primitives.
The composite state is therefore a **software simulation substrate**, not a
claim that a physical QPU is connected.

The receipt permanently records in v1:

- `qpu_access = NOT_ESTABLISHED`,
- `quantum_advantage = NOT_ESTABLISHED`,
- `authority_scope = DIAGNOSTIC_ONLY`.

CUDA-Q alone must not establish the composite quantum manifold. cuQuantum alone
must not establish it either.

## Required next receipts for real execution

The next execution slice should introduce adapter-owned, sandbox-produced
receipts rather than widening planner authority:

- `NvidiaGpuEnvironmentReceipt`: GPU identity, compute capability, driver,
  CUDA compatibility, container/runtime digest.
- `BioNemoExecutionReceipt`: exact model/config/input/output digests, GPU
  environment receipt binding, terminal execution state, numerical metadata.
- `CudaQBackendReceipt`: selected CUDA-Q target, simulator/remote/emulated
  classification, backend configuration digest.
- `QuantumExecutionReceipt`: circuit/kernel digest, shots/observables, backend
  identity, simulator/QPU classification, raw result digest.
- `NvidiaAgentRunReceipt`: Agent Toolkit workflow/config/tool graph digests,
  input/output evidence digests and profiler/evaluator metadata.

None of those receipts may directly promote T2/T3 state into canonical T4
knowledge. Existing verification/admission gates remain mandatory.

## Upstream references

- NVIDIA BioNeMo Inference Runtime: https://docs.nvidia.com/bionemo/inference-runtime/overview/
- BioNeMo Python API: https://docs.nvidia.com/bionemo/inference-runtime/latest/references/api/
- NVIDIA CUDA-Q: https://nvidia.github.io/cuda-quantum/latest/index.html
- CUDA-Q quantum platform abstraction: https://nvidia.github.io/cuda-quantum/latest/specification/cudaq/platform.html
- NVIDIA cuQuantum: https://developer.nvidia.com/cuquantum
- NVIDIA documentation hub / Agent Intelligence Toolkit: https://docs.nvidia.com/
