// AEGIS-Ω Console — the NOUS core.
// A living luminous entity: thousands of light particles streaming inward on a
// curl field, consumed at a breathing nucleus and reborn at the rim — energy
// converging into the mind. Canvas 2D with additive blending for volumetric
// bloom, motion trails, and a cursor gravity-well so it reacts to your presence.
// Tuned to stay smooth on an AMD RX 570.

import { useEffect, useRef } from 'react'

interface P { x: number; y: number; vx: number; vy: number; life: number; hue: number }

const COUNT = 900
// palette: deep indigo → gold → cyan, biased to indigo (professional restraint)
const HUES = [232, 232, 232, 43, 43, 190]

export function CoreCanvas() {
  const ref = useRef<HTMLCanvasElement | null>(null)

  useEffect(() => {
    const canvas = ref.current
    if (!canvas) return
    const ctx = canvas.getContext('2d', { alpha: false })
    if (!ctx) return

    const dpr = Math.min(window.devicePixelRatio || 1, 2)
    let w = 0, h = 0, cx = 0, cy = 0
    function resize() {
      w = canvas!.clientWidth; h = canvas!.clientHeight
      canvas!.width = Math.floor(w * dpr); canvas!.height = Math.floor(h * dpr)
      ctx!.setTransform(dpr, 0, 0, dpr, 0, 0)
      cx = w / 2; cy = h * 0.74  // sun on the horizon — entire upper half stays clean for text
    }
    resize()
    window.addEventListener('resize', resize)

    const pointer = { x: cx, y: cy, has: false }
    const target = { x: cx, y: cy }
    function onMove(e: PointerEvent) {
      const r = canvas!.getBoundingClientRect()
      pointer.x = e.clientX - r.left; pointer.y = e.clientY - r.top; pointer.has = true
    }
    window.addEventListener('pointermove', onMove)

    const rand = (a: number, b: number) => a + Math.random() * (b - a)
    function spawn(p: P) {
      const ang = rand(0, Math.PI * 2)
      const rad = rand(Math.min(w, h) * 0.34, Math.min(w, h) * 0.52)
      p.x = cx + Math.cos(ang) * rad
      p.y = cy + Math.sin(ang) * rad
      const tang = ang + Math.PI / 2
      const v = rand(0.3, 0.9)
      p.vx = Math.cos(tang) * v; p.vy = Math.sin(tang) * v
      p.life = rand(0.4, 1)
      p.hue = HUES[Math.floor(Math.random() * HUES.length)]!
    }
    const ps: P[] = Array.from({ length: COUNT }, () => {
      const p = { x: 0, y: 0, vx: 0, vy: 0, life: 0, hue: 232 }
      spawn(p); return p
    })

    let raf = 0, t = 0
    function frame() {
      t += 0.0045
      // ease core toward cursor (parallax presence)
      const px = pointer.has ? pointer.x : cx
      const py = pointer.has ? pointer.y : cy
      target.x += (px - target.x) * 0.05; target.y += (py - target.y) * 0.05
      const ox = (target.x - cx) * 0.14, oy = (target.y - cy) * 0.14
      const ccx = cx + ox, ccy = cy + oy

      // motion-trail fade (deep near-black with a hint of blue)
      ctx!.globalCompositeOperation = 'source-over'
      ctx!.fillStyle = 'rgba(6, 7, 12, 0.20)'
      ctx!.fillRect(0, 0, w, h)

      ctx!.globalCompositeOperation = 'lighter'
      const breath = 1 + Math.sin(t * 5) * 0.06

      for (let i = 0; i < ps.length; i++) {
        const p = ps[i]!
        let dx = ccx - p.x, dy = ccy - p.y
        const d = Math.hypot(dx, dy) || 1
        dx /= d; dy /= d
        // inward pull + tangential swirl + curl wander
        const pull = 0.045 + 0.06 * (1 - Math.min(1, d / (Math.min(w, h) * 0.5)))
        const swirl = 0.55
        p.vx += dx * pull + -dy * swirl * 0.04
        p.vy += dy * pull + dx * swirl * 0.04
        const n = Math.sin((p.x + t * 120) * 0.006) + Math.cos((p.y - t * 90) * 0.006)
        p.vx += Math.cos(n * 3) * 0.05; p.vy += Math.sin(n * 3) * 0.05
        // cursor gravity well
        if (pointer.has) {
          let gx = pointer.x - p.x, gy = pointer.y - p.y
          const gd = Math.hypot(gx, gy)
          if (gd < 180 && gd > 1) { gx /= gd; gy /= gd; const f = (1 - gd / 180) * 0.4; p.vx += gx * f; p.vy += gy * f }
        }
        p.vx *= 0.94; p.vy *= 0.94
        p.x += p.vx; p.y += p.vy
        const speed = Math.hypot(p.vx, p.vy)
        const sat = 90, lig = 55 + Math.min(30, speed * 18)
        const a = 0.5 * p.life
        ctx!.fillStyle = `hsla(${p.hue}, ${sat}%, ${lig}%, ${a})`
        const r = 0.7 + speed * 0.9
        ctx!.beginPath(); ctx!.arc(p.x, p.y, r, 0, Math.PI * 2); ctx!.fill()
        if (d < 26 * breath) spawn(p)
      }

      // nucleus — layered bloom
      const coreR = 30 * breath
      const grad = ctx!.createRadialGradient(ccx, ccy, 0, ccx, ccy, coreR * 4)
      grad.addColorStop(0, 'rgba(255, 248, 230, 0.82)')
      grad.addColorStop(0.16, 'rgba(200, 169, 110, 0.42)')
      grad.addColorStop(0.42, 'rgba(129, 140, 248, 0.18)')
      grad.addColorStop(1, 'rgba(129, 140, 248, 0)')
      ctx!.fillStyle = grad
      ctx!.beginPath(); ctx!.arc(ccx, ccy, coreR * 4, 0, Math.PI * 2); ctx!.fill()
      ctx!.fillStyle = 'rgba(255,255,255,0.75)'
      ctx!.beginPath(); ctx!.arc(ccx, ccy, coreR * 0.22, 0, Math.PI * 2); ctx!.fill()

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
      position: 'fixed', inset: 0, width: '100%', height: '100%',
      zIndex: 0, display: 'block', background: '#06070C',
    }} />
  )
}
