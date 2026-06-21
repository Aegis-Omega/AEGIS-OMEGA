// AEGIS-Ω Console — the NOUS core.
// Not a particle cloud — an ordered, monumental geometry. A vast slowly-turning
// architecture (concentric rings, a precision bezel, fine radial spokes) with
// ordered light streams spiralling into a pristine nucleus. Intelligence reads
// as order at scale, not chaos: this is the iris of a great mind, unhurried and
// regal. Canvas 2D, additive bloom, cursor parallax. Smooth on an RX 570.

import { useEffect, useRef } from 'react'

interface Stream { a: number; r: number; w: number; tone: number } // tone 0..1 outer→inner

const STREAMS = 520
const GOLD: [number, number, number] = [200, 169, 110]
const INDIGO: [number, number, number] = [129, 140, 248]
const PLAT: [number, number, number] = [236, 234, 227]

function mix(a: [number, number, number], b: [number, number, number], t: number): string {
  return `${Math.round(a[0] + (b[0] - a[0]) * t)},${Math.round(a[1] + (b[1] - a[1]) * t)},${Math.round(a[2] + (b[2] - a[2]) * t)}`
}

export function CoreCanvas({ contained = false }: { contained?: boolean } = {}) {
  const ref = useRef<HTMLCanvasElement | null>(null)

  useEffect(() => {
    const canvas = ref.current
    if (!canvas) return
    const ctx = canvas.getContext('2d', { alpha: false })
    if (!ctx) return
    const dpr = Math.min(window.devicePixelRatio || 1, 2)
    let w = 0, h = 0, cx = 0, cy = 0, S = 0
    function resize() {
      w = canvas!.clientWidth; h = canvas!.clientHeight
      canvas!.width = Math.floor(w * dpr); canvas!.height = Math.floor(h * dpr)
      ctx!.setTransform(dpr, 0, 0, dpr, 0, 0)
      cx = w / 2; cy = h * (contained ? 0.84 : 0.62); S = Math.min(w, h)
    }
    resize(); window.addEventListener('resize', resize)

    const ptr = { x: cx, y: cy, has: false }
    const tilt = { x: 0, y: 0 }
    function onMove(e: PointerEvent) {
      const r = canvas!.getBoundingClientRect()
      ptr.x = e.clientX - r.left; ptr.y = e.clientY - r.top; ptr.has = true
    }
    window.addEventListener('pointermove', onMove)

    const rand = (a: number, b: number) => a + Math.random() * (b - a)
    const Rmax = () => S * 0.52
    function spawn(s: Stream) {
      s.r = Rmax() * rand(0.7, 1.04)
      s.a = rand(0, Math.PI * 2)
      s.w = rand(0.0016, 0.0042) * (Math.random() < 0.5 ? 1 : -1)
      s.tone = 0
    }
    const streams: Stream[] = Array.from({ length: STREAMS }, () => {
      const s = { a: 0, r: 0, w: 0, tone: 0 }; spawn(s); return s
    })

    let raf = 0, rot = 0
    function ring(r: number, col: string, a: number, lw = 1) {
      ctx!.beginPath(); ctx!.arc(0, 0, r, 0, Math.PI * 2)
      ctx!.strokeStyle = `rgba(${col},${a})`; ctx!.lineWidth = lw; ctx!.stroke()
    }
    function frame() {
      rot += 0.0011
      // parallax tilt toward cursor — composed, not frantic
      const tx = ptr.has ? (ptr.x - cx) * 0.05 : 0
      const ty = ptr.has ? (ptr.y - cy) * 0.05 : 0
      tilt.x += (tx - tilt.x) * 0.04; tilt.y += (ty - tilt.y) * 0.04
      const ox = cx + tilt.x, oy = cy + tilt.y

      // crisp clear — pristine, minimal smear. Contained mode clears transparent
      // so the host page (σ-field, gradients) shows through.
      ctx!.globalCompositeOperation = 'source-over'
      if (contained) { ctx!.clearRect(0, 0, w, h) }
      else { ctx!.fillStyle = 'rgba(6,7,12,0.34)'; ctx!.fillRect(0, 0, w, h) }

      // ── STRUCTURE: the architecture of the mind ────────────────────────────
      ctx!.save(); ctx!.translate(ox, oy)
      ctx!.globalCompositeOperation = 'lighter'
      const R = Rmax()
      // concentric rings (gold/indigo alternating, faint, precise)
      for (let i = 1; i <= 6; i++) {
        const rr = R * (i / 6)
        ring(rr, i % 2 ? GOLD.join(',') : INDIGO.join(','), 0.05 + (i === 6 ? 0.04 : 0))
      }
      // precision bezel — outer ring of fine ticks, slow rotation
      ctx!.save(); ctx!.rotate(rot)
      for (let i = 0; i < 96; i++) {
        const ang = (i / 96) * Math.PI * 2
        const r0 = R * 0.98, r1 = R * (i % 8 === 0 ? 1.06 : 1.02)
        ctx!.beginPath()
        ctx!.moveTo(Math.cos(ang) * r0, Math.sin(ang) * r0)
        ctx!.lineTo(Math.cos(ang) * r1, Math.sin(ang) * r1)
        ctx!.strokeStyle = `rgba(${GOLD.join(',')},${i % 8 === 0 ? 0.18 : 0.07})`
        ctx!.lineWidth = 1; ctx!.stroke()
      }
      ctx!.restore()
      // fine radial spokes, counter-rotating — depth + order
      ctx!.save(); ctx!.rotate(-rot * 0.6)
      for (let i = 0; i < 60; i++) {
        const ang = (i / 60) * Math.PI * 2
        ctx!.beginPath()
        ctx!.moveTo(Math.cos(ang) * R * 0.16, Math.sin(ang) * R * 0.16)
        ctx!.lineTo(Math.cos(ang) * R * 0.92, Math.sin(ang) * R * 0.92)
        ctx!.strokeStyle = `rgba(${INDIGO.join(',')},0.025)`; ctx!.lineWidth = 1; ctx!.stroke()
      }
      ctx!.restore()

      // ── STREAMS: ordered light spiralling inward ───────────────────────────
      for (let i = 0; i < streams.length; i++) {
        const s = streams[i]!
        const inward = 0.10 + (1 - s.r / R) * 0.55
        s.r -= inward
        s.a += s.w * (1 + (R / Math.max(s.r, 24)) * 0.5) // faster as it nears center
        s.tone = 1 - Math.min(1, s.r / R)
        if (s.r < S * 0.05) { spawn(s); continue }
        const x = Math.cos(s.a) * s.r, y = Math.sin(s.a) * s.r
        const col = s.tone < 0.6 ? mix(INDIGO, GOLD, s.tone / 0.6) : mix(GOLD, PLAT, (s.tone - 0.6) / 0.4)
        ctx!.fillStyle = `rgba(${col},${0.35 + s.tone * 0.45})`
        const rad = 0.6 + s.tone * 1.5
        ctx!.beginPath(); ctx!.arc(x, y, rad, 0, Math.PI * 2); ctx!.fill()
      }

      // ── NUCLEUS: pristine point of mind ────────────────────────────────────
      const pulse = 1 + Math.sin(rot * 9) * 0.05
      const cr = S * 0.05 * pulse
      const g = ctx!.createRadialGradient(0, 0, 0, 0, 0, cr * 5)
      g.addColorStop(0, 'rgba(255,252,245,0.9)')
      g.addColorStop(0.14, 'rgba(200,169,110,0.5)')
      g.addColorStop(0.4, 'rgba(129,140,248,0.16)')
      g.addColorStop(1, 'rgba(129,140,248,0)')
      ctx!.fillStyle = g
      ctx!.beginPath(); ctx!.arc(0, 0, cr * 5, 0, Math.PI * 2); ctx!.fill()
      ctx!.fillStyle = 'rgba(255,255,255,0.82)'
      ctx!.beginPath(); ctx!.arc(0, 0, cr * 0.34, 0, Math.PI * 2); ctx!.fill()
      ctx!.restore()

      raf = requestAnimationFrame(frame)
    }
    frame()

    return () => {
      cancelAnimationFrame(raf)
      window.removeEventListener('resize', resize)
      window.removeEventListener('pointermove', onMove)
    }
  }, [])

  return (
    <canvas ref={ref} aria-hidden="true" style={{
      position: contained ? 'absolute' : 'fixed', inset: 0, width: '100%', height: '100%',
      zIndex: 0, display: 'block', background: contained ? 'transparent' : '#06070C',
      pointerEvents: 'none',
    }} />
  )
}
