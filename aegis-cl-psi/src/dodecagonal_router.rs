//! Gate 212: Dodecagonal Symmetry Router
//! EPISTEMIC TIER: T2 (engineering hypothesis)
//! 12-fold symmetric routing topology using integer arithmetic.
//! Each node i connects to (i±1)%12 (ring neighbors) and (i+6)%12 (opposite).

use std::collections::{BTreeSet, VecDeque};

pub const DODECAGON_NODES: u8 = 12;

pub struct DodecagonalMesh {
    pub adjacency: [[u8; 3]; 12],
}

pub fn build_dodecagonal_mesh() -> DodecagonalMesh {
    let mut adjacency = [[0u8; 3]; 12];
    for i in 0..DODECAGON_NODES {
        let n1 = (i + 1) % DODECAGON_NODES;
        let n2 = (i + 11) % DODECAGON_NODES;
        let n3 = (i + 6) % DODECAGON_NODES;
        let mut neighbors = [n1, n2, n3];
        neighbors.sort();
        adjacency[i as usize] = neighbors;
    }
    DodecagonalMesh { adjacency }
}

pub fn route(mesh: &DodecagonalMesh, from: u8, to: u8) -> Vec<u8> {
    assert!(from < DODECAGON_NODES && to < DODECAGON_NODES, "Node index out of bounds");
    if from == to {
        return vec![from];
    }

    let mut queue = VecDeque::new();
    queue.push_back(vec![from]);
    let mut visited = BTreeSet::new();
    visited.insert(from);

    while let Some(path) = queue.pop_front() {
        let node = *path.last().unwrap();
        let neighbors = mesh.adjacency[node as usize];

        for &next in &neighbors {
            if next == to {
                let mut new_path = path.clone();
                new_path.push(next);
                return new_path;
            }
            if visited.insert(next) {
                let mut new_path = path.clone();
                new_path.push(next);
                queue.push_back(new_path);
            }
        }
    }
    vec![]
}

pub fn ring_distance(a: u8, b: u8) -> u8 {
    let diff = if a > b { a - b } else { b - a };
    std::cmp::min(diff, DODECAGON_NODES - diff)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_adjacent_nodes() {
        let mesh = build_dodecagonal_mesh();
        assert_eq!(ring_distance(0, 1), 1);
        assert_eq!(route(&mesh, 0, 1).len(), 2);
    }

    #[test]
    fn test_opposite_node() {
        let mesh = build_dodecagonal_mesh();
        assert_eq!(ring_distance(0, 6), 6);
        let path = route(&mesh, 0, 6);
        assert_eq!(path.len(), 2);
    }

    #[test]
    fn test_symmetry() {
        let mesh = build_dodecagonal_mesh();
        for a in 0..12 {
            for b in 0..12 {
                assert_eq!(route(&mesh, a, b).len(), route(&mesh, b, a).len());
            }
        }
    }

    #[test]
    fn test_self_route() {
        let mesh = build_dodecagonal_mesh();
        for i in 0..12 {
            assert_eq!(route(&mesh, i, i), vec![i]);
        }
    }

    #[test]
    fn test_ring_distance_metrics() {
        assert_eq!(ring_distance(0, 6), 6);
        assert_eq!(ring_distance(0, 11), 1);
        assert_eq!(ring_distance(1, 11), 2);
    }

    #[test]
    fn test_btree_determinism() {
        let mesh = build_dodecagonal_mesh();
        for i in 0..12 {
            let neighbors = mesh.adjacency[i as usize];
            assert!(neighbors[0] < neighbors[1] && neighbors[1] < neighbors[2]);
        }
    }

    #[test]
    fn test_all_nodes_reachable() {
        let mesh = build_dodecagonal_mesh();
        for dest in 0..12 {
            let path = route(&mesh, 0, dest);
            assert!(!path.is_empty());
            assert_eq!(*path.first().unwrap(), 0);
            assert_eq!(*path.last().unwrap(), dest);
        }
    }
}
