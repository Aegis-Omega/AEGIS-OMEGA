struct VertexOut {
  @builtin(position) pos: vec4<f32>,
  @location(0)       uv : vec2<f32>,
}

struct Uniforms {
  dt              : f32,
  frame           : u32,
  lambda_influence: f32,
  sigma_perturb   : f32,
  width           : u32,
  height          : u32,
  mouse_x         : f32,
  mouse_y         : f32,
  canvas_aspect   : f32,
}

@vertex
fn vs_main(@builtin(vertex_index) vi: u32) -> VertexOut {
  var positions = array<vec2<f32>, 3>(
    vec2<f32>(-1.0, -1.0),
    vec2<f32>( 3.0, -1.0),
    vec2<f32>(-1.0,  3.0),
  );
  var uvs = array<vec2<f32>, 3>(
    vec2<f32>(0.0, 1.0),
    vec2<f32>(2.0, 1.0),
    vec2<f32>(0.0, -1.0),
  );
  var out: VertexOut;
  out.pos = vec4<f32>(positions[vi], 0.0, 1.0);
  out.uv  = uvs[vi];
  return out;
}

@group(0) @binding(0) var sigma_tex : texture_2d<f32>;
@group(0) @binding(1) var rho_tex   : texture_2d<f32>;
@group(0) @binding(2) var lambda_tex: texture_2d<f32>;
@group(0) @binding(3) var<uniform> u: Uniforms;

// ── Hash / noise ──────────────────────────────────────────────────────────────

fn hash21(p: vec2<f32>) -> f32 {
  let q = fract(p * vec2<f32>(127.1, 311.7));
  return fract((q.x + q.y * 19.19) * 43758.5453);
}

fn hash11(n: f32) -> f32 {
  return fract(sin(n) * 43758.5453);
}

fn value_noise(p: vec2<f32>) -> f32 {
  let i = floor(p);
  let f = fract(p);
  let u = f * f * (3.0 - 2.0 * f);
  let a = hash21(i);
  let b = hash21(i + vec2<f32>(1.0, 0.0));
  let c = hash21(i + vec2<f32>(0.0, 1.0));
  let d = hash21(i + vec2<f32>(1.0, 1.0));
  return mix(mix(a, b, u.x), mix(c, d, u.x), u.y);
}

// 5-octave domain-warped fBm — unrolled for WGSL compatibility
fn fbm(p: vec2<f32>) -> f32 {
  var v = 0.0;
  var pp = p;
  v  += value_noise(pp * 1.00) * 0.500; pp += vec2<f32>(0.31, 0.71);
  v  += value_noise(pp * 2.10) * 0.250; pp += vec2<f32>(0.53, 0.43);
  v  += value_noise(pp * 4.41) * 0.125; pp += vec2<f32>(0.17, 0.89);
  v  += value_noise(pp * 9.26) * 0.063; pp += vec2<f32>(0.63, 0.21);
  v  += value_noise(pp * 19.4) * 0.031;
  return v;
}

// ── Stars with diffraction spikes ────────────────────────────────────────────

fn stars(uv: vec2<f32>, density: f32, time: f32) -> vec3<f32> {
  let scale   = 300.0 * density;
  let cell    = floor(uv * scale);
  let local   = fract(uv * scale) - 0.5;
  let h       = hash21(cell);
  let offset  = vec2<f32>(hash11(h), hash11(h + 7.3)) - 0.5;
  let sp      = offset * 0.7;
  let dist    = length(local - sp);
  let bright  = hash11(h + 13.1);
  let twinkle = 0.55 + 0.45 * sin(time * (2.0 + h * 3.7) + h * 61.3);
  let core    = smoothstep(0.04, 0.0, dist) * step(0.92, bright) * (bright - 0.92) * 14.0 * twinkle;

  // 4-spike diffraction cross on the brightest stars
  let dp      = local - sp;
  let spk_x   = exp(-abs(dp.y) * 90.0) * exp(-abs(dp.x) * 7.0) * max(0.0, 0.48 - abs(dp.x));
  let spk_y   = exp(-abs(dp.x) * 90.0) * exp(-abs(dp.y) * 7.0) * max(0.0, 0.48 - abs(dp.y));
  let spikes  = (spk_x + spk_y) * step(0.965, bright) * (bright - 0.965) * 7.0 * twinkle;

  let mag    = core + spikes;
  let tint_h = hash11(h + 3.7);
  var color  = vec3<f32>(0.85, 0.90, 1.00);
  if (tint_h < 0.25) { color = vec3<f32>(0.65, 0.80, 1.00); }
  else if (tint_h > 0.75) { color = vec3<f32>(1.00, 0.88, 0.60); }
  return color * mag;
}

