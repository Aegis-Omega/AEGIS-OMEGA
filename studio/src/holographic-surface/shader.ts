// EPISTEMIC TIER: T2 (engineering hypothesis) — φ holographic correspondence
// 2D holographic substrate: the boundary equation that projects bulk reality.
// The 2x2 unitary matrix M = [[1,1],[1,0]] (eigenvalues φ and −1/φ) is the
// minimal information surface needed to generate infinite self-similar structure.
//
// Expansion axis (φ):       wave_x1 = cos(x·φ + y·INV_PHI)
//                           wave_y1 = sin(y·φ − x·INV_PHI)
// Contraction axis (−1/φ):  wave_x2 = cos(x·INV_PHI − y·φ)
//                           wave_y2 = sin(y·INV_PHI + x·φ)
//
// Superposition → interference → smoothstep ring at abs(val) ∈ (0.20, 0.30).
// R = macro (φ channel) · G = micro (INV_PHI channel) · B = intensity.
// The phyllotaxis spirals and quasicrystalline grid emerge from geometric necessity.

export const HOLOGRAPHIC_SHADER_WGSL = /* wgsl */`
struct Uniforms {
  time:       f32,
  resolution: vec2<f32>,
  padding:    f32,
}

@group(0) @binding(0) var<uniform> u: Uniforms;

@vertex
fn vs_main(@builtin(vertex_index) vi: u32) -> @builtin(position) vec4<f32> {
  let x = f32((vi & 1u) << 1u) - 1.0;
  let y = f32((vi & 2u))       - 1.0;
  return vec4<f32>(x, y, 0.0, 1.0);
}

const PHI:     f32 = 1.61803398875;
const INV_PHI: f32 = 0.61803398875;

@fragment
fn fs_main(@builtin(position) pos: vec4<f32>) -> @location(0) vec4<f32> {
  // Centre and scale: maps screen to ±10 substrate-space units
  let st = (pos.xy / u.resolution - vec2<f32>(0.5, 0.5)) * 2.0 * 10.0;
  let t  = u.time * 0.18;

  // Expansion axis — driven by φ (manages global scale and epoch progression)
  let wave_x1 = cos(st.x * PHI     + st.y * INV_PHI + t);
  let wave_y1 = sin(st.y * PHI     - st.x * INV_PHI + t * 0.73);

  // Contraction axis — driven by −1/φ (manages boundary conditions and micro-scale)
  let wave_x2 = cos(st.x * INV_PHI - st.y * PHI     - t * 0.51);
  let wave_y2 = sin(st.y * INV_PHI + st.x * PHI     + t * 1.09);

  // Superposition of both eigenvalue definitions in wave space
  let interference = (wave_x1 + wave_y1 + wave_x2 + wave_y2) / 4.0;

  // High-contrast fringe at the interference boundary
  let intensity = intensity_map(interference);

  // φ-channel separation: R = macro (φ dominant), G = micro (INV_PHI dominant)
  let r = abs(wave_x1 + wave_y1) * 0.5;
  let g = abs(wave_x2 + wave_y2) * 0.5;
  let b = intensity;

  return vec4<f32>(r, g, b, 1.0);
}

// Maps interference amplitude to a high-contrast edge ring at ≈ 0.225
fn intensity_map(val: f32) -> f32 {
  let edge = abs(val);
  return smoothstep(0.2, 0.25, edge) * (1.0 - smoothstep(0.25, 0.3, edge));
}
`
