//! AEGIS-Ω / NVIDIA Jetson deterministic execution contract.
//!
//! EPISTEMIC TIER: T2 (engineering implementation; target-hardware admission remains T1 evidence).
//!
//! This module encodes the fail-closed invariants for the Jetson pipeline:
//!
//! Sensor/NVMM -> NNDAL -> CUDA -> TensorRT -> RAGC -> SGM -> Receipt.
//!
//! It deliberately separates:
//! - CUDA IPC from NVMM/dma-buf transport;
//! - target-local TensorRT engine construction from portable model artifacts;
//! - the deterministic hard-real-time plane from the non-authoritative agent plane;
//! - a conversation/design contract from target-hardware execution evidence.
//!
//! No target is promoted merely because a manifest says `PASSED`. Admission requires
//! a complete conjunction of independently verified gates and a receipt whose digest
//! commits to the measured evidence.

use serde::{Deserialize, Serialize};
use sha2::{Digest, Sha256};
use std::fmt;

pub const HELLINGER_SCALE_PPB: u64 = 1_000_000_000;
pub const ORIN_SM: u16 = 87;
pub const RAGC_BUDGET_US: u64 = 15_000;
pub const END_TO_END_BUDGET_US: u64 = 50_000;

#[derive(Clone, Copy, Debug, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "SCREAMING_SNAKE_CASE")]
pub enum JetsonSku {
    OrinNanoSuper8Gb,
    OrinNx8Gb,
    OrinNx16Gb,
}

impl JetsonSku {
    pub fn expected_sm(self) -> u16 { ORIN_SM }

    /// Power envelopes accepted by the architecture. The actual `nvpmodel` mode ID
    /// is discovered at runtime and is never hard-coded here.
    pub fn allowed_power_watts(self) -> &'static [u16] {
        match self {
            Self::OrinNanoSuper8Gb => &[25],
            Self::OrinNx8Gb => &[40],
            Self::OrinNx16Gb => &[25, 40],
        }
    }

    pub fn accepts_power_watts(self, watts: u16) -> bool {
        self.allowed_power_watts().contains(&watts)
    }
}

#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
pub struct NvpModelProbe {
    pub raw_output_digest: String,
    pub mode_name: String,
    pub mode_id: Option<u32>,
}

impl NvpModelProbe {
    /// Parse the stable semantic fields from `nvpmodel -q` output without assuming
    /// that a mode number is identical across JetPack/L4T releases or SKUs.
    pub fn parse(output: &str) -> Result<Self, JetsonContractError> {
        if output.trim().is_empty() {
            return Err(JetsonContractError::EmptyNvpModelOutput);
        }

        let mut mode_name = None;
        let mut mode_id = None;

        for line in output.lines().map(str::trim) {
            if let Some((_, value)) = line.split_once("NV Power Mode:") {
                let value = value.trim();
                if !value.is_empty() { mode_name = Some(value.to_owned()); }
            }

            let lower = line.to_ascii_lowercase();
            if lower.contains("mode id") {
                if let Some(value) = line.split(':').nth(1) {
                    mode_id = value.trim().parse::<u32>().ok();
                }
            }
        }

        let mode_name = mode_name.ok_or(JetsonContractError::MissingNvpModelModeName)?;
        Ok(Self {
            raw_output_digest: sha256_hex(output.as_bytes()),
            mode_name,
            mode_id,
        })
    }
}

#[derive(Clone, Copy, Debug, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "SCREAMING_SNAKE_CASE")]
pub enum ZeroCopyKind {
    CudaIpc,
    NvmmDmaBuf,
    CudaDevice,
    CudaUnified,
}

#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
pub struct ZeroCopyDescriptor {
    pub kind: ZeroCopyKind,
    pub allocation_id: u64,
    pub bytes: u64,
    pub device_id: i32,
    pub dmabuf_fd: Option<i32>,
    /// SHA-256 of the opaque CUDA IPC handle bytes; the raw handle is never persisted.
    pub ipc_handle_digest: Option<String>,
    pub producer_event_id: u64,
    pub lineage_sequence: u64,
}