// ── Portal helpers ──────────────────────────────────────────────────────────────

fn screen_dist(uv: vec2<f32>, center: vec2<f32>, inv_aspect: f32) -> f32 {
  let p = uv - center;
  return length(vec2<f32>(p.x * inv_aspect, p.y));
}

// Chromatic-aberrated portal rings + electric arcs
fn portal(uv: vec2<f32>, sigma: f32, time: f32, inv_aspect: f32) -> vec3<f32> {
  let center    = vec2<f32>(0.5, 0.45);
  let ring_r    = 0.32 + sigma * 0.04 + sin(time * 0.65) * 0.010;
  let chroma    = 0.007 + abs(sigma) * 0.003;
  let p         = vec2<f32>((uv.x - center.x) * inv_aspect, uv.y - center.y);
  let d         = length(p);
  let angle     = atan2(p.y, p.x);

  // RGB radius split → chromatic fringing
  let dr = d - ring_r * (1.0 - chroma);
  let dg = d - ring_r;
  let db = d - ring_r * (1.0 + chroma);
  let mr = exp(-dr * dr * 80.0);
  let mg = exp(-dg * dg * 80.0);
  let mb = exp(-db * db * 80.0);

  // Inner + outer halos (no chroma split)
  let inner = exp(-(d - ring_r * 0.55) * (d - ring_r * 0.55) * 240.0) * 0.28;
  let outer = exp(-(d - ring_r * 1.30) * (d - ring_r * 1.30) *  35.0) * 0.18;
  let mask  = smoothstep(0.70, 0.0, d);

  // Electricity arcs: high-freq angular noise locked to ring edge
  let arc1  = pow(max(0.0, sin(angle * 18.0 + time * 3.1 + hash11(floor(time * 0.5)) * 6.28)), 8.0);
  let arc2  = pow(max(0.0, sin(angle * 23.0 - time * 2.7 + 1.1)), 10.0);
  let arcs  = (arc1 * 0.7 + arc2 * 0.4) * exp(-(d - ring_r) * (d - ring_r) * 700.0) * 2.5;

  let r_ch = (mr + inner + outer + arcs * 1.3) * mask;
  let g_ch = (mg + inner + outer + arcs * 0.9) * mask;
  let b_ch = (mb + inner + outer + arcs * 0.5) * mask;

  // Portal void teal fill driven by σ
  let interior  = 1.0 - smoothstep(0.0, ring_r * 0.48, d) * 0.45;
  let sigma_n   = (sigma + 1.0) * 0.5;
  let void_fill = pow(max(sigma_n, 0.0), 1.6) * 1.7 * interior;

  return vec3<f32>(
    r_ch * 0.22 + void_fill * 0.07,
    g_ch * 0.72 + void_fill * 0.82,
    b_ch * 0.88 + void_fill * 0.93
  );
}

// Void mask for heat shimmer
fn void_mask(uv: vec2<f32>, inv_aspect: f32) -> f32 {
  return smoothstep(0.22, 0.0, screen_dist(uv, vec2<f32>(0.5, 0.45), inv_aspect));
}

// Anamorphic lens flare: horizontal streak + ghost + hexagonal aperture
fn lens_flare(uv: vec2<f32>, sigma: f32, time: f32, inv_aspect: f32) -> vec3<f32> {
  let center   = vec2<f32>(0.5, 0.45);
  let dx       = (uv.x - center.x) * inv_aspect;
  let dy       = uv.y - center.y;
  let streak   = exp(-dy * dy * 2200.0) * exp(-abs(dx) * 3.8);
  let ghost_d  = screen_dist(uv, vec2<f32>(1.0 - center.x, 1.0 - center.y), inv_aspect);
  let ghost    = exp(-ghost_d * ghost_d * 130.0) * 0.10;
  let angle    = atan2(dy, dx);
  let hex      = pow(max(0.0, cos(angle * 3.0)), 8.0) * 0.18
               * exp(-screen_dist(uv, center, inv_aspect) * screen_dist(uv, center, inv_aspect) * 70.0);
  let amp      = clamp((sigma + 1.0) * 0.5, 0.0, 1.0);
  return vec3<f32>(0.50, 0.78, 1.00) * (streak * 0.28 + ghost + hex) * amp;
}

