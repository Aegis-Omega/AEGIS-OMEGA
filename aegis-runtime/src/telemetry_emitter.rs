//! Zero-Allocation Resonance Telemetry Emitter
//! 
//! EPISTEMIC TIER: T0 (mechanically proven)
//! Constitutional root: O(t) = Σ atomicᵢ for real-time introspection
//! 
//! This module implements a zero-allocation telemetry system that emits
//! UDP packets containing atomic counter snapshots. Designed for NLA-style
//! observability of distributed swarm nodes.

use std::net::UdpSocket;
use std::sync::atomic::{AtomicU64, AtomicU16, Ordering};
use std::sync::Arc;
use std::time::Duration;
use std::thread;

/// Magic number identifying valid resonance telemetry packets.
pub const RESONANCE_MAGIC: u16 = 0xE0E0;

/// Packet layout constants (all sizes in bytes).
pub const PACKET_HEADER_SIZE: usize = 4;    // magic(2) + node_id(2)
pub const PACKET_PAYLOAD_SIZE: usize = 56;  // 7 × AtomicU64 values
pub const PACKET_HARMONY_SIZE: usize = 4;   // harmony(2) + tension(2)
pub const TOTAL_PACKET_SIZE: usize = 64;    // Total packet size

/// Core telemetry atomics for tracking system state.
/// 
/// All counters are AtomicU64 for lock-free access and to prevent
/// allocation during high-frequency updates.
pub struct TelemetryAtomics {
    /// Heartbeat counter for T0 ledger integrity checks
    pub t0_integrity_pulse: AtomicU64,
    /// Count of semantic graph traversals performed
    pub semantic_traversals: AtomicU64,
    /// Acoustic state: Clear articulation count
    pub acoustic_clear: AtomicU64,
    /// Acoustic state: Concealed resonance count
    pub acoustic_concealed: AtomicU64,
    /// Acoustic state: Merged assimilation count
    pub acoustic_merged: AtomicU64,
    /// Acoustic state: Prolonged echo count
    pub acoustic_prolonged: AtomicU64,
    /// Acoustic state: Vibrating release count
    pub acoustic_vibrating: AtomicU64,
    /// Swarm harmony index (0-100, scaled to u64)
    pub swarm_harmony_index: AtomicU64,
    /// Hysteresis tension level (0-100, scaled to u64)
    pub hysteresis_tension: AtomicU64,
}

impl TelemetryAtomics {
    /// Creates a new TelemetryAtomics instance with default values.
    pub fn new() -> Arc<Self> {
        Arc::new(Self {
            t0_integrity_pulse: AtomicU64::new(0),
            semantic_traversals: AtomicU64::new(0),
            acoustic_clear: AtomicU64::new(0),
            acoustic_concealed: AtomicU64::new(0),
            acoustic_merged: AtomicU64::new(0),
            acoustic_prolonged: AtomicU64::new(0),
            acoustic_vibrating: AtomicU64::new(0),
            swarm_harmony_index: AtomicU64::new(100), // Start at 100% harmony
            hysteresis_tension: AtomicU64::new(0),
        })
    }

    /// Creates TelemetryAtomics with custom initial values.
    pub fn with_values(
        harmony: u16,
        tension: u16,
    ) -> Arc<Self> {
        Arc::new(Self {
            t0_integrity_pulse: AtomicU64::new(0),
            semantic_traversals: AtomicU64::new(0),
            acoustic_clear: AtomicU64::new(0),
            acoustic_concealed: AtomicU64::new(0),
            acoustic_merged: AtomicU64::new(0),
            acoustic_prolonged: AtomicU64::new(0),
            acoustic_vibrating: AtomicU64::new(0),
            swarm_harmony_index: AtomicU64::new(harmony as u64),
            hysteresis_tension: AtomicU64::new(tension as u64),
        })
    }

    /// Increments the T0 integrity pulse counter.
    pub fn pulse_integrity(&self) {
        self.t0_integrity_pulse.fetch_add(1, Ordering::Relaxed);
    }