impl ZeroCopyDescriptor {
    pub fn validate(&self) -> Result<(), JetsonContractError> {
        if self.allocation_id == 0 { return Err(JetsonContractError::InvalidAllocationId); }
        if self.bytes == 0 { return Err(JetsonContractError::ZeroSizedBuffer); }
        if self.device_id < 0 { return Err(JetsonContractError::InvalidDeviceId); }
        if self.producer_event_id == 0 { return Err(JetsonContractError::InvalidProducerEvent); }

        match self.kind {
            ZeroCopyKind::CudaIpc => {
                if self.dmabuf_fd.is_some() {
                    return Err(JetsonContractError::BackendFieldCollision);
                }
                validate_sha256(self.ipc_handle_digest.as_deref().ok_or(
                    JetsonContractError::MissingCudaIpcHandleDigest,
                )?)?;
            }
            ZeroCopyKind::NvmmDmaBuf => {
                let fd = self.dmabuf_fd.ok_or(JetsonContractError::MissingDmaBufFd)?;
                if fd < 0 { return Err(JetsonContractError::InvalidDmaBufFd); }
                if self.ipc_handle_digest.is_some() {
                    return Err(JetsonContractError::BackendFieldCollision);
                }
            }
            ZeroCopyKind::CudaDevice | ZeroCopyKind::CudaUnified => {
                if self.dmabuf_fd.is_some() || self.ipc_handle_digest.is_some() {
                    return Err(JetsonContractError::BackendFieldCollision);
                }
            }
        }
        Ok(())
    }
}

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum LeaseState {
    Produced,
    ProducerComplete,
    ConsumerWaiting,
    ConsumerReleased,
    ProducerDestroyed,
}

/// Runtime state machine enforcing:
/// consumer_release < producer_destroy and
/// ProducerComplete(e_p) && StreamWait(e_p) => ConsumerReadSafe.
#[derive(Clone, Debug)]
pub struct BufferLease {
    descriptor: ZeroCopyDescriptor,
    state: LeaseState,
    waited_event_id: Option<u64>,
}

impl BufferLease {
    pub fn new(descriptor: ZeroCopyDescriptor) -> Result<Self, JetsonContractError> {
        descriptor.validate()?;
        Ok(Self { descriptor, state: LeaseState::Produced, waited_event_id: None })
    }

    pub fn descriptor(&self) -> &ZeroCopyDescriptor { &self.descriptor }
    pub fn state(&self) -> LeaseState { self.state }

    pub fn mark_producer_complete(&mut self, event_id: u64) -> Result<(), JetsonContractError> {
        if self.state != LeaseState::Produced {
            return Err(JetsonContractError::InvalidLeaseTransition {
                from: self.state,
                action: "mark_producer_complete",
            });
        }
        if event_id != self.descriptor.producer_event_id {
            return Err(JetsonContractError::ProducerEventMismatch);
        }
        self.state = LeaseState::ProducerComplete;
        Ok(())
    }

    pub fn consumer_stream_wait(&mut self, event_id: u64) -> Result<(), JetsonContractError> {
        if self.state != LeaseState::ProducerComplete {
            return Err(JetsonContractError::InvalidLeaseTransition {
                from: self.state,
                action: "consumer_stream_wait",
            });
        }
        if event_id != self.descriptor.producer_event_id {
            return Err(JetsonContractError::ProducerEventMismatch);
        }
        self.waited_event_id = Some(event_id);
        self.state = LeaseState::ConsumerWaiting;
        Ok(())
    }

    pub fn consumer_read_safe(&self) -> bool {
        matches!(self.state, LeaseState::ConsumerWaiting | LeaseState::ConsumerReleased)
            && self.waited_event_id == Some(self.descriptor.producer_event_id)
    }

    pub fn consumer_release(&mut self) -> Result<(), JetsonContractError> {
        if self.state != LeaseState::ConsumerWaiting || !self.consumer_read_safe() {
            return Err(JetsonContractError::InvalidLeaseTransition {
                from: self.state,
                action: "consumer_release",
            });
        }
        self.state = LeaseState::ConsumerReleased;
        Ok(())
    }

    pub fn producer_destroy(&mut self) -> Result<(), JetsonContractError> {
        if self.state != LeaseState::ConsumerReleased {
            return Err(JetsonContractError::ProducerDestroyBeforeConsumerRelease);
        }
        self.state = LeaseState::ProducerDestroyed;
        Ok(())
    }
}

#[derive(Clone, Copy, Debug, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "SCREAMING_SNAKE_CASE")]
pub enum TensorRtPrecision {
    Fp16,
    Int8Qat,
    Int4WeightOnly,
    Fp8,
}

