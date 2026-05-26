//! Gate 207: Pyramidal Stack Engine
//! Computes cumulative causal capacity of mesh layers using square pyramidal numbers.
//! Validates P_n = n(n+1)(2n+1)/6 and enforces geometric capacity limits.

/// Computes the nth square pyramidal number: P_n = sum_{k=1}^n k^2
#[inline]
pub fn pyramidal_number(n: u64) -> u64 {
    if n == 0 {
        return 0;
    }
    // P_n = n * (n + 1) * (2n + 1) / 6
    n * (n + 1) * (2 * n + 1) / 6
}

/// Represents a layer in the pyramidal stack with its node capacity.
#[derive(Debug, Clone)]
pub struct PyramidalLayer {
    pub layer_index: u64,
    pub node_capacity: u64, // k^2 for this layer
    pub cumulative_nodes: u64, // P_k up to this layer
}

/// The PyramidalStack manages the layered causal capacity of the mesh.
pub struct PyramidalStack {
    layers: Vec<PyramidalLayer>,
    max_layer: u64,
}

impl PyramidalStack {
    pub fn new(max_layer: u64) -> Self {
        let mut stack = Self {
            layers: Vec::new(),
            max_layer,
        };
        stack.initialize_layers();
        stack
    }

    fn initialize_layers(&mut self) {
        for k in 1..=self.max_layer {
            let node_capacity = k * k;
            let cumulative = pyramidal_number(k);
            self.layers.push(PyramidalLayer {
                layer_index: k,
                node_capacity,
                cumulative_nodes: cumulative,
            });
        }
    }

    /// Returns the total capacity up to the given layer.
    pub fn get_cumulative_capacity(&self, layer: u64) -> Option<u64> {
        if layer == 0 || layer > self.max_layer {
            return None;
        }
        Some(pyramidal_number(layer))
    }

    /// Validates that the 8th layer equals exactly 204 nodes.
    pub fn validate_layer_8(&self) -> Result<bool, &'static str> {
        let expected = 204u64;
        let actual = pyramidal_number(8);
        if actual == expected {
            Ok(true)
        } else {
            Err("Layer 8 capacity mismatch: expected 204, got {actual}")
        }
    }

    /// Checks if a node count exceeds the geometric capacity of a given layer.
    pub fn check_capacity(&self, node_count: u64, layer: u64) -> Result<bool, CapacityExceeded> {
        let capacity = self.get_cumulative_capacity(layer)
            .ok_or(CapacityExceeded::InvalidLayer(layer))?;
        
        if node_count > capacity {
            Err(CapacityExceeded::NodeCountExceeded {
                node_count,
                capacity,
                layer,
            })
        } else {
            Ok(true)
        }
    }

    /// Returns the minimum layer required to accommodate a given node count.
    pub fn find_minimum_layer(&self, node_count: u64) -> Option<u64> {
        for layer in &self.layers {
            if node_count <= layer.cumulative_nodes {
                return Some(layer.layer_index);
            }
        }
        None
    }

    /// Verifies the algebraic dependency: P_8 = (8 * 9 * 17) / 6
    pub fn verify_algebraic_structure(&self) -> Result<(), &'static str> {
        let n = 8u64;
        let computed = (n * (n + 1) * (2 * n + 1)) / 6;
        let expected = 204u64;
        
        if computed == expected {
            Ok(())
        } else {
            Err("Algebraic structure verification failed")
        }
    }
}

#[derive(Debug, PartialEq)]
pub enum CapacityExceeded {
    InvalidLayer(u64),
    NodeCountExceeded { node_count: u64, capacity: u64, layer: u64 },
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_pyramidal_number_formula() {
        assert_eq!(pyramidal_number(1), 1);
        assert_eq!(pyramidal_number(2), 5);   // 1 + 4
        assert_eq!(pyramidal_number(3), 14);  // 1 + 4 + 9
        assert_eq!(pyramidal_number(8), 204); // Target value
    }

    #[test]
    fn test_validate_layer_8() {
        let stack = PyramidalStack::new(8);
        assert!(stack.validate_layer_8().is_ok());
    }

    #[test]
    fn test_check_capacity_within_bounds() {
        let stack = PyramidalStack::new(8);
        assert!(stack.check_capacity(100, 8).is_ok()); // Layer 8 cumulative = 204 >= 100
        assert!(stack.check_capacity(55, 5).is_ok());  // Layer 5 cumulative = 55 >= 55
    }

    #[test]
    fn test_check_capacity_exceeded() {
        let stack = PyramidalStack::new(8);
        let result = stack.check_capacity(205, 8);
        assert!(matches!(result, Err(CapacityExceeded::NodeCountExceeded { .. })));
    }

    #[test]
    fn test_find_minimum_layer() {
        let stack = PyramidalStack::new(8);
        assert_eq!(stack.find_minimum_layer(1), Some(1));
        assert_eq!(stack.find_minimum_layer(5), Some(2));
        assert_eq!(stack.find_minimum_layer(14), Some(3));
        assert_eq!(stack.find_minimum_layer(204), Some(8));
        assert_eq!(stack.find_minimum_layer(205), None);
    }

    #[test]
    fn test_verify_algebraic_structure() {
        let stack = PyramidalStack::new(8);
        assert!(stack.verify_algebraic_structure().is_ok());
    }
}
