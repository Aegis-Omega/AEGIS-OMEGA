//! Gate 213: Proportional Unit Metric
//! EPISTEMIC TIER: T2 (engineering hypothesis)
//! Rational arithmetic proportional coordinates — avoids float comparison via cross-multiplication.
//! SQUARED_SUM_K8 = 204 = Σi² for i=1..8 (T0: mechanically verified).

pub const SQUARED_SUM_K8: u64 = 204;

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub struct ProportionalPoint {
    pub numerator: u64,
    pub denominator: u64,
}

#[derive(Debug)]
pub struct MetricError(pub &'static str);

impl ProportionalPoint {
    pub fn new(numerator: u64, denominator: u64) -> Result<Self, MetricError> {
        if denominator == 0 {
            return Err(MetricError("Denominator must be > 0"));
        }
        Ok(Self { numerator, denominator })
    }

    pub fn is_proportional_to(&self, other: &ProportionalPoint) -> bool {
        self.numerator * other.denominator == other.numerator * self.denominator
    }

    pub fn scale(&self, factor: u64) -> ProportionalPoint {
        ProportionalPoint {
            numerator: self.numerator * factor,
            denominator: self.denominator,
        }
    }

    pub fn normalized_to(&self, base_denominator: u64) -> Option<ProportionalPoint> {
        if base_denominator % self.denominator == 0 {
            let factor = base_denominator / self.denominator;
            Some(ProportionalPoint {
                numerator: self.numerator * factor,
                denominator: base_denominator,
            })
        } else {
            None
        }
    }
}

pub struct ProportionalGrid {
    pub base_unit: ProportionalPoint,
    pub width_units: u64,
    pub height_units: u64,
}

impl ProportionalGrid {
    pub fn new(base: ProportionalPoint, width: u64, height: u64) -> Self {
        Self { base_unit: base, width_units: width, height_units: height }
    }

    pub fn point_at(&self, x: u64, y: u64) -> Option<ProportionalPoint> {
        if x >= self.width_units || y >= self.height_units {
            return None;
        }
        Some(self.base_unit.scale(x + y + 1))
    }

    pub fn verify_squared_sum(&self) -> bool {
        if self.width_units == 8 {
            (1..=8u64).map(|i| i * i).sum::<u64>() == SQUARED_SUM_K8
        } else {
            false
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_squared_sum_constant() {
        assert_eq!(SQUARED_SUM_K8, 204);
        // Mechanically verify: 1+4+9+16+25+36+49+64 = 204
        let computed: u64 = (1..=8).map(|i: u64| i * i).sum();
        assert_eq!(computed, SQUARED_SUM_K8);
    }

    #[test]
    fn test_invalid_point() {
        assert!(ProportionalPoint::new(1, 0).is_err());
    }

    #[test]
    fn test_proportionality() {
        let p1 = ProportionalPoint::new(1, 2).unwrap();
        let p2 = ProportionalPoint::new(2, 4).unwrap();
        let p3 = ProportionalPoint::new(1, 3).unwrap();
        assert!(p1.is_proportional_to(&p2));
        assert!(!p1.is_proportional_to(&p3));
    }

    #[test]
    fn test_scaling() {
        let p = ProportionalPoint::new(2, 5).unwrap();
        let scaled = p.scale(3);
        assert_eq!(scaled.numerator, 6);
        assert_eq!(scaled.denominator, 5);
    }

    #[test]
    fn test_grid_squared_sum() {
        let base = ProportionalPoint::new(1, 1).unwrap();
        let grid = ProportionalGrid::new(base, 8, 8);
        assert!(grid.verify_squared_sum());
    }

    #[test]
    fn test_grid_bounds() {
        let base = ProportionalPoint::new(1, 1).unwrap();
        let grid = ProportionalGrid::new(base, 8, 8);
        assert!(grid.point_at(9, 0).is_none());
        assert!(grid.point_at(7, 7).is_some());
    }

    #[test]
    fn test_204_divisible_by_12() {
        assert_eq!(SQUARED_SUM_K8 % 12, 0);
        assert_eq!(SQUARED_SUM_K8 / 12, 17);
    }

    #[test]
    fn test_normalized_to() {
        let p = ProportionalPoint::new(1, 3).unwrap();
        let norm = p.normalized_to(9).unwrap();
        assert_eq!(norm.numerator, 3);
        assert_eq!(norm.denominator, 9);
        assert!(p.normalized_to(7).is_none());
    }

    // 9. grid with width != 8 returns false for verify_squared_sum
    #[test]
    fn grid_non_8_width_fails_verify_squared_sum() {
        let base = ProportionalPoint::new(1, 1).unwrap();
        let grid = ProportionalGrid::new(base, 7, 8);
        assert!(!grid.verify_squared_sum());
        let grid9 = ProportionalGrid::new(base, 9, 8);
        assert!(!grid9.verify_squared_sum());
    }

    // 10. scale multiplies numerator, denominator unchanged
    #[test]
    fn scale_preserves_denominator() {
        let p = ProportionalPoint::new(3, 7).unwrap();
        let scaled = p.scale(5);
        assert_eq!(scaled.numerator, 15);
        assert_eq!(scaled.denominator, 7);
    }
}