#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
pub struct TensorRtEngineManifest {
    pub engine_id: String,
    pub target_sku: JetsonSku,
    pub target_sm: u16,
    pub target_local_build: bool,
    pub precision: TensorRtPrecision,
    pub explicit_qdq: bool,
    pub unsupported_precision_fallbacks: u32,
    pub model_digest: String,
    pub onnx_digest: String,
    pub plugin_digest: String,
    pub engine_digest: String,
    pub calibration_digest: String,
    /// Signed parts-per-million accuracy delta against the accepted baseline.
    pub accuracy_delta_ppm: i64,
    pub max_accuracy_loss_ppm: u64,
    pub latency_p99_us: u64,
}

impl TensorRtEngineManifest {
    pub fn validate(&self) -> Result<(), JetsonContractError> {
        if self.engine_id.trim().is_empty() {
            return Err(JetsonContractError::EmptyEngineId);
        }
        if !self.target_local_build {
            return Err(JetsonContractError::EngineNotTargetLocal);
        }
        if self.target_sm != self.target_sku.expected_sm() {
            return Err(JetsonContractError::ComputeCapabilityMismatch);
        }
        if self.precision == TensorRtPrecision::Fp8 {
            return Err(JetsonContractError::Fp8UnsupportedOnOrin);
        }
        if matches!(self.precision, TensorRtPrecision::Int8Qat | TensorRtPrecision::Int4WeightOnly)
            && !self.explicit_qdq
        {
            return Err(JetsonContractError::ExplicitQdqRequired);
        }
        if self.unsupported_precision_fallbacks != 0 {
            return Err(JetsonContractError::UnsupportedPrecisionFallback);
        }
        for digest in [
            &self.model_digest,
            &self.onnx_digest,
            &self.plugin_digest,
            &self.engine_digest,
            &self.calibration_digest,
        ] {
            validate_sha256(digest)?;
        }
        if self.accuracy_delta_ppm < -(self.max_accuracy_loss_ppm as i64) {
            return Err(JetsonContractError::AccuracyRegressionExceeded);
        }
        if self.latency_p99_us > END_TO_END_BUDGET_US {
            return Err(JetsonContractError::EngineLatencyBudgetExceeded);
        }
        Ok(())
    }
}

#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
pub struct SgmPolicy {
    pub revision: String,
    pub max_hellinger_squared_ppb: u64,
    pub max_latency_p99_us: u64,
    pub max_temperature_millicelsius: u32,
}

#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
struct SgmReceiptBody {
    engine_digest: String,
    input_digest: String,
    output_digest: String,
    hellinger_squared_ppb: u64,
    latency_p99_us: u64,
    temperature_millicelsius: u32,
    policy_revision: String,
    accepted: bool,
}

#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
pub struct SgmCertificate {
    pub engine_digest: String,
    pub input_digest: String,
    pub output_digest: String,
    pub hellinger_squared_ppb: u64,
    pub latency_p99_us: u64,
    pub temperature_millicelsius: u32,
    pub policy_revision: String,
    pub accepted: bool,
    pub receipt_hash: String,
}

impl SgmCertificate {
    pub fn issue(
        engine_digest: String,
        input_digest: String,
        output_digest: String,
        baseline_distribution: &[u64],
        candidate_distribution: &[u64],
        latency_p99_us: u64,
        temperature_millicelsius: u32,
        policy: &SgmPolicy,
    ) -> Result<Self, JetsonContractError> {
        validate_sha256(&engine_digest)?;
        validate_sha256(&input_digest)?;
        validate_sha256(&output_digest)?;
        if policy.revision.trim().is_empty() {
            return Err(JetsonContractError::EmptyPolicyRevision);
        }

        let hellinger_squared_ppb =
            hellinger_squared_ppb(baseline_distribution, candidate_distribution)?;
        let accepted = hellinger_squared_ppb <= policy.max_hellinger_squared_ppb
            && latency_p99_us <= policy.max_latency_p99_us
            && temperature_millicelsius <= policy.max_temperature_millicelsius;

        let body = SgmReceiptBody {
            engine_digest: engine_digest.clone(),
            input_digest: input_digest.clone(),
            output_digest: output_digest.clone(),
            hellinger_squared_ppb,
            latency_p99_us,
            temperature_millicelsius,
            policy_revision: policy.revision.clone(),
            accepted,
        };
        let bytes = serde_json::to_vec(&body)
            .map_err(|_| JetsonContractError::ReceiptSerializationFailed)?;
        let receipt_hash = sha256_hex(&bytes);

        Ok(Self {
            engine_digest,
            input_digest,
            output_digest,
            hellinger_squared_ppb,
            latency_p99_us,
            temperature_millicelsius,
            policy_revision: policy.revision.clone(),
            accepted,
            receipt_hash,
        })
    }

