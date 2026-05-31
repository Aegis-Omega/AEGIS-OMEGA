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

@group(0) @binding(0) var lambda_in : texture_2d<f32>;
@group(0) @binding(1) var lambda_out: texture_storage_2d<rgba32float, write>;
@group(0) @binding(2) var sigma_in  : texture_2d<f32>;
@group(0) @binding(3) var<uniform> u: Uniforms;

@compute @workgroup_size(8, 8)
fn main(@builtin(global_invocation_id) gid: vec3<u32>) {
  if (gid.x >= u.width || gid.y >= u.height) { return; }
  let c    = vec2<i32>(gid.xy);
  let dims = vec2<i32>(i32(u.width) - 1, i32(u.height) - 1);

  let lambda = textureLoad(lambda_in, c, 0).r;
  let sigma  = textureLoad(sigma_in,  c, 0).r;

  // Spatial blur — λ spreads like nebula plasma across neighboring cells
  let r = textureLoad(lambda_in, clamp(c + vec2<i32>( 1,  0), vec2<i32>(0), dims), 0).r;
  let l = textureLoad(lambda_in, clamp(c + vec2<i32>(-1,  0), vec2<i32>(0), dims), 0).r;
  let t = textureLoad(lambda_in, clamp(c + vec2<i32>( 0,  1), vec2<i32>(0), dims), 0).r;
  let b = textureLoad(lambda_in, clamp(c + vec2<i32>( 0, -1), vec2<i32>(0), dims), 0).r;
  let blur = (r + l + t + b) * 0.25;

  // λ' = decay + spatial spread + sigma imprint * scroll influence
  let next = lambda * 0.988 + blur * 0.008 + sigma * 0.012 * u.lambda_influence;
  textureStore(lambda_out, c, vec4<f32>(next, 0.0, 0.0, 1.0));
}