// God rays: 3 harmonic sets
fn god_rays(uv: vec2<f32>, sigma: f32, time: f32, inv_aspect: f32) -> f32 {
  let center    = vec2<f32>(0.5, 0.45);
  let p         = vec2<f32>((uv.x - center.x) * inv_aspect, uv.y - center.y);
  let angle     = atan2(p.y, p.x);
  let r         = length(p);
  let primary   = pow(max(0.0, sin(angle * 6.0 + time * 0.22)), 14.0);
  let secondary = pow(max(0.0, sin(angle * 6.0 + time * 0.22 + 0.52)), 14.0) * 0.40;
  let tertiary  = pow(max(0.0, sin(angle * 12.0 - time * 0.31 + 0.8)), 20.0) * 0.18;
  let ray_mask  = primary + secondary + tertiary;
  let falloff   = exp(-abs(r - 0.32) * 3.5) * 0.6 + exp(-r * 2.2) * 0.4;
  let amp       = clamp((sigma + 1.0) * 0.6, 0.1, 1.0);
  return ray_mask * falloff * amp * smoothstep(0.04, 0.12, r);
}

// Domain-warped fBm nebula clouds
fn nebula(uv: vec2<f32>, lambda: f32, time: f32) -> vec3<f32> {
  let lam     = clamp((lambda + 0.5) * 1.2, 0.0, 1.0);
  let breathe = sin(time * 0.28) * 0.5 + 0.5;

  let p1 = uv * 2.8 + vec2<f32>(time * 0.015,  time * 0.008);
  let p2 = uv * 1.9 + vec2<f32>(-time * 0.011,  time * 0.013);
  let p3 = uv * 4.2 + vec2<f32>( time * 0.007, -time * 0.019);

  let c1 = fbm(p1);
  let c2 = fbm(p2 + vec2<f32>(c1 * 0.55, 0.0));
  let c3 = fbm(p3 + vec2<f32>(c2 * 0.30, c1 * 0.20));

  let density = pow(max(0.0, c2 * 0.6 + c3 * 0.4 - 0.15), 1.8) * lam;
  let wisps   = pow(max(0.0, c3 - 0.30), 2.2) * lam;

  let violet_col = vec3<f32>(0.45 + breathe * 0.15, 0.05 + breathe * 0.04, 0.85 - breathe * 0.08);
  let wisp_col   = vec3<f32>(0.90, 0.25 + breathe * 0.10, 0.65);
  return violet_col * density * 1.3 + wisp_col * wisps * 0.9;
}

// Aurora with fBm waviness + vertical ray structure
fn aurora(uv: vec2<f32>, lambda: f32, time: f32) -> vec3<f32> {
  let lam_c = clamp((lambda + 0.4) * 1.4, 0.0, 1.0);

  let noise1 = value_noise(vec2<f32>(uv.x * 3.1 + time * 0.12, time * 0.07)) * 0.06
             + value_noise(vec2<f32>(uv.x * 7.4 - time * 0.09, time * 0.05)) * 0.03;
  let wave1  = sin(uv.x * 5.2 + time * 0.35 + lambda * 3.1) * 0.07
             + sin(uv.x * 2.7 - time * 0.19) * 0.04 + noise1;
  let band1  = exp(-pow((uv.y - 0.28 - wave1) * 8.5, 2.0));
  let rays1  = pow(max(0.0, sin(uv.x * 22.0 + time * 0.8 + lambda * 5.0)), 3.0) * band1 * 0.45;

  let wave2  = sin(uv.x * 7.1 - time * 0.28 + lambda * 2.3) * 0.05
             + sin(uv.x * 3.4 + time * 0.14) * 0.03;
  let band2  = exp(-pow((uv.y - 0.14 - wave2) * 11.0, 2.0));
  let rays2  = pow(max(0.0, sin(uv.x * 31.0 - time * 0.6)), 4.0) * band2 * 0.30;

  let wave3  = sin(uv.x * 4.3 + time * 0.21) * 0.04;
  let band3  = exp(-pow((uv.y - 0.42 - wave3) * 14.0, 2.0));

  let green  = vec3<f32>(0.05, 0.92, 0.65) * (band1 + rays1) * 0.80;
  let violet = vec3<f32>(0.45, 0.12, 0.98) * (band2 + rays2) * 0.50;
  let pink   = vec3<f32>(0.95, 0.35, 0.70) * band3 * 0.28;
  return (green + violet + pink) * lam_c;
}