    pub fn verify_receipt(&self) -> Result<bool, JetsonContractError> {
        let body = SgmReceiptBody {
            engine_digest: self.engine_digest.clone(),
            input_digest: self.input_digest.clone(),
            output_digest: self.output_digest.clone(),
            hellinger_squared_ppb: self.hellinger_squared_ppb,
            latency_p99_us: self.latency_p99_us,
            temperature_millicelsius: self.temperature_millicelsius,
            policy_revision: self.policy_revision.clone(),
            accepted: self.accepted,
        };
        let bytes = serde_json::to_vec(&body)
            .map_err(|_| JetsonContractError::ReceiptSerializationFailed)?;
        Ok(sha256_hex(&bytes) == self.receipt_hash)
    }
}

/// Deterministic integer projection of H²(P,Q), scaled to 1e9.
/// Floating point is used only inside this measurement function; the persisted
/// and hashed value is the rounded integer projection.
pub fn hellinger_squared_ppb(p: &[u64], q: &[u64]) -> Result<u64, JetsonContractError> {
    if p.is_empty() || q.is_empty() || p.len() != q.len() {
        return Err(JetsonContractError::DistributionShapeMismatch);
    }
    let p_total: u128 = p.iter().map(|&v| v as u128).sum();
    let q_total: u128 = q.iter().map(|&v| v as u128).sum();
    if p_total == 0 || q_total == 0 {
        return Err(JetsonContractError::ZeroMassDistribution);
    }

    let mut sum = 0.0f64;
    for (&pv, &qv) in p.iter().zip(q.iter()) {
        let pn = (pv as f64) / (p_total as f64);
        let qn = (qv as f64) / (q_total as f64);
        let delta = pn.sqrt() - qn.sqrt();
        sum += delta * delta;
    }
    let h2 = (0.5 * sum).clamp(0.0, 1.0);
    Ok((h2 * HELLINGER_SCALE_PPB as f64).round() as u64)
}

#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
pub struct JetsonAdmissionEvidence {
    pub scope_match: bool,
    pub nvpmodel_profile_valid: bool,
    pub preempt_rt_gate_passed: bool,
    pub zero_copy_verified: bool,
    pub host_memcpy_in_critical_path: u32,
    pub buffer_reallocations_after_warmup: u32,
    pub dma_sync_errors: u32,
    pub lifecycle_violations: u32,
    pub precision_supported: bool,
    pub target_local_engine: bool,
    pub engine_hash_bound: bool,
    pub unsupported_precision_fallbacks: u32,
    pub ragc_window_p99_us: u64,
    pub end_to_end_p99_us: u64,
    pub thermal_throttle_events: u32,
    pub deadline_misses: u32,
    pub sgm_certificate_valid: bool,
    pub sgm_accepted: bool,
    pub replay_verified: bool,
    pub agent_plane_blocks_hard_path: bool,
}

impl JetsonAdmissionEvidence {
    pub fn admit(&self) -> bool {
        self.scope_match
            && self.nvpmodel_profile_valid
            && self.preempt_rt_gate_passed
            && self.zero_copy_verified
            && self.host_memcpy_in_critical_path == 0
            && self.buffer_reallocations_after_warmup == 0
            && self.dma_sync_errors == 0
            && self.lifecycle_violations == 0
            && self.precision_supported
            && self.target_local_engine
            && self.engine_hash_bound
            && self.unsupported_precision_fallbacks == 0
            && self.ragc_window_p99_us <= RAGC_BUDGET_US
            && self.end_to_end_p99_us <= END_TO_END_BUDGET_US
            && self.thermal_throttle_events == 0
            && self.deadline_misses == 0
            && self.sgm_certificate_valid
            && self.sgm_accepted
            && self.replay_verified
            && !self.agent_plane_blocks_hard_path
    }
}

pub fn sha256_hex(bytes: &[u8]) -> String {
    let digest = Sha256::digest(bytes);
    let mut out = String::with_capacity(64);
    for byte in digest { out.push_str(&format!("{byte:02x}")); }
    out
}

fn validate_sha256(value: &str) -> Result<(), JetsonContractError> {
    let value = value.strip_prefix("sha256:").unwrap_or(value);
    if value.len() != 64 || !value.bytes().all(|b| b.is_ascii_hexdigit()) {
        return Err(JetsonContractError::InvalidSha256Digest);
    }
    Ok(())
}

