// ============================================================
// AEGIS Ω — Empirical Bernstein LCB in Q32.32 Fixed-Point
// EPISTEMIC TIER: T0
// Byte-identical port of bernsteinLCBQ32 from src/core/fixedpoint.ts.
// Q32.32: integer where the value = integer / 2^32.
// All BigInt arithmetic in TypeScript maps to i64/i128 in Rust.
// f64 transcendentals (ln, sqrt) are used identically in both.
// ============================================================

const Q_SCALE: i64 = 1i64 << 32; // 2^32 = 4294967296

/// Port of bernsteinLCBQ32 from fixedpoint.ts.
/// All Q32.32 values are i64 (passed as BigInt from JavaScript).
/// n: sample count (i32 in WASM interface, i64 internally).
pub fn bernstein_lcb_q32(sum: i64, sum_sq: i64, n: i64, alpha: i64) -> i64 {
    // n === 0n → -Infinity proxy (-(Q_ONE << 10n) in TS)
    if n == 0 {
        return -(Q_SCALE << 10);
    }

    // mean = sum / n (integer division in Q32.32 space)
    let mean = sum / n;

    // mulQ32(sum, sum) = (sum * sum) >> 32 — use i128 to prevent overflow
    let sum_mul_sum: i64 = ((sum as i128 * sum as i128) >> 32) as i64;

    // sumSqMean = mulQ32(sum, sum) / n
    let sum_sq_mean: i64 = (sum_mul_sum as i128 / n as i128) as i64;

    // rawVariance = sumSq - sumSqMean
    let raw_variance = sum_sq - sum_sq_mean;

    // variance: 0 if n <= 1 or rawVariance <= 0; else rawVariance / (n-1)
    let variance: i64 = if n > 1 && raw_variance > 0 {
        raw_variance / (n - 1)
    } else {
        0
    };

    // fromQ32(alpha) = alpha as f64 / 2^32
    let alpha_f = alpha as f64 / Q_SCALE as f64;

    // logTerm = toQ32(Math.log(2 / fromQ32(alpha)))
    let log_term_f = (2.0_f64 / alpha_f).ln();
    let log_term: i64 = (log_term_f * Q_SCALE as f64).round() as i64;

    // varianceTerm = toQ32(sqrt(2 * fromQ32(variance) * fromQ32(logTerm) / Number(n)))
    let variance_f = variance as f64 / Q_SCALE as f64;
    let log_term_val = log_term as f64 / Q_SCALE as f64;
    let inner = 2.0 * variance_f * log_term_val / n as f64;
    let variance_term_f = if inner >= 0.0 { inner.sqrt() } else { 0.0 };
    let variance_term: i64 = (variance_term_f * Q_SCALE as f64).round() as i64;

    // biasTerm = divQ32(2n * logTerm, 3n * BigInt(Number(n)) << 32n)
    // divQ32(a, b) = (a << 32) / b
    // = (2 * logTerm << 32) / (3 * n << 32)
    // = (2 * logTerm) / (3 * n) in Q32.32
    let bias_num = (2i128 * log_term as i128) << 32;
    let bias_den = (3i128 * n as i128) << 32;
    let bias_term: i64 = (bias_num / bias_den) as i64;

    mean - variance_term - bias_term
}