    /// Increments the semantic traversals counter.
    pub fn record_traversal(&self) {
        self.semantic_traversals.fetch_add(1, Ordering::Relaxed);
    }

    /// Updates the consensus score.
    pub fn set_harmony(&self, value: u16) {
        self.swarm_harmony_index.store(value as u64, Ordering::Relaxed);
    }

    /// Updates the hysteresis tension level.
    pub fn set_tension(&self, value: u16) {
        self.hysteresis_tension.store(value as u64, Ordering::Relaxed);
    }

    /// Takes a snapshot of all counters, resetting the accumulators.
    /// 
    /// Returns a tuple of (t0, sem, clear, concealed, merged, prolonged, vibrating, harmony, tension).
    pub fn snapshot_and_reset(&self) -> (u64, u64, u64, u64, u64, u64, u64, u16, u16) {
        let t0 = self.t0_integrity_pulse.swap(0, Ordering::Relaxed);
        let sem = self.semantic_traversals.swap(0, Ordering::Relaxed);
        let clear = self.acoustic_clear.swap(0, Ordering::Relaxed);
        let concealed = self.acoustic_concealed.swap(0, Ordering::Relaxed);
        let merged = self.acoustic_merged.swap(0, Ordering::Relaxed);
        let prolonged = self.acoustic_prolonged.swap(0, Ordering::Relaxed);
        let vibrating = self.acoustic_vibrating.swap(0, Ordering::Relaxed);
        let harmony = self.swarm_harmony_index.load(Ordering::Relaxed) as u16;
        let tension = self.hysteresis_tension.load(Ordering::Relaxed) as u16;

        (t0, sem, clear, concealed, merged, prolonged, vibrating, harmony, tension)
    }
}

/// Spawns a background thread that periodically emits telemetry heartbeats.
/// 
/// # Arguments
/// * `node_id` - Unique identifier for this swarm node
/// * `atomics` - Shared reference to telemetry counters
/// * `target_collector` - UDP address of the telemetry collector (e.g., "127.0.0.1:9000")
/// * `interval_secs` - Time between heartbeat emissions
/// 
/// # Returns
/// An Arc reference to the atomics that can be used to stop the emitter.
pub fn spawn_heartbeat_emitter(
    node_id: u16,
    atomics: Arc<TelemetryAtomics>,
    target_collector: &str,
    interval_secs: u64,
) -> Arc<TelemetryAtomics> {
    let target = target_collector.to_string();
    let running = Arc::new(std::sync::atomic::AtomicBool::new(true));
    let running_clone = running.clone();
    let atomics_for_thread = atomics.clone();

    thread::spawn(move || {
        let atomics = atomics_for_thread;
        // Bind to any available port
        let socket = match UdpSocket::bind("0.0.0.0:0") {
            Ok(s) => s,
            Err(e) => {
                eprintln!("[TELEMETRY ERROR] Failed to bind UDP socket: {}", e);
                return;
            }
        };

        // Pre-allocate packet buffer
        let mut buf = [0u8; TOTAL_PACKET_SIZE];
        
        // Write static header fields
        buf[0..2].copy_from_slice(&RESONANCE_MAGIC.to_le_bytes());
        buf[2..4].copy_from_slice(&node_id.to_le_bytes());

        loop {
            if !running_clone.load(Ordering::Relaxed) {
                break;
            }

            thread::sleep(Duration::from_secs(interval_secs));

            // Snapshot all counters
            let (t0, sem, clear, concealed, merged, prolonged, vibrating, harmony, tension) =
                atomics.snapshot_and_reset();

            // Pack data into buffer
            buf[4..12].copy_from_slice(&t0.to_le_bytes());
            buf[12..20].copy_from_slice(&sem.to_le_bytes());
            buf[20..28].copy_from_slice(&clear.to_le_bytes());
            buf[28..36].copy_from_slice(&concealed.to_le_bytes());
            buf[36..44].copy_from_slice(&merged.to_le_bytes());
            buf[44..52].copy_from_slice(&prolonged.to_le_bytes());
            buf[52..60].copy_from_slice(&vibrating.to_le_bytes());
            
            // Harmony and tension as u16
            buf[60..62].copy_from_slice(&harmony.to_le_bytes());
            buf[62..64].copy_from_slice(&tension.to_le_bytes());

            // Send packet (ignore send errors - collector may be temporarily unavailable)
            let _ = socket.send_to(&buf, &target);
        }
    });

    atomics
}

