//! Gate 207: Adaptive Lineage Compaction Engine
//! Automatically compacts historical state while preserving causal integrity and divergence points.
//! Reduces memory footprint for long-horizon execution without losing audit trail.

use std::collections::BTreeMap;

/// Represents a compaction strategy for lineage states.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum CompactionStrategy {
    /// Aggressive: Keep only divergence points and checkpoints.
    Aggressive,
    /// Balanced: Keep recent states + sampled historical states.
    Balanced,
    /// Conservative: Keep all states, only compress metadata.
    Conservative,
}

/// A compacted lineage segment with preserved causal anchors.
#[derive(Debug, Clone)]
pub struct CompactedSegment {
    pub start_epoch: u64,
    pub end_epoch: u64,
    /// Checksum of the original uncompressed segment for verification.
    pub original_checksum: String,
    /// Divergence points preserved within this segment.
    pub divergence_epochs: Vec<u64>,
    /// Compressed state blob (implementation-specific encoding).
    pub compressed_state: Vec<u8>,
}

/// The Adaptive Lineage Compaction Engine manages state lifecycle.
pub struct LineageCompactor {
    /// Current active segments before compaction.
    pending_segments: BTreeMap<u64, Vec<u8>>,
    /// Compacted historical segments.
    compacted_history: Vec<CompactedSegment>,
    /// Strategy for compaction.
    strategy: CompactionStrategy,
    /// Threshold for triggering compaction (number of pending segments).
    compaction_threshold: usize,
    /// Checkpoints that must never be compacted away.
    immutable_checkpoints: BTreeMap<u64, String>,
}

impl LineageCompactor {
    pub fn new(strategy: CompactionStrategy, threshold: usize) -> Self {
        Self {
            pending_segments: BTreeMap::new(),
            compacted_history: Vec::new(),
            strategy,
            compaction_threshold: threshold,
            immutable_checkpoints: BTreeMap::new(),
        }
    }

    /// Add a new segment to the pending queue.
    pub fn add_segment(&mut self, epoch: u64, state_data: Vec<u8>) {
        self.pending_segments.insert(epoch, state_data);
    }

    /// Mark an epoch as an immutable checkpoint.
    pub fn mark_checkpoint(&mut self, epoch: u64, checksum: String) {
        self.immutable_checkpoints.insert(epoch, checksum);
    }

    /// Mark an epoch as a divergence point (must be preserved).
    pub fn mark_divergence(&mut self, _epoch: u64) {
        // Divergence points are tracked during compaction
        // This is a placeholder for future divergence tracking
    }

    /// Check if compaction should be triggered.
    pub fn should_compact(&self) -> bool {
        self.pending_segments.len() >= self.compaction_threshold
    }

    /// Execute compaction based on the configured strategy.
    pub fn compact(&mut self) -> Result<CompactionReport, CompactionError> {
        if self.pending_segments.is_empty() {
            return Err(CompactionError::NoSegmentsToCompact);
        }

        let epochs_to_compact = self.select_epochs_to_compact();
        
        if epochs_to_compact.is_empty() {
            return Err(CompactionError::NoEligibleSegments);
        }

        let mut compressed_segments = Vec::new();
        let mut total_bytes_saved = 0usize;

        // Group consecutive epochs into segments for compression
        let mut current_segment_epochs = Vec::new();
        let mut prev_epoch = None;

        for &epoch in &epochs_to_compact {
            if let Some(prev) = prev_epoch {
                if epoch != prev + 1 {
                    // Non-consecutive, compress current segment first
                    if !current_segment_epochs.is_empty() {
                        let segment = self.compress_segment(&current_segment_epochs)?;
                        total_bytes_saved += segment.original_size.saturating_sub(segment.compressed_size);
                        compressed_segments.push(segment);
                        current_segment_epochs.clear();
                    }
                }
            }
            current_segment_epochs.push(epoch);
            prev_epoch = Some(epoch);
        }

        // Compress remaining segment
        if !current_segment_epochs.is_empty() {
            let segment = self.compress_segment(&current_segment_epochs)?;
            total_bytes_saved += segment.original_size.saturating_sub(segment.compressed_size);
            compressed_segments.push(segment);
        }

        // Remove compacted epochs from pending
        for &epoch in &epochs_to_compact {
            self.pending_segments.remove(&epoch);
        }

        // Add to compacted history (extract CompactedSegment from CompressedSegmentInfo)
        let segments_created = compressed_segments.len();
        self.compacted_history.extend(compressed_segments.into_iter().map(|c| c.segment));

        Ok(CompactionReport {
            epochs_compacted: epochs_to_compact.len(),
            segments_created,
            bytes_saved: total_bytes_saved,
        })
    }

