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

  // Sobel 3×3 gradient — more isotropic than central differences;
  // the weighted centre row/column produces smoother, less aliased edges.
  let tl = textureLoad(sigma_in, clamp(c + vec2<i32>(-1,  1), vec2<i32>(0), dims), 0).r;
  let tc = textureLoad(sigma_in, clamp(c + vec2<i32>( 0,  1), vec2<i32>(0), dims), 0).r;
  let tr = textureLoad(sigma_in, clamp(c + vec2<i32>( 1,  1), vec2<i32>(0), dims), 0).r;
  let ml = textureLoad(sigma_in, clamp(c + vec2<i32>(-1,  0), vec2<i32>(0), dims), 0).r;
  let mr = textureLoad(sigma_in, clamp(c + vec2<i32>( 1,  0), vec2<i32>(0), dims), 0).r;
  let bl = textureLoad(sigma_in, clamp(c + vec2<i32>(-1, -1), vec2<i32>(0), dims), 0).r;
  let bc = textureLoad(sigma_in, clamp(c + vec2<i32>( 0, -1), vec2<i32>(0), dims), 0).r;
  let br = textureLoad(sigma_in, clamp(c + vec2<i32>( 1, -1), vec2<i32>(0), dims), 0).r;

  // Sobel kernels (each direction normalised by sum of absolute weights = 8)
  let gx = ((tr + 2.0*mr + br) - (tl + 2.0*ml + bl)) * 0.125;
  let gy = ((tl + 2.0*tc + tr) - (bl + 2.0*bc + br)) * 0.125;
  let grad = sqrt(gx*gx + gy*gy);
  let rho  = smoothstep(0.02, 0.25, grad);
  textureStore(rho_out, c, vec4<f32>(rho, 0.0, 0.0, 1.0));
}
