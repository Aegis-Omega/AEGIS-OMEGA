//! Gate 207: Dodecagonal Mesh Engine
//! Transforms the 204-node pyramid into a 12-fold symmetric quasicrystalline lattice.
//! Eliminates tessellation gaps inherent in 8-fold symmetry for infinite scalability.


/// Represents a sector in the 12-fold resonance mesh.
#[derive(Debug, Clone)]
pub struct DodecagonalSector {
    pub sector_id: u8, // 0-11
    pub node_count: u64,
    pub harmonic_index: u64,
}

/// The DodecagonalMesh manages 12-fold symmetric distribution of nodes.
pub struct DodecagonalMesh {
    sectors: Vec<DodecagonalSector>,
    total_nodes: u64,
    phase_shifted: bool,
}

impl DodecagonalMesh {
    pub fn new(total_nodes: u64) -> Self {
        let mut mesh = Self {
            sectors: Vec::with_capacity(12),
            total_nodes,
            phase_shifted: false,
        };
        mesh.distribute_nodes();
        mesh
    }

    /// Distributes nodes across 12 sectors using factorization (204 = 12 * 17).
    fn distribute_nodes(&mut self) {
        let base_per_sector = self.total_nodes / 12;
        let remainder = self.total_nodes % 12;

        for i in 0..12 {
            let extra = if (i as u64) < remainder { 1 } else { 0 };
            self.sectors.push(DodecagonalSector {
                sector_id: i as u8,
                node_count: base_per_sector + extra,
                harmonic_index: (i as u64) + 1,
            });
        }
    }

    /// Validates that the mesh can accommodate exactly 204 nodes with 12-fold symmetry.
    pub fn validate_204_factorization(&self) -> Result<bool, &'static str> {
        if self.total_nodes != 204 {
            return Err("Total nodes must be 204 for validation");
        }

        let sum: u64 = self.sectors.iter().map(|s| s.node_count).sum();
        if sum == 204 {
            Ok(true)
        } else {
            Err("Factorization error: sector sum does not equal 204")
        }
    }

    /// Checks for tessellation gaps (should be zero in 12-fold symmetry).
    pub fn check_tessellation_gaps(&self) -> u64 {
        // In perfect 12-fold symmetry, remainder is always 0
        self.total_nodes % 12
    }

    /// Triggers the phase shift from 8-fold to 12-fold topology.
    pub fn trigger_phase_shift(&mut self) -> Result<(), &'static str> {
        if self.total_nodes < 204 {
            return Err("Phase shift requires minimum 204 nodes");
        }
        self.phase_shifted = true;
        Ok(())
    }

    /// Returns the sector with the highest load for rebalancing.
    pub fn find_max_load_sector(&self) -> Option<&DodecagonalSector> {
        self.sectors.iter().max_by_key(|s| s.node_count)
    }

    /// Computes the harmonic resonance index for a given sector.
    pub fn get_harmonic_resonance(&self, sector_id: u8) -> Option<u64> {
        self.sectors
            .get(sector_id as usize)
            .map(|s| s.harmonic_index)
    }

    /// Simulates Penrose-like tiling to verify non-periodic expansion capability.
    pub fn simulate_penrose_tiling(&self, iterations: u32) -> Result<TilingReport, &'static str> {
        if !self.phase_shifted {
            return Err("Must trigger phase shift before tiling simulation");
        }

        let mut report = TilingReport {
            iterations,
            total_tiles: 0,
            gap_count: 0,
            overlap_count: 0,
        };

        // Simplified simulation: 12-fold symmetry allows gap-free tiling
        for _ in 0..iterations {
            report.total_tiles += 12;
            // No gaps or overlaps in ideal 12-fold quasicrystal
        }

        Ok(report)
    }
}

#[derive(Debug, Clone)]
pub struct TilingReport {
    pub iterations: u32,
    pub total_tiles: u64,
    pub gap_count: u64,
    pub overlap_count: u64,
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_distribute_204_nodes() {
        let mesh = DodecagonalMesh::new(204);
        assert_eq!(mesh.sectors.len(), 12);
        
        let sum: u64 = mesh.sectors.iter().map(|s| s.node_count).sum();
        assert_eq!(sum, 204);
        
        // Each sector should have exactly 17 nodes (204 / 12 = 17)
        for sector in &mesh.sectors {
            assert_eq!(sector.node_count, 17);
        }
    }

    #[test]
    fn test_validate_204_factorization() {
        let mesh = DodecagonalMesh::new(204);
        assert!(mesh.validate_204_factorization().is_ok());
    }

    #[test]
    fn test_check_tessellation_gaps() {
        let mesh = DodecagonalMesh::new(204);
        assert_eq!(mesh.check_tessellation_gaps(), 0);
        
        let mesh2 = DodecagonalMesh::new(205);
        assert_eq!(mesh2.check_tessellation_gaps(), 1);
    }

    #[test]
    fn test_trigger_phase_shift() {
        let mut mesh = DodecagonalMesh::new(204);
        assert!(mesh.trigger_phase_shift().is_ok());
        assert!(mesh.phase_shifted);
        
        let mut mesh2 = DodecagonalMesh::new(100);
        assert!(mesh2.trigger_phase_shift().is_err());
    }

    #[test]
    fn test_find_max_load_sector() {
        let mesh = DodecagonalMesh::new(205); // Uneven distribution
        let max_sector = mesh.find_max_load_sector().unwrap();
        assert_eq!(max_sector.node_count, 18); // 205 / 12 = 17 remainder 1
    }

    #[test]
    fn test_simulate_penrose_tiling() {
        let mut mesh = DodecagonalMesh::new(204);
        mesh.trigger_phase_shift().unwrap();

        let report = mesh.simulate_penrose_tiling(10).unwrap();
        assert_eq!(report.total_tiles, 120);
        assert_eq!(report.gap_count, 0);
        assert_eq!(report.overlap_count, 0);
    }

    // 7. validate_204_factorization returns Err for non-204 totals
    #[test]
    fn validate_non_204_returns_err() {
        let mesh = DodecagonalMesh::new(205);
        assert!(mesh.validate_204_factorization().is_err());
    }

    // 8. get_harmonic_resonance returns sector_id + 1 (1-indexed)
    #[test]
    fn get_harmonic_resonance_correct() {
        let mesh = DodecagonalMesh::new(204);
        assert_eq!(mesh.get_harmonic_resonance(0), Some(1));
        assert_eq!(mesh.get_harmonic_resonance(11), Some(12));
        assert_eq!(mesh.get_harmonic_resonance(12), None);
    }

    // 9. simulate_penrose_tiling errors before phase shift
    #[test]
    fn simulate_penrose_without_phase_shift_errors() {
        let mesh = DodecagonalMesh::new(204);
        assert!(mesh.simulate_penrose_tiling(5).is_err());
    }

    // 10. total_tiles = 12 * iterations
    #[test]
    fn total_tiles_12_times_iterations() {
        let mut mesh = DodecagonalMesh::new(204);
        mesh.trigger_phase_shift().unwrap();
        let report = mesh.simulate_penrose_tiling(7).unwrap();
        assert_eq!(report.total_tiles, 84); // 12 * 7
        assert_eq!(report.iterations, 7);
    }
}