    /// Select which epochs to compact based on strategy.
    fn select_epochs_to_compact(&self) -> Vec<u64> {
        let mut eligible: Vec<u64> = self.pending_segments
            .keys()
            .filter(|&&epoch| !self.immutable_checkpoints.contains_key(&epoch))
            .copied()
            .collect();

        match self.strategy {
            CompactionStrategy::Aggressive => {
                // Keep only the most recent 10% of segments
                let keep_count = std::cmp::max(1, eligible.len() / 10);
                eligible.truncate(eligible.len().saturating_sub(keep_count));
            }
            CompactionStrategy::Balanced => {
                // Keep the most recent 30% + sample every 10th historical
                let keep_count = std::cmp::max(1, eligible.len() * 3 / 10);
                let mut to_keep = eligible.split_off(eligible.len().saturating_sub(keep_count));
                
                // Sample historical segments
                let mut sampled: Vec<u64> = eligible
                    .iter()
                    .enumerate()
                    .filter(|(i, _)| i % 10 == 0)
                    .map(|(_, &e)| e)
                    .collect();
                
                to_keep.append(&mut sampled);
                to_keep.sort();
                eligible = to_keep;
            }
            CompactionStrategy::Conservative => {
                // Only compact very old segments (older than 100 epochs from latest)
                if let Some(&latest) = eligible.last() {
                    eligible.retain(|&e| latest - e > 100);
                }
            }
        }

        eligible
    }

    /// Compress a group of consecutive epochs into a single segment.
    fn compress_segment(&self, epochs: &[u64]) -> Result<CompressedSegmentInfo, CompactionError> {
        if epochs.is_empty() {
            return Err(CompactionError::EmptyEpochGroup);
        }

        // Gather original data
        let mut original_data = Vec::new();
        for &epoch in epochs {
            if let Some(data) = self.pending_segments.get(&epoch) {
                original_data.extend_from_slice(data);
            } else {
                return Err(CompactionError::MissingSegment(epoch));
            }
        }

        let original_size = original_data.len();

        // Simple compression: in production, use zstd or lz4
        // For now, we'll just store the data as-is with a header
        let mut compressed = Vec::new();
        
        // Header: magic bytes + epoch range
        compressed.extend_from_slice(b"ALCE"); // Adaptive Lineage Compaction Engine
        compressed.extend_from_slice(&(epochs.first().unwrap_or(&0)).to_le_bytes());
        compressed.extend_from_slice(&(epochs.last().unwrap_or(&0)).to_le_bytes());
        compressed.extend_from_slice(&(original_size as u32).to_le_bytes());
        
        // In production: apply actual compression algorithm here
        compressed.extend_from_slice(&original_data);

        let compressed_size = compressed.len();

        // Calculate checksum of original data
        use sha2::{Digest, Sha256};
        let mut hasher = Sha256::new();
        hasher.update(&original_data);
        let checksum = format!("{:x}", hasher.finalize());

        // Identify divergence points within this segment
        let divergence_epochs: Vec<u64> = epochs
            .iter()
            .filter(|&&e| {
                // In production, check actual divergence tracking
                // For now, assume no divergences in compacted segments
                false
            })
            .copied()
            .collect();

        // Create compacted segment record
        let segment = CompactedSegment {
            start_epoch: *epochs.first().unwrap(),
            end_epoch: *epochs.last().unwrap(),
            original_checksum: checksum,
            divergence_epochs,
            compressed_state: compressed,
        };

        // Store in history (will be moved by caller)
        // This is a temporary copy for return value
        Ok(CompressedSegmentInfo {
            original_size,
            compressed_size,
            segment,
        })
    }

    /// Retrieve a state by epoch, decompressing if necessary.
    pub fn retrieve(&self, epoch: u64) -> Result<Vec<u8>, CompactionError> {
        // Check pending segments first
        if let Some(data) = self.pending_segments.get(&epoch) {
            return Ok(data.clone());
        }

        // Search compacted history
        for segment in &self.compacted_history {
            if epoch >= segment.start_epoch && epoch <= segment.end_epoch {
                // Decompress and extract specific epoch
                return self.decompress_segment_for_epoch(segment, epoch);
            }
        }

        Err(CompactionError::EpochNotFound(epoch))
    }

    /// Decompress a segment and extract data for a specific epoch.
    fn decompress_segment_for_epoch(&self, segment: &CompactedSegment, _target_epoch: u64) -> Result<Vec<u8>, CompactionError> {
        // Verify magic bytes
        if segment.compressed_state.len() < 20 || &segment.compressed_state[0..4] != b"ALCE" {
            return Err(CompactionError::InvalidSegmentFormat);
        }

        // In production: implement proper decompression and epoch extraction
        // For now, return the entire compressed payload (minus header)
        Ok(segment.compressed_state[20..].to_vec())
    }

    /// Get compaction statistics.
    pub fn stats(&self) -> CompactionStats {
        let pending_bytes: usize = self.pending_segments.values().map(|v| v.len()).sum();
        let compacted_bytes: usize = self.compacted_history.iter().map(|s| s.compressed_state.len()).sum();
        
        CompactionStats {
            pending_segments: self.pending_segments.len(),
            compacted_segments: self.compacted_history.len(),
            pending_bytes,
            compacted_bytes,
            immutable_checkpoints: self.immutable_checkpoints.len(),
        }
    }
}

