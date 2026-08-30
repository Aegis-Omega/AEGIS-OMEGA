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

@group(0) @binding(0) var sigma_in  : texture_2d<f32>;
@group(0) @binding(1) var sigma_out : texture_storage_2d<rgba32float, write>;
@group(0) @binding(2) var lambda_in : texture_2d<f32>;
@group(0) @binding(3) var<uniform> u: Uniforms;

@compute @workgroup_size(8, 8)
fn main(@builtin(global_invocation_id) gid: vec3<u32>) {
  if (gid.x >= u.width || gid.y >= u.height) { return; }
  let c    = vec2<i32>(gid.xy);
  let dims = vec2<i32>(i32(u.width) - 1, i32(u.height) - 1);

  let sigma  = textureLoad(sigma_in, c, 0).r;
  let lambda = textureLoad(lambda_in, c, 0).r;

  // 9-point isotropic Laplacian
  let r  = textureLoad(sigma_in, clamp(c + vec2<i32>( 1,  0), vec2<i32>(0), dims), 0).r;
  let l  = textureLoad(sigma_in, clamp(c + vec2<i32>(-1,  0), vec2<i32>(0), dims), 0).r;
  let t  = textureLoad(sigma_in, clamp(c + vec2<i32>( 0,  1), vec2<i32>(0), dims), 0).r;
  let b  = textureLoad(sigma_in, clamp(c + vec2<i32>( 0, -1), vec2<i32>(0), dims), 0).r;
  let tr = textureLoad(sigma_in, clamp(c + vec2<i32>( 1,  1), vec2<i32>(0), dims), 0).r;
  let tl = textureLoad(sigma_in, clamp(c + vec2<i32>(-1,  1), vec2<i32>(0), dims), 0).r;
  let br = textureLoad(sigma_in, clamp(c + vec2<i32>( 1, -1), vec2<i32>(0), dims), 0).r;
  let bl = textureLoad(sigma_in, clamp(c + vec2<i32>(-1, -1), vec2<i32>(0), dims), 0).r;
  let lap = 0.5*(r+l+t+b) + 0.25*(tr+tl+br+bl) - 3.0*sigma;

  var mouse_kick = 0.0;
  if (u.mouse_x >= 0.0 && u.mouse_y >= 0.0) {
    let mx = u.mouse_x * f32(u.width);
    let my = u.mouse_y * f32(u.height);
    let dx = f32(c.x) - mx;
    let dy = f32(c.y) - my;
    let d2 = (dx * dx + dy * dy) / (40.0 * 40.0);
    mouse_kick = exp(-d2) * 2.5;
  }

  let reaction = sin(sigma + lambda) + cos(lambda) * 0.8;
  let next = sigma + u.dt * (reaction + 0.18 * lap) + u.sigma_perturb + mouse_kick * u.dt;
  let clamped = next / (1.0 + abs(next) * 0.04);
  textureStore(sigma_out, c, vec4<f32>(clamped, 0.0, 0.0, 1.0));
}
