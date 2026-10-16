import { useEffect, useRef, useState } from 'react'
import './sovereign-matter.css'

/**
 * AEGIS Ω — Sovereign Matter. A bounded, authored WebGL2 SDF material.
 *
 * Visual metaphor, NOT a mathematical plot. The material's hue distinguishes
 * research domains and its inner density responds to recorded boundary count.
 * Text, source links and evidence decisions remain ordinary accessible HTML.
 * No autoplay; never starts a background render loop without user intent.
 */
const VERTEX = `#version 300 es
in vec2 position;
void main() { gl_Position = vec4(position, 0.0, 1.0); }`

const FRAGMENT = `#version 300 es
precision highp float;
out vec4 outColor;
uniform vec2 u_resolution;
uniform float u_time;
uniform float u_domain;
uniform float u_limits;
uniform float u_concept;
uniform float u_view_angle;
uniform float u_step_count;
#define PI 3.14159265359

mat2 rot(float a) { float c=cos(a),s=sin(a); return mat2(c,-s,s,c); }
float octa(vec3 p,float s) {
  p=abs(p); float m=p.x+p.y+p.z-s; vec3 q;
  if(3.0*p.x<m) q=p.xyz;
  else if(3.0*p.y<m) q=p.yzx;
  else if(3.0*p.z<m) q=p.zxy;
  else return m*.57735027;
  float k=clamp(.5*(q.z-q.y+s),0.,s);
  return length(vec3(q.x,q.y-s+k,q.z-k));
}
float segment(vec2 p,vec2 a,vec2 b) {
  vec2 pa=p-a,ba=b-a;
  return length(pa-ba*clamp(dot(pa,ba)/dot(ba,ba),0.,1.));
}
float omega(vec3 p) {
  vec2 q=p.xy;
  float arc=max(abs(length(q-vec2(0.,.16))-.65)-.085,-.46-q.y);
  float left=segment(q,vec2(-.38,-.38),vec2(-.67,-.73))-.08;
  float right=segment(q,vec2(.38,-.38),vec2(.67,-.73))-.08;
  float foot=min(segment(q,vec2(-.87,-.73),vec2(-.31,-.73)),
    segment(q,vec2(.31,-.73),vec2(.87,-.73)))-.065;
  float glyph=min(arc,min(left,min(right,foot)));
  vec2 d=vec2(glyph,abs(p.z)-.115);
  return length(max(d,0.))+min(max(d.x,d.y),0.);
}
// Holon envelope: clipped periodic gyroid sculpture, purely authored art.
float holonField(vec3 p) {
  float g=sin(p.x*5.8)*cos(p.y*5.8)+sin(p.y*5.8)*cos(p.z*5.8)+sin(p.z*5.8)*cos(p.x*5.8);
  return max((abs(g)-.27)*.085,length(p)-1.02);
}
// One luminous strand per recorded boundary (capped at three), never a proof verdict.
float evidenceStrand(vec3 p,float radius,float width,float phase) {
  float angle=atan(p.z,p.x);
  float r=radius+.085*sin(5.0*angle+phase);
  float height=.17*sin(3.0*angle+phase*1.4);
  return length(vec2(length(p.xz)-r,p.y-height))-width;
}
vec2 map(vec3 p) {
  float a=u_view_angle-.28 + .11*u_time;
  p.xz=rot(a)*p.xz; p.xy=rot(-.29-a*.19)*p.xy;
  vec3 crystal=p; crystal.xz=rot(.785398)*crystal.xz;
  float shell=u_concept>.5?omega(p):holonField(p);
  float facet=u_concept>.5?100.:omega(crystal*1.32)/1.32;
  float ring=u_limits>=.5?evidenceStrand(p,1.31,.024,.0):100.;
  vec3 r=p; r.xy=rot(1.14)*r.xy;
  float ring2=u_limits>=1.5?evidenceStrand(r,1.25,.018,1.9):100.;
  r=p; r.yz=rot(.88)*r.yz;
  float ring3=u_limits>=2.5?evidenceStrand(r,1.33,.015,3.8):100.;
  float d=min(min(shell,facet),min(ring,min(ring2,ring3)));
  float id=shell<min(facet,min(ring,min(ring2,ring3)))?1.0:
    facet<min(ring,min(ring2,ring3))?2.0:3.0;
  return vec2(d,id);
}
vec3 norm(vec3 p) {
  vec2 e=vec2(.0019,0.);
  return normalize(vec3(
    map(p+e.xyy).x-map(p-e.xyy).x,
    map(p+e.yxy).x-map(p-e.yxy).x,
    map(p+e.yyx).x-map(p-e.yyx).x));
}
vec3 accent(float d) {
  if(d<.5) return vec3(.55,.79,1.);
  if(d<1.5) return vec3(.69,.68,1.);
  if(d<2.5) return vec3(.47,.87,.77);
  if(d<3.5) return vec3(.91,.73,.49);
  return vec3(.66,.81,.94);
}
// Studio-light response in linear colour; no environment-map download required.
float sat(float v) { return clamp(v,0.,1.); }
vec3 fresnelSchlick(float VoH,vec3 F0) {
  return F0+(vec3(1.)-F0)*pow(1.-sat(VoH),5.);
}
float distributionGGX(float NoH,float roughness) {
  float a=roughness*roughness, a2=a*a;
  float d=NoH*NoH*(a2-1.)+1.;
  return a2/max(3.14159265*d*d,.0001);
}
float geometrySmith(float NoV,float NoL,float roughness) {
  float k=pow(roughness+1.,2.)/8.;
  return NoV/max(NoV*(1.-k)+k,.001)*NoL/max(NoL*(1.-k)+k,.001);
}
vec3 keyLight(vec3 n,vec3 v,vec3 l,vec3 radiance,vec3 F0,float roughness) {
  vec3 h=normalize(v+l);
  float NoL=sat(dot(n,l)),NoV=sat(dot(n,v));
  float NoH=sat(dot(n,h)),VoH=sat(dot(v,h));
  float D=distributionGGX(NoH,roughness);
  float G=geometrySmith(NoV,NoL,roughness);
  vec3 F=fresnelSchlick(VoH,F0);
  vec3 spec=(D*G*F)/max(4.*NoV*NoL,.04);
  return radiance*(spec*NoL);
}
vec3 atmosphere(vec2 uv) {
  vec3 base=vec3(.008,.015,.029);
  base+=vec3(.032,.055,.11)*exp(-1.4*length((uv-vec2(-.25,.18))*vec2(.75,1.2)));
  base+=vec3(.024,.017,.065)*exp(-3.1*length((uv-vec2(.56,-.27))*vec2(.66,1.1)));
  return base;
}
float ambientOcclusion(vec3 p,vec3 n) {
  // Two sparse probes: material separation without a mobile-hostile shadow march.
  float s1=map(p+n*.085).x, s2=map(p+n*.19).x;
  return sat(.64+.24*sat(s1/.085)+.12*sat(s2/.19));
}
vec3 tonemapACES(vec3 x) {
  return clamp((x*(2.51*x+.03))/(x*(2.43*x+.59)+.14),0.,1.);
}
void main() {
  vec2 uv=(2.*gl_FragCoord.xy-u_resolution)/min(u_resolution.x,u_resolution.y);
  vec3 bg=atmosphere(uv);
  vec3 ro=vec3(0.,0.,3.9),rd=normalize(vec3(uv,-2.20));
  float t=0.,mid=0.;vec3 hit=vec3(0.);
  for(int i=0;i<82;i++) {
    if(float(i)>=u_step_count)break;
    vec2 h=map(ro+rd*t);
    if(h.x<.0019){mid=h.y;hit=ro+rd*t;break;}
    if(t>7.)break;
    t+=max(h.x*.72,.004);
  }
  vec3 col=bg;
  if(mid>0.) {
    vec3 n=norm(hit),v=-rd;
    float NoV=sat(dot(n,v));
    vec3 hue=accent(u_domain);
    vec3 ink=mid<1.5?mix(vec3(.15,.35,.73),hue,.35):mid<2.5?
      mix(hue,vec3(.29,.66,.85),.44):mix(vec3(.69,.45,.24),hue,.18);
    float roughness=mid<1.5?.18:mid<2.5?.24:.26;
    float ao=ambientOcclusion(hit,n);
    vec3 F0=mid<1.5?vec3(.055):mix(vec3(.09),ink*.72,.64);
    vec3 key=keyLight(n,v,normalize(vec3(-.52,.77,1.)),vec3(3.7,4.0,4.7),F0,roughness);
    vec3 rim=keyLight(n,v,normalize(vec3(.81,-.26,-.68)),vec3(.60,.88,2.1),F0,.24);
    vec3 warm=keyLight(n,v,normalize(vec3(.55,.72,.30)),vec3(1.55,.97,.48),F0,.38);
    float fres=pow(1.-NoV,5.);
    vec3 refr=atmosphere(uv+n.xy*.10);
    // Thin-film impression is explicitly artistic; not a measured optical coating.
    float phase=sin((1.-NoV)*15.5+dot(n,vec3(2.4,1.7,.4)));
    vec3 film=mix(vec3(.73,.86,1.06),vec3(1.08,.76,.98),.5+.5*phase);
    vec3 opticalBody=mix(vec3(.06,.22,.43),ink,.46+.18*NoV);
    vec3 transmission=refr*(.34+.30*ao)+opticalBody*(.10+.12*sat(dot(n,normalize(vec3(-.52,.77,1.)))))*ao;
    vec3 reflected=(key+rim+warm)*ao;
    vec3 edge=fres*ink*film*(mid<1.5?.85:.53);
    col=transmission+reflected+edge;
    col+=ink*.07*sat(1.-NoV)*(1.+.25*u_limits);
    col=mix(bg,col,exp(-.014*t*t));
  }
  // Vignette respects legibility: artwork does not serve as the reading plane.
  col*=.96+.04*(1.-smoothstep(.80,2.1,length(uv)));
  outColor=vec4(pow(tonemapACES(max(col,vec3(0.))),vec3(1./2.2)),1.);
}}`