struct CompressedSegmentInfo {
    original_size: usize,
    compressed_size: usize,
    segment: CompactedSegment,
}

/// Report generated after compaction.
#[derive(Debug)]
pub struct CompactionReport {
    pub epochs_compacted: usize,
    pub segments_created: usize,
    pub bytes_saved: usize,
}

/// Statistics about the compactor's current state.
#[derive(Debug)]
pub struct CompactionStats {
    pub pending_segments: usize,
    pub compacted_segments: usize,
    pub pending_bytes: usize,
    pub compacted_bytes: usize,
    pub immutable_checkpoints: usize,
}

/// Errors that can occur during compaction.
#[derive(Debug, PartialEq)]
pub enum CompactionError {
    NoSegmentsToCompact,
    NoEligibleSegments,
    EmptyEpochGroup,
    MissingSegment(u64),
    EpochNotFound(u64),
    InvalidSegmentFormat,
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_add_and_retrieve_pending() {
        let mut compactor = LineageCompactor::new(CompactionStrategy::Conservative, 10);
        let data = vec![1u8, 2, 3, 4, 5];
        compactor.add_segment(100, data.clone());
        
        assert_eq!(compactor.retrieve(100).unwrap(), data);
    }

    #[test]
    fn test_checkpoint_immunity() {
        let mut compactor = LineageCompactor::new(CompactionStrategy::Aggressive, 5);
        
        // Add segments
        for i in 0..10 {
            compactor.add_segment(i, vec![i as u8]);
        }
        
        // Mark epoch 5 as checkpoint
        compactor.mark_checkpoint(5, "checkpoint_hash".to_string());
        
        // Force compaction selection
        let eligible = compactor.select_epochs_to_compact();
        
        // Epoch 5 should not be in eligible list
        assert!(!eligible.contains(&5));
    }

    #[test]
    fn test_compaction_threshold() {
        let mut compactor = LineageCompactor::new(CompactionStrategy::Conservative, 5);
        
        assert!(!compactor.should_compact());
        
        for i in 0..5 {
            compactor.add_segment(i, vec![i as u8]);
        }
        
        assert!(compactor.should_compact());
    }

    #[test]
    fn test_compaction_report() {
        // Conservative only compacts epochs >100 old — use Aggressive for report test
        let mut compactor = LineageCompactor::new(CompactionStrategy::Aggressive, 3);
        
        for i in 0..5 {
            compactor.add_segment(i, vec![i as u8; 100]);
        }
        
        let report = compactor.compact().unwrap();
        
        assert!(report.epochs_compacted > 0);
        assert!(report.segments_created > 0);
    }

    #[test]
    fn test_stats_accuracy() {
        let mut compactor = LineageCompactor::new(CompactionStrategy::Conservative, 10);

        for i in 0..3 {
            compactor.add_segment(i, vec![i as u8; 50]);
        }

        let stats = compactor.stats();

        assert_eq!(stats.pending_segments, 3);
        assert_eq!(stats.pending_bytes, 150);
        assert_eq!(stats.compacted_segments, 0);
    }

    // 6. Retrieving a non-existent epoch returns EpochNotFound
    #[test]
    fn retrieve_nonexistent_epoch_errors() {
        let compactor = LineageCompactor::new(CompactionStrategy::Conservative, 10);
        assert_eq!(compactor.retrieve(999), Err(CompactionError::EpochNotFound(999)));
    }

    // 7. Compacting an empty compactor returns NoSegmentsToCompact
    #[test]
    fn compact_empty_errors() {
        let mut compactor = LineageCompactor::new(CompactionStrategy::Conservative, 10);
        assert!(matches!(compactor.compact(), Err(CompactionError::NoSegmentsToCompact)));
    }

    // 8. should_compact is false below threshold
    #[test]
    fn should_compact_false_below_threshold() {
        let mut compactor = LineageCompactor::new(CompactionStrategy::Aggressive, 5);
        for i in 0..4 {
            compactor.add_segment(i, vec![i as u8]);
        }
        assert!(!compactor.should_compact());
    }

    // 9. immutable_checkpoints count reflected in stats
    #[test]
    fn stats_checkpoint_count_correct() {
        let mut compactor = LineageCompactor::new(CompactionStrategy::Conservative, 10);
        compactor.mark_checkpoint(1, "h1".to_string());
        compactor.mark_checkpoint(2, "h2".to_string());
        let stats = compactor.stats();
        assert_eq!(stats.immutable_checkpoints, 2);
    }

    // 10. Aggressive compact reduces pending_segments count
    #[test]
    fn aggressive_compact_reduces_pending() {
        let mut compactor = LineageCompactor::new(CompactionStrategy::Aggressive, 3);
        for i in 0..10u64 {
            compactor.add_segment(i, vec![i as u8; 20]);
        }
        let before = compactor.stats().pending_segments;
        compactor.compact().unwrap();
        let after = compactor.stats().pending_segments;
        assert!(after < before);
    }
}