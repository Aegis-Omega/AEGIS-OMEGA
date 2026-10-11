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
float torus(vec3 p,vec2 t) {
  vec2 q=vec2(length(p.xz)-t.x,p.y);
  return length(q)-t.y;
}
vec2 map(vec3 p) {
  float a=-.28 + .11*u_time;
  p.xz=rot(a)*p.xz; p.xy=rot(-.29-a*.19)*p.xy;
  vec3 crystal=p; crystal.xz=rot(.785398)*crystal.xz;
  float shell=u_concept>.5?omega(p):octa(p,1.01);
  float facet=u_concept>.5?100.:abs(octa(crystal*.87,.81)/.87)-.022;
  float ring=torus(p,vec2(1.39,.026));
  vec3 r=p; r.xy=rot(1.14)*r.xy;
  float ring2=torus(r,vec2(1.27,.015));
  r=p; r.yz=rot(.88)*r.yz;
  float ring3=torus(r,vec2(1.36,.013));
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
vec3 atmosphere(vec2 uv) {
  vec3 b=vec3(.013,.020,.035);
  b+=exp(-1.9*length((uv-vec2(.10,.08))*vec2(.82,1.1)))*vec3(.036,.061,.12);
  b+=exp(-5.0*length((uv+vec2(.5,-.28))*vec2(.75,1.2)))*vec3(.025,.021,.063);
  return b;
}
void main() {
  vec2 uv=(2.*gl_FragCoord.xy-u_resolution)/min(u_resolution.x,u_resolution.y);
  vec3 bg=atmosphere(uv), ro=vec3(0.,0.,3.9);
  vec3 rd=normalize(vec3(uv,-2.20));
  float t=0.,mid=0.;vec3 hit=vec3(0.);
  for(int i=0;i<82;i++) {
    vec2 h=map(ro+rd*t);
    if(h.x<.0018) { mid=h.y; hit=ro+rd*t; break; }
    if(t>7.) break;
    t+=max(h.x*.72,.0035);
  }
  vec3 col=bg, hue=accent(u_domain);
  if(mid>0.) {
    vec3 n=norm(hit),v=-rd;
    vec3 l=normalize(vec3(-.48,.72,1.3));
    float lambert=max(dot(n,l),0.);
    float fres=pow(1.-max(dot(n,v),0.),3.0);
    float spec=pow(max(dot(reflect(-l,n),v),0.),58.);
    float density=clamp(.22+.065*u_limits,.22,.47);
    vec3 refr=atmosphere(uv+refract(-v,n,.73).xy*.16);
    vec3 ink=mid<1.5?mix(hue,vec3(.83,.91,1.),.56):mid<2.5?hue:vec3(.82,.72,.56);
    col=mix(refr+ink*(.12+.24*lambert)*density,ink,mid<1.5?.18:.35);
    col+=fres*ink*.55+spec*vec3(1.,.98,.93)*.85;
    col=mix(bg,col,exp(-.018*t*t));
  }
  col+=hue*.014*exp(-2.3*dot(uv,uv));
  col*=.91+.09*(1.-smoothstep(.65,2.1,length(uv)));
  outColor=vec4(pow(max(col,vec3(0.)),vec3(.93)),1.);
}`

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

export function SovereignMatter({ sourceId, limitCount, motionOverride, conceptArt = false }: {
  sourceId: string; limitCount: number; motionOverride?: boolean; conceptArt?: boolean
}) {
  const canvas = useRef<HTMLCanvasElement>(null)
  const [motion, setMotion] = useState(false)
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
          const scale = Math.min(activeMotion ? 1 : 1.25, window.devicePixelRatio || 1)
          const w = Math.max(1, Math.round(rect.width * scale))
          const h = Math.max(1, Math.round(rect.height * scale))
          if (target.width !== w || target.height !== h) {
            target.width = w; target.height = h
          }
          gl.viewport(0, 0, w, h)
          gl.uniform2f(resolution, w, h)
          gl.uniform1f(time, activeMotion && !reduced ? (now - start) * .001 : 0)
          gl.drawArrays(gl.TRIANGLES, 0, 6)
        }
        if (activeMotion && !reduced && visible && !document.hidden) frame = window.requestAnimationFrame(draw)
      }
      setAvailable(true)
      draw(performance.now())
    } catch {
      setAvailable(false)
    }
    return () => {
      pause = true
      window.cancelAnimationFrame(frame)
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
    <div className="sm-south" aria-hidden="true">{conceptArt ? 'PROCEDURAL ART · NOT TELEMETRY' : 'SIGNED DISTANCE · FRESNEL · DOMAIN-BOUND'}</div>
    {motionOverride === undefined && <div className="sm-command">
      <span>{available ? 'GPU MATERIAL' : 'VECTOR FALLBACK'}</span>
      <button type="button" aria-label={motion ? 'Pause material motion' : 'Play material motion'}
        aria-pressed={motion && !reduced} disabled={reduced}
        onClick={() => setMotion(v => !v)}>
        {reduced ? 'Motion reduced' : motion ? 'Pause motion' : 'Explore motion'}
      </button>
    </div>}
  </div>
}