#[derive(Clone, Debug, PartialEq, Eq)]
pub enum JetsonContractError {
    EmptyNvpModelOutput,
    MissingNvpModelModeName,
    InvalidAllocationId,
    ZeroSizedBuffer,
    InvalidDeviceId,
    InvalidProducerEvent,
    MissingCudaIpcHandleDigest,
    MissingDmaBufFd,
    InvalidDmaBufFd,
    BackendFieldCollision,
    InvalidSha256Digest,
    InvalidLeaseTransition { from: LeaseState, action: &'static str },
    ProducerEventMismatch,
    ProducerDestroyBeforeConsumerRelease,
    EmptyEngineId,
    EngineNotTargetLocal,
    ComputeCapabilityMismatch,
    Fp8UnsupportedOnOrin,
    ExplicitQdqRequired,
    UnsupportedPrecisionFallback,
    AccuracyRegressionExceeded,
    EngineLatencyBudgetExceeded,
    EmptyPolicyRevision,
    DistributionShapeMismatch,
    ZeroMassDistribution,
    ReceiptSerializationFailed,
}

impl fmt::Display for JetsonContractError {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        write!(f, "{self:?}")
    }
}
impl std::error::Error for JetsonContractError {}

#[cfg(test)]
mod tests {
    use super::*;

    fn d(ch: char) -> String { ch.to_string().repeat(64) }

    fn valid_ipc_descriptor() -> ZeroCopyDescriptor {
        ZeroCopyDescriptor {
            kind: ZeroCopyKind::CudaIpc,
            allocation_id: 1,
            bytes: 4096,
            device_id: 0,
            dmabuf_fd: None,
            ipc_handle_digest: Some(d('a')),
            producer_event_id: 7,
            lineage_sequence: 1,
        }
    }

    fn valid_manifest(precision: TensorRtPrecision) -> TensorRtEngineManifest {
        TensorRtEngineManifest {
            engine_id: "lut-kan-orin-v1".into(),
            target_sku: JetsonSku::OrinNanoSuper8Gb,
            target_sm: ORIN_SM,
            target_local_build: true,
            precision,
            explicit_qdq: true,
            unsupported_precision_fallbacks: 0,
            model_digest: d('1'),
            onnx_digest: d('2'),
            plugin_digest: d('3'),
            engine_digest: d('4'),
            calibration_digest: d('5'),
            accuracy_delta_ppm: -1_000,
            max_accuracy_loss_ppm: 10_000,
            latency_p99_us: 10_000,
        }
    }

    #[test]
    fn nvpmodel_probe_does_not_assume_mode_id() {
        let p = NvpModelProbe::parse("NV Power Mode: MAXN_SUPER\nMODE ID: 2\n").unwrap();
        assert_eq!(p.mode_name, "MAXN_SUPER");
        assert_eq!(p.mode_id, Some(2));
        assert_eq!(p.raw_output_digest.len(), 64);
    }

    #[test]
    fn sku_power_envelopes_are_separate() {
        assert!(JetsonSku::OrinNanoSuper8Gb.accepts_power_watts(25));
        assert!(!JetsonSku::OrinNanoSuper8Gb.accepts_power_watts(40));
        assert!(JetsonSku::OrinNx8Gb.accepts_power_watts(40));
        assert!(JetsonSku::OrinNx16Gb.accepts_power_watts(25));
        assert!(JetsonSku::OrinNx16Gb.accepts_power_watts(40));
    }

    #[test]
    fn cuda_ipc_and_nvmm_fields_cannot_mix() {
        let mut desc = valid_ipc_descriptor();
        desc.dmabuf_fd = Some(3);
        assert_eq!(desc.validate(), Err(JetsonContractError::BackendFieldCollision));
    }

    #[test]
    fn nvmm_requires_a_valid_dma_buf_fd() {
        let desc = ZeroCopyDescriptor {
            kind: ZeroCopyKind::NvmmDmaBuf,
            allocation_id: 2,
            bytes: 8192,
            device_id: 0,
            dmabuf_fd: Some(5),
            ipc_handle_digest: None,
            producer_event_id: 8,
            lineage_sequence: 2,
        };
        assert!(desc.validate().is_ok());
    }

    #[test]
    fn producer_cannot_destroy_before_consumer_release() {
        let mut lease = BufferLease::new(valid_ipc_descriptor()).unwrap();
        lease.mark_producer_complete(7).unwrap();
        lease.consumer_stream_wait(7).unwrap();
        assert!(lease.consumer_read_safe());
        assert_eq!(
            lease.producer_destroy(),
            Err(JetsonContractError::ProducerDestroyBeforeConsumerRelease)
        );
    }