// Two-armed spiral galaxy with bright core
fn galaxy(uv: vec2<f32>, lambda: f32, time: f32, inv_aspect: f32) -> f32 {
  let p     = vec2<f32>((uv.x - 0.5) * inv_aspect, uv.y - 0.5);
  let angle = atan2(p.y, p.x);
  let r     = length(p);
  let arm1  = smoothstep(0.0, 1.0, sin(angle * 2.0 + r * 18.0 - lambda * 6.0 + time * 0.18));
  let arm2  = smoothstep(0.0, 1.0, sin(angle * 2.0 + r * 18.0 + 3.14159 - lambda * 6.0 + time * 0.18));
  let core  = exp(-r * r * 9.0) * 0.55;
  return (arm1 * 0.5 + arm2 * 0.5) * exp(-r * 4.5) * 0.55 + core;
}

// 8-tap bloom
fn bloom(uv: vec2<f32>, dims: vec2<i32>) -> vec3<f32> {
  let iw = f32(dims.x + 1);
  let ih = f32(dims.y + 1);
  let px = vec2<f32>(1.0 / iw, 1.0 / ih);
  var acc = vec3<f32>(0.0);

  var taps = array<vec2<i32>, 8>(
    clamp(vec2<i32>((uv + vec2<f32>( 4.0,  0.0) * px) * vec2<f32>(iw, ih)), vec2<i32>(0), dims),
    clamp(vec2<i32>((uv + vec2<f32>(-4.0,  0.0) * px) * vec2<f32>(iw, ih)), vec2<i32>(0), dims),
    clamp(vec2<i32>((uv + vec2<f32>( 0.0,  4.0) * px) * vec2<f32>(iw, ih)), vec2<i32>(0), dims),
    clamp(vec2<i32>((uv + vec2<f32>( 0.0, -4.0) * px) * vec2<f32>(iw, ih)), vec2<i32>(0), dims),
    clamp(vec2<i32>((uv + vec2<f32>( 3.0,  3.0) * px) * vec2<f32>(iw, ih)), vec2<i32>(0), dims),
    clamp(vec2<i32>((uv + vec2<f32>(-3.0,  3.0) * px) * vec2<f32>(iw, ih)), vec2<i32>(0), dims),
    clamp(vec2<i32>((uv + vec2<f32>( 3.0, -3.0) * px) * vec2<f32>(iw, ih)), vec2<i32>(0), dims),
    clamp(vec2<i32>((uv + vec2<f32>(-3.0, -3.0) * px) * vec2<f32>(iw, ih)), vec2<i32>(0), dims)
  );
  var wts = array<f32, 8>(0.14, 0.14, 0.14, 0.14, 0.07, 0.07, 0.07, 0.07);

  for (var i = 0; i < 8; i++) {
    let rr = textureLoad(rho_tex,    taps[i], 0).r;
    let ss = textureLoad(sigma_tex,  taps[i], 0).r;
    let ll = textureLoad(lambda_tex, taps[i], 0).r;
    let b_r = pow(rr, 1.8) * 2.5;
    let b_s = pow(max(0.0, abs(ss) - 0.4), 1.5) * 0.6;
    let b_l = pow(max(0.0, ll + 0.3), 1.5) * 0.5;
    acc += vec3<f32>(1.00, 0.72, 0.08) * (b_r + b_s) * wts[i];
    acc += vec3<f32>(0.55, 0.18, 0.92) * b_l * wts[i];
  }
  return acc;
}