const DOMAIN: Record<string, number> = {
  'formal-fork': 0, 'qgi-lab': 1, qbp: 2,
  calibration: 3, source: 4, docs: 4,
}

function compile(gl: WebGL2RenderingContext, type: number, source: string) {
  const shader = gl.createShader(type)
  if (!shader) throw new Error('Shader unavailable')
  gl.shaderSource(shader, source)
  gl.compileShader(shader)
  if (!gl.getShaderParameter(shader, gl.COMPILE_STATUS)) {
    const message = gl.getShaderInfoLog(shader) || 'Shader compile failed'
    gl.deleteShader(shader)
    throw new Error(message)
  }
  return shader
}

export function SovereignMatter({ sourceId, limitCount, motionOverride, conceptArt = false, viewYaw }: {
  sourceId: string; limitCount: number; motionOverride?: boolean; conceptArt?: boolean; viewYaw?: number
}) {
  const canvas = useRef<HTMLCanvasElement>(null)
  const [motion, setMotion] = useState(false)
  const [localYaw,setLocalYaw] = useState(0)
  const yawRef = useRef(viewYaw ?? localYaw)
  const redrawRef = useRef<(() => void)|null>(null)
  useEffect(() => {
    yawRef.current = viewYaw ?? localYaw
    redrawRef.current?.()
  }, [viewYaw, localYaw])
  const activeMotion = motionOverride ?? motion
  const [reduced, setReduced] = useState(false)
  const [available, setAvailable] = useState(false)
  const [visible, setVisible] = useState(true)
  const [contextEpoch, setContextEpoch] = useState(0)

  useEffect(() => {
    const query = window.matchMedia('(prefers-reduced-motion: reduce)')
    const sync = () => setReduced(query.matches)
    sync()
    query.addEventListener('change', sync)
    return () => query.removeEventListener('change', sync)
  }, [])

  useEffect(() => {
    const target = canvas.current
    if (!target || typeof IntersectionObserver === 'undefined') return
    const observer = new IntersectionObserver(entries => setVisible(entries[0]?.isIntersecting ?? false))
    observer.observe(target)
    return () => observer.disconnect()
  }, [])

  useEffect(() => {
    const target = canvas.current
    if (!target) return
    let gl: WebGL2RenderingContext | null = null
    let program: WebGLProgram | null = null
    let buffer: WebGLBuffer | null = null
    let vs: WebGLShader | null = null
    let fs: WebGLShader | null = null
    let frame = 0
    let last = -1000
    let pause = false
    let lost = false
    let onReturn: (() => void) | null = null
    let resizeObserver: ResizeObserver | null = null
    const onLoss = (event: Event) => { event.preventDefault(); lost = true; setAvailable(false) }
    const onRestore = () => { lost = false; setAvailable(false); setContextEpoch(value => value + 1) }
    target.addEventListener('webglcontextlost', onLoss)
    target.addEventListener('webglcontextrestored', onRestore)
    try {
      gl = target.getContext('webgl2', {
        alpha: false, antialias: false, powerPreference: 'low-power',
      })
      if (!gl) throw new Error('WebGL2 unavailable')
      vs = compile(gl, gl.VERTEX_SHADER, VERTEX)
      fs = compile(gl, gl.FRAGMENT_SHADER, FRAGMENT)
      program = gl.createProgram()
      if (!program) throw new Error('Program unavailable')
      gl.attachShader(program, vs)
      gl.attachShader(program, fs)
      gl.linkProgram(program)
      if (!gl.getProgramParameter(program, gl.LINK_STATUS)) throw new Error(gl.getProgramInfoLog(program) || 'Link failed')
      gl.useProgram(program)
      buffer = gl.createBuffer()
      gl.bindBuffer(gl.ARRAY_BUFFER, buffer)
      gl.bufferData(gl.ARRAY_BUFFER, new Float32Array([-1,-1,1,-1,-1,1,-1,1,1,-1,1,1]), gl.STATIC_DRAW)
      const pos = gl.getAttribLocation(program, 'position')
      gl.enableVertexAttribArray(pos)
      gl.vertexAttribPointer(pos, 2, gl.FLOAT, false, 0, 0)
      const resolution = gl.getUniformLocation(program, 'u_resolution')
      const time = gl.getUniformLocation(program, 'u_time')
      const viewAngle = gl.getUniformLocation(program, 'u_view_angle')
      const stepCount = gl.getUniformLocation(program, 'u_step_count')
      gl.uniform1f(gl.getUniformLocation(program, 'u_domain'), DOMAIN[sourceId] ?? 4)
      gl.uniform1f(gl.getUniformLocation(program, 'u_limits'), Math.min(6, Math.max(0, limitCount)))
      gl.uniform1f(gl.getUniformLocation(program, 'u_concept'), conceptArt ? 1 : 0)
      const start = performance.now()
      onReturn = () => { if (!document.hidden && activeMotion && !reduced && visible) frame = window.requestAnimationFrame(draw) }
      document.addEventListener('visibilitychange', onReturn)
      const draw = (now: number) => {
        if (!gl || lost || pause) return
        if (now - last >= 1000 / 24) {
          last = now
          const rect = target.getBoundingClientRect()
          // Budget bounded for phone GPUs, Retina, and reduced-motion devices.
          const small = rect.width < 720 || window.matchMedia('(pointer:coarse)').matches
          const scale = Math.min(small ? .85 : (activeMotion ? 1 : 1.2), window.devicePixelRatio || 1)
          const w = Math.max(1, Math.min(1200, Math.round(rect.width * scale)))
          const h = Math.max(1, Math.min(900, Math.round(rect.height * scale)))
          if (target.width !== w || target.height !== h) {
            target.width = w; target.height = h
          }
          gl.viewport(0, 0, w, h)
          gl.uniform2f(resolution, w, h)
          gl.uniform1f(time, activeMotion && !reduced ? (now - start) * .001 : 0)
          gl.uniform1f(viewAngle, yawRef.current)
          gl.uniform1f(stepCount, w < 600 ? 55 : 82)
          gl.drawArrays(gl.TRIANGLES, 0, 6)
        }
        if (activeMotion && !reduced && visible && !document.hidden) frame = window.requestAnimationFrame(draw)
      }
      setAvailable(true)
      redrawRef.current = () => {
        window.cancelAnimationFrame(frame)
        last = -1000
        frame = window.requestAnimationFrame(draw)
      }
      draw(performance.now())
      if (typeof ResizeObserver !== 'undefined') {
        resizeObserver = new ResizeObserver(() => {
          if (!activeMotion || reduced) frame = window.requestAnimationFrame(draw)
        })
        resizeObserver.observe(target)
      }
    } catch {
      setAvailable(false)
    }
    return () => {
      pause = true
      redrawRef.current = null
      window.cancelAnimationFrame(frame)
      resizeObserver?.disconnect()
      target.removeEventListener('webglcontextlost', onLoss)
      target.removeEventListener('webglcontextrestored', onRestore)
      if (onReturn) document.removeEventListener('visibilitychange', onReturn)
      if (gl && !lost) {
        if (buffer) gl.deleteBuffer(buffer)
        if (program) gl.deleteProgram(program)
        if (vs) gl.deleteShader(vs)
        if (fs) gl.deleteShader(fs)
      }
    }
  }, [sourceId, limitCount, activeMotion, reduced, visible, contextEpoch, conceptArt])

  return <div className={'sm-stage' + (conceptArt ? ' sm-concept' : '')}>
    <div className="sm-fallback" aria-hidden="true">
      <div className="sm-fallback-body" />
      <div className="sm-ring sm-ring-one" />
      <div className="sm-ring sm-ring-two" />
      <div className="sm-ring sm-ring-three" />
    </div>
    <canvas ref={canvas} className={'sm-canvas' + (available ? ' sm-canvas-ready' : '')}
      aria-hidden="true" />
    <div className="sm-north" aria-hidden="true">{conceptArt ? 'AEGIS Ω / MATERIAL CONCEPT' : 'AEGIS Ω / MATTER STUDY 001'}</div>
    <div className="sm-south" aria-hidden="true">{conceptArt ? 'PROCEDURAL ART · NOT TELEMETRY' : 'HOLON · BOUNDARY FILAMENTS · PROCEDURAL ART'}</div>
    {motionOverride === undefined && <div className="sm-command">
      <span>{available ? 'GPU MATERIAL' : 'VECTOR FALLBACK'}</span>
      <button type="button" aria-label="Rotate sculpture left" disabled={!available} onClick={() => setLocalYaw(value => Math.max(-3.14, value-.35))}>←</button>
      <button type="button" aria-label="Rotate sculpture right" disabled={!available} onClick={() => setLocalYaw(value => Math.min(3.14, value+.35))}>→</button>
      <button type="button" aria-label={motion ? 'Pause material motion' : 'Play material motion'}
        aria-pressed={motion && !reduced && available} disabled={reduced || !available}
        onClick={() => setMotion(v => !v)}>
        {reduced ? 'Motion reduced' : !available ? '3D unavailable' : motion ? 'Pause motion' : 'Explore motion'}
      </button>
    </div>}
  </div>
}