    #[test]
    fn lease_happy_path_enforces_ordering() {
        let mut lease = BufferLease::new(valid_ipc_descriptor()).unwrap();
        lease.mark_producer_complete(7).unwrap();
        lease.consumer_stream_wait(7).unwrap();
        lease.consumer_release().unwrap();
        lease.producer_destroy().unwrap();
        assert_eq!(lease.state(), LeaseState::ProducerDestroyed);
    }

    #[test]
    fn consumer_wait_requires_matching_producer_event() {
        let mut lease = BufferLease::new(valid_ipc_descriptor()).unwrap();
        lease.mark_producer_complete(7).unwrap();
        assert_eq!(
            lease.consumer_stream_wait(9),
            Err(JetsonContractError::ProducerEventMismatch)
        );
    }

    #[test]
    fn fp8_is_fail_closed_on_orin() {
        assert_eq!(
            valid_manifest(TensorRtPrecision::Fp8).validate(),
            Err(JetsonContractError::Fp8UnsupportedOnOrin)
        );
    }

    #[test]
    fn int4_requires_explicit_qdq() {
        let mut manifest = valid_manifest(TensorRtPrecision::Int4WeightOnly);
        manifest.explicit_qdq = false;
        assert_eq!(manifest.validate(), Err(JetsonContractError::ExplicitQdqRequired));
    }

    #[test]
    fn target_local_int4_manifest_passes() {
        assert!(valid_manifest(TensorRtPrecision::Int4WeightOnly).validate().is_ok());
    }

    #[test]
    fn identical_distributions_have_zero_hellinger_distance() {
        assert_eq!(hellinger_squared_ppb(&[1, 2, 3], &[1, 2, 3]).unwrap(), 0);
    }

    #[test]
    fn disjoint_distributions_have_max_hellinger_distance() {
        assert_eq!(
            hellinger_squared_ppb(&[1, 0], &[0, 1]).unwrap(),
            HELLINGER_SCALE_PPB
        );
    }

    #[test]
    fn sgm_receipt_is_deterministic_and_replay_verifiable() {
        let policy = SgmPolicy {
            revision: "policy:v1".into(),
            max_hellinger_squared_ppb: 10_000_000,
            max_latency_p99_us: END_TO_END_BUDGET_US,
            max_temperature_millicelsius: 75_000,
        };
        let issue = || SgmCertificate::issue(
            d('a'), d('b'), d('c'),
            &[100, 200], &[100, 200],
            12_000, 60_000, &policy,
        ).unwrap();
        let a = issue();
        let b = issue();
        assert!(a.accepted);
        assert_eq!(a.receipt_hash, b.receipt_hash);
        assert!(a.verify_receipt().unwrap());
    }

    #[test]
    fn sgm_rejects_excessive_distribution_shift() {
        let policy = SgmPolicy {
            revision: "policy:v1".into(),
            max_hellinger_squared_ppb: 100,
            max_latency_p99_us: END_TO_END_BUDGET_US,
            max_temperature_millicelsius: 75_000,
        };
        let cert = SgmCertificate::issue(
            d('a'), d('b'), d('c'),
            &[1, 0], &[0, 1],
            12_000, 60_000, &policy,
        ).unwrap();
        assert!(!cert.accepted);
        assert!(cert.verify_receipt().unwrap());
    }

    #[test]
    fn admission_is_a_strict_conjunction() {
        let mut evidence = JetsonAdmissionEvidence {
            scope_match: true,
            nvpmodel_profile_valid: true,
            preempt_rt_gate_passed: true,
            zero_copy_verified: true,
            host_memcpy_in_critical_path: 0,
            buffer_reallocations_after_warmup: 0,
            dma_sync_errors: 0,
            lifecycle_violations: 0,
            precision_supported: true,
            target_local_engine: true,
            engine_hash_bound: true,
            unsupported_precision_fallbacks: 0,
            ragc_window_p99_us: RAGC_BUDGET_US,
            end_to_end_p99_us: END_TO_END_BUDGET_US,
            thermal_throttle_events: 0,
            deadline_misses: 0,
            sgm_certificate_valid: true,
            sgm_accepted: true,
            replay_verified: true,
            agent_plane_blocks_hard_path: false,
        };
        assert!(evidence.admit());
        evidence.deadline_misses = 1;
        assert!(!evidence.admit());
    }
}