@fragment
fn fs_main(in: VertexOut) -> @location(0) vec4<f32> {
  let dims       = vec2<i32>(i32(u.width) - 1, i32(u.height) - 1);
  let uv         = vec2<f32>(in.uv.x, 1.0 - in.uv.y);
  let inv_aspect = 1.0 / max(u.canvas_aspect, 0.1);
  let time       = f32(u.frame) * 0.016;

  // Heat shimmer: distort UV inside portal void before field reads
  let vm      = void_mask(uv, inv_aspect);
  let shimmer = vec2<f32>(
    sin(uv.y * 44.0 + time * 2.4) * 0.0028,
    cos(uv.x * 39.0 + time * 2.0) * 0.0028
  ) * vm;
  let d_uv = uv + shimmer;

  let coord = clamp(
    vec2<i32>(d_uv * vec2<f32>(f32(u.width), f32(u.height))),
    vec2<i32>(0, 0), dims
  );
  let sigma  = textureLoad(sigma_tex,  coord, 0).r;
  let rho    = textureLoad(rho_tex,    coord, 0).r;
  let lambda = textureLoad(lambda_tex, coord, 0).r;

  let bg = vec3<f32>(0.004, 0.008, 0.026);

  let star_color = stars(uv, 1.0,    time)        * 1.00
                 + stars(uv * 1.618, 0.65, time * 0.71) * 0.65
                 + stars(uv * 2.414, 0.35, time * 0.53) * 0.35;

  let portal_color = portal(uv, sigma, time, inv_aspect);

  let rays      = god_rays(uv, sigma, time, inv_aspect);
  let ray_color = vec3<f32>(0.28, 0.76, 0.98) * rays * 1.5;

  let flare_color = lens_flare(uv, sigma, time, inv_aspect);

  let aurora_color = aurora(uv, lambda, time);

  let nebula_color = nebula(uv, lambda, time);

  let gal        = galaxy(uv, lambda, time, inv_aspect);
  let galaxy_col = vec3<f32>(0.55, 0.78, 1.00) * gal * 0.80;

  let rho_sharp   = pow(rho, 1.4);
  let gold_bright = vec3<f32>(1.00, 0.72, 0.08) * rho_sharp * 3.2;
  let gold_soft   = vec3<f32>(0.85, 0.52, 0.05) * pow(rho, 0.6) * 0.42;

  let rim        = exp(-sigma * sigma * 6.0);
  let iridescent = vec3<f32>(0.30, 0.98, 0.92) * rim * 0.55;

  let bloom_color = bloom(uv, dims) * 0.85;

  var cursor_glow = vec3<f32>(0.0);
  if (u.mouse_x >= 0.0) {
    let hover     = u.mouse_y < 0.0;
    let actual_y  = select(u.mouse_y, -(u.mouse_y + 1.0), hover);
    let intensity = select(1.0, 0.40, hover);
    let m_uv      = vec2<f32>(u.mouse_x, 1.0 - actual_y);
    let m_dist    = length(uv - m_uv);
    let inner     = exp(-m_dist * m_dist * 800.0) * intensity;
    let outer     = exp(-m_dist * m_dist * 80.0) * 0.35 * intensity;
    cursor_glow   = vec3<f32>(1.00, 0.88, 0.55) * (inner + outer);
  }

  let vig_p    = vec2<f32>((uv.x - 0.5) * inv_aspect, uv.y - 0.5);
  let vignette = 1.0 - dot(vig_p, vig_p) * 1.65;

  let hdr = (bg + star_color + portal_color + ray_color + flare_color
             + aurora_color + nebula_color + galaxy_col
             + gold_bright + gold_soft + iridescent
             + bloom_color + cursor_glow)
            * clamp(vignette, 0.08, 1.0);

  let lum      = dot(hdr, vec3<f32>(0.2126, 0.7152, 0.0722));
  let mapped   = hdr * (1.0 + lum * 0.18) / (1.0 + hdr);
  let gray     = vec3<f32>(dot(mapped, vec3<f32>(0.333)));
  let saturated = mix(gray, mapped, 1.18);
  let gamma    = pow(clamp(saturated, vec3<f32>(0.0), vec3<f32>(1.0)), vec3<f32>(1.0 / 2.2));
  return vec4<f32>(gamma, 1.0);
}
