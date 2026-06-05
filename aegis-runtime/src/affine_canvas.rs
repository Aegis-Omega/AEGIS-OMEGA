//! Pillar 3 — Deterministic Affine Multi-Agent Coordinate Space
//!
//! EPISTEMIC TIER: T2 (engineering hypothesis)
//!
//! Maps agent positions, network telemetry, and node clustering profiles into
//! a proportional viewport layout using integer affine transformations.
//! No floating-point — all coordinates are scaled integer (units × 1000).
//!
//! Affine transform: [x', y'] = [a·x + b·y + tx, c·x + d·y + ty]
//! where a, b, c, d, tx, ty are i64 scaled by SCALE_FACTOR = 1000.
//!
//! Constitutional invariants:
//! - Integer arithmetic only — no f32/f64
//! - BTreeMap<AgentId, AgentBound> — deterministic iteration
//! - layout_agents() is a pure function (no side effects)
//! - fingerprint() — SHA-256 over sorted agent bounds

use sha2::{Sha256, Digest};
use std::collections::BTreeMap;

pub type AgentId = u64;

/// Scale factor — all coordinates stored as integer × SCALE_FACTOR.
pub const SCALE_FACTOR: i64 = 1000;

/// Integer 2D affine transform matrix (scaled by SCALE_FACTOR).
/// Applies: x' = (a*x + b*y)/SCALE + tx, y' = (c*x + d*y)/SCALE + ty
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub struct AffineMatrix {
    pub a: i64, pub b: i64, pub tx: i64,
    pub c: i64, pub d: i64, pub ty: i64,
}

impl AffineMatrix {
    /// Identity transform.
    pub fn identity() -> Self {
        Self { a: SCALE_FACTOR, b: 0, tx: 0, c: 0, d: SCALE_FACTOR, ty: 0 }
    }

    /// Scale transform (sx, sy scaled by SCALE_FACTOR).
    pub fn scale(sx: i64, sy: i64) -> Self {
        Self { a: sx, b: 0, tx: 0, c: 0, d: sy, ty: 0 }
    }

    /// Translation.
    pub fn translate(tx: i64, ty: i64) -> Self {
        Self { a: SCALE_FACTOR, b: 0, tx, c: 0, d: SCALE_FACTOR, ty }
    }

    /// Apply to a point (x, y) — both scaled by SCALE_FACTOR.
    pub fn apply(&self, x: i64, y: i64) -> (i64, i64) {
        let xp = (self.a * x + self.b * y) / SCALE_FACTOR + self.tx;
        let yp = (self.c * x + self.d * y) / SCALE_FACTOR + self.ty;
        (xp, yp)
    }

    /// Compose two transforms: self then other.
    pub fn compose(&self, other: &AffineMatrix) -> AffineMatrix {
        AffineMatrix {
            a: (other.a * self.a + other.b * self.c) / SCALE_FACTOR,
            b: (other.a * self.b + other.b * self.d) / SCALE_FACTOR,
            tx: (other.a * self.tx + other.b * self.ty) / SCALE_FACTOR + other.tx,
            c: (other.c * self.a + other.d * self.c) / SCALE_FACTOR,
            d: (other.c * self.b + other.d * self.d) / SCALE_FACTOR,
            ty: (other.c * self.tx + other.d * self.ty) / SCALE_FACTOR + other.ty,
        }
    }
}

/// Bounding box of one agent in the canvas coordinate space.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub struct AgentBound {
    pub x: i64, pub y: i64,
    pub width: i64, pub height: i64,
}

/// Agent layout input.
pub struct AgentSpec {
    pub id: AgentId,
    pub logical_x: i64,
    pub logical_y: i64,
    pub logical_w: i64,
    pub logical_h: i64,
}

/// Deterministic affine canvas layout.
pub struct AffineCanvas {
    bounds: BTreeMap<AgentId, AgentBound>,
    transform: AffineMatrix,
}