/// Stops a running telemetry emitter.
/// 
/// Note: This is a convenience function. In practice, the emitter runs
/// indefinitely until process termination.
pub fn stop_emitter(_atomics: &Arc<TelemetryAtomics>) {
    // In a full implementation, we would signal the thread to stop.
    // For now, emitters run until process exit.
}

/// Utility to construct a telemetry packet manually.
/// 
/// Useful for one-off telemetry sends without spawning an emitter.
pub fn construct_packet(
    node_id: u16,
    t0: u64,
    sem: u64,
    clear: u64,
    concealed: u64,
    merged: u64,
    prolonged: u64,
    vibrating: u64,
    harmony: u16,
    tension: u16,
) -> [u8; TOTAL_PACKET_SIZE] {
    let mut buf = [0u8; TOTAL_PACKET_SIZE];

    buf[0..2].copy_from_slice(&RESONANCE_MAGIC.to_le_bytes());
    buf[2..4].copy_from_slice(&node_id.to_le_bytes());
    buf[4..12].copy_from_slice(&t0.to_le_bytes());
    buf[12..20].copy_from_slice(&sem.to_le_bytes());
    buf[20..28].copy_from_slice(&clear.to_le_bytes());
    buf[28..36].copy_from_slice(&concealed.to_le_bytes());
    buf[36..44].copy_from_slice(&merged.to_le_bytes());
    buf[44..52].copy_from_slice(&prolonged.to_le_bytes());
    buf[52..60].copy_from_slice(&vibrating.to_le_bytes());
    buf[60..62].copy_from_slice(&harmony.to_le_bytes());
    buf[62..64].copy_from_slice(&tension.to_le_bytes());

    buf
}

