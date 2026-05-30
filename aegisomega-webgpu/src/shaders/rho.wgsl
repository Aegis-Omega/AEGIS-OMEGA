struct Uniforms {
  dt              : f32,
  frame           : u32,
  lambda_influence: f32,
  sigma_perturb   : f32,
  width           : u32,
  height          : u32,
  mouse_x         : f32,
  mouse_y         : f32,
}

@group(0) @binding(0) var sigma_in: texture_2d<f32>;
@group(0) @binding(1) var rho_out : texture_storage_2d<rgba32float, write>;
@group(0) @binding(2) var<uniform> u: Uniforms;

@compute @workgroup_size(8, 8)
fn main(@builtin(global_invocation_id) gid: vec3<u32>) {
  if (gid.x >= u.width || gid.y >= u.height) { return; }
  let c    = vec2<i32>(gid.xy);
  let dims = vec2<i32>(i32(u.width) - 1, i32(u.height) - 1);
  // Finite-difference gradient of σ (central differences, clamped at boundary)
  let r = textureLoad(sigma_in, clamp(c + vec2<i32>( 1,  0), vec2<i32>(0), dims), 0).r;
  let l = textureLoad(sigma_in, clamp(c + vec2<i32>(-1,  0), vec2<i32>(0), dims), 0).r;
  let t = textureLoad(sigma_in, clamp(c + vec2<i32>( 0,  1), vec2<i32>(0), dims), 0).r;
  let b = textureLoad(sigma_in, clamp(c + vec2<i32>( 0, -1), vec2<i32>(0), dims), 0).r;
  let dx   = (r - l) * 0.5;
  let dy   = (t - b) * 0.5;
  // ρ = smoothstep(0.02, 0.25, |∇σ|)
  let grad = sqrt(dx * dx + dy * dy);
  let rho  = smoothstep(0.02, 0.25, grad);
  textureStore(rho_out, c, vec4<f32>(rho, 0.0, 0.0, 1.0));
}