impl AffineCanvas {
    pub fn new(transform: AffineMatrix) -> Self {
        Self { bounds: BTreeMap::new(), transform }
    }

    /// Place a set of agents onto the canvas using the stored transform.
    /// Pure function — same input → same output.
    pub fn layout_agents(&mut self, agents: &[AgentSpec]) {
        self.bounds.clear();
        for spec in agents {
            let (x, y) = self.transform.apply(spec.logical_x, spec.logical_y);
            let (w, _) = self.transform.apply(spec.logical_w, 0);
            let (_, h) = self.transform.apply(0, spec.logical_h);
            self.bounds.insert(spec.id, AgentBound { x, y, width: w.abs(), height: h.abs() });
        }
    }

    pub fn get_bound(&self, id: AgentId) -> Option<&AgentBound> { self.bounds.get(&id) }
    pub fn agent_count(&self) -> usize { self.bounds.len() }

    /// SHA-256 fingerprint over all agent bounds in BTreeMap order.
    pub fn fingerprint(&self) -> [u8; 32] {
        let mut h = Sha256::new();
        for (id, b) in &self.bounds {
            h.update(id.to_le_bytes());
            h.update(b.x.to_le_bytes());   h.update(b.y.to_le_bytes());
            h.update(b.width.to_le_bytes()); h.update(b.height.to_le_bytes());
        }
        h.finalize().into()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn agents(n: u64) -> Vec<AgentSpec> {
        (1..=n).map(|i| AgentSpec { id: i, logical_x: i as i64 * 1000,
            logical_y: 0, logical_w: 500, logical_h: 500 }).collect()
    }

    #[test] fn identity_transform_preserves_coords() {
        let m = AffineMatrix::identity();
        assert_eq!(m.apply(2000, 3000), (2000, 3000));
    }
    #[test] fn scale_doubles_coords() {
        let m = AffineMatrix::scale(2000, 2000);
        assert_eq!(m.apply(1000, 1000), (2000, 2000));
    }
    #[test] fn translate_shifts() {
        let m = AffineMatrix::translate(500, -200);
        assert_eq!(m.apply(0, 0), (500, -200));
    }
    #[test] fn layout_places_all_agents() {
        let mut canvas = AffineCanvas::new(AffineMatrix::identity());
        canvas.layout_agents(&agents(5));
        assert_eq!(canvas.agent_count(), 5);
    }
    #[test] fn fingerprint_deterministic_3x() {
        let make = || {
            let mut c = AffineCanvas::new(AffineMatrix::identity());
            c.layout_agents(&agents(3)); c.fingerprint()
        };
        assert_eq!(make(), make()); assert_eq!(make(), make());
    }
    #[test] fn different_agents_different_fingerprint() {
        let mut c1 = AffineCanvas::new(AffineMatrix::identity()); c1.layout_agents(&agents(3));
        let mut c2 = AffineCanvas::new(AffineMatrix::identity()); c2.layout_agents(&agents(4));
        assert_ne!(c1.fingerprint(), c2.fingerprint());
    }
    #[test] fn compose_identity_is_identity() {
        let i = AffineMatrix::identity();
        let composed = i.compose(&i);
        assert_eq!(composed, AffineMatrix::identity());
    }

    // 8. SCALE_FACTOR constant is 1000
    #[test] fn scale_factor_constant_is_1000() {
        assert_eq!(SCALE_FACTOR, 1000);
    }

    // 9. new canvas has zero agents before layout
    #[test] fn agent_count_zero_before_layout() {
        let canvas = AffineCanvas::new(AffineMatrix::identity());
        assert_eq!(canvas.agent_count(), 0);
    }

    // 10. get_bound returns None for an agent not in the canvas
    #[test] fn get_bound_none_for_unknown_agent() {
        let canvas = AffineCanvas::new(AffineMatrix::identity());
        assert!(canvas.get_bound(999).is_none());
    }
}