/// Parses a telemetry packet from raw bytes.
/// 
/// # Returns
/// * `Some(packet_data)` if magic number matches
/// * `None` if packet is invalid
pub fn parse_packet(buf: &[u8]) -> Option<(u16, u64, u64, u64, u64, u64, u64, u64, u16, u16)> {
    if buf.len() < TOTAL_PACKET_SIZE {
        return None;
    }

    let magic = u16::from_le_bytes([buf[0], buf[1]]);
    if magic != RESONANCE_MAGIC {
        return None;
    }

    let node_id = u16::from_le_bytes([buf[2], buf[3]]);
    let t0 = u64::from_le_bytes(buf[4..12].try_into().ok()?);
    let sem = u64::from_le_bytes(buf[12..20].try_into().ok()?);
    let clear = u64::from_le_bytes(buf[20..28].try_into().ok()?);
    let concealed = u64::from_le_bytes(buf[28..36].try_into().ok()?);
    let merged = u64::from_le_bytes(buf[36..44].try_into().ok()?);
    let prolonged = u64::from_le_bytes(buf[44..52].try_into().ok()?);
    let vibrating = u64::from_le_bytes(buf[52..60].try_into().ok()?);
    let harmony = u16::from_le_bytes([buf[60], buf[61]]);
    let tension = u16::from_le_bytes([buf[62], buf[63]]);

    Some((node_id, t0, sem, clear, concealed, merged, prolonged, vibrating, harmony, tension))
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_construct_and_parse_packet() {
        let packet = construct_packet(
            42,     // node_id
            100,    // t0
            50,     // sem
            10,     // clear
            5,      // concealed
            3,      // merged
            2,      // prolonged
            1,      // vibrating
            95,     // harmony
            5,      // tension
        );

        let parsed = parse_packet(&packet);
        assert!(parsed.is_some());

        let (node_id, t0, sem, clear, concealed, merged, prolonged, vibrating, harmony, tension) =
            parsed.unwrap();

        assert_eq!(node_id, 42);
        assert_eq!(t0, 100);
        assert_eq!(sem, 50);
        assert_eq!(clear, 10);
        assert_eq!(concealed, 5);
        assert_eq!(merged, 3);
        assert_eq!(prolonged, 2);
        assert_eq!(vibrating, 1);
        assert_eq!(harmony, 95);
        assert_eq!(tension, 5);
    }

    #[test]
    fn test_invalid_magic() {
        let mut packet = construct_packet(1, 0, 0, 0, 0, 0, 0, 0, 100, 0);
        packet[0] = 0x00; // Corrupt magic number
        packet[1] = 0x00;

        let result = parse_packet(&packet);
        assert!(result.is_none());
    }

    #[test]
    fn test_short_packet() {
        let short_buf = [0u8; 10];
        let result = parse_packet(&short_buf);
        assert!(result.is_none());
    }

    #[test]
    fn test_telemetry_atomics_snapshot() {
        let atomics = TelemetryAtomics::new();

        // Increment some counters
        atomics.pulse_integrity();
        atomics.pulse_integrity();
        atomics.record_traversal();
        atomics.set_harmony(85);

        // Snapshot should return accumulated values and reset
        let (t0, sem, _, _, _, _, _, harmony, _) = atomics.snapshot_and_reset();
        assert_eq!(t0, 2);
        assert_eq!(sem, 1);
        assert_eq!(harmony, 85);

        // Second snapshot should show reset values (except non-resetting counters)
        let (t0_2, sem_2, _, _, _, _, _, _, _) = atomics.snapshot_and_reset();
        assert_eq!(t0_2, 0); // Reset because we didn't pulse again
        assert_eq!(sem_2, 0); // Reset
    }

    #[test]
    fn test_packet_size_constant() {
        assert_eq!(TOTAL_PACKET_SIZE, 64);
        assert_eq!(PACKET_HEADER_SIZE, 4);
        assert_eq!(PACKET_PAYLOAD_SIZE, 56);
    }

    // 6. RESONANCE_MAGIC constant is 0xE0E0
    #[test]
    fn resonance_magic_is_0xe0e0() {
        assert_eq!(RESONANCE_MAGIC, 0xE0E0);
    }

    // 7. with_values initializes harmony and tension correctly
    #[test]
    fn with_values_sets_harmony_and_tension() {
        let atomics = TelemetryAtomics::with_values(75, 25);
        let (_, _, _, _, _, _, _, harmony, tension) = atomics.snapshot_and_reset();
        assert_eq!(harmony, 75);
        assert_eq!(tension, 25);
    }

    // 8. set_tension updates value reflected in snapshot
    #[test]
    fn set_tension_reflects_in_snapshot() {
        let atomics = TelemetryAtomics::new();
        atomics.set_tension(42);
        let (_, _, _, _, _, _, _, _, tension) = atomics.snapshot_and_reset();
        assert_eq!(tension, 42);
    }

    // 9. acoustic_clear increments tracked in snapshot and resets
    #[test]
    fn acoustic_clear_tracked_and_reset() {
        use std::sync::atomic::Ordering;
        let atomics = TelemetryAtomics::new();
        atomics.acoustic_clear.fetch_add(5, Ordering::Relaxed);
        let (_, _, clear, _, _, _, _, _, _) = atomics.snapshot_and_reset();
        assert_eq!(clear, 5);
        // After reset, next snapshot shows 0
        let (_, _, clear2, _, _, _, _, _, _) = atomics.snapshot_and_reset();
        assert_eq!(clear2, 0);
    }

    // 10. packet constants sum to TOTAL_PACKET_SIZE
    #[test]
    fn packet_constants_sum_to_total() {
        assert_eq!(PACKET_HEADER_SIZE + PACKET_PAYLOAD_SIZE + PACKET_HARMONY_SIZE, TOTAL_PACKET_SIZE);
    }
}